import time
import secrets
import string

import discord
from discord import app_commands
from discord.ext import commands

from utils import database as db
from utils import branding
from utils import roles

# Duration options for generated codes (label -> seconds; -1 = lifetime)
DURATIONS = {
    "1 Hour": 3600,
    "6 Hours": 21600,
    "1 Day": 86400,
    "3 Days": 259200,
    "7 Days": 604800,
    "30 Days": 2592000,
    "Lifetime": -1,
}

DURATION_CHOICES = [app_commands.Choice(name=k, value=k) for k in DURATIONS]


def _generate_code():
    prefix = db.config_get("code_prefix", "WARMY") or "WARMY"
    alphabet = string.ascii_uppercase + string.digits
    while True:
        body = "".join(secrets.choice(alphabet) for _ in range(4))
        body2 = "".join(secrets.choice(alphabet) for _ in range(4))
        code = f"{prefix.upper()}-{body}-{body2}"
        if not db.code_exists(code):
            return code


async def _log_event(bot, title, description, kind="primary"):
    channel_id = db.config_int("log_channel_id", 0)
    if not channel_id:
        return
    try:
        channel = await bot.fetch_channel(channel_id)
        await channel.send(embed=branding.make_embed(title=title, description=description, kind=kind))
    except discord.HTTPException:
        pass


