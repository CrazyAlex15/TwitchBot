import discord
from discord import app_commands
from discord.ext import commands
import os
import aiosqlite
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Settings & Database Files
DB_NAME = "voice_channels.db"
SETTINGS_FILE = "vc_settings.json"

# Intents
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True 
intents.message_content = True

class HiddenVCBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.synced = False

    async def setup_hook(self):
        # Database Setup for Active Channels
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    channel_id INTEGER PRIMARY KEY,
                    owner_id INTEGER,
                    password TEXT,
                    guild_id INTEGER
                )
            """)
            await db.commit()
        
        # Sync Slash Commands
        await self.tree.sync()
        print("Database connected & Commands synced.")

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('Hidden VC Bot is ready!')

bot = HiddenVCBot()

# --- HELPER FUNCTIONS ---

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {}
    with open(SETTINGS_FILE, "r") as f:
        return json.load(f)

def save_settings(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_allowed_channel(guild_id):
    data = load_settings()
    return data.get(str(guild_id))

# --- SLASH COMMANDS ---

@bot.tree.command(name="setup_vc", description="Set the text channel allowed for VC commands")
@app_commands.describe(channel="The text channel for create/join commands")
@app_commands.checks.has_permissions(administrator=True)
async def setup_vc(interaction: discord.Interaction, channel: discord.TextChannel):
    data = load_settings()
    data[str(interaction.guild_id)] = channel.id
    save_settings(data)
    await interaction.response.send_message(f"✅ Setup complete! Hidden VC commands are now allowed in {channel.mention}")

@bot.tree.command(name="createvc", description="Create a HIDDEN voice channel with a password")
@app_commands.describe(name="Channel Name", limit="User Limit (0 for unlimited)", password="The Password")
async def createvc(interaction: discord.Interaction, name: str, password: str, limit: int = 0):
    allowed_channel_id = get_allowed_channel(interaction.guild_id)
    
    if not allowed_channel_id or interaction.channel_id != allowed_channel_id:
        await interaction.response.send_message(f"❌ This command can only be used in the configured VC channel.", ephemeral=True)
        return

    guild = interaction.guild
    member = interaction.user
    
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=False), # Nobody sees it
        member: discord.PermissionOverwrite(connect=True, view_channel=True, manage_channels=True), # Creator sees it
        guild.me: discord.PermissionOverwrite(connect=True, view_channel=True, manage_channels=True)
    }

    try:
        channel = await guild.create_voice_channel(
            name=name,
            user_limit=limit,
            overwrites=overwrites
        )

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT INTO channels (channel_id, owner_id, password, guild_id) VALUES (?, ?, ?, ?)",
                (channel.id, member.id, password, guild.id)
            )
            await db.commit()

        # AUTO-MOVE
        if member.voice:
            await member.move_to(channel)
            await interaction.response.send_message(f"👻 Invisible channel **{name}** created! I moved you in. Password: `{password}`", ephemeral=True)
        else:
            await interaction.response.send_message(f"👻 Invisible channel **{name}** created! Join a voice channel so I can pull you in. Password: `{password}`", ephemeral=True)

    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)


@bot.tree.command(name="joinvc", description="Join a hidden channel using its name and password")
@app_commands.describe(channel_name="Exact name of the channel", password="The Password")
async def joinvc(interaction: discord.Interaction, channel_name: str, password: str):
    allowed_channel_id = get_allowed_channel(interaction.guild_id)
    
    if not allowed_channel_id or interaction.channel_id != allowed_channel_id:
        await interaction.response.send_message(f"❌ This command can only be used in the configured VC channel.", ephemeral=True)
        return

    guild = interaction.guild
    channel = discord.utils.get(guild.voice_channels, name=channel_name)

    if not channel:
        await interaction.response.send_message(f"❌ Channel **{channel_name}** not found. Check capitalization!", ephemeral=True)
        return

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT password FROM channels WHERE channel_id = ?", (channel.id,))
        result = await cursor.fetchone()
    
    if not result:
        await interaction.response.send_message("❌ This channel is not managed by the bot.", ephemeral=True)
        return

    stored_password = result[0]

    if password == stored_password:
        # Give Permissions
        await channel.set_permissions(interaction.user, connect=True, view_channel=True)
        
        # AUTO-MOVE LOGIC
        if interaction.user.voice:
            try:
                await interaction.user.move_to(channel)
                await interaction.response.send_message(f"🔓 Password accepted! Moving you to **{channel.name}**...", ephemeral=True)
            except discord.errors.HTTPException:
                await interaction.response.send_message(f"🔓 Password accepted! I couldn't move you (Channel full?). It is now visible to you: {channel.mention}", ephemeral=True)
        else:
            await interaction.response.send_message(f"🔓 Password accepted! The channel is now visible: {channel.mention}. (Join a VC first next time for auto-move!)", ephemeral=True)
            
    else:
        await interaction.response.send_message("⛔ Wrong password.", ephemeral=True)

# --- EVENTS ---

@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel == after.channel:
        return

    if before.channel is not None:
        channel = before.channel
        
        # If channel is empty
        if len(channel.members) == 0:
            async with aiosqlite.connect(DB_NAME) as db:
                cursor = await db.execute("SELECT channel_id FROM channels WHERE channel_id = ?", (channel.id,))
                result = await cursor.fetchone()
                
                if result:
                    try:
                        await channel.delete()
                        await db.execute("DELETE FROM channels WHERE channel_id = ?", (channel.id,))
                        await db.commit()
                        print(f"Deleted invisible channel: {channel.name}")
                    except Exception as e:
                        print(f"Error deleting channel: {e}")

if TOKEN:
    bot.run(TOKEN)
else:
    print("Error: DISCORD_TOKEN not found in .env")