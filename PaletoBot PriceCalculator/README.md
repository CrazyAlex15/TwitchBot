# 🔧 Paleto Tuners Bot

> **Streamline your Mechanic Shop RP.** The ultimate tool for automated price calculations, invoices, and logging for GTA RP servers.

[![Invite Bot](https://img.shields.io/badge/Discord-Invite%20Bot-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com/oauth2/authorize?client_id=1386805973699657798&permissions=536890368&integration_type=0&scope=bot+applications.commands)

---

## 🚀 Why add this bot?

🛠️ **Interactive Dashboard**
Forget manual calculations! Mechanics can select services (Repairs, Upgrades, Parts) from beautiful **Dropdown Menus**. The bot handles the math automatically.

💸 **Smart Invoicing**
* **Auto-Discounts:** Automatically applies a **50% discount** for Police (LSPD) and EMS clients.
* **Quantity Control:** Easily edit quantities for bulk orders using pop-up forms.
* **Receipts:** Generates a clear, itemized receipt for the customer instantly.

📜 **Secure Logging**
Every transaction is logged! The bot sends a detailed invoice to a private Discord channel via **Webhooks**, keeping your business finances organized and cheat-free.

🌍 **Universal Support**
Works on any server! As an Admin, you decide exactly which channels the bot uses for the Price List and the Job Panel.

---

## 📥 How to Use

**Step 1:** Click the link below to invite the bot to your server.
[**🔗 ADD BOT TO SERVER**](https://discord.com/oauth2/authorize?client_id=1386805973699657798&permissions=536890368&integration_type=0&scope=bot+applications.commands)

**Step 2:** Go to your admin channel and run the setup command:

/setup_paleto [menu_channel] [job_channel] [webhook_url]

* `menu_channel`: The public channel where the **Price List** will be displayed.
* `job_channel`: The private channel where mechanics will see the **Dashboard**.
* `webhook_url`: The Discord Webhook URL for your logs channel.

**Step 3:** That's it! The panels are deployed and ready to use.

---

## ⚡ Available Commands

| Command | Description | Permission |
| :--- | :--- | :--- |
| `/setup_paleto` | Deploy the interactive menus and set up logging. | **Administrator** |

---

> *Built with Python for speed and reliability.*