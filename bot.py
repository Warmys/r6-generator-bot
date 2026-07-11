import os
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

from utils import database as db

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("warmy")

# Uses non-privileged default intents so the bot starts reliably without
# requiring the "Server Members Intent" toggle in the Developer Portal.
# Enable members intent below (and in the portal) if you need richer member data.
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


_ACTIVITY_TYPES = {
    "playing": discord.ActivityType.playing,
    "watching": discord.ActivityType.watching,
    "listening": discord.ActivityType.listening,
    "competing": discord.ActivityType.competing,
}


async def apply_presence():
    """Set the bot presence from the configurable status settings."""
    status_text = db.config_get("status_text", "Warmy's Services | /gen")
    status_type = (db.config_get("status_type", "watching") or "watching").lower()
    activity = discord.Activity(
        type=_ACTIVITY_TYPES.get(status_type, discord.ActivityType.watching),
        name=status_text,
    )
    await bot.change_presence(activity=activity, status=discord.Status.online)


# Expose so /config status can refresh presence live
bot.apply_presence = apply_presence


@bot.event
async def setup_hook():
    db.init_db()
    for filename in os.listdir("./commands"):
        if filename.endswith(".py") and not filename.startswith("_"):
            try:
                await bot.load_extension(f"commands.{filename[:-3]}")
                log.info("Loaded extension: %s", filename)
            except Exception as e:
                log.exception("Failed to load %s: %s", filename, e)


@bot.event
async def on_ready():
    log.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)
    await apply_presence()
    try:
        synced = await bot.tree.sync()
        log.info("Synced %d slash commands.", len(synced))
    except Exception as e:
        log.exception("Command sync failed: %s", e)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    """Friendly, branded error handling for every slash command."""
    from utils import branding

    if isinstance(error, discord.app_commands.MissingPermissions):
        message = "You don't have permission to use this command."
    elif isinstance(error, discord.app_commands.CommandOnCooldown):
        message = f"Please slow down. Try again in {error.retry_after:.0f}s."
    else:
        # Surface the real underlying error so it can be diagnosed quickly.
        original = getattr(error, "original", error)
        detail = f"{type(original).__name__}: {original}"
        log.exception("Command error: %s", error)
        message = ("Something went wrong while running that command.\n"
                   f"```\n{detail[:500]}\n```")

    embed = branding.make_embed(title="⚠️ Error", description=message, kind="error")
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except discord.HTTPException:
        pass


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set. Copy .env.example to .env and add your token.")
    bot.run(TOKEN)
