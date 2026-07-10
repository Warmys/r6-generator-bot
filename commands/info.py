import discord
from discord import app_commands
from discord.ext import commands

from utils import database as db
from utils import branding


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show all available commands")
    async def help(self, interaction: discord.Interaction):
        name = db.config_get("bot_name", "Warmy's Services")
        embed = branding.make_embed(title=f"📖 {name} — Help", kind="primary")
        embed.add_field(
            name="🎁 Generation",
            value="`/gen` — Generate a free or premium account (delivered by DM)",
            inline=False,
        )
        embed.add_field(
            name="📦 Stock",
            value="`/stock amount` — Check current stock levels",
            inline=False,
        )
        embed.add_field(
            name="ℹ️ Info",
            value="`/help` — This menu\n`/about` — About the service",
            inline=False,
        )
        embed.add_field(
            name="🔧 Admin",
            value=(
                "`/stock add` · `/stock remove` · `/stock list`\n"
                "`/addaccess` · `/removeaccess` · `/listaccess` · `/setcooldown`\n"
                "`/config branding` · `/config footer` · `/config colors` · `/config status`\n"
                "`/config cooldown` · `/config messages` · `/config settings` · `/config view`"
            ),
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="about", description="About this service")
    async def about(self, interaction: discord.Interaction):
        name = db.config_get("bot_name", "Warmy's Services")
        link = db.config_get("discord_link", "")
        desc = f"**{name}** — your trusted account generation service."
        if link:
            desc += f"\n\n🔗 Join our Discord: {link}"
        embed = branding.make_embed(title=f"✨ About {name}", description=desc, kind="primary")
        embed.add_field(name="Free Stock", value=f"**{db.stock_count('free')}**", inline=True)
        embed.add_field(name="Premium Stock", value=f"**{db.stock_count('premium')}**", inline=True)
        embed.add_field(name="Total Claimed", value=f"**{db.claim_count()}**", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Info(bot))
