# Warmy's Services — Discord Bot

A fully branded Discord account-generation bot with a runtime configuration
system. Change branding, colors, cooldowns, messages, feature toggles and stock
**from inside Discord** — no code edits required.

---

## Features

- **Account generation** (`/gen`) delivered privately by DM, never in public.
- **Inventory system** backed by SQLite: stock, used items, and full claim history.
- **Premium access** management with timed or lifetime grants.
- **Per-user & per-tier cooldowns** with admin overrides.
- **Runtime configuration** via `/config` — branding, footer, colors, status,
  cooldowns, messages, channels and feature toggles, all saved to SQLite.
- **Branded embeds everywhere** (red & black theme by default), instantly
  restyled when you change config.

---

## Slash Commands

### Public
| Command | Description |
|---|---|
| `/gen <tier>` | Generate a free or premium account (sent to your DMs) |
| `/stock amount` | Check current stock levels |
| `/help` | List commands |
| `/about` | About the service |

### Admin (requires **Administrator** permission)
| Command | Description |
|---|---|
| `/stock add <tier> <credentials>` | Add credentials (`email:pass`, space/comma separated) |
| `/stock remove <tier> <amount>` | Remove N entries from a tier |
| `/stock list <tier>` | Preview available credentials |
| `/addaccess <user> <duration>` | Grant premium (1/3/7/30 days or Lifetime) |
| `/removeaccess <user>` | Remove premium |
| `/listaccess` | List premium users |
| `/setcooldown <user> <tier> <seconds>` | Per-user cooldown override |
| `/config branding` | Bot name, item name, logo, thumbnail |
| `/config footer` | Footer text + Discord link |
| `/config colors` | Embed colors (hex) |
| `/config status` | Bot presence/status |
| `/config cooldown` | Default cooldown per tier |
| `/config messages` | Customize user-facing messages |
| `/config settings` | Feature toggles, channel IDs, item name |
| `/config view` | View all current configuration |

> Note: Discord doesn't allow both a bare `/stock` command and `/stock`
> subcommands. `/stock amount` reproduces the original stock overview.

---

## Local Setup

```bash
pip install -r requirements.txt
cp .env.example .env      # then fill in your token + channel IDs
python bot.py
```

On first launch the bot creates `data/warmy.db` and automatically imports any
existing `free.txt`, `premium.txt`, and legacy JSON data.

---

## Environment Variables (secrets only)

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | ✅ | Your bot token |
| `FREE_CHANNEL_ID` | optional | Seeds the free-gen channel on first run |
| `PREMIUM_CHANNEL_ID` | optional | Seeds the premium-gen channel on first run |
| `LOG_CHANNEL_ID` | optional | Seeds the claim-log channel on first run |

Everything else (branding, colors, cooldowns, messages, channels) lives in
SQLite and is editable via `/config`.

---

## Deploying to Railway

1. Push this repository to GitHub.
2. In [Railway](https://railway.app), create a **New Project → Deploy from GitHub repo**.
3. Under **Variables**, add `DISCORD_TOKEN` (and optionally the channel IDs).
4. Railway uses the included `Procfile` (`worker: python bot.py`) to start the bot.
5. **Add a Volume** mounted at `/app/data` so `warmy.db` (stock, config, claims)
   persists across restarts and redeploys.

### Keeping data safe
- Never commit `.env` — it's already in `.gitignore`.
- The SQLite database lives in `data/warmy.db`; back it up or use a Railway volume.

---

## Rebranding checklist

All branding is runtime-editable — no code changes needed:

```
/config branding name:Warmy's Services item:R6 Account
/config footer text:Warmy's Services discord_link:https://discord.gg/yourlink
/config colors primary:FF0000 success:2ECC71 error:E74C3C premium:F1C40F
/config status text:Warmy's Services | /gen type:Watching
```
