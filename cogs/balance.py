from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from economy import EconomyStore
from presentation import guild_id, send_card


class Balance(commands.Cog):
    def __init__(self, store: EconomyStore) -> None:
        self.store = store

    @app_commands.command(name="잔액", description="내 월령 잔액을 확인합니다.")
    @app_commands.guild_only()
    async def balance(self, interaction: discord.Interaction) -> None:
        value = await asyncio.to_thread(
            self.store.balance, guild_id(interaction), interaction.user.id
        )
        await send_card(
            interaction,
            "월령 잔액",
            f"내 잔액은 **{value:,} 월령**입니다.",
            color=discord.Color.gold(),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Balance(bot.store))
