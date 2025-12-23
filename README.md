# 🟣 Twitch Live Notifier

> **Automatic "Going Live" alerts for your Discord community.** Connect Discord users to their Twitch channels and get instant notifications.

[![Invite Bot](https://img.shields.io/badge/Discord-Invite%20Bot-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com/oauth2/authorize?client_id=1452372393082224872&permissions=268584960&integration_type=0&scope=bot)

---

## 🚀 Features
* **🔴 Instant Alerts:** Checks Twitch API every 2 minutes.
* **🎭 Auto-Role:** Automatically assigns a "Live Now" role to streamers when they go online, and removes it when they stop.
* **🔗 User Linking:** Connects specific Discord members to Twitch channels.
* **🌍 Universal:** Works on any server. Admins configure their own channel and role.
* **✨ Rich Embeds:** Posts beautiful cards with Stream Title, Game, and Link.

---

## 📥 How to Use

**Step 1:** Invite the bot to your server.
**Step 2:** Admin runs the setup command:

/setup_twitch [channel] [role]

* `channel`: Where the alerts will be posted.
* `role`: The role to assign to live streamers (make sure the Bot's role is *above* this role in Server Settings!).

**Step 3:** Add streamers to the watchlist:
/addstreamer [@User] [twitch_channel_name]


---

## ⚡ Commands

| Command | Description | Permission |
| :--- | :--- | :--- |
| `/setup_twitch` | Configure channel and role. | **Admin** |
| `/addstreamer` | Link a Discord user to a Twitch channel. | **Admin** |
| `/removestreamer` | Remove a user from the list. | **Admin** |
| `/liststreamers` | Show all tracked streamers. | **Everyone** |

---

## 🛠️ Self-Hosting Requirements
* Python 3.8+
* Twitch Developer Account (Client ID & Secret)
* `discord.py` & `requests`