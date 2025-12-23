# 👻 Hidden Voice Channels Bot

> **Create temporary, password-protected voice channels that are invisible to everyone else!**

[![Invite Bot](https://img.shields.io/badge/Discord-Invite%20Bot-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com/oauth2/authorize?client_id=1291651842765361183&permissions=16778256&integration_type=0&scope=bot)

---

## 🔒 How it Works
1. **Create:** A user runs `/createvc`.
2. **Hide:** The bot creates a Voice Channel that **only** the creator (and the bot) can see.
3. **Password:** To join, friends must use `/joinvc` with the correct password.
4. **Auto-Delete:** Once everyone leaves, the channel is automatically deleted to keep your server clean.

## 🚀 Features
* **👻 True Invisibility:** Channels are hidden from the sidebar for anyone who hasn't joined.
* **🔑 Password Protection:** Keep your conversations private.
* **🧹 Auto-Cleanup:** No manual deletion needed. Empty channels vanish instantly.
* **⚡ Auto-Move:** If you are already in a voice channel, the bot will drag you into the hidden one automatically upon creation/joining.

---

## 📥 How to Use

**Step 1:** Invite the bot to your server.
**Step 2:** An Admin must run the setup command once:

/setup_vc [text_channel]

*(This defines the specific text channel where users can run the Create/Join commands)*

**Step 3:** Users can now use:
* `/createvc [name] [password] [limit]`
* `/joinvc [channel_name] [password]`

---

## ⚡ Requirements (Self-Hosting)
* Python 3.8+
* `discord.py`
* `aiosqlite` (for database management)

---

> *Note: The bot requires "Manage Channels" and "Move Members" p