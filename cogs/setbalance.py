from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from economy import EconomyStore
from permissions import administrator_only
from presentation import guild_id, send_card
from settings import MAX_POINTS


class SetBalance(commands.Cog):
    def __init__(self, store: EconomyStore) -> None:
        self.store = store

    @app_commands.command(
        name="잔액설정", description="멤버의 월령 잔액을 설정합니다. (관리자)"
    )
    @administrator_only()
    @app_commands.describe(member="잔액을 설정할 멤버", amount="설정할 최종 잔액")
    @app_commands.rename(member="대상", amount="잔액")
    async def setbalance(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: app_commands.Range[int, 0, MAX_POINTS],
    ) -> None:
        await asyncio.to_thread(
            self.store.set_balance, guild_id(interaction), member.id, amount
        )
        await send_card(
            interaction,
            "잔액 설정 완료",
            f"{member.mention}님의 잔액을 **{amount:,} 월령**으로 설정했습니다.",
            color=discord.Color.green(),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SetBalance(bot.store))
