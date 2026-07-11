"""Parse rich account credential lines and build the DM embeds.

Expected line format (fields after the login are optional and order-independent):

email@example.com:password | Username: zako | Level: 359 | Items: 1714 |
Email: Yes | Phone: Yes | Banned: No | Renown: 27554 | Credits: 556 |
Platforms: XBL Linkable | Wanted Items: None | Wanted Ranks: Champions |
Skin Link: https://r6skins.locker/profile/xxxx

Optional inventory fields (include these in the line to show the Inventory embed):
| Seasonals: A, B | Black Ices: SASG-12 | Elite Skins: X | Attachment Skins: Gray, Brown |
| Ranked Charms: 3 | Avatar: https://...
"""

import re

from utils import branding

PLATFORM_MAP = {
    "XBL": "Xbox", "XBOX": "Xbox",
    "PSN": "PlayStation", "PS": "PlayStation", "PS4": "PlayStation", "PS5": "PlayStation",
    "PC": "PC", "STEAM": "Steam",
    "EPIC": "Epic",
    "UPLAY": "Ubisoft", "UBI": "Ubisoft", "UBISOFT": "Ubisoft",
}

# label shown in embed -> possible field keys in the line
INVENTORY_FIELDS = [
    ("Seasonals", ("seasonals", "seasonal skins", "seasonal")),
    ("Black Ices", ("black ices", "black ice", "blackices")),
    ("Elite Skins", ("elite skins", "elites", "elite")),
    ("Attachment Skins", ("attachment skins", "attachments", "attachment")),
]


def parse_account(line):
    line = (line or "").strip()
    parts = [p.strip() for p in line.split("|")]
    data = {"raw": line}

    login = parts[0].strip()
    data["login"] = login
    if ":" in login:
        email, password = login.split(":", 1)
    else:
        email, password = login, ""
    data["email"] = email.strip()
    data["password"] = password.strip()

    fields = {}
    for seg in parts[1:]:
        if ":" in seg:
            k, v = seg.split(":", 1)
            fields[k.strip().lower()] = v.strip()

    data["username"] = fields.get("username")
    data["level"] = fields.get("level")
    data["items"] = fields.get("items")
    data["email_verified"] = fields.get("email")
    data["phone_verified"] = fields.get("phone")
    data["banned"] = fields.get("banned")
    data["renown"] = fields.get("renown")
    data["credits"] = fields.get("credits")
    data["platforms"] = fields.get("platforms")
    data["wanted_items"] = fields.get("wanted items")
    data["wanted_ranks"] = fields.get("wanted ranks")
    data["skin_link"] = fields.get("skin link")
    data["avatar"] = fields.get("avatar")
    data["charms"] = fields.get("ranked charms") or fields.get("charms")

    inventory = {}
    for label, keys in INVENTORY_FIELDS:
        for k in keys:
            if fields.get(k):
                inventory[label] = fields[k]
                break
    data["inventory"] = inventory
    return data


def _fmt_num(value):
    if value is None:
        return None
    try:
        return f"{int(str(value).replace(',', '').strip()):,}"
    except (TypeError, ValueError):
        return value


def format_platforms(raw):
    if not raw:
        return None
    tokens = re.split(r"[ ,/]+", raw)
    names = []
    for t in tokens:
        name = PLATFORM_MAP.get(t.upper().strip())
        if name and name not in names:
            names.append(name)
    return " • ".join(names) if names else raw


def _count(value):
    return len([x for x in value.split(",") if x.strip()])


def _clip(text, limit=1024):
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_embeds(data, item):
    """Return (main_embed, inventory_embed_or_None)."""
    main = branding.make_embed(title=f"{item} Generated!", kind="success")
    main.description = _clip(branding.render("msg_dm_success"), 4096)
    main.add_field(name="Account Credentials", value=_clip(f"||{data['login']}||"), inline=False)

    details = []
    if data.get("username"):
        details.append(f"**Username** `{data['username']}`")
    plats = format_platforms(data.get("platforms"))
    if plats:
        details.append(f"**Linked Platforms** {plats}")
    if data.get("level"):
        details.append(f"**Level** `{data['level']}`")

    currency = []
    renown = _fmt_num(data.get("renown"))
    credits = _fmt_num(data.get("credits"))
    if renown is not None:
        currency.append(f"Renown `{renown}`")
    if credits is not None:
        currency.append(f"Credits `{credits}`")
    if currency:
        details.append("**Currency** " + " · ".join(currency))

    if data.get("items"):
        details.append(f"**Total Items** `{data['items']}` items")
    if data.get("skin_link"):
        details.append(f"**Profile Link** [View Profile]({data['skin_link']})")

    if details:
        main.add_field(name="Account Details", value=_clip("\n".join(details)), inline=False)

    if data.get("avatar"):
        main.set_thumbnail(url=data["avatar"])

    inv = data.get("inventory") or {}
    inv_embed = None
    if inv or data.get("charms"):
        inv_embed = branding.make_embed(title="🎒 Account Inventory", kind="success")
        for label, value in inv.items():
            inv_embed.add_field(name=f"{label} ({_count(value)})", value=_clip(value), inline=False)
        if data.get("charms"):
            inv_embed.add_field(name="🎗️ Ranked Charms", value=_clip(str(data["charms"])), inline=False)

    return main, inv_embed
