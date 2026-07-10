import discord
from discord import app_commands
from discord.ext import commands

from utils import database as db
from utils import branding

STATUS_TYPES = [
    app_commands.Choice(name="Playing", value="playing"),
    app_commands.Choice(name="Watching", value="watching"),
    app_commands.Choice(name="Listening", value="listening"),
    app_commands.Choice(name="Competing", value="competing"),
]

MESSAGE_KEYS = [
    app_commands.Choice(name="DM success", value="msg_dm_success"),
    app_commands.Choice(name="DM footer", value="msg_dm_footer"),
    app_commands.Choice(name="Cooldown", value="msg_cooldown"),
    app_commands.Choice(name="Out of stock", value="msg_no_stock"),
    app_commands.Choice(name="No premium", value="msg_no_premium"),
    app_commands.Choice(name="Wrong channel", value="msg_wrong_channel"),
    app_commands.Choice(name="DM failed", value="msg_dm_failed"),
    app_commands.Choice(name="Feature disabled", value="msg_feature_disabled"),
]

SETTINGS_KEYS = [
    app_commands.Choice(name="Free enabled (1/0)", value="free_enabled"),
    app_commands.Choice(name="Premium enabled (1/0)", value="premium_enabled"),
    app_commands.Choice(name="Free channel ID", value="free_channel_id"),
    app_commands.Choice(name="Premium channel ID", value="premium_channel_id"),
    app_commands.Choice(name="Log channel ID", value="log_channel_id"),
    app_commands.Choice(name="Premium role ID (0=off)", value="premium_role_id"),
    app_commands.Choice(name="Item name (e.g. R6 Account)", value="item_name"),
]


