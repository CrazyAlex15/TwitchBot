# 🤖 Discord Bots Collection

A collection of small, focused Discord bots (plus a personal CV site), each
self-contained and deployable on its own — most run happily 24/7 on a
Raspberry Pi. Built with **discord.py** (Python) and **discord.js** (Node).

> Maintained by [CrazyAlex15](https://github.com/CrazyAlex15)

---

## 📦 Bots in this repository

| Bot | What it does | Stack | Invite |
| :-- | :-- | :-- | :-- |
| [🎫 GTA RP Ticket Bot](GTA%20RP%20Ticket%20Bot) | Private-thread support tickets + live FiveM player count | discord.js | [Add](https://discord.com/oauth2/authorize?client_id=1432746979154460763&permissions=395137009664&scope=bot) |
| [🎁 Free Games & Offers](FNO) | Auto-posts free games from the GamerPower API every 6h | discord.py | [Add](https://discord.com/oauth2/authorize?client_id=1292173790981259306&permissions=248832&scope=bot+applications.commands) |
| [👻 Hidden Voice Channels](HiddenVC) | Password-protected, invisible, auto-deleting voice channels | discord.py | [Add](https://discord.com/oauth2/authorize?client_id=1291651842765361183&permissions=16778256&scope=bot) |
| [🔧 Paleto Tuners](PaletoBot%20PriceCalculator) | GTA RP mechanic price calculator, invoices & webhook logs | discord.py | [Add](https://discord.com/oauth2/authorize?client_id=1386805973699657798&permissions=536890368&scope=bot+applications.commands) |
| [🟣 Twitch Live Notifier](Twitch%20Streaming) | "Now live" alerts + auto Live role via the Twitch Helix API | discord.py | [Add](https://discord.com/oauth2/authorize?client_id=1452372393082224872&permissions=268584960&scope=bot) |
| [📄 MyCV](MyCV) | Personal CV / portfolio web page | HTML | — |

## 🌐 Sibling repositories

These bots live in their own repos:

- 🎧 **CrazyMusic** — high-quality YouTube music bot (yt-dlp + ffmpeg) — [repo](https://github.com/CrazyAlex15/CrazyMusic)
- 📡 **NetMonitor** — scheduled internet speedtest reporter — [repo](https://github.com/CrazyAlex15/NetMonitor)
- 🥧 **PiStats-Bot** — Raspberry Pi health monitor (temp / CPU / RAM) — [repo](https://github.com/CrazyAlex15/PiStats-Bot)

---

## 🛠️ Self-hosting (Python bots)

Each Python bot folder is standalone. From inside a bot's folder:

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file with the required secrets (see each bot's README), e.g.:

```ini
DISCORD_TOKEN=your_bot_token_here
```

Then run it:

```bash
python main.py
```

The **GTA RP Ticket Bot** is Node.js — run `npm install` then `node index.js`.

### Running 24/7 with PM2

```bash
pm2 start main.py --name my-bot --interpreter ./venv/bin/python3
pm2 save
```

---

## 🔒 Security

Secrets (`.env`, tokens, cookies) are git-ignored and must **never** be
committed. Each bot validates that its required environment variables are
present on startup and exits with a clear message if they are missing.

## 📁 Structure

```
FNO/                          Free Games & Offers bot (Python)
GTA RP Ticket Bot/            FiveM ticket bot (Node.js)
HiddenVC/                     Hidden voice channels bot (Python)
PaletoBot PriceCalculator/    Mechanic price calculator (Python)
Twitch Streaming/             Twitch live notifier (Python)
MyCV/                         Personal CV web page (HTML)
```

---

<sub>Built with ❤️ by <a href="https://github.com/CrazyAlex15">CrazyAlex</a></sub>
