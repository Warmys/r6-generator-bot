# Warmy's Services — Discord Bot (PRD)

## Original Problem
Rebrand an existing "Floyy" Discord account-generation bot into **Warmy's Services**
without removing/breaking any existing slash commands. Add a SQLite-backed runtime
configuration system, admin `/config` commands, an improved credential/inventory
system, and Railway hosting prep.

## Tech Stack
- Python + discord.py 2.3.2
- SQLite (data/warmy.db) — no paid DB
- Secrets via .env (DISCORD_TOKEN, channel IDs)

## Architecture
- `bot.py` — entry point, presence, global error handler, loads all cogs in /commands
- `utils/database.py` — all persistence: config, stock, claims, premium, cooldowns
- `utils/branding.py` — `make_embed()` pulls live branding/colors/footer from SQLite
- `utils/{access,cooldowns,file_io}.py` — thin backward-compatible wrappers over DB
- `commands/{gen,stock,admin,config,info}.py` — cogs

## Existing commands (preserved)
- `/gen`, `/addaccess`, `/removeaccess`, `/listaccess`, `/setcooldown`
- Original `/stock` overview preserved as `/stock amount` (Discord API can't have a
  bare command + subcommands under the same name)

## New commands
- `/stock add|remove|list` (admin), `/stock amount` (public)
- `/config branding|footer|colors|status|cooldown|messages|settings|view` (admin)
- `/help`, `/about`

## Implemented (2026-07-10)
- Full rebrand to Warmy's Services; red/black theme via config; footer with Discord link
- SQLite config system (branding, colors, footer, status, cooldowns, toggles, channels, messages)
- SQLite inventory: stock + claim history (used items, who/when), DM-only delivery,
  cooldown protection, claim logging to log channel, credential restored on DM failure
- One-time migration of legacy free.txt/premium.txt/JSON into SQLite (576 free, 252 premium)
- Railway prep: Procfile, runtime.txt, .env.example, .gitignore, README with volume guidance
- Improved logging, branded error handling, graceful presence updates

## Verified
- Bot logs in + syncs 9 slash commands (live token)
- DB: init, migrate, config get/set, stock pop/add/remove, claims, cooldowns

## Notes / Backlog
- Server Members privileged intent disabled for reliable startup; `/listaccess` falls
  back to user IDs when a member isn't cached. Enable in portal + set intents.members=True for richer data.
- Slash commands not driveable by automated test agent (no web UI); verified via direct logic tests + live login/sync.

## Backlog (P1/P2)
- P1: `/config messages` preview, per-guild config (multi-server)
- P2: pagination for `/stock list`, claim history command, auto-restock alerts
