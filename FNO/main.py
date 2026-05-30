"""Free Games & Offers Bot.

Scans the GamerPower giveaways API every few hours and posts newly-found
free games to every configured Discord server. De-duplicates by giveaway ID
so the same offer is never posted twice.
"""

import json
import logging
import os
import sys
from typing import Any

import aiohttp
import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("FreeGamesBot")

# Config
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

SEEN_GAMES_FILE = "seen_games.json"
SETTINGS_FILE = "server_settings.json"
GIVEAWAYS_URL = "https://www.gamerpower.com/api/giveaways"
CHECK_INTERVAL_HOURS = 6
MAX_SEEN_IDS = 150
EMBED_COLOR = 0x5865F2

# Bot setup
intents = discord.Intents.default()


class FreeGamesBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        await self.tree.sync()


bot = FreeGamesBot()


# Storage helpers
def load_json(filename: str) -> Any:
    """Load JSON storage, returning a sensible empty default if absent."""
    if not os.path.exists(filename):
        return [] if filename == SEEN_GAMES_FILE else {}
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.error("Failed to read %s: %s", filename, exc)
        return [] if filename == SEEN_GAMES_FILE else {}


def save_json(filename: str, data: Any) -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def save_seen_id(game_id: int) -> None:
    """Record a giveaway ID so it is never posted again (keeps last 150)."""
    seen_ids = load_json(SEEN_GAMES_FILE)
    if game_id not in seen_ids:
        seen_ids.append(game_id)
        if len(seen_ids) > MAX_SEEN_IDS:
            seen_ids = seen_ids[-MAX_SEEN_IDS:]
        save_json(SEEN_GAMES_FILE, seen_ids)


# Slash commands
@bot.tree.command(name="setup_offers", description="Set the channel for free game alerts")
@app_commands.describe(
    channel="The channel where games will be posted",
    role="The role to ping (optional)",
)
@app_commands.checks.has_permissions(administrator=True)
async def setup_offers(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    role: discord.Role | None = None,
) -> None:
    settings = load_json(SETTINGS_FILE)
    gid = str(interaction.guild_id)

    settings[gid] = {
        "channel_id": channel.id,
        "role_id": role.id if role else None,
    }
    save_json(SETTINGS_FILE, settings)

    msg = f"✅ Setup complete! Free Games will be posted in {channel.mention}."
    if role:
        msg += f" (Role to ping: {role.mention})"
    await interaction.response.send_message(msg)


@bot.tree.command(name="check_now", description="Manually check for free games immediately")
@app_commands.checks.has_permissions(administrator=True)
async def check_now(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    await check_special_offers()
    await interaction.followup.send("✅ Check complete!")


# Background task
@tasks.loop(hours=CHECK_INTERVAL_HOURS)
async def check_special_offers() -> None:
    log.info("Checking for new free games...")
    settings = load_json(SETTINGS_FILE)
    if not settings:
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(GIVEAWAYS_URL) as response:
                if response.status != 200:
                    log.warning("GamerPower API returned status %s", response.status)
                    return
                giveaways = await response.json()
    except Exception as exc:
        log.error("API error: %s", exc)
        return

    seen_ids = load_json(SEEN_GAMES_FILE)
    new_game_found = False

    for game in giveaways:
        # Only active giveaways we have not already posted.
        if game["id"] in seen_ids or game.get("status") != "Active":
            continue

        embed = discord.Embed(
            title=game["title"],
            description=game.get("description", "Click the link to get it!"),
            url=game["open_giveaway_url"],
            color=EMBED_COLOR,
        )
        embed.set_image(url=game["image"])
        embed.add_field(name="Price", value=game.get("worth", "Free"), inline=True)
        embed.add_field(name="Platform", value=game["platforms"], inline=True)
        embed.set_footer(text=f"Ends: {game.get('end_date', 'Unknown')}")

        # Broadcast to every registered server.
        for gid, config in settings.items():
            guild = bot.get_guild(int(gid))
            if not guild:
                continue
            channel = guild.get_channel(config["channel_id"])
            if not channel:
                continue

            role_ping = ""
            if config["role_id"]:
                role = guild.get_role(config["role_id"])
                if role:
                    role_ping = role.mention

            try:
                await channel.send(
                    content=f"{role_ping} **New Free Game!** 🎁", embed=embed
                )
            except Exception as exc:
                log.error("Failed to send in %s: %s", guild.name, exc)

        save_seen_id(game["id"])
        new_game_found = True

    log.info("New games posted!" if new_game_found else "No new games found.")


@bot.event
async def on_ready() -> None:
    log.info("%s is online (Free Games Bot)", bot.user)
    if not check_special_offers.is_running():
        check_special_offers.start()


def main() -> None:
    if not DISCORD_TOKEN:
        log.error("DISCORD_BOT_TOKEN not found - add it to your .env file.")
        sys.exit(1)
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
