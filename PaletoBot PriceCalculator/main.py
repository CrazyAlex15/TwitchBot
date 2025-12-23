import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import aiohttp
from dotenv import load_dotenv

# Load Env & Config
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
PRICES_FILE = "prices.json"
SETTINGS_FILE = "server_settings.json"

# Intents
intents = discord.Intents.default()
intents.guilds = True

class PaletoBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

bot = PaletoBot()

# --- DATA LOADING ---
def load_json(filename):
    if not os.path.exists(filename): return {}
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

raw_prices = load_json(PRICES_FILE)
prices = {k: {"price": v if isinstance(v, int) else 0, "available": isinstance(v, int)} for k, v in raw_prices.items()}

CATEGORIES = {
    "Repair Jobs": ["Full Repair", "HG Full Repair", "Repair Kit", "Advanced Repair Kit"],
    "Lockpick Tools": ["LockPick", "Advanced Lockpick"],
    "Performance Parts": ["Racing Harness", "NOS"],
    "Communication": ["Long Range Radio"],
    "Cosmetics": ["Fantastic Wax"],
    "Upgrades": [
        "Engine 1", "Engine 2", "Engine 3",
        "Suspension 1", "Suspension 2", "Suspension 3",
        "Transmission 1", "Transmission 2", "Transmission 3",
        "Brakes 1", "Brakes 2", "Brakes 3",
        "Turbo", "Upgrade Package"
    ]
}

DISCOUNTS = {"normal": 1.0, "lspd": 0.5, "ems": 0.5}

# --- WEBHOOK LOGGING ---
async def send_webhook(url, embed):
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(url, session=session)
        await webhook.send(embed=embed, username="Paleto Bot Logs")

# --- UI CLASSES ---

class QuantityModal(discord.ui.Modal):
    def __init__(self, selected_jobs, session_data, original_interaction):
        super().__init__(title="Edit Quantities")
        self.selected_jobs = selected_jobs
        self.session_data = session_data
        self.original_interaction = original_interaction
        
        # Add inputs dynamically
        for job in selected_jobs:
            self.add_item(discord.ui.TextInput(
                label=job, 
                default=str(session_data.get(job, 1)),
                min_length=1, max_length=2, required=True
            ))

    async def on_submit(self, interaction: discord.Interaction):
        for item in self.children:
            try:
                qty = int(item.value)
                if qty < 1: qty = 1
                self.session_data[item.label] = qty
            except ValueError:
                pass
        
        await interaction.response.send_message("✅ Quantities updated! Click **Checkout** to finish.", ephemeral=True)