class Premium(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------------------------------------------------------------- /redeem
    @app_commands.command(name="redeem", description="Redeem a premium access code")
    @app_commands.describe(code="The code you were given")
    async def redeem(self, interaction: discord.Interaction, code: str):
        code = code.strip().upper()
        row = db.code_get(code)

        if row is None:
            embed = branding.make_embed(title="❌ Invalid Code",
                                        description="That code doesn't exist.", kind="error")
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        if row["status"] == "revoked":
            embed = branding.make_embed(title="🚫 Code Revoked",
                                        description="That code has been revoked and can't be used.", kind="error")
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        if row["status"] == "redeemed":
            embed = branding.make_embed(title="⚠️ Already Used",
                                        description="That code has already been redeemed.", kind="error")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        dur = int(row["duration_seconds"])
        if dur == -1:
            expiry = "lifetime"
            expires_at = None
            ends = "**Never** (Lifetime)"
        else:
            expires_at = time.time() + dur
            expiry = int(expires_at)
            ends = f"<t:{int(expires_at)}:R> (<t:{int(expires_at)}:F>)"

        db.premium_set(interaction.user.id, expiry)
        db.code_redeem(code, interaction.user.id, str(interaction.user), expires_at)
        role_note = await roles.grant(interaction.guild, interaction.user.id)

        desc = f"✅ Premium access activated!\n**Ends:** {ends}"
        if role_note:
            desc += f"\n{role_note}"
        embed = branding.make_embed(title="🎉 Code Redeemed", description=desc, kind="premium")
        await interaction.response.send_message(embed=embed, ephemeral=True)

        await _log_event(
            self.bot, "🎟️ Code Redeemed",
            f"{interaction.user.mention} redeemed `{code}` ({row['duration_label']}).\nEnds: {ends}",
            kind="premium",
        )

    # --------------------------------------------------------------- /code ...
    code = app_commands.Group(
        name="code",
        description="Manage premium redeem codes (admin only)",
        default_permissions=discord.Permissions(administrator=True),
    )

    @code.command(name="generate", description="Generate a new premium redeem code")
    @app_commands.describe(duration="How long premium lasts after the code is redeemed")
    @app_commands.choices(duration=DURATION_CHOICES)
    @app_commands.checks.has_permissions(administrator=True)
    async def generate(self, interaction: discord.Interaction, duration: app_commands.Choice[str]):
        seconds = DURATIONS[duration.value]
        code = _generate_code()
        db.code_create(code, seconds, duration.value, interaction.user.id, str(interaction.user))

        embed = branding.make_embed(title="🎟️ Code Generated", kind="premium")
        embed.add_field(name="Code", value=f"```{code}```", inline=False)
        embed.add_field(name="Duration", value=duration.value, inline=True)
        embed.add_field(name="Redeem with", value="`/redeem`", inline=True)
        embed.set_footer(text="Countdown starts when the user redeems it.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

        await _log_event(
            self.bot, "🆕 Code Generated",
            f"{interaction.user.mention} generated `{code}` ({duration.value}).",
        )

    @code.command(name="list", description="View every code: available, active, expired, revoked")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_codes(self, interaction: discord.Interaction):
        codes = db.codes_all()
        if not codes:
            embed = branding.make_embed(title="📜 Premium Codes",
                                        description="No codes have been generated yet.", kind="primary")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        now = time.time()
        counts = {"available": 0, "active": 0, "expired": 0, "revoked": 0}
        lines = []
        for c in codes:
            status = c["status"]
            if status == "revoked":
                label = "🚫 Revoked"
                counts["revoked"] += 1
            elif status == "available":
                label = "🟢 Available"
                counts["available"] += 1
            else:  # redeemed
                exp = c["expires_at"]
                who = f"<@{c['redeemed_by']}>" if c["redeemed_by"] else "?"
                if exp is None:
                    label = f"💎 Active (Lifetime) — {who}"
                    counts["active"] += 1
                elif float(exp) <= now:
                    label = f"⌛ Expired — {who}"
                    counts["expired"] += 1
                else:
                    label = f"🔴 Active — {who} · ends <t:{int(float(exp))}:R>"
                    counts["active"] += 1
            lines.append(f"`{c['code']}` · {c['duration_label']} · {label}")

        summary = (f"🟢 Available: **{counts['available']}** · "
                   f"🔴 Active: **{counts['active']}** · "
                   f"⌛ Expired: **{counts['expired']}** · "
                   f"🚫 Revoked: **{counts['revoked']}**")

        # Keep within Discord's embed limits
        shown = lines[:40]
        body = summary + "\n\n" + "\n".join(shown)
        if len(lines) > len(shown):
            body += f"\n\n_Showing {len(shown)} of {len(lines)} codes._"

        embed = branding.make_embed(title="📜 Premium Codes", description=body, kind="primary")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @code.command(name="revoke", description="Ban/revoke a code and pull access from whoever redeemed it")
    @app_commands.describe(code="The code to revoke")
    @app_commands.checks.has_permissions(administrator=True)
    async def revoke_code(self, interaction: discord.Interaction, code: str):
        code = code.strip().upper()
        row = db.code_get(code)
        if row is None:
            embed = branding.make_embed(title="❌ Not Found",
                                        description="That code doesn't exist.", kind="error")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        note = ""
        if row["status"] == "redeemed" and row["redeemed_by"]:
            db.premium_remove(row["redeemed_by"])
            role_note = await roles.revoke(interaction.guild, row["redeemed_by"])
            note = f"\nPulled access from <@{row['redeemed_by']}>."
            if role_note:
                note += f" {role_note}"

        db.code_revoke(code)
        embed = branding.make_embed(
            title="🚫 Code Revoked",
            description=f"`{code}` has been revoked and can no longer be used.{note}",
            kind="success",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await _log_event(self.bot, "🚫 Code Revoked",
                         f"{interaction.user.mention} revoked `{code}`.{note}")

    @code.command(name="delete", description="Permanently delete a code record (also pulls active access)")
    @app_commands.describe(code="The code to delete")
    @app_commands.checks.has_permissions(administrator=True)
    async def delete_code(self, interaction: discord.Interaction, code: str):
        code = code.strip().upper()
        row = db.code_get(code)
        if row is None:
            embed = branding.make_embed(title="❌ Not Found",
                                        description="That code doesn't exist.", kind="error")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        note = ""
        if row["status"] == "redeemed" and row["redeemed_by"]:
            db.premium_remove(row["redeemed_by"])
            role_note = await roles.revoke(interaction.guild, row["redeemed_by"])
            note = f"\nPulled access from <@{row['redeemed_by']}>."
            if role_note:
                note += f" {role_note}"

        db.code_delete(code)
        embed = branding.make_embed(
            title="🗑️ Code Deleted",
            description=f"`{code}` has been permanently deleted.{note}",
            kind="success",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await _log_event(self.bot, "🗑️ Code Deleted",
                         f"{interaction.user.mention} deleted `{code}`.{note}")


async def setup(bot):
    await bot.add_cog(Premium(bot))
