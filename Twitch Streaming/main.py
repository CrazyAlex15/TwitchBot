"""Twitch Live Notifier Bot.

Links Discord members to Twitch channels and posts a "Now Live" alert (and
assigns a Live role) when they go live, removing the role when they stop.
Twitch state is polled every couple of minutes via the Helix API.

Network calls use the blocking requests library, so they are dispatched to
a worker thread with asyncio.to_thread() to avoid blocking the Discord event
loop during each poll.
"""

import asyncio
import json
import logging
import os
import sys

import discord
import requests
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("TwitchBot")

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")

DB_FILE = "twitch_data.json"
CHECK_INTERVAL_MINUTES = 2
HTTP_TIMEOUT = 10
EMBED_COLOR = 0x9146FF

intents = discord.Intents.default()
intents.members = True


class TwitchBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        await self.tree.sync()


bot = TwitchBot()


def load_data() -> dict:
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.error("Failed to read %s: %s", DB_FILE, exc)
        return {}


def save_data(data: dict) -> None:
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def get_twitch_access_token() -> str | None:
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": TWITCH_CLIENT_ID,
        "client_secret": TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials",
    }
    try:
        response = requests.post(url, params=params, timeout=HTTP_TIMEOUT)
        return response.json().get("access_token")
    except Exception as exc:
        log.error("Error getting Twitch token: %s", exc)
        return None


def is_channel_live(channel_name: str, access_token: str) -> tuple[bool, str | None, str | None]:
    url = f"https://api.twitch.tv/helix/streams?user_login={channel_name}"
    headers = {"Client-ID": TWITCH_CLIENT_ID, "Authorization": f"Bearer {access_token}"}
    try:
        response = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
        data = response.json()
        if data.get("data"):
            return True, data["data"][0]["title"], data["data"][0]["game_name"]
        return False, None, None
    except Exception as exc:
        log.error("Error checking %s: %s", channel_name, exc)
        return False, None, None


@bot.tree.command(name="setup_twitch", description="Configure the channel and role for Twitch alerts")
@app_commands.describe(channel="Channel for alerts", role="Role to ping (Live Now)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_twitch(
    interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role
) -> None:
    data = load_data()
    gid = str(interaction.guild_id)
    if gid not in data:
        data[gid] = {"streamers": {}}
    data[gid]["channel_id"] = channel.id
    data[gid]["role_id"] = role.id
    save_data(data)
    await interaction.response.send_message(
        f"✅ Setup complete! Alerts in {channel.mention}, Role: {role.mention}"
    )


@bot.tree.command(name="addstreamer", description="Add a streamer to the watchlist")
@app_commands.describe(member="Discord User", twitch_name="Twitch Channel Name")
@app_commands.checks.has_permissions(administrator=True)
async def addstreamer(
    interaction: discord.Interaction, member: discord.Member, twitch_name: str
) -> None:
    data = load_data()
    gid = str(interaction.guild_id)
    if gid not in data or "channel_id" not in data[gid]:
        await interaction.response.send_message(
            "⚠️ Please run `" + chr(47) + "setup_twitch` first!", ephemeral=True
        )
        return
    data[gid]["streamers"][str(member.id)] = {"twitch": twitch_name, "is_live": False}
    save_data(data)
    await interaction.response.send_message(
        f"✅ Linked {member.mention} to Twitch channel: **{twitch_name}**"
    )


@bot.tree.command(name="removestreamer", description="Remove a streamer from the watchlist")
@app_commands.checks.has_permissions(administrator=True)
async def removestreamer(interaction: discord.Interaction, member: discord.Member) -> None:
    data = load_data()
    gid = str(interaction.guild_id)
    if gid in data and str(member.id) in data[gid]["streamers"]:
        del data[gid]["streamers"][str(member.id)]
        save_data(data)
        await interaction.response.send_message(f"🗑️ Removed {member.mention} from the list.")
    else:
        await interaction.response.send_message("❌ User not found in the list.", ephemeral=True)


@bot.tree.command(name="liststreamers", description="Show all tracked streamers")
async def liststreamers(interaction: discord.Interaction) -> None:
    data = load_data()
    gid = str(interaction.guild_id)
    if gid not in data or not data[gid]["streamers"]:
        await interaction.response.send_message("List is empty.", ephemeral=True)
        return
    msg = "**📺 Tracked Streamers:**" + chr(10)
    for uid, info in data[gid]["streamers"].items():
        msg += f"<@{uid}> -> https://twitch.tv/{info['twitch']}" + chr(10)
    await interaction.response.send_message(msg)


@tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
async def check_live_streams() -> None:
    data = load_data()
    if not data:
        return

    token = await asyncio.to_thread(get_twitch_access_token)
    if not token:
        return

    changes_made = False

    for gid, server_data in data.items():
        if "channel_id" not in server_data:
            continue

        guild = bot.get_guild(int(gid))
        if not guild:
            continue

        channel = guild.get_channel(server_data["channel_id"])
        role = guild.get_role(server_data["role_id"])

        for user_id, info in server_data["streamers"].items():
            twitch_name = info["twitch"]
            was_live = info["is_live"]

            is_live_now, stream_title, game_name = await asyncio.to_thread(
                is_channel_live, twitch_name, token
            )
            member = guild.get_member(int(user_id))
            if not member:
                continue

            if is_live_now and not was_live:
                server_data["streamers"][user_id]["is_live"] = True
                changes_made = True
                if role:
                    await member.add_roles(role)
                if channel:
                    embed = discord.Embed(
                        title=f"{twitch_name} is LIVE!",
                        url=f"https://twitch.tv/{twitch_name}",
                        color=EMBED_COLOR,
                    )
                    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
                    embed.add_field(name="Title", value=stream_title, inline=False)
                    embed.add_field(name="Game", value=game_name, inline=True)
                    embed.set_thumbnail(url=member.display_avatar.url)
                    await channel.send(
                        content=f"🔴 **NOW LIVE!** {member.mention} {role.mention if role else ''}",
                        embed=embed,
                    )

            elif not is_live_now and was_live:
                server_data["streamers"][user_id]["is_live"] = False
                changes_made = True
                if role:
                    await member.remove_roles(role)

    if changes_made:
        save_data(data)


@bot.event
async def on_ready() -> None:
    log.info("Logged in as %s (Twitch Bot)", bot.user)
    if not check_live_streams.is_running():
        check_live_streams.start()


def main() -> None:
    if not DISCORD_TOKEN:
        log.error("DISCORD_TOKEN not found - add it to your .env file.")
        sys.exit(1)
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        log.error("TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET not found - add them to your .env file.")
        sys.exit(1)
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