class Config(commands.Cog):
    """Admin-only runtime configuration, saved permanently to SQLite."""

    def __init__(self, bot):
        self.bot = bot

    config = app_commands.Group(
        name="config",
        description="Configure Warmy's Services (admin only)",
        default_permissions=discord.Permissions(administrator=True),
    )

    async def _saved(self, interaction, description):
        embed = branding.make_embed(title="✅ Settings Saved", description=description, kind="success")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @config.command(name="branding", description="Set the bot name, item name, logo and thumbnail")
    @app_commands.describe(
        name="Bot / brand name",
        item="What the bot hands out (e.g. R6 Account)",
        logo_url="Footer icon URL",
        thumbnail_url="Embed thumbnail URL",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def branding_cmd(self, interaction, name: str = None, item: str = None,
                           logo_url: str = None, thumbnail_url: str = None):
        changes = []
        if name is not None:
            db.config_set("bot_name", name)
            changes.append(f"**Name** → {name}")
        if item is not None:
            db.config_set("item_name", item)
            changes.append(f"**Item** → {item}")
        if logo_url is not None:
            db.config_set("logo_url", logo_url)
            changes.append("**Logo** updated")
        if thumbnail_url is not None:
            db.config_set("thumbnail_url", thumbnail_url)
            changes.append("**Thumbnail** updated")
        if not changes:
            changes.append("No fields provided.")
        await self._saved(interaction, "\n".join(changes))

    @config.command(name="footer", description="Set the footer text and Discord invite link")
    @app_commands.describe(text="Footer text", discord_link="Discord invite link")
    @app_commands.checks.has_permissions(administrator=True)
    async def footer_cmd(self, interaction, text: str = None, discord_link: str = None):
        changes = []
        if text is not None:
            db.config_set("footer_text", text)
            changes.append(f"**Footer** → {text}")
        if discord_link is not None:
            db.config_set("discord_link", discord_link)
            changes.append(f"**Discord** → {discord_link}")
        if not changes:
            changes.append("No fields provided.")
        await self._saved(interaction, "\n".join(changes))

    @config.command(name="colors", description="Set embed colors (hex, e.g. FF0000)")
    @app_commands.describe(primary="Primary/brand", success="Success", error="Error", premium="Premium")
    @app_commands.checks.has_permissions(administrator=True)
    async def colors_cmd(self, interaction, primary: str = None, success: str = None,
                         error: str = None, premium: str = None):
        mapping = {
            "color_primary": primary,
            "color_success": success,
            "color_error": error,
            "color_premium": premium,
        }
        changes = []
        for key, val in mapping.items():
            if val is not None:
                clean = val.replace("#", "").replace("0x", "").strip()
                try:
                    int(clean, 16)
                except ValueError:
                    embed = branding.make_embed(title="❌ Invalid Color",
                                                description=f"`{val}` is not a valid hex color.", kind="error")
                    return await interaction.response.send_message(embed=embed, ephemeral=True)
                db.config_set(key, clean)
                changes.append(f"**{key.replace('color_', '').capitalize()}** → #{clean.upper()}")
        if not changes:
            changes.append("No colors provided.")
        await self._saved(interaction, "\n".join(changes))

    @config.command(name="status", description="Set the bot's presence/status")
    @app_commands.describe(text="Status text", type="Activity type")
    @app_commands.choices(type=STATUS_TYPES)
    @app_commands.checks.has_permissions(administrator=True)
    async def status_cmd(self, interaction, text: str = None, type: app_commands.Choice[str] = None):
        changes = []
        if text is not None:
            db.config_set("status_text", text)
            changes.append(f"**Text** → {text}")
        if type is not None:
            db.config_set("status_type", type.value)
            changes.append(f"**Type** → {type.name}")
        if hasattr(self.bot, "apply_presence"):
            await self.bot.apply_presence()
        if not changes:
            changes.append("No fields provided.")
        await self._saved(interaction, "\n".join(changes))

    @config.command(name="cooldown", description="Set the default cooldown for a tier (seconds)")
    @app_commands.describe(tier="Tier", seconds="Cooldown in seconds")
    @app_commands.choices(tier=[
        app_commands.Choice(name="Free", value="free"),
        app_commands.Choice(name="Premium", value="premium"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def cooldown_cmd(self, interaction, tier: app_commands.Choice[str], seconds: int):
        db.config_set(f"cooldown_{tier.value}", seconds)
        await self._saved(
            interaction,
            f"**{tier.name}** default cooldown → {branding.format_duration(seconds)}",
        )

    @config.command(name="messages", description="Customize a user-facing message")
    @app_commands.describe(key="Which message to edit", value="New message text")
    @app_commands.choices(key=MESSAGE_KEYS)
    @app_commands.checks.has_permissions(administrator=True)
    async def messages_cmd(self, interaction, key: app_commands.Choice[str], value: str):
        db.config_set(key.value, value)
        await self._saved(interaction, f"**{key.name}** message updated.")

    @config.command(name="settings", description="Toggle features, channels and item name")
    @app_commands.describe(setting="Which setting", value="New value")
    @app_commands.choices(setting=SETTINGS_KEYS)
    @app_commands.checks.has_permissions(administrator=True)
    async def settings_cmd(self, interaction, setting: app_commands.Choice[str], value: str):
        db.config_set(setting.value, value)
        await self._saved(interaction, f"**{setting.name}** → `{value}`")

    @config.command(name="view", description="View all current configuration")
    @app_commands.checks.has_permissions(administrator=True)
    async def view_cmd(self, interaction):
        cfg = db.config_all()
        groups = {
            "🎨 Branding": ["bot_name", "footer_text", "discord_link", "item_name", "logo_url", "thumbnail_url"],
            "🌈 Colors": ["color_primary", "color_success", "color_error", "color_premium"],
            "📶 Status": ["status_text", "status_type"],
            "⏱️ Cooldowns": ["cooldown_free", "cooldown_premium"],
            "⚙️ Settings": ["free_enabled", "premium_enabled", "free_channel_id",
                            "premium_channel_id", "log_channel_id", "premium_role_id"],
        }
        embed = branding.make_embed(title="🛠️ Current Configuration", kind="primary")
        for section, keys in groups.items():
            lines = [f"`{k}` = {cfg.get(k, '') or '—'}" for k in keys]
            embed.add_field(name=section, value="\n".join(lines), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Config(bot))
