from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from economy import EconomyStore, InsufficientFunds
from permissions import administrator_only
from presentation import guild_id, send_card
from settings import MAX_POINTS


class Deduct(commands.Cog):
    def __init__(self, store: EconomyStore) -> None:
        self.store = store

    @app_commands.command(name="차감", description="멤버의 월령을 차감합니다. (관리자)")
    @administrator_only()
    @app_commands.describe(member="차감할 멤버", amount="차감할 월령")
    @app_commands.rename(member="대상", amount="월령")
    async def deduct(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: app_commands.Range[int, 1, MAX_POINTS],
    ) -> None:
        try:
            value = await asyncio.to_thread(
                self.store.adjust, guild_id(interaction), member.id, -amount
            )
        except InsufficientFunds as error:
            await send_card(
                interaction,
                "차감할 수 없습니다",
                f"잔액보다 많이 차감할 수 없습니다. 현재 잔액: **{error.balance:,} 월령**",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        await send_card(
            interaction,
            "월령 차감 완료",
            f"{member.mention}님의 잔액에서 **{amount:,} 월령**을 차감했습니다.\n잔액: **{value:,} 월령**",
            color=discord.Color.orange(),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Deduct(bot.store))
