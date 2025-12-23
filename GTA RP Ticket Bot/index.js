// index.js — FiveM Ticket Bot with Private Threads
require("dotenv").config();
const {
  Client,
  GatewayIntentBits,
  Partials,
  PermissionsBitField,
  ChannelType,
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  EmbedBuilder,
  ActivityType,
} = require("discord.js");
const axios = require("axios");
const httpAgent = new (require("http")).Agent({ keepAlive: true });
const httpsAgent = new (require("https")).Agent({ keepAlive: true });

// --- CONFIGURATION ---
const {
  DISCORD_TOKEN,
  FIVEM_SERVER_IP,
  STAFF_ROLE_ID,
  LOG_CHANNEL_ID,
  PANEL_CHANNEL_ID,
  PANEL_CHANNEL_NAME,
  DEBUG
} = process.env;

// Validation
const REQUIRED = ["DISCORD_TOKEN", "FIVEM_SERVER_IP", "STAFF_ROLE_ID", "LOG_CHANNEL_ID", "PANEL_CHANNEL_ID"];
const missing = REQUIRED.filter((k) => !process.env[k]);
if (missing.length) {
  console.error("❌ Missing ENV:", missing.join(", "));
  process.exit(1);
}

// --- CONSTANTS ---
const COLORS = { panel: 0x2b2d31, primary: 0x5865f2, success: 0x57f287, danger: 0xed4245 };
const http = axios.create({ timeout: 4000, httpAgent, httpsAgent });

// --- STATE ---
const openTickets = new Map(); // guildId -> Map<userId, threadId>
const activeCreates = new Set();
const createCooldown = new Map();
const CREATE_COOLDOWN_MS = 3000;

// Ticket Configuration
const ticketTypes = {
  "v3:ticket_support":      { name: "Support",       prefix: "support" },
  "v3:ticket_playerreport": { name: "Player Report", prefix: "report"  },
  "v3:ticket_bugreport":    { name: "Bug Report",    prefix: "bug"     },
};

// --- CLIENT SETUP ---
const client = new Client({
  intents: [GatewayIntentBits.Guilds],
  partials: [Partials.Channel],
  allowedMentions: { parse: [], roles: [STAFF_ROLE_ID] },
});

// --- HELPER FUNCTIONS ---
function sanitize(s) { return (s || "").toLowerCase().replace(/[^a-z0-9]/g, ""); }

async function sendLog(guild, embed) {
  try {
    const ch = guild.channels.cache.get(LOG_CHANNEL_ID) || (await guild.channels.fetch(LOG_CHANNEL_ID).catch(() => null));
    if (ch?.isTextBased()) await ch.send({ embeds: [embed] });
  } catch (e) { console.error("Log error:", e.message); }
}

async function resolvePanelChannel() {
  if (PANEL_CHANNEL_ID) {
    try {
      const ch = await client.channels.fetch(PANEL_CHANNEL_ID).catch(() => null);
      if (ch?.isTextBased()) return ch;
    } catch {}
  }
  return null;
}

// --- FIVE M PRESENCE ---
async function updatePresence() {
  try {
    const [players, info] = await Promise.all([
      http.get(`http://${FIVEM_SERVER_IP}/players.json`),
      http.get(`http://${FIVEM_SERVER_IP}/info.json`),
    ]);
    const count = Array.isArray(players.data) ? players.data.length : 0;
    const max = Number(info.data?.vars?.sv_maxClients) || 64;
    
    await client.user.setPresence({ 
      status: "online", 
      activities: [{ name: `Players: ${count}/${max}`, type: ActivityType.Watching }] 
    });
  } catch {
    await client.user.setPresence({ 
      status: "dnd", 
      activities: [{ name: "Server Offline", type: ActivityType.Watching }] 
    });
  }
}

