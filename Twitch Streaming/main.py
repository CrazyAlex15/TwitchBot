import discord
from discord import app_commands
from discord.ext import tasks, commands
import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')

# Database File
DB_FILE = "twitch_data.json"

# Setup Bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

class TwitchBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

bot = TwitchBot()

# --- HELPER FUNCTIONS ---

def load_data():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_twitch_access_token():
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": TWITCH_CLIENT_ID,
        "client_secret": TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    try:
        response = requests.post(url, params=params)
        return response.json().get('access_token')
    except Exception as e:
        print(f"Error getting Twitch Token: {e}")
        return None

def is_channel_live(channel_name, access_token):
    url = f"https://api.twitch.tv/helix/streams?user_login={channel_name}"
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {access_token}"
    }
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        if data.get('data'): 
            return True, data['data'][0]['title'], data['data'][0]['game_name']
        return False, None, None
    except Exception as e:
        print(f"Error checking {channel_name}: {e}")
        return False, None, None

# --- SLASH COMMANDS ---

@bot.tree.command(name="setup_twitch", description="Configure the channel and role for Twitch alerts")
@app_commands.describe(channel="Channel for alerts", role="Role to ping (Live Now)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_twitch(interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role):
    data = load_data()
    gid = str(interaction.guild_id)
    
    if gid not in data:
        data[gid] = {"streamers": {}}
        
    data[gid]["channel_id"] = channel.id
    data[gid]["role_id"] = role.id
    
    save_data(data)
    await interaction.response.send_message(f"✅ Setup complete! Alerts in {channel.mention}, Role: {role.mention}")

@bot.tree.command(name="addstreamer", description="Add a streamer to the watchlist")
@app_commands.describe(member="Discord User", twitch_name="Twitch Channel Name")
@app_commands.checks.has_permissions(administrator=True)
async def addstreamer(interaction: discord.Interaction, member: discord.Member, twitch_name: str):
    data = load_data()
    gid = str(interaction.guild_id)

    if gid not in data or "channel_id" not in data[gid]:
        await interaction.response.send_message("⚠️ Please run `/setup_twitch` first!", ephemeral=True)
        return

    data[gid]["streamers"][str(member.id)] = {"twitch": twitch_name, "is_live": False}
    save_data(data)
    await interaction.response.send_message(f"✅ Linked {member.mention} to Twitch channel: **{twitch_name}**")

@bot.tree.command(name="removestreamer", description="Remove a streamer from the watchlist")
@app_commands.checks.has_permissions(administrator=True)
async def removestreamer(interaction: discord.Interaction, member: discord.Member):
    data = load_data()
    gid = str(interaction.guild_id)
    
    if gid in data and str(member.id) in data[gid]["streamers"]:
        del data[gid]["streamers"][str(member.id)]
        save_data(data)
        await interaction.response.send_message(f"🗑️ Removed {member.mention} from the list.")
    else:
        await interaction.response.send_message("❌ User not found in the list.", ephemeral=True)

@bot.tree.command(name="liststreamers", description="Show all tracked streamers")
async def liststreamers(interaction: discord.Interaction):
    data = load_data()
    gid = str(interaction.guild_id)
    
    if gid not in data or not data[gid]["streamers"]:
        await interaction.response.send_message("List is empty.", ephemeral=True)
        return

    msg = "**📺 Tracked Streamers:**\n"
    for uid, info in data[gid]["streamers"].items():
        msg += f"<@{uid}> -> https://twitch.tv/{info['twitch']}\n"
    await interaction.response.send_message(msg)

# --- BACKGROUND LOOP ---

@tasks.loop(minutes=2)
async def check_live_streams():
    data = load_data()
    if not data: return 

    token = get_twitch_access_token()
    if not token: return

    changes_made = False

    # Iterate through ALL servers
    for gid, server_data in data.items():
        if "channel_id" not in server_data: continue

        guild = bot.get_guild(int(gid))
        if not guild: continue

        channel = guild.get_channel(server_data["channel_id"])
        role = guild.get_role(server_data["role_id"])

        for user_id, info in server_data["streamers"].items():
            twitch_name = info['twitch']
            was_live = info['is_live']
            
            is_live_now, stream_title, game_name = is_channel_live(twitch_name, token)
            member = guild.get_member(int(user_id))
            
            if not member: continue

            # CASE: WENT LIVE
            if is_live_now and not was_live:
                server_data["streamers"][user_id]['is_live'] = True
                changes_made = True
                
                if role: await member.add_roles(role)
                if channel:
                    embed = discord.Embed(title=f"{twitch_name} is LIVE!", url=f"https://twitch.tv/{twitch_name}", color=0x9146FF)
                    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
                    embed.add_field(name="Title", value=stream_title, inline=False)
                    embed.add_field(name="Game", value=game_name, inline=True)
                    embed.set_thumbnail(url=member.display_avatar.url)
                    
                    await channel.send(content=f"🔴 **NOW LIVE!** {member.mention} {role.mention if role else ''}", embed=embed)

            # CASE: WENT OFFLINE
            elif not is_live_now and was_live:
                server_data["streamers"][user_id]['is_live'] = False
                changes_made = True
                if role: await member.remove_roles(role)

    if changes_made:
        save_data(data)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (Twitch Bot)')
    check_live_streams.start()

if DISCORD_TOKEN:
    bot.run(DISCORD_TOKEN)
else:
    print("Error: DISCORD_TOKEN not found in .env")