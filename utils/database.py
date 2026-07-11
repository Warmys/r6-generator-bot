"""
SQLite-backed persistence for Warmy's Services.

Stores everything editable at runtime so the bot can be customized from
Discord instead of editing code:
  - config      : branding, colors, footer, messages, cooldowns, toggles, channels
  - stock       : available credentials/items per tier
  - claims      : claim history (who claimed what, when) = "used" items
  - premium     : premium access grants
  - cooldowns   : last claim timestamp per user/tier
  - custom_cd   : per-user cooldown overrides
"""

import os
import json
import time
import sqlite3
import threading
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "warmy.db")

_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Default configuration (seeded on first run, editable via /config in Discord)
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    # Branding
    "bot_name": "Warmy's Services",
    "footer_text": "Warmy's Services",
    "discord_link": "https://discord.gg/jcyMJF5QDz",
    "logo_url": "",
    "thumbnail_url": "",
    "item_name": "R6 Account",

    # Colors (hex, without # or 0x)
    "color_primary": "FF0000",
    "color_success": "2ECC71",
    "color_error": "E74C3C",
    "color_premium": "F1C40F",

    # Presence / status
    "status_text": "Warmy's Services | /gen",
    "status_type": "watching",  # playing | watching | listening | competing

    # Cooldowns (seconds)
    "cooldown_free": "600",
    "cooldown_premium": "600",

    # Feature toggles
    "free_enabled": "1",
    "premium_enabled": "1",

    # Discord role granted/revoked with premium access (0 = disabled)
    "premium_role_id": "0",

    # Prefix used when generating premium redeem codes
    "code_prefix": "WARMY",

    # Channels (seeded from env on first launch)
    "free_channel_id": "0",
    "premium_channel_id": "0",
    "log_channel_id": "0",

    # Customizable user-facing messages ({item}, {tier}, {remaining} placeholders)
    "msg_dm_success": "💌 Your {item} has been sent to your DMs!",
    "msg_dm_footer": "Enjoy your {item}! If it doesn't work, open a ticket.",
    "msg_cooldown": "You're on cooldown. Please wait **{remaining}** before generating again.",
    "msg_no_stock": "We're out of **{tier}** {item}s right now. Please check back later.",
    "msg_no_premium": "You don't have active premium access. Purchase premium to unlock this.",
    "msg_wrong_channel": "Please use this command in the correct channel.",
    "msg_dm_failed": "I couldn't send you a DM. Please enable **Direct Messages** from server members and try again.",
    "msg_feature_disabled": "This tier is currently **disabled**. Please check back later.",
}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables, seed defaults, and migrate legacy JSON/TXT data once."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with _lock, _conn() as conn:
        c = conn.cursor()
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS stock (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                tier       TEXT NOT NULL,
                credential TEXT NOT NULL,
                added_at   TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS claims (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT NOT NULL,
                username   TEXT,
                tier       TEXT NOT NULL,
                credential TEXT NOT NULL,
                claimed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS premium (
                user_id TEXT PRIMARY KEY,
                expiry  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id    TEXT NOT NULL,
                tier       TEXT NOT NULL,
                last_claim REAL NOT NULL,
                PRIMARY KEY (user_id, tier)
            );
            CREATE TABLE IF NOT EXISTS custom_cd (
                user_id TEXT NOT NULL,
                tier    TEXT NOT NULL,
                seconds INTEGER NOT NULL,
                PRIMARY KEY (user_id, tier)
            );
            CREATE TABLE IF NOT EXISTS codes (
                code             TEXT PRIMARY KEY,
                duration_seconds INTEGER NOT NULL,
                duration_label   TEXT,
                created_by       TEXT,
                created_by_name  TEXT,
                created_at       TEXT NOT NULL,
                status           TEXT NOT NULL DEFAULT 'available',
                redeemed_by      TEXT,
                redeemed_by_name TEXT,
                redeemed_at      TEXT,
                expires_at       REAL
            );
            CREATE INDEX IF NOT EXISTS idx_stock_tier ON stock (tier);
            """
        )
        # Seed default config (only missing keys)
        for k, v in DEFAULT_CONFIG.items():
            c.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", (k, v))

        # Seed channel IDs from environment on first launch
        for env_key, cfg_key in (
            ("FREE_CHANNEL_ID", "free_channel_id"),
            ("PREMIUM_CHANNEL_ID", "premium_channel_id"),
            ("LOG_CHANNEL_ID", "log_channel_id"),
        ):
            env_val = os.getenv(env_key)
            if env_val:
                cur = c.execute("SELECT value FROM config WHERE key=?", (cfg_key,)).fetchone()
                if cur is None or cur["value"] in ("", "0", None):
                    c.execute("UPDATE config SET value=? WHERE key=?", (env_val, cfg_key))
        conn.commit()

    _migrate_legacy()


def _migrate_legacy():
    """One-time import of the old JSON/TXT data into SQLite."""
    if config_get("_migrated") == "1":
        return

    # Stock: free.txt / premium.txt
    for tier in ("free", "premium"):
        path = os.path.join(DATA_DIR, f"{tier}.txt")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    creds = [ln.strip() for ln in f if ":" in ln]
                if creds:
                    stock_add_bulk(tier, creds)
            except Exception as e:
                print(f"[migrate] stock {tier}: {e}")

    # Premium users
    pfile = os.path.join(DATA_DIR, "premium_users.json")
    if os.path.exists(pfile):
        try:
            with open(pfile, "r") as f:
                data = json.load(f)
            for uid, expiry in data.items():
                premium_set(uid, expiry)
        except Exception as e:
            print(f"[migrate] premium: {e}")

    # Cooldowns
    cfile = os.path.join(DATA_DIR, "cooldowns.json")
    if os.path.exists(cfile):
        try:
            with open(cfile, "r") as f:
                data = json.load(f)
            with _lock, _conn() as conn:
                for uid, tiers in data.items():
                    for tier, ts in tiers.items():
                        conn.execute(
                            "INSERT OR REPLACE INTO cooldowns (user_id, tier, last_claim) VALUES (?,?,?)",
                            (str(uid), tier, float(ts)),
                        )
                conn.commit()
        except Exception as e:
            print(f"[migrate] cooldowns: {e}")

    # Custom cooldowns
    ccfile = os.path.join(DATA_DIR, "custom_cooldowns.json")
    if os.path.exists(ccfile):
        try:
            with open(ccfile, "r") as f:
                data = json.load(f)
            for uid, tiers in data.items():
                for tier, secs in tiers.items():
                    set_custom_cooldown(uid, tier, int(secs))
        except Exception as e:
            print(f"[migrate] custom cooldowns: {e}")

    config_set("_migrated", "1")
    print("[migrate] legacy data imported into SQLite.")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def config_get(key, default=None):
    with _lock, _conn() as conn:
        row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    if row is not None:
        return row["value"]
    if default is not None:
        return default
    return DEFAULT_CONFIG.get(key)


def config_set(key, value):
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO config (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )
        conn.commit()


def config_all():
    with _lock, _conn() as conn:
        rows = conn.execute("SELECT key, value FROM config").fetchall()
    return {r["key"]: r["value"] for r in rows}


def config_int(key, default=0):
    try:
        return int(config_get(key))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Stock / Inventory
# ---------------------------------------------------------------------------
def stock_add(tier, credential):
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO stock (tier, credential, added_at) VALUES (?, ?, ?)",
            (tier, credential.strip(), _now_iso()),
        )
        conn.commit()


def stock_add_bulk(tier, credentials):
    rows = [(tier, c.strip(), _now_iso()) for c in credentials if c and ":" in c]
    if not rows:
        return 0
    with _lock, _conn() as conn:
        conn.executemany(
            "INSERT INTO stock (tier, credential, added_at) VALUES (?, ?, ?)", rows
        )
        conn.commit()
    return len(rows)


def stock_count(tier):
    with _lock, _conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM stock WHERE tier=?", (tier,)
        ).fetchone()
    return row["n"] if row else 0


def stock_list(tier, limit=25):
    with _lock, _conn() as conn:
        rows = conn.execute(
            "SELECT credential FROM stock WHERE tier=? ORDER BY id LIMIT ?",
            (tier, limit),
        ).fetchall()
    return [r["credential"] for r in rows]


def stock_pop(tier):
    """Remove and return the oldest available credential for a tier, or None."""
    with _lock, _conn() as conn:
        row = conn.execute(
            "SELECT id, credential FROM stock WHERE tier=? ORDER BY id LIMIT 1",
            (tier,),
        ).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM stock WHERE id=?", (row["id"],))
        conn.commit()
    return row["credential"]


def stock_remove(tier, amount):
    """Remove up to `amount` credentials from a tier. Returns count removed."""
    with _lock, _conn() as conn:
        rows = conn.execute(
            "SELECT id FROM stock WHERE tier=? ORDER BY id LIMIT ?", (tier, amount)
        ).fetchall()
        ids = [r["id"] for r in rows]
        if ids:
            conn.executemany("DELETE FROM stock WHERE id=?", [(i,) for i in ids])
            conn.commit()
    return len(ids)


def stock_clear():
    """Delete ALL stock across every tier. Returns number removed."""
    with _lock, _conn() as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM stock").fetchone()["n"]
        conn.execute("DELETE FROM stock")
        conn.commit()
    return n


def _login_key(credential):
    """The unique login part (email:pass) used for duplicate detection."""
    return credential.split("|")[0].strip().lower()


def stock_existing_logins():
    """Set of login keys already present in stock or claim history."""
    logins = set()
    with _lock, _conn() as conn:
        for r in conn.execute("SELECT credential FROM stock").fetchall():
            logins.add(_login_key(r["credential"]))
        for r in conn.execute("SELECT credential FROM claims").fetchall():
            logins.add(_login_key(r["credential"]))
    return logins


# ---------------------------------------------------------------------------
# Claims (history / used items)
# ---------------------------------------------------------------------------
def record_claim(user_id, username, tier, credential):
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO claims (user_id, username, tier, credential, claimed_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (str(user_id), username, tier, credential, _now_iso()),
        )
        conn.commit()


def claim_count(tier=None):
    with _lock, _conn() as conn:
        if tier:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM claims WHERE tier=?", (tier,)
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) AS n FROM claims").fetchone()
    return row["n"] if row else 0


def recent_claims(limit=10):
    with _lock, _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM claims ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Premium access
# ---------------------------------------------------------------------------
def premium_set(user_id, expiry):
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO premium (user_id, expiry) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET expiry=excluded.expiry",
            (str(user_id), str(expiry)),
        )
        conn.commit()


def premium_remove(user_id):
    with _lock, _conn() as conn:
        cur = conn.execute("DELETE FROM premium WHERE user_id=?", (str(user_id),))
        conn.commit()
    return cur.rowcount > 0


def premium_all():
    with _lock, _conn() as conn:
        rows = conn.execute("SELECT user_id, expiry FROM premium").fetchall()
    return {r["user_id"]: r["expiry"] for r in rows}


def premium_expired():
    """Return user_ids whose (non-lifetime) premium has expired."""
    now = time.time()
    expired = []
    for uid, expiry in premium_all().items():
        if expiry == "lifetime":
            continue
        try:
            if float(expiry) <= now:
                expired.append(uid)
        except (TypeError, ValueError):
            continue
    return expired


def has_active_premium(user_id):
    with _lock, _conn() as conn:
        row = conn.execute(
            "SELECT expiry FROM premium WHERE user_id=?", (str(user_id),)
        ).fetchone()
    if row is None:
        return False
    expiry = row["expiry"]
    if expiry == "lifetime":
        return True
    try:
        return float(expiry) > time.time()
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Cooldowns
# ---------------------------------------------------------------------------
def get_cooldown_seconds(user_id, tier):
    with _lock, _conn() as conn:
        row = conn.execute(
            "SELECT seconds FROM custom_cd WHERE user_id=? AND tier=?",
            (str(user_id), tier),
        ).fetchone()
    if row is not None:
        return int(row["seconds"])
    return config_int(f"cooldown_{tier}", 600)


def cooldown_remaining(user_id, tier):
    """Seconds remaining, 0 if ready."""
    with _lock, _conn() as conn:
        row = conn.execute(
            "SELECT last_claim FROM cooldowns WHERE user_id=? AND tier=?",
            (str(user_id), tier),
        ).fetchone()
    last = row["last_claim"] if row else 0
    remaining = get_cooldown_seconds(user_id, tier) - (time.time() - last)
    return max(0, int(remaining))


def check_cooldown(user_id, tier):
    return cooldown_remaining(user_id, tier) <= 0


def update_cooldown(user_id, tier):
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO cooldowns (user_id, tier, last_claim) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, tier) DO UPDATE SET last_claim=excluded.last_claim",
            (str(user_id), tier, time.time()),
        )
        conn.commit()


def set_custom_cooldown(user_id, tier, seconds):
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO custom_cd (user_id, tier, seconds) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, tier) DO UPDATE SET seconds=excluded.seconds",
            (str(user_id), tier, int(seconds)),
        )
        conn.commit()



# ---------------------------------------------------------------------------
# Premium redeem codes
# ---------------------------------------------------------------------------
def code_create(code, duration_seconds, duration_label, created_by, created_by_name):
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO codes (code, duration_seconds, duration_label, created_by, "
            "created_by_name, created_at, status) VALUES (?, ?, ?, ?, ?, ?, 'available')",
            (code, int(duration_seconds), duration_label, str(created_by),
             created_by_name, _now_iso()),
        )
        conn.commit()


def code_get(code):
    with _lock, _conn() as conn:
        row = conn.execute("SELECT * FROM codes WHERE code=?", (code,)).fetchone()
    return dict(row) if row else None


def code_exists(code):
    with _lock, _conn() as conn:
        row = conn.execute("SELECT 1 FROM codes WHERE code=?", (code,)).fetchone()
    return row is not None


def code_redeem(code, user_id, user_name, expires_at):
    with _lock, _conn() as conn:
        conn.execute(
            "UPDATE codes SET status='redeemed', redeemed_by=?, redeemed_by_name=?, "
            "redeemed_at=?, expires_at=? WHERE code=?",
            (str(user_id), user_name, _now_iso(), expires_at, code),
        )
        conn.commit()


def code_revoke(code):
    with _lock, _conn() as conn:
        conn.execute("UPDATE codes SET status='revoked' WHERE code=?", (code,))
        conn.commit()


def code_delete(code):
    with _lock, _conn() as conn:
        cur = conn.execute("DELETE FROM codes WHERE code=?", (code,))
        conn.commit()
    return cur.rowcount > 0


def codes_all():
    with _lock, _conn() as conn:
        rows = conn.execute("SELECT * FROM codes ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]