class ClientTypeView(discord.ui.View):
    def __init__(self, session_data, webhook_url):
        super().__init__(timeout=120)
        self.session_data = session_data
        self.webhook_url = webhook_url

    @discord.ui.select(placeholder="Select Client Type", options=[
        discord.SelectOption(label="Normal Customer", value="normal"),
        discord.SelectOption(label="LSPD (50% Off)", value="lspd"),
        discord.SelectOption(label="EMS (50% Off)", value="ems")
    ])
    async def select_client(self, interaction: discord.Interaction, select: discord.ui.Select):
        client_type = select.values[0]
        total = 0
        lines = []

        for job, qty in self.session_data.items():
            price = prices[job]['price']
            total += price * qty
            lines.append(f"• {job} x{qty} = ${price * qty:,}")

        discount = DISCOUNTS.get(client_type, 1.0)
        final_total = int(total * discount)

        # Receipt Embed
        embed = discord.Embed(title="✅ Job Submitted", color=0x27ae60)
        embed.add_field(name="🛠️ Services", value="\n".join(lines), inline=False)
        embed.add_field(name="💵 Total", value=f"${final_total:,} ({client_type.upper()})", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Webhook Log
        if self.webhook_url:
            log_embed = discord.Embed(title="📋 New Invoice", color=0x00b894, timestamp=interaction.created_at)
            log_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            log_embed.description = "\n".join(lines)
            log_embed.add_field(name="Client", value=client_type.upper(), inline=True)
            log_embed.add_field(name="Total", value=f"${final_total:,}", inline=True)
            try:
                await send_webhook(self.webhook_url, log_embed)
            except Exception as e:
                print(f"Webhook Error: {e}")

class JobSelectView(discord.ui.View):
    def __init__(self, category, webhook_url):
        super().__init__(timeout=180)
        self.category = category
        self.webhook_url = webhook_url
        self.session_data = {} # Stores {JobName: Quantity}
        self.selected_jobs = []

        # Create Select Menu dynamically
        options = []
        for job in CATEGORIES[category]:
            if prices.get(job, {}).get('available', False):
                options.append(discord.SelectOption(label=job, value=job))
        
        if not options: return # Should handle empty categories gracefully

        select = discord.ui.Select(
            placeholder="Select Services (Multi-select)",
            min_values=1,
            max_values=min(len(options), 25),
            options=options,
            custom_id="job_select"
        )
        select.callback = self.job_callback
        self.add_item(select)

    async def job_callback(self, interaction: discord.Interaction):
        # Update selected jobs
        select_menu = [x for x in self.children if isinstance(x, discord.ui.Select)][0]
        self.selected_jobs = select_menu.values
        
        # Initialize qty to 1 if not set
        for job in self.selected_jobs:
            if job not in self.session_data:
                self.session_data[job] = 1
        
        await interaction.response.defer()

    @discord.ui.button(label="Edit Quantities", style=discord.ButtonStyle.primary, row=1)
    async def edit_qty(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_jobs:
            return await interaction.response.send_message("⚠️ Select at least one job first!", ephemeral=True)
        if len(self.selected_jobs) > 5:
            return await interaction.response.send_message("⚠️ You can only edit 5 items at a time due to Discord limits.", ephemeral=True)
        
        await interaction.response.send_modal(QuantityModal(self.selected_jobs, self.session_data, interaction))

    @discord.ui.button(label="Checkout", style=discord.ButtonStyle.success, row=1)
    async def checkout(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.session_data:
            return await interaction.response.send_message("⚠️ Cart is empty.", ephemeral=True)
        
        view = ClientTypeView(self.session_data, self.webhook_url)
        await interaction.response.send_message("Select Client Type:", view=view, ephemeral=True)

class CategoryView(discord.ui.View):
    def __init__(self, webhook_url):
        super().__init__(timeout=None) # Persistent View
        self.webhook_url = webhook_url

    @discord.ui.select(placeholder="Select a Category", options=[
        discord.SelectOption(label="Repair Jobs", emoji="🔧"),
        discord.SelectOption(label="Lockpick Tools", emoji="🛠️"),
        discord.SelectOption(label="Upgrades", emoji="🚗"),
        discord.SelectOption(label="Performance Parts", emoji="🏁")
    ], custom_id="main_cat_select")
    async def select_category(self, interaction: discord.Interaction, select: discord.ui.Select):
        category = select.values[0]
        view = JobSelectView(category, self.webhook_url)
        await interaction.response.send_message(f"**{category}** - Select items:", view=view, ephemeral=True)

# --- SLASH COMMANDS ---

@bot.tree.command(name="setup_paleto", description="Deploy the Menu and Job Panel")
@app_commands.describe(menu_channel="Where to post prices", job_channel="Where to post the dashboard", webhook="Log Webhook URL")
@app_commands.checks.has_permissions(administrator=True)
async def setup_paleto(interaction: discord.Interaction, menu_channel: discord.TextChannel, job_channel: discord.TextChannel, webhook: str):
    settings = load_json(SETTINGS_FILE)
    settings[str(interaction.guild_id)] = {
        "menu_channel": menu_channel.id,
        "job_channel": job_channel.id,
        "webhook": webhook
    }
    save_json(SETTINGS_FILE, settings)
    
    await interaction.response.send_message("✅ Setup saved! Deploying panels...", ephemeral=True)

    # Deploy Price Embed
    embed = discord.Embed(title="💰 Paleto Tuners Price List", color=0x00aaff)
    embed.description = "Welcome! Below are our current service rates.\n❌ = Out of Stock / Unavailable"
    
    for cat, items in CATEGORIES.items():
        if cat == "Upgrades": continue
        lines = []
        for job in items:
            data = prices.get(job, {'price':0, 'available':False})
            if data['available']:
                lines.append(f"• **{job}** — ${data['price']:,}")
            else:
                lines.append(f"• ~{job}~ — **N/A**")
        embed.add_field(name=cat, value="\n".join(lines), inline=False)
    
    # Add Upgrades Separate
    upg_lines = []
    for job in CATEGORIES["Upgrades"]:
        data = prices.get(job, {'price':0, 'available':False})
        if data['available']:
            upg_lines.append(f"• **{job}** — ${data['price']:,}")
    embed.add_field(name="🚗 Upgrades", value="\n".join(upg_lines) if upg_lines else "None", inline=False)

    await menu_channel.send(embed=embed)

    # Deploy Job Panel
    await job_channel.send(
        content="👋 **Mechanic Dashboard**\nSelect a category below to start an order:",
        view=CategoryView(webhook)
    )

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    # Re-register views for persistence (if needed later)
    # bot.add_view(CategoryView(webhook_url="...")) 
    # Note: For full persistence across restarts, we need to load webhooks from DB on ready.
    # For now, simplistic approach is fine.

if TOKEN:
    bot.run(TOKEN)
else:
    print("Error: DISCORD_TOKEN not found in .env")