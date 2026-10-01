from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from economy import EconomyStore
from permissions import administrator_only
from presentation import guild_id, send_card
from shop_names import display_shop_name, normalize_shop_name


class ProductRemove(commands.Cog):
    def __init__(self, store: EconomyStore) -> None:
        self.store = store

    @app_commands.command(name="상품삭제", description="상점에서 상품을 제거합니다. (관리자)")
    @administrator_only()
    @app_commands.describe(name="삭제할 상품 이름")
    @app_commands.rename(name="상품")
    async def product_remove(self, interaction: discord.Interaction, name: str) -> None:
        name = normalize_shop_name(name)
        removed = await asyncio.to_thread(
            self.store.remove_shop_item, guild_id(interaction), name
        )
        if not removed:
            await send_card(
                interaction,
                "상품을 찾을 수 없습니다",
                "`/상점`에서 등록된 상품 이름을 확인해 주세요.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        await send_card(
            interaction,
            "상품 삭제 완료",
            f"**{display_shop_name(name)}** 상품을 상점에서 제거했습니다.\n이미 구매한 인벤토리는 유지됩니다.",
            color=discord.Color.orange(),
            ephemeral=True,
        )

    @product_remove.autocomplete("name")
    async def name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        items = await asyncio.to_thread(
            self.store.list_shop_items, guild_id(interaction)
        )
        query = normalize_shop_name(current).casefold()
        return [
            app_commands.Choice(name=item.name, value=item.name)
            for item in items
            if not query or query in item.name.casefold()
        ][:25]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ProductRemove(bot.store))
