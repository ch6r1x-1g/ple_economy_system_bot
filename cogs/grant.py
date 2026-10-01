from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from economy import EconomyStore
from permissions import administrator_only
from presentation import guild_id, send_card
from settings import MAX_POINTS


class Grant(commands.Cog):
    def __init__(self, store: EconomyStore) -> None:
        self.store = store

    @app_commands.command(name="지급", description="멤버에게 포인트를 지급합니다. (관리자)")
    @administrator_only()
    @app_commands.describe(member="지급할 멤버", amount="지급할 포인트")
    @app_commands.rename(member="대상", amount="포인트")
    async def grant(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: app_commands.Range[int, 1, MAX_POINTS],
    ) -> None:
        value = await asyncio.to_thread(
            self.store.adjust, guild_id(interaction), member.id, amount
        )
        await send_card(
            interaction,
            "포인트 지급 완료",
            f"{member.mention}님에게 **{amount:,} P**를 지급했습니다.\n잔액: **{value:,} P**",
            color=discord.Color.green(),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Grant(bot.store))
