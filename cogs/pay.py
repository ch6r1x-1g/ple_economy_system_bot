from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from economy import EconomyStore, InsufficientFunds
from presentation import guild_id, send_card
from settings import MAX_POINTS


class Pay(commands.Cog):
    def __init__(self, store: EconomyStore) -> None:
        self.store = store

    @app_commands.command(name="송금", description="다른 멤버에게 포인트를 보냅니다.")
    @app_commands.guild_only()
    @app_commands.describe(member="포인트를 받을 멤버", amount="보낼 포인트")
    @app_commands.rename(member="받는_사람", amount="포인트")
    async def pay(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: app_commands.Range[int, 1, MAX_POINTS],
    ) -> None:
        if member.id == interaction.user.id:
            await send_card(
                interaction,
                "송금할 수 없습니다",
                "자기 자신에게는 보낼 수 없습니다.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        if member.bot:
            await send_card(
                interaction,
                "송금할 수 없습니다",
                "봇 계정에는 보낼 수 없습니다.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        try:
            sender_balance, recipient_balance = await asyncio.to_thread(
                self.store.transfer,
                guild_id(interaction),
                interaction.user.id,
                member.id,
                amount,
            )
        except InsufficientFunds as error:
            await send_card(
                interaction,
                "포인트가 부족합니다",
                f"현재 잔액: **{error.balance:,} P**",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        await send_card(
            interaction,
            "송금 완료",
            f"{member.mention}님에게 **{amount:,} P**를 보냈습니다. "
            f"내 잔액: **{sender_balance:,} P** · 상대 잔액: **{recipient_balance:,} P**",
            color=discord.Color.green(),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Pay(bot.store))
