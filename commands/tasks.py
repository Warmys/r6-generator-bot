import logging

import discord
from discord.ext import commands, tasks

from utils import database as db
from utils import branding

log = logging.getLogger("warmy.tasks")


class PremiumExpiry(commands.Cog):
    """Every minute, revoke premium access (and the premium role) once it expires."""

    def __init__(self, bot):
        self.bot = bot
        self.check_expiry.start()

    def cog_unload(self):
        self.check_expiry.cancel()

    @tasks.loop(minutes=1)
    async def check_expiry(self):
        expired = db.premium_expired()
        if not expired:
            return

        role_id = db.config_int("premium_role_id", 0)
        log_channel_id = db.config_int("log_channel_id", 0)

        for uid in expired:
            db.premium_remove(uid)
            removed_from = None

            if role_id:
                for guild in self.bot.guilds:
                    role = guild.get_role(role_id)
                    if role is None:
                        continue
                    try:
                        member = await guild.fetch_member(int(uid))
                    except (discord.NotFound, discord.HTTPException):
                        continue
                    if role in member.roles:
                        try:
                            await member.remove_roles(role, reason="Premium expired")
                            removed_from = member
                        except discord.HTTPException:
                            pass

            log.info("Premium expired for user %s (role removed: %s)", uid, bool(removed_from))

            if log_channel_id:
                try:
                    channel = await self.bot.fetch_channel(log_channel_id)
                    target = removed_from.mention if removed_from else f"`{uid}`"
                    embed = branding.make_embed(
                        title="⌛ Premium Expired",
                        description=f"Premium access for {target} has expired and been revoked.",
                        kind="primary",
                    )
                    await channel.send(embed=embed)
                except discord.HTTPException:
                    pass

    @check_expiry.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(PremiumExpiry(bot))
