from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from economy import EconomyStore, InsufficientInventory, ItemNotInInventory
from presentation import guild_id, send_card
from shop_names import display_shop_name, normalize_shop_name


class Sell(commands.Cog):
    def __init__(self, store: EconomyStore) -> None:
        self.store = store

    @app_commands.command(name="판매", description="구매한 상품을 상점에 판매합니다.")
    @app_commands.guild_only()
    @app_commands.describe(item_name="인벤토리에 있는 상품 이름", quantity="판매 수량")
    @app_commands.rename(item_name="상품", quantity="수량")
    async def sell(
        self,
        interaction: discord.Interaction,
        item_name: str,
        quantity: app_commands.Range[int, 1, 100] = 1,
    ) -> None:
        requested_name = normalize_shop_name(item_name)
        try:
            (
                name,
                principal,
                refund,
                balance,
                remaining_quantity,
                remaining_stock,
                role_id,
            ) = await asyncio.to_thread(
                self.store.sell,
                guild_id(interaction),
                interaction.user.id,
                requested_name,
                quantity,
            )
        except ItemNotInInventory:
            await send_card(
                interaction,
                "인벤토리에 상품이 없습니다",
                "`/인벤토리`에서 판매할 상품 이름을 확인해 주세요.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        except InsufficientInventory as error:
            await send_card(
                interaction,
                "보유 수량이 부족합니다",
                f"현재 보유 수량: **{error.available:,}개**",
                color=discord.Color.orange(),
                ephemeral=True,
            )
            return

        role_message = ""
        if role_id is not None:
            role_to_remove = interaction.guild.get_role(role_id)
            if role_to_remove is None:
                role_message = (
                    "\n연결된 역할을 찾을 수 없어 역할을 회수하지 못했습니다."
                )
            elif (
                not role_to_remove.is_assignable()
                or not interaction.app_permissions.manage_roles
            ):
                role_message = (
                    "\n역할 회수에 실패했습니다. 봇의 역할 순서를 확인해 주세요."
                )
            else:
                try:
                    await interaction.user.remove_roles(
                        role_to_remove, reason=f"상점 상품 판매: {name}"
                    )
                    role_message = f"\n회수된 역할: {role_to_remove.mention}"
                except (discord.Forbidden, discord.HTTPException):
                    role_message = (
                        "\n역할 회수에 실패했습니다. 봇의 역할 순서를 확인해 주세요."
                    )

        details = (
            f"판매 원금: **{principal:,} P** · 환급(80%): **{refund:,} P**\n"
            f"현재 잔액: **{balance:,} P**"
        )
        if remaining_quantity:
            details += f"\n남은 수량: **{remaining_quantity:,}개**"
        if remaining_stock is not None:
            details += f"\n상점 재고: **{remaining_stock:,}개**"

        await send_card(
            interaction,
            "상품 판매 완료",
            f"**{display_shop_name(name)}** 상품을 **{quantity:,}개** 판매했습니다.\n"
            f"{details}{role_message}",
            color=discord.Color.green(),
            ephemeral=True,
        )

    @sell.autocomplete("item_name")
    async def item_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        items = await asyncio.to_thread(
            self.store.inventory, guild_id(interaction), interaction.user.id
        )
        query = normalize_shop_name(current).casefold()
        return [
            app_commands.Choice(
                name=f"{name} · 보유 {quantity:,}개",
                value=name,
            )
            for name, quantity in items
            if not query or query in name.casefold()
        ][:25]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Sell(bot.store))
