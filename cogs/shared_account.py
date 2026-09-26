from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from economy import EconomyStore, InsufficientFunds, InsufficientSharedFunds
from presentation import guild_id, send_card
from settings import MAX_POINTS


class SharedAccount(commands.Cog):
    def __init__(self, store: EconomyStore) -> None:
        self.store = store

    @app_commands.command(
        name="공동계좌", description="마을 공동 계좌 잔액을 확인합니다."
    )
    @app_commands.guild_only()
    async def shared_account(self, interaction: discord.Interaction) -> None:
        balance = await asyncio.to_thread(
            self.store.shared_balance, guild_id(interaction)
        )
        await send_card(
            interaction,
            "마을 공동 계좌",
            f"공동 계좌 잔액은 **{balance:,} P**입니다.",
            color=discord.Color.gold(),
            ephemeral=True,
        )

    @app_commands.command(
        name="공동입금", description="내 포인트를 마을 공동 계좌에 넣습니다."
    )
    @app_commands.guild_only()
    @app_commands.describe(amount="입금할 포인트")
    @app_commands.rename(amount="포인트")
    async def deposit(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, MAX_POINTS],
    ) -> None:
        try:
            personal_balance, shared_balance = await asyncio.to_thread(
                self.store.deposit_shared,
                guild_id(interaction),
                interaction.user.id,
                amount,
            )
        except InsufficientFunds as error:
            await send_card(
                interaction,
                "입금할 수 없습니다",
                f"개인 잔액이 부족합니다. 현재 잔액: **{error.balance:,} P**",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return

        await send_card(
            interaction,
            "공동 계좌 입금 완료",
            f"**{amount:,} P**를 입금했습니다.\n"
            f"내 잔액: **{personal_balance:,} P** · 공동 계좌: **{shared_balance:,} P**",
            color=discord.Color.green(),
            ephemeral=True,
        )

    @app_commands.command(
        name="공동출금",
        description="마을 공동 계좌에서 내 잔액으로 포인트를 꺼냅니다.",
    )
    @app_commands.guild_only()
    @app_commands.describe(amount="출금할 포인트")
    @app_commands.rename(amount="포인트")
    async def withdraw(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, MAX_POINTS],
    ) -> None:
        try:
            personal_balance, shared_balance = await asyncio.to_thread(
                self.store.withdraw_shared,
                guild_id(interaction),
                interaction.user.id,
                amount,
            )
        except InsufficientSharedFunds as error:
            await send_card(
                interaction,
                "출금할 수 없습니다",
                f"공동 계좌 잔액이 부족합니다. 현재 잔액: **{error.balance:,} P**",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return

        await send_card(
            interaction,
            "공동 계좌 출금 완료",
            f"**{amount:,} P**를 출금했습니다.\n"
            f"내 잔액: **{personal_balance:,} P** · 공동 계좌: **{shared_balance:,} P**",
            color=discord.Color.green(),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SharedAccount(bot.store))
