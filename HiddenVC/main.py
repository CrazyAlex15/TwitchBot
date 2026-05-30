"""Hidden Voice Channels Bot.

Lets members create password-protected voice channels that are invisible to
everyone except people who join with the correct password. Empty hidden
channels are auto-deleted. Channel ownership/passwords live in a small SQLite
database; the per-guild "command channel" lives in a JSON settings file.
"""

import json
import logging
import os
import sys

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("HiddenVCBot")

# Config
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

DB_NAME = "voice_channels.db"
SETTINGS_FILE = "vc_settings.json"

# Intents - only what the bot actually needs.
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True


class HiddenVCBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS channels (
                    channel_id INTEGER PRIMARY KEY,
                    owner_id INTEGER,
                    password TEXT,
                    guild_id INTEGER
                )
                """
            )
            await db.commit()
        await self.tree.sync()
        log.info("Database ready & commands synced.")

    async def on_ready(self) -> None:
        log.info("Logged in as %s (ID: %s) - Hidden VC Bot is ready!", self.user, self.user.id)


bot = HiddenVCBot()


# Settings helpers
def load_settings() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.error("Failed to read %s: %s", SETTINGS_FILE, exc)
        return {}


def save_settings(data: dict) -> None:
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def get_allowed_channel(guild_id: int) -> int | None:
    return load_settings().get(str(guild_id))


# Slash commands
@bot.tree.command(name="setup_vc", description="Set the text channel allowed for VC commands")
@app_commands.describe(channel="The text channel for create/join commands")
@app_commands.checks.has_permissions(administrator=True)
async def setup_vc(interaction: discord.Interaction, channel: discord.TextChannel) -> None:
    data = load_settings()
    data[str(interaction.guild_id)] = channel.id
    save_settings(data)
    await interaction.response.send_message(
        f"✅ Setup complete! Hidden VC commands are now allowed in {channel.mention}"
    )


@bot.tree.command(name="createvc", description="Create a HIDDEN voice channel with a password")
@app_commands.describe(
    name="Channel Name", limit="User Limit (0 for unlimited)", password="The Password"
)
async def createvc(
    interaction: discord.Interaction, name: str, password: str, limit: int = 0
) -> None:
    allowed_channel_id = get_allowed_channel(interaction.guild_id)
    if not allowed_channel_id or interaction.channel_id != allowed_channel_id:
        await interaction.response.send_message(
            "❌ This command can only be used in the configured VC channel.", ephemeral=True
        )
        return

    guild = interaction.guild
    member = interaction.user

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=False),
        member: discord.PermissionOverwrite(connect=True, view_channel=True, manage_channels=True),
        guild.me: discord.PermissionOverwrite(connect=True, view_channel=True, manage_channels=True),
    }

    try:
        channel = await guild.create_voice_channel(
            name=name, user_limit=limit, overwrites=overwrites
        )

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT INTO channels (channel_id, owner_id, password, guild_id) VALUES (?, ?, ?, ?)",
                (channel.id, member.id, password, guild.id),
            )
            await db.commit()

        if member.voice:
            await member.move_to(channel)
            await interaction.response.send_message(
                f"👻 Invisible channel **{name}** created! I moved you in. Password: `{password}`",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"👻 Invisible channel **{name}** created! Join a voice channel so I can pull you in. "
                f"Password: `{password}`",
                ephemeral=True,
            )
    except Exception as exc:
        log.error("createvc failed: %s", exc)
        await interaction.response.send_message(f"❌ Error: {exc}", ephemeral=True)


@bot.tree.command(name="joinvc", description="Join a hidden channel using its name and password")
@app_commands.describe(channel_name="Exact name of the channel", password="The Password")
async def joinvc(
    interaction: discord.Interaction, channel_name: str, password: str
) -> None:
    allowed_channel_id = get_allowed_channel(interaction.guild_id)
    if not allowed_channel_id or interaction.channel_id != allowed_channel_id:
        await interaction.response.send_message(
            "❌ This command can only be used in the configured VC channel.", ephemeral=True
        )
        return

    guild = interaction.guild
    channel = discord.utils.get(guild.voice_channels, name=channel_name)
    if not channel:
        await interaction.response.send_message(
            f"❌ Channel **{channel_name}** not found. Check capitalization!", ephemeral=True
        )
        return

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT password FROM channels WHERE channel_id = ?", (channel.id,)
        )
        result = await cursor.fetchone()

    if not result:
        await interaction.response.send_message(
            "❌ This channel is not managed by the bot.", ephemeral=True
        )
        return

    if password != result[0]:
        await interaction.response.send_message("⛔ Wrong password.", ephemeral=True)
        return

    # Password accepted - grant access and auto-move if possible.
    await channel.set_permissions(interaction.user, connect=True, view_channel=True)
    if interaction.user.voice:
        try:
            await interaction.user.move_to(channel)
            await interaction.response.send_message(
                f"🔓 Password accepted! Moving you to **{channel.name}**...", ephemeral=True
            )
        except discord.errors.HTTPException:
            await interaction.response.send_message(
                f"🔓 Password accepted! I couldn't move you (channel full?). "
                f"It is now visible to you: {channel.mention}",
                ephemeral=True,
            )
    else:
        await interaction.response.send_message(
            f"🔓 Password accepted! The channel is now visible: {channel.mention}. "
            f"(Join a VC first next time for auto-move!)",
            ephemeral=True,
        )


# Events
@bot.event
async def on_voice_state_update(
    member: discord.Member,
    before: discord.VoiceState,
    after: discord.VoiceState,
) -> None:
    if before.channel == after.channel or before.channel is None:
        return

    channel = before.channel
    if len(channel.members) != 0:
        return

    # Channel is now empty - delete it if the bot manages it.
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT channel_id FROM channels WHERE channel_id = ?", (channel.id,)
        )
        result = await cursor.fetchone()
        if result:
            try:
                await channel.delete()
                await db.execute("DELETE FROM channels WHERE channel_id = ?", (channel.id,))
                await db.commit()
                log.info("Deleted invisible channel: %s", channel.name)
            except Exception as exc:
                log.error("Error deleting channel: %s", exc)


def main() -> None:
    if not TOKEN:
        log.error("DISCORD_TOKEN not found - add it to your .env file.")
        sys.exit(1)
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
