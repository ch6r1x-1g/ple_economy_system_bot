from __future__ import annotations

import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from credentials import load_discord_token
from economy import EconomyStore
from presentation import send_card
from settings import Settings, load_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("points-bot")

VOICE_REWARDS_ENABLED = False

EXTENSIONS = (
    "cogs.balance",
    "cogs.daily",
    "cogs.pay",
    "cogs.shared_account",
    "cogs.grant",
    "cogs.deduct",
    "cogs.setbalance",
    "cogs.shop",
    "cogs.buy",
    "cogs.inventory",
    "cogs.sell",
    "cogs.product_add",
    "cogs.product_remove",
    "cogs.product_edit",
)


class PointsBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.voice_states = VOICE_REWARDS_ENABLED
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
        )
        self.settings = settings
        self.store = EconomyStore(
            settings.database_path, settings.database_url, settings.guild_ids
        )

    async def setup_hook(self) -> None:
        await asyncio.to_thread(
            self.store.initialize,
            voice_rewards_enabled=VOICE_REWARDS_ENABLED,
        )
        extensions = EXTENSIONS
        if VOICE_REWARDS_ENABLED:
            extensions += ("cogs.voice_rewards",)
        for extension in extensions:
            await self.load_extension(extension)
        log.info("Loaded %d command extensions", len(extensions))

        if self.settings.sync_guild_id:
            guild = discord.Object(id=self.settings.sync_guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info(
                "Synced %d commands to guild %s",
                len(synced),
                self.settings.sync_guild_id,
            )
        else:
            synced = await self.tree.sync()
            log.info("Synced %d global commands", len(synced))


settings = load_settings()
bot = PointsBot(settings)


@bot.event
async def on_ready() -> None:
    await bot.change_presence(activity=discord.Game(name="티모의 정찰대 🍄"))
    log.info("Logged in as %s", bot.user)


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    if isinstance(error, app_commands.MissingPermissions):
        title = "권한이 없습니다"
        message = "이 명령어는 서버 관리자만 사용할 수 있습니다."
        color = discord.Color.red()
    elif isinstance(error, app_commands.NoPrivateMessage):
        title = "서버에서 사용할 수 있는 명령어입니다"
        message = "이 명령어는 서버 안에서만 사용할 수 있습니다."
        color = discord.Color.orange()
    else:
        log.error(
            "Application command failed",
            exc_info=(type(error), error, error.__traceback__),
        )
        title = "명령 처리 실패"
        message = "명령을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요."
        color = discord.Color.red()

    await send_card(interaction, title, message, color=color, ephemeral=True)


if __name__ == "__main__":
    bot.run(load_discord_token(), log_handler=None)
