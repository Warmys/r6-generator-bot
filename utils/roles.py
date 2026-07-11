"""Shared helpers for granting/revoking the configured premium Discord role.

Uses guild.fetch_member (HTTP) so it works without the privileged Members intent.
"""

import discord

from utils import database as db


async def grant(guild, user_id):
    role_id = db.config_int("premium_role_id", 0)
    if not role_id or guild is None:
        return None
    role = guild.get_role(role_id)
    if role is None:
        return "⚠️ Premium role not found in this server."
    try:
        member = await guild.fetch_member(int(user_id))
        await member.add_roles(role, reason="Premium access granted")
        return f"Added {role.mention}"
    except discord.Forbidden:
        return "⚠️ Missing permission to assign the premium role (need Manage Roles + higher role)."
    except discord.NotFound:
        return "⚠️ User is not in this server."
    except discord.HTTPException:
        return "⚠️ Could not assign the premium role."


async def revoke(guild, user_id):
    role_id = db.config_int("premium_role_id", 0)
    if not role_id or guild is None:
        return None
    role = guild.get_role(role_id)
    if role is None:
        return None
    try:
        member = await guild.fetch_member(int(user_id))
        if role in member.roles:
            await member.remove_roles(role, reason="Premium access removed")
            return f"Removed {role.mention}"
    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
        return "⚠️ Could not remove the premium role."
    return None
