import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
from dotenv import load_dotenv, dotenv_values 
load_dotenv() 
os.getenv("discordbottoken")
from cryptography.fernet import Fernet
import json
import io
import asyncio

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

NOTES_DIR = "notes"
KEYS_DIR = "user_keys"
PRIVACY_FILE = "privacy_settings.json"

os.makedirs(NOTES_DIR, exist_ok=True)
os.makedirs(KEYS_DIR, exist_ok=True)

if not os.path.exists(PRIVACY_FILE):
    with open(PRIVACY_FILE, "w") as f:
        json.dump({}, f)

with open(PRIVACY_FILE, "r") as f:
    privacy_settings = json.load(f)

def get_user_key(user_id: str):
    key_path = os.path.join(KEYS_DIR, f"{user_id}.key")
    if not os.path.exists(key_path):
        key = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(key)
    else:
        with open(key_path, "rb") as f:
            key = f.read()
    return Fernet(key)

def user_notes(user_id: str):
    return [f[:-4] for f in os.listdir(NOTES_DIR) if f.endswith(".txt") and f.startswith(f"{user_id}_")]

async def update_status():
    while True:
        total_notes = len([n for n in os.listdir(NOTES_DIR) if n.endswith(".txt")])
        total_servers = len(bot.guilds)

        notes_word = "note" if total_notes == 1 else "notes"
        servers_word = "server" if total_servers == 1 else "servers"

        await bot.change_presence(activity=discord.Game(f"hosting {total_notes} {notes_word}"))
        await asyncio.sleep(5)
        await bot.change_presence(activity=discord.Game(f"in {total_servers} {servers_word}"))
        await asyncio.sleep(5)

@bot.tree.command(name="create_note", description="create a new note")
async def create_note(interaction: discord.Interaction, note_name: str, content: str):
    cipher_suite = get_user_key(str(interaction.user.id))
    note_path = os.path.join(NOTES_DIR, f"{interaction.user.id}_{note_name}.txt")

    encrypted_content = cipher_suite.encrypt(content.encode())
    with open(note_path, "wb") as f:
        f.write(encrypted_content)

    await interaction.response.send_message(
        embed=discord.Embed(description=f"note '{note_name}' created successfully!", color=discord.Color.yellow()),
        ephemeral=True
    )

@bot.tree.command(name="rename_note", description="rename one of your notes")
async def rename_note(interaction: discord.Interaction, old_name: str, new_name: str):
    old_path = os.path.join(NOTES_DIR, f"{interaction.user.id}_{old_name}.txt")
    new_path = os.path.join(NOTES_DIR, f"{interaction.user.id}_{new_name}.txt")

    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        await interaction.response.send_message(
            embed=discord.Embed(description=f"note '{old_name}' renamed to '{new_name}'", color=discord.Color.yellow()),
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            embed=discord.Embed(description=f"note '{old_name}' not found.", color=discord.Color.red()),
            ephemeral=True
        )

@bot.tree.command(name="delete_note", description="delete one of your notes")
async def delete_note(interaction: discord.Interaction, note_name: str):
    note_path = os.path.join(NOTES_DIR, f"{interaction.user.id}_{note_name}.txt")

    if os.path.exists(note_path):
        os.remove(note_path)
        await interaction.response.send_message(
            embed=discord.Embed(description=f"note '{note_name}' deleted.", color=discord.Color.yellow()),
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            embed=discord.Embed(description=f"note '{note_name}' not found.", color=discord.Color.red()),
            ephemeral=True
        )

@bot.tree.command(name="list_notes", description="list your notes")
async def list_notes(interaction: discord.Interaction):
    notes = user_notes(str(interaction.user.id))
    if notes:
        embed = discord.Embed(
            description="your notes:\n" + "\n".join(notes),
            color=discord.Color.yellow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(
            embed=discord.Embed(description="you have no notes.", color=discord.Color.yellow()),
            ephemeral=True
        )

@bot.tree.command(name="view_note", description="view one of your notes")
async def view_note(interaction: discord.Interaction, note_name: str):
    note_path = os.path.join(NOTES_DIR, f"{interaction.user.id}_{note_name}.txt")
    if os.path.exists(note_path):
        cipher_suite = get_user_key(str(interaction.user.id))
        encrypted_content = open(note_path, "rb").read()
        decrypted_content = cipher_suite.decrypt(encrypted_content).decode()

        embed = discord.Embed(
            title=f"note: {note_name}",
            description=decrypted_content,
            color=discord.Color.yellow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(
            embed=discord.Embed(description=f"note '{note_name}' not found.", color=discord.Color.red()),
            ephemeral=True
        )

@bot.tree.command(name="download_note", description="download one of your notes")
async def download_note(interaction: discord.Interaction, note_name: str):
    note_path = os.path.join(NOTES_DIR, f"{interaction.user.id}_{note_name}.txt")
    if os.path.exists(note_path):
        cipher_suite = get_user_key(str(interaction.user.id))
        encrypted_content = open(note_path, "rb").read()
        decrypted_content = cipher_suite.decrypt(encrypted_content).decode()

        file = io.BytesIO(decrypted_content.encode())
        file.name = f"{note_name}.txt"
        file.seek(0)

        await interaction.response.send_message(
            file=discord.File(file, f"{note_name}.txt"),
            embed=discord.Embed(description=f"here is your note '{note_name}'", color=discord.Color.yellow()),
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            embed=discord.Embed(description=f"note '{note_name}' not found.", color=discord.Color.red()),
            ephemeral=True
        )

@bot.tree.command(name="about", description="learn about pasty")
async def about(interaction: discord.Interaction):
    embed = discord.Embed(
        title="about pasty",
        description=(
            "pasty is a secure note bot that lets you create, edit, view, and download private notes.\n"
            "all notes are encrypted per-user with fernet, so only you can access your own data.\n\n"
        ),
        color=discord.Color.yellow()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="help", description="list all available commands")
async def help(interaction: discord.Interaction):
    cmds = [
        "`/create_note` - create a note",
        "`/rename_note` - rename a note",
        "`/delete_note` - delete a note",
        "`/list_notes` - list your notes",
        "`/view_note` - view a note",
        "`/download_note` - download a note",
        "`/about` - learn about pasty",
        "`/help` - show this help",
        "`/support` - get the support server"
    ]
    embed = discord.Embed(
        title="pasty commands",
        description="\n".join(cmds),
        color=discord.Color.yellow()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="support", description="get the support server")
async def support(interaction: discord.Interaction):
    await interaction.response.send_message(
        "https://discord.gg/D3ZMCHCMXY",
        ephemeral=True
    )

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"synced {len(synced)} commands globally")
    except Exception as e:
        print(f"error syncing commands: {e}")
    print(f"logged in as {bot.user}!")
    bot.loop.create_task(update_status())
token = os.getenv("discordbottoken")
bot.run(token)