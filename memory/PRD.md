# Warmy's Services — Discord Bot (PRD)

## Original
Rebrand "Floyy" account-gen bot to Warmy's Services; keep all commands; add SQLite
config, admin config commands, improved inventory, Railway hosting.

## Stack
Python 3.13 (Railway) / 3.11 (local) + discord.py 2.3.2 + audioop-lts (3.13) + SQLite.
Secrets in .env (DISCORD_TOKEN + channel IDs). No paid DB.

## Commands (12 top-level synced)
Public: /gen, /redeem, /stock amount, /help, /about
Admin: /stock add|remove|list, /stockclear, /addaccess, /removeaccess, /listaccess,
/setcooldown, /code generate|list|revoke|delete, /config branding|footer|colors|status|
cooldown|messages|settings|view

## Implemented
- 2026-07-10: Full rebrand, SQLite config+inventory, /config, /stock group, /help,/about,
  claim history, DM-only delivery, cooldowns, Railway prep (Procfile), branded embeds.
- 2026-07-10: Premium Discord role auto-grant on /addaccess + auto-revoke on expiry
  (background task every 1 min, uses fetch_member — no privileged intent). runtime.txt removed.
- 2026-07-10: audioop-lts added for Python 3.13 (fixes ModuleNotFoundError crash).
- 2026-07-11: /stockclear + emptied legacy free.txt/premium.txt (phantom stock). Cleaner
  public + DM embeds (title "{item} Generated!", 💌 sent to DMs; DM = single click-to-copy
  credential code block; removed "open a ticket" footer).
- 2026-07-11: Premium CODE system — codes table + /code generate (timed, incl 1h/6h/1d/3d/7d/30d/Lifetime),
  /redeem (starts countdown on redemption, grants access+role), /code list (available/active/
  expired/revoked + end timeline via <t:..:R>), /code revoke & /code delete (pull access+role).

## Verified
Live login + sync of 12 commands; DB init/migrate; stock clear; code create/redeem/revoke/
delete/list; premium expiry detection. (Slash flows validated via direct logic + live sync;
no web UI so automated browser test agent N/A.)

## Notes
- To fully clear phantom stock on an existing Railway volume, run /stockclear once after deploy.
- Premium role features require: set premium_role_id via /config settings, bot has Manage Roles,
  bot role above the premium role.

## Backlog
- P2: pagination for /code list & /stock list; /claims history command; low-stock alerts.

## 2026-07-11 — Rich account embeds + TXT upload
- utils/account_parser.py parses full credential line (email:pass + Username/Level/Items/
  Email/Phone/Banned/Renown/Credits/Platforms/Wanted*/Skin Link + optional inventory fields).
- DM now sends rich embed(s): "{item} Generated!", spoiler credentials ||login||, Account
  Details (username, platform names, level, currency renown/credits, total items, View Profile
  link when Skin Link present), avatar thumbnail if Avatar field present. Separate Account
  Inventory embed (Seasonals/Black Ices/Elite Skins/Attachment Skins/Ranked Charms) shown only
  if those fields are present in the line.
- /stock upload <tier> <file.txt>: reads every line, skips blanks, skips duplicates (by login),
  stores full parsed line. /stock add also dedupes now.
- /config premiumrole <@role>: pick premium role from menu (no ID needed); warns if bot can't manage it.
- LIMITATION: r6skins.locker is behind Cloudflare + no public API, so live inventory/avatar
  scraping from Skin Link is NOT reliably possible from a hosted bot. Inventory shows only when
  included in the credential line; View Profile link always shown so users open the locker themselves.
