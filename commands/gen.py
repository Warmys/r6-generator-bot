import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils import database as db
from utils import branding
from utils import account_parser

log = logging.getLogger("warmy.gen")


class Gen(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="gen", description="Generate a free or premium account")
    @app_commands.describe(tier="Choose either free or premium")
    @app_commands.choices(tier=[
        app_commands.Choice(name="Free", value="free"),
        app_commands.Choice(name="Premium", value="premium"),
    ])
    async def gen(self, interaction: discord.Interaction, tier: app_commands.Choice[str]):
        tier = tier.value.lower()
        user_id = str(interaction.user.id)
        channel_id = interaction.channel.id
        item = db.config_get("item_name", "account")

        # Feature toggle
        if db.config_get(f"{tier}_enabled", "1") != "1":
            embed = branding.make_embed(
                title="🚫 Unavailable",
                description=branding.render("msg_feature_disabled"),
                kind="error",
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Channel restriction
        allowed_channel = db.config_int(f"{tier}_channel_id", 0)
        if allowed_channel and channel_id != allowed_channel:
            embed = branding.make_embed(
                title="❌ Wrong Channel",
                description=f"{branding.render('msg_wrong_channel')}\nUse <#{allowed_channel}>.",
                kind="error",
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Cooldown
        remaining = db.cooldown_remaining(user_id, tier)
        if remaining > 0:
            embed = branding.make_embed(
                title="⏳ On Cooldown",
                description=branding.render("msg_cooldown", remaining=branding.format_duration(remaining)),
                kind="error",
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Premium gate
        if tier == "premium" and not db.has_active_premium(user_id):
            embed = branding.make_embed(
                title="🔒 Premium Required",
                description=branding.render("msg_no_premium"),
                kind="premium",
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Stock
        account = db.stock_pop(tier)
        if not account:
            embed = branding.make_embed(
                title="📭 Out of Stock",
                description=branding.render("msg_no_stock", tier=tier),
                kind="error",
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Acknowledge immediately so the interaction can't expire while we DM
        await interaction.response.defer()

        # Parse the rich credential line and build the DM embeds
        account = account.strip()
        data = account_parser.parse_account(account)
        main_embed, inv_embed = account_parser.build_embeds(data, item)
        embeds = [main_embed] + ([inv_embed] if inv_embed else [])

        try:
            await interaction.user.send(embeds=embeds)
        except discord.Forbidden:
            # Return the credential to the pool so it isn't lost
            db.stock_add(tier, account)
            embed = branding.make_embed(
                title="📪 DM Failed",
                description=branding.render("msg_dm_failed"),
                kind="error",
            )
            return await interaction.edit_original_response(embed=embed)
        except discord.HTTPException as e:
            db.stock_add(tier, account)
            log.warning("DM send failed: %s", e)
            embed = branding.make_embed(
                title="⚠️ Could Not Send",
                description="There was a problem sending your account. Please try again.",
                kind="error",
            )
            return await interaction.edit_original_response(embed=embed)

        # Success bookkeeping
        db.update_cooldown(user_id, tier)
        db.record_claim(user_id, str(interaction.user), tier, account)

        confirm = branding.make_embed(
            title=f"{item} Generated!",
            description=branding.render("msg_dm_success"),
            kind="success",
        )
        await interaction.edit_original_response(embed=confirm)
        await self._log(interaction, tier, account)

    async def _log(self, interaction, tier, account):
        from utils.logger import log_generation
        await log_generation(interaction, tier, account)


async def setup(bot):
    await bot.add_cog(Gen(bot))
