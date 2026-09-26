from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from economy import EconomyStore
from presentation import guild_id, send_card
from shop_names import display_shop_name


class Inventory(commands.Cog):
    def __init__(self, store: EconomyStore) -> None:
        self.store = store

    @app_commands.command(name="인벤토리", description="내가 구매한 상품을 확인합니다.")
    @app_commands.guild_only()
    async def inventory(self, interaction: discord.Interaction) -> None:
        items = await asyncio.to_thread(
            self.store.inventory, guild_id(interaction), interaction.user.id
        )
        if not items:
            await send_card(
                interaction,
                "인벤토리가 비어 있습니다",
                "`/상점`에서 상품을 구매해 보세요.",
                color=discord.Color.blurple(),
                ephemeral=True,
            )
            return

        lines = [
            f"**{display_shop_name(name)}** · **{quantity:,}개**"
            for name, quantity in items
        ]
        await send_card(
            interaction,
            "내 인벤토리",
            "\n".join(lines),
            color=discord.Color.blurple(),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Inventory(bot.store))