// --- MAIN LOGIC ---
client.once("ready", async () => {
  console.log(`✅ Logged in as ${client.user.tag}`);
  
  // Start Presence Loop
  updatePresence();
  setInterval(updatePresence, 30000);

  // Deploy Panel
  const panel = await resolvePanelChannel();
  if (panel) {
    try {
        // Clean old bot messages
        const messages = await panel.messages.fetch({ limit: 20 });
        const botMsgs = messages.filter(m => m.author.id === client.user.id);
        if (botMsgs.size > 0) await panel.bulkDelete(botMsgs);

        // Send new panel
        const embed = new EmbedBuilder()
            .setTitle("🎫 Server Support Tickets")
            .setDescription("Select a category below to open a private ticket.\n\n" +
                            "🧰 **Support** – General help & questions\n" +
                            "🚨 **Player Report** – Report rule breakers\n" +
                            "🐞 **Bug Report** – Server issues & glitches")
            .setColor(COLORS.panel)
            .setImage("https://i.imgur.com/your-banner-here.png"); // Optional Banner

        const row = new ActionRowBuilder().addComponents(
            new ButtonBuilder().setCustomId("v3:ticket_support").setLabel("Support").setStyle(ButtonStyle.Primary).setEmoji("🧰"),
            new ButtonBuilder().setCustomId("v3:ticket_playerreport").setLabel("Report").setStyle(ButtonStyle.Danger).setEmoji("🚨"),
            new ButtonBuilder().setCustomId("v3:ticket_bugreport").setLabel("Bug").setStyle(ButtonStyle.Success).setEmoji("🐞")
        );

        await panel.send({ embeds: [embed], components: [row] });
        console.log(`✅ Panel deployed to #${panel.name}`);
    } catch (e) {
        console.error("❌ Failed to deploy panel:", e.message);
    }
  } else {
      console.warn("⚠️ PANEL_CHANNEL_ID not found.");
  }
});

client.on("interactionCreate", async (interaction) => {
  if (!interaction.isButton()) return;
  if (!interaction.guild) return;

  const { customId, user, guild } = interaction;

  // 1. OPEN TICKET
  if (ticketTypes[customId]) {
    await interaction.deferReply({ ephemeral: true });
    
    // Cooldown check
    const now = Date.now();
    if (createCooldown.get(user.id) && now - createCooldown.get(user.id) < 3000) {
        return interaction.editReply("⏳ Please wait a moment.");
    }
    createCooldown.set(user.id, now);

    try {
        const panel = await resolvePanelChannel();
        const type = ticketTypes[customId];
        const threadName = `${type.prefix}-${sanitize(user.username)}`;

        const thread = await panel.threads.create({
            name: threadName,
            autoArchiveDuration: 1440,
            type: ChannelType.PrivateThread,
            reason: `Ticket by ${user.tag}`
        });

        await thread.members.add(user.id);
        
        // Ping Staff
        const staffMsg = `<@&${STAFF_ROLE_ID}> | Ticket by ${user.mention}`;
        
        const embed = new EmbedBuilder()
            .setTitle(`🎫 ${type.name} Ticket`)
            .setDescription(`Hello ${user.mention}!\nA staff member will be with you shortly.\n\nPlease provide:\n- Description of issue\n- Evidence (if reporting)\n- Relevant IDs`)
            .setColor(COLORS.primary)
            .setTimestamp();

        const closeRow = new ActionRowBuilder().addComponents(
            new ButtonBuilder().setCustomId("v3:close_ticket").setLabel("Close Ticket").setStyle(ButtonStyle.Secondary).setEmoji("🔒")
        );

        await thread.send({ content: staffMsg, embeds: [embed], components: [closeRow] });

        await interaction.editReply(`✅ Ticket created: <#${thread.id}>`);
        
        // Log
        sendLog(guild, new EmbedBuilder().setTitle("Ticket Opened").setDescription(`User: ${user.tag}\nType: ${type.name}\nThread: <#${thread.id}>`).setColor(COLORS.success));

    } catch (e) {
        console.error(e);
        interaction.editReply("❌ Error creating ticket. Check bot permissions.");
    }
  }

  // 2. CLOSE TICKET
  if (customId === "v3:close_ticket") {
    const thread = interaction.channel;
    if (!thread.isThread()) return;

    await interaction.reply("🔒 Closing ticket in 5 seconds...");
    
    // Log
    sendLog(guild, new EmbedBuilder().setTitle("Ticket Closed").setDescription(`Closed by: ${user.tag}\nThread: ${thread.name}`).setColor(COLORS.danger));

    setTimeout(async () => {
        try {
            await thread.setLocked(true);
            await thread.setArchived(true);
        } catch (e) { console.error(e); }
    }, 5000);
  }
});

client.login(DISCORD_TOKEN);