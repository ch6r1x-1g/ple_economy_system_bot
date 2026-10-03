from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from economy import EconomyStore
from presentation import guild_id, send_card
from shop_names import display_shop_name


class Bag(commands.Cog):
    def __init__(self, store: EconomyStore) -> None:
        self.store = store

    @app_commands.command(name="가방", description="내 월령 잔액과 보유 상품을 확인합니다.")
    @app_commands.guild_only()
    async def bag(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        server_id = guild_id(interaction)
        user_id = interaction.user.id
        balance = await asyncio.to_thread(self.store.balance, server_id, user_id)
        items = await asyncio.to_thread(self.store.inventory, server_id, user_id)

        if items:
            item_lines = [
                f"**{display_shop_name(name)}** · **{quantity:,}개**"
                for name, quantity in items
            ]
            inventory_text = "\n".join(item_lines)
        else:
            inventory_text = "보유한 상품이 없습니다."

        await send_card(
            interaction,
            "내 가방",
            f"월령 잔액: **{balance:,} 월령**\n\n"
            f"**보유 상품**\n{inventory_text}",
            color=discord.Color.gold(),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Bag(bot.store))
