from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from economy import EconomyStore
from presentation import guild_id, send_card
from shop_names import display_shop_name


class Shop(commands.Cog):
    def __init__(self, store: EconomyStore) -> None:
        self.store = store

    @app_commands.command(name="상점", description="구매할 수 있는 상품을 확인합니다.")
    @app_commands.guild_only()
    async def shop(self, interaction: discord.Interaction) -> None:
        items = await asyncio.to_thread(self.store.list_shop_items, guild_id(interaction))
        if not items:
            await send_card(
                interaction,
                "상점이 비어 있습니다",
                "관리자는 `/상품등록`으로 상품을 추가할 수 있습니다.",
                color=discord.Color.gold(),
            )
            return

        lines = []
        for item in items:
            stock = "무제한" if item.stock is None else f"{item.stock:,}개"
            details = item.description or "설명 없음"
            role = f"\n구매 시 역할: <@&{item.role_id}>" if item.role_id is not None else ""
            lines.append(
                f"**{display_shop_name(item.name)}** · **{item.price:,} 월령** · "
                f"재고 {stock}{role}\n{details}"
            )
        await send_card(
            interaction,
            "포인트 상점",
            "\n\n".join(lines),
            color=discord.Color.gold(),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Shop(bot.store))
