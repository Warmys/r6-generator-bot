import time

import discord
from discord import app_commands
from discord.ext import commands

from utils import database as db
from utils import branding

DURATION_MAP = {
    "1 Day": 1,
    "3 Days": 3,
    "7 Days": 7,
    "30 Days": 30,
    "Lifetime": "lifetime",
}


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="addaccess", description="Grant premium access to a user")
    @app_commands.describe(user="User to grant access to", duration="Premium access duration")
    @app_commands.choices(duration=[
        app_commands.Choice(name="1 Day", value="1 Day"),
        app_commands.Choice(name="3 Days", value="3 Days"),
        app_commands.Choice(name="7 Days", value="7 Days"),
        app_commands.Choice(name="30 Days", value="30 Days"),
        app_commands.Choice(name="Lifetime", value="Lifetime"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def addaccess(self, interaction: discord.Interaction, user: discord.User, duration: app_commands.Choice[str]):
        selected = duration.value
        if selected == "Lifetime":
            expiry = "lifetime"
        else:
            days = DURATION_MAP[selected]
            expiry = int(time.time() + days * 86400)

        db.premium_set(user.id, expiry)

        exp_display = "Never" if expiry == "lifetime" else f"<t:{int(expiry)}:R>"
        embed = branding.make_embed(title="👑 Premium Access Granted", kind="premium")
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Duration", value=selected, inline=True)
        embed.add_field(name="Expires", value=exp_display, inline=True)
        embed.add_field(name="Granted By", value=interaction.user.mention, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="removeaccess", description="Remove premium access from a user")
    @app_commands.describe(user="User to remove premium from")
    @app_commands.checks.has_permissions(administrator=True)
    async def removeaccess(self, interaction: discord.Interaction, user: discord.User):
        removed = db.premium_remove(user.id)
        if removed:
            embed = branding.make_embed(
                title="✅ Premium Removed",
                description=f"{user.mention} has been removed from premium access.",
                kind="success",
            )
        else:
            embed = branding.make_embed(
                title="ℹ️ Not Found",
                description=f"{user.mention} was not in the premium list.",
                kind="primary",
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="listaccess", description="View all users with premium access")
    @app_commands.checks.has_permissions(administrator=True)
    async def listaccess(self, interaction: discord.Interaction):
        premium = db.premium_all()
        if not premium:
            embed = branding.make_embed(
                title="📋 Premium Access List",
                description="No users currently have premium access.",
                kind="primary",
            )
            return await interaction.response.send_message(embed=embed)

        lines = []
        for uid, expiry in premium.items():
            member = interaction.guild.get_member(int(uid)) if interaction.guild else None
            name = member.mention if member else f"User ID {uid}"
            if expiry == "lifetime":
                expires = "💎 Lifetime"
            else:
                try:
                    expires = f"<t:{int(float(expiry))}:R>"
                except (TypeError, ValueError):
                    expires = "⚠️ Invalid"
            lines.append(f"{name} — {expires}")

        embed = branding.make_embed(
            title="📋 Premium Access List",
            description="\n".join(lines),
            kind="premium",
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setcooldown", description="Set a custom cooldown time for a user")
    @app_commands.describe(user="User to modify", tier="Tier to modify", seconds="Cooldown in seconds")
    @app_commands.choices(tier=[
        app_commands.Choice(name="Free", value="free"),
        app_commands.Choice(name="Premium", value="premium"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def setcooldown(self, interaction: discord.Interaction, user: discord.User, tier: app_commands.Choice[str], seconds: int):
        db.set_custom_cooldown(user.id, tier.value, seconds)
        embed = branding.make_embed(
            title="⏱️ Custom Cooldown Set",
            description=f"User: {user.mention}\nTier: **{tier.value.capitalize()}**\n"
                        f"Cooldown: **{branding.format_duration(seconds)}**",
            kind="primary",
        )
        embed.set_footer(text="User-specific cooldowns override defaults.")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Admin(bot))
