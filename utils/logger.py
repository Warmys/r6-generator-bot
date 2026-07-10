import logging
import discord

from utils import database as db
from utils import branding

log = logging.getLogger("warmy.logger")


async def log_generation(interaction: discord.Interaction, tier: str, account: str):
    """Post a claim log to the configured log channel (never public credentials)."""
    channel_id = db.config_int("log_channel_id", 0)
    if not channel_id:
        return
    try:
        channel = await interaction.client.fetch_channel(channel_id)
        user = interaction.user
        item = db.config_get("item_name", "account")

        embed = branding.make_embed(title=f"✅ {item} Claimed", kind="success")
        embed.add_field(name="👤 User", value=f"{user.mention} (`{user.id}`)", inline=False)
        embed.add_field(name="🏷️ Tier", value=f"`{tier.upper()}`", inline=True)
        embed.add_field(name="📦 Credential", value=f"```{account}```", inline=False)
        embed.timestamp = discord.utils.utcnow()

        await channel.send(embed=embed)
    except Exception as e:
        log.warning("Logging failed: %s", e)
