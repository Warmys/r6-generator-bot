"""
Branding helpers for Warmy's Services.

Every embed in the bot is built through `make_embed()` so that the bot name,
colors, footer, Discord link, logo and thumbnail are always pulled live from
the SQLite config. Change them with /config and every response updates.
"""

import discord
from utils import database as db

_COLOR_MAP = {
    "primary": ("color_primary", "FF0000"),
    "success": ("color_success", "2ECC71"),
    "error": ("color_error", "E74C3C"),
    "premium": ("color_premium", "F1C40F"),
}


def _hex_to_color(value, fallback):
    try:
        cleaned = str(value).replace("#", "").replace("0x", "").strip()
        return discord.Color(int(cleaned, 16))
    except (TypeError, ValueError):
        return discord.Color(int(fallback, 16))


def color(kind="primary"):
    key, fallback = _COLOR_MAP.get(kind, _COLOR_MAP["primary"])
    return _hex_to_color(db.config_get(key), fallback)


def get(key, default=""):
    val = db.config_get(key, default)
    return val if val is not None else default


def render(template_key, **kwargs):
    """Fetch a message template from config and fill placeholders."""
    template = db.config_get(template_key, "")
    defaults = {
        "item": db.config_get("item_name", "account"),
    }
    defaults.update(kwargs)
    try:
        return (template or "").format(**defaults)
    except (KeyError, IndexError):
        return template or ""


def footer_text():
    base = get("footer_text", "Warmy's Services")
    link = get("discord_link", "")
    return f"{base} • Discord: {link}" if link else base


def format_duration(seconds):
    """Human-friendly duration, e.g. 90 -> '1m 30s'."""
    seconds = int(seconds)
    if seconds <= 0:
        return "0s"
    parts = []
    for label, size in (("d", 86400), ("h", 3600), ("m", 60), ("s", 1)):
        if seconds >= size:
            qty, seconds = divmod(seconds, size)
            parts.append(f"{qty}{label}")
    return " ".join(parts)


def make_embed(title=None, description=None, kind="primary", thumbnail=True, footer=True):
    embed = discord.Embed(color=color(kind))
    if title:
        embed.title = title
    if description:
        embed.description = description

    if footer:
        logo = get("logo_url", "")
        if logo:
            embed.set_footer(text=footer_text(), icon_url=logo)
        else:
            embed.set_footer(text=footer_text())

    if thumbnail:
        thumb = get("thumbnail_url", "")
        if thumb:
            embed.set_thumbnail(url=thumb)

    return embed
