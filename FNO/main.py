import discord
from discord import app_commands
from discord.ext import tasks, commands
import aiohttp
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Storage Files
SEEN_GAMES_FILE = "seen_games.json"
SETTINGS_FILE = "server_settings.json"

# Setup Bot
intents = discord.Intents.default()

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()

# --- HELPER FUNCTIONS ---

def load_json(filename):
    if not os.path.exists(filename):
        return [] if filename == SEEN_GAMES_FILE else {}
    with open(filename, "r") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

def save_seen_id(game_id):
    """Saves game ID to avoid duplicates"""
    seen_ids = load_json(SEEN_GAMES_FILE)
    if game_id not in seen_ids:
        seen_ids.append(game_id)
        # Keep only the last 150 IDs
        if len(seen_ids) > 150:
            seen_ids = seen_ids[-150:]
        save_json(SEEN_GAMES_FILE, seen_ids)

# --- SLASH COMMANDS ---

@bot.tree.command(name="setup_offers", description="Set the channel for free game alerts")
@app_commands.describe(channel="The channel where games will be posted", role="The role to ping (optional)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_offers(interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role = None):
    settings = load_json(SETTINGS_FILE)
    gid = str(interaction.guild_id)
    
    settings[gid] = {
        "channel_id": channel.id,
        "role_id": role.id if role else None
    }
    
    save_json(SETTINGS_FILE, settings)
    
    msg = f"✅ Setup complete! Free Games will be posted in {channel.mention}."
    if role:
        msg += f" (Role to ping: {role.mention})"
    
    await interaction.response.send_message(msg)

@bot.tree.command(name="check_now", description="Manually check for free games immediately")
@app_commands.checks.has_permissions(administrator=True)
async def check_now(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await check_special_offers()
    await interaction.followup.send("✅ Check complete!")

# --- BACKGROUND TASK ---

@tasks.loop(hours=6) # Check every 6 hours
async def check_special_offers():
    print("Checking for new free games...")
    settings = load_json(SETTINGS_FILE)
    if not settings: return

    url = "https://www.gamerpower.com/api/giveaways"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200: return
                giveaways = await response.json()
    except Exception as e:
        print(f"API Error: {e}")
        return

    seen_ids = load_json(SEEN_GAMES_FILE)
    new_game_found = False

    for game in giveaways:
        # Filter: Must be Active and not seen before
        if game['id'] in seen_ids or game.get('status') != 'Active':
            continue

        # Create Embed
        embed = discord.Embed(
            title=game['title'],
            description=game.get('description', 'Click the link to get it!'),
            url=game['open_giveaway_url'],
            color=0x5865F2
        )
        embed.set_image(url=game['image'])
        embed.add_field(name="Price", value=game.get('worth', 'Free'), inline=True)
        embed.add_field(name="Platform", value=game['platforms'], inline=True)
        embed.set_footer(text=f"Ends: {game.get('end_date', 'Unknown')}")

        # Send to ALL registered servers
        for gid, config in settings.items():
            guild = bot.get_guild(int(gid))
            if not guild: continue
            
            channel = guild.get_channel(config['channel_id'])
            if not channel: continue

            role_ping = ""
            if config['role_id']:
                role = guild.get_role(config['role_id'])
                if role: role_ping = role.mention

            try:
                await channel.send(content=f"{role_ping} **New Free Game!** 🎁", embed=embed)
            except Exception as e:
                print(f"Failed to send in {guild.name}: {e}")

        # Mark as seen
        save_seen_id(game['id'])
        new_game_found = True

    if new_game_found:
        print("New games posted!")
    else:
        print("No new games found.")

@bot.event
async def on_ready():
    print(f'{bot.user} is online (Free Games Bot)')
    if not check_special_offers.is_running():
        check_special_offers.start()

if __name__ == "__main__":
    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN)
    else:
        print("Error: DISCORD_BOT_TOKEN not found in .env")