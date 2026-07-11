import re

import discord
from discord import app_commands
from discord.ext import commands

from utils import database as db
from utils import branding

TIER_CHOICES = [
    app_commands.Choice(name="Free", value="free"),
    app_commands.Choice(name="Premium", value="premium"),
]


def _parse_credentials(raw: str):
    """Accept multiple accounts. Rich lines (with '|') are kept whole; simple
    email:pass tokens can be space/comma/semicolon separated."""
    results = []
    for line in raw.replace(";", "\n").splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            if ":" in line.split("|")[0]:
                results.append(line)
        else:
            for tok in re.split(r"[\s,]+", line):
                if ":" in tok:
                    results.append(tok)
    return results


class Stock(commands.Cog):
    """Inventory management. `/stock amount` is public; add/remove/list are admin-only."""

    def __init__(self, bot):
        self.bot = bot

    stock = app_commands.Group(name="stock", description="View and manage account stock")

    @stock.command(name="amount", description="Check current account stock")
    async def amount(self, interaction: discord.Interaction):
        free_count = db.stock_count("free")
        premium_count = db.stock_count("premium")
        item = db.config_get("item_name", "account")

        embed = branding.make_embed(title=f"📦 {item} Stock", kind="primary")
        embed.add_field(name="🆓 Free", value=f"**{free_count}**", inline=True)
        embed.add_field(name="💎 Premium", value=f"**{premium_count}**", inline=True)
        embed.add_field(name="📊 Total Claimed", value=f"**{db.claim_count()}**", inline=True)
        await interaction.response.send_message(embed=embed)

    @stock.command(name="add", description="Add credentials to stock (email:pass, space/comma separated)")
    @app_commands.describe(tier="Which tier to add to", credentials="One or more email:password entries")
    @app_commands.choices(tier=TIER_CHOICES)
    @app_commands.checks.has_permissions(administrator=True)
    async def add(self, interaction: discord.Interaction, tier: app_commands.Choice[str], credentials: str):
        creds = _parse_credentials(credentials)
        if not creds:
            embed = branding.make_embed(
                title="❌ Invalid Input",
                description="No valid `email:password` entries found.",
                kind="error",
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        existing = db.stock_existing_logins()
        seen, to_add, dupes = set(), [], 0
        for c in creds:
            key = c.split("|")[0].strip().lower()
            if key in existing or key in seen:
                dupes += 1
                continue
            seen.add(key)
            to_add.append(c)

        added = db.stock_add_bulk(tier.value, to_add) if to_add else 0
        desc = (f"Added **{added}** · Skipped **{dupes}** duplicate(s).\n"
                f"New total: **{db.stock_count(tier.value)}**")
        embed = branding.make_embed(title="✅ Stock Added", description=desc, kind="success")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @stock.command(name="upload", description="Upload a .txt file of accounts (one per line)")
    @app_commands.describe(tier="Which tier to add to", file="A .txt file with one account per line")
    @app_commands.choices(tier=TIER_CHOICES)
    @app_commands.checks.has_permissions(administrator=True)
    async def upload(self, interaction: discord.Interaction, tier: app_commands.Choice[str], file: discord.Attachment):
        if not file.filename.lower().endswith(".txt"):
            embed = branding.make_embed(title="❌ Wrong File Type",
                                        description="Please upload a `.txt` file.", kind="error")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        try:
            raw = (await file.read()).decode("utf-8", errors="ignore")
        except Exception:
            embed = branding.make_embed(title="❌ Read Failed",
                                        description="Could not read that file.", kind="error")
            return await interaction.followup.send(embed=embed, ephemeral=True)

        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        existing = db.stock_existing_logins()
        seen, to_add, dupes, invalid = set(), [], 0, 0
        for ln in lines:
            login = ln.split("|")[0].strip()
            if ":" not in login:
                invalid += 1
                continue
            key = login.lower()
            if key in existing or key in seen:
                dupes += 1
                continue
            seen.add(key)
            to_add.append(ln)

        added = db.stock_add_bulk(tier.value, to_add) if to_add else 0
        embed = branding.make_embed(title="📥 Upload Complete", kind="success")
        embed.add_field(name="✅ Added", value=f"**{added}**", inline=True)
        embed.add_field(name="♻️ Duplicates skipped", value=f"**{dupes}**", inline=True)
        embed.add_field(name="⚠️ Invalid skipped", value=f"**{invalid}**", inline=True)
        embed.add_field(name=f"📦 {tier.value.capitalize()} total", value=f"**{db.stock_count(tier.value)}**", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @stock.command(name="remove", description="Remove a number of entries from a tier's stock")
    @app_commands.describe(tier="Which tier to remove from", amount="How many to remove")
    @app_commands.choices(tier=TIER_CHOICES)
    @app_commands.checks.has_permissions(administrator=True)
    async def remove(self, interaction: discord.Interaction, tier: app_commands.Choice[str], amount: int):
        if amount < 1:
            embed = branding.make_embed(title="❌ Invalid Amount", description="Amount must be at least 1.", kind="error")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        removed = db.stock_remove(tier.value, amount)
        embed = branding.make_embed(
            title="🗑️ Stock Removed",
            description=f"Removed **{removed}** entr{'y' if removed == 1 else 'ies'} from **{tier.value.capitalize()}**.\n"
                        f"Remaining: **{db.stock_count(tier.value)}**",
            kind="success",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @stock.command(name="list", description="Preview available credentials for a tier (admin only)")
    @app_commands.describe(tier="Which tier to preview")
    @app_commands.choices(tier=TIER_CHOICES)
    @app_commands.checks.has_permissions(administrator=True)
    async def list_stock(self, interaction: discord.Interaction, tier: app_commands.Choice[str]):
        items = db.stock_list(tier.value, limit=25)
        total = db.stock_count(tier.value)
        if not items:
            body = "_No credentials in stock._"
        else:
            body = "```\n" + "\n".join(items) + "\n```"
            if total > len(items):
                body += f"\n_Showing {len(items)} of {total}._"
        embed = branding.make_embed(
            title=f"📋 {tier.value.capitalize()} Stock ({total})",
            description=body,
            kind="primary",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Stock(bot))
    await bot.add_cog(StockClear(bot))


class StockClear(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="stockclear", description="Clear ALL stock from every tier (admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def stockclear(self, interaction: discord.Interaction):
        removed = db.stock_clear()
        embed = branding.make_embed(
            title="🧹 Stock Cleared",
            description=f"Removed **{removed}** entr{'y' if removed == 1 else 'ies'} from all tiers.\n"
                        f"Free: **{db.stock_count('free')}** · Premium: **{db.stock_count('premium')}**",
            kind="success",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
