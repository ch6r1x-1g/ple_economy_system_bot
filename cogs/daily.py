from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from economy import EconomyStore
from presentation import guild_id, send_card


class Daily(commands.Cog):
    def __init__(self, store: EconomyStore, reward: int, timezone: ZoneInfo) -> None:
        self.store = store
        self.reward = reward
        self.timezone = timezone

    @app_commands.command(name="일일", description="하루 한 번 월령을 받습니다.")
    @app_commands.guild_only()
    async def daily(self, interaction: discord.Interaction) -> None:
        today = datetime.now(self.timezone).date().isoformat()
        claimed, value = await asyncio.to_thread(
            self.store.claim_daily,
            guild_id(interaction),
            interaction.user.id,
            today,
            self.reward,
        )
        if not claimed:
            await send_card(
                interaction,
                "오늘 보상은 이미 받았습니다",
                f"현재 잔액: **{value:,} 월령**",
                color=discord.Color.orange(),
                ephemeral=True,
            )
            return
        await send_card(
            interaction,
            "일일 보상 지급 완료",
            f"일일 보상 **{self.reward:,} 월령**를 받았습니다!\n현재 잔액: **{value:,} 월령**",
            color=discord.Color.green(),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Daily(bot.store, bot.settings.daily_reward, bot.settings.timezone))
