from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from economy import EconomyStore, InsufficientFunds, OutOfStock, ShopItemNotFound
from presentation import guild_id, send_card
from shop_names import display_shop_name, normalize_shop_name


class Buy(commands.Cog):
    def __init__(self, store: EconomyStore) -> None:
        self.store = store

    @app_commands.command(name="구매", description="상점에서 상품을 구매합니다.")
    @app_commands.guild_only()
    @app_commands.describe(item_name="상점에 등록된 상품 이름", quantity="구매 수량")
    @app_commands.rename(item_name="상품", quantity="수량")
    async def buy(
        self,
        interaction: discord.Interaction,
        item_name: str,
        quantity: app_commands.Range[int, 1, 100] = 1,
    ) -> None:
        requested_name = normalize_shop_name(item_name)
        role_to_assign: discord.Role | None = None
        shop_items = await asyncio.to_thread(
            self.store.list_shop_items, guild_id(interaction)
        )
        requested_item = next(
            (
                item
                for item in shop_items
                if item.name.casefold() == requested_name.casefold()
            ),
            None,
        )
        if requested_item is not None and requested_item.role_id is not None:
            role_to_assign = interaction.guild.get_role(requested_item.role_id)
            if role_to_assign is None:
                await send_card(
                    interaction,
                    "상품 역할을 찾을 수 없습니다",
                    "관리자가 상품을 수정하거나 삭제해야 합니다.",
                    color=discord.Color.red(),
                    ephemeral=True,
                )
                return
            bot_member = interaction.guild.me
            if bot_member is None or not bot_member.guild_permissions.manage_roles:
                await send_card(
                    interaction,
                    "봇에 역할 관리 권한이 없습니다",
                    "서버 설정에서 봇 역할에 `역할 관리` 권한을 부여해 주세요.",
                    color=discord.Color.red(),
                    ephemeral=True,
                )
                return
            if not role_to_assign.is_assignable():
                if role_to_assign.managed:
                    message = "이 역할은 Discord 연동에서 관리하므로 봇이 지급할 수 없습니다."
                else:
                    message = (
                        "봇의 가장 높은 역할을 상품 역할보다 위로 올려 주세요. "
                        "구매자의 역할 순위와는 관계가 없습니다."
                    )
                await send_card(
                    interaction,
                    "봇이 상품 역할을 관리할 수 없습니다",
                    message,
                    color=discord.Color.red(),
                    ephemeral=True,
                )
                return
        try:
            name, total, balance, remaining, role_id = await asyncio.to_thread(
                self.store.purchase,
                guild_id(interaction),
                interaction.user.id,
                requested_name,
                quantity,
            )
        except ShopItemNotFound:
            await send_card(
                interaction,
                "상품을 찾을 수 없습니다",
                "`/상점`에서 상품 이름을 확인해 주세요.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        except OutOfStock as error:
            await send_card(
                interaction,
                "재고가 부족합니다",
                f"현재 남은 수량: **{error.remaining:,}개**",
                color=discord.Color.orange(),
                ephemeral=True,
            )
            return
        except InsufficientFunds as error:
            await send_card(
                interaction,
                "월령이 부족합니다",
                f"필요 월령: **{(error.required or 0):,} 월령**\n"
                f"현재 잔액: **{error.balance:,} 월령**",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return

        role_message = ""
        if role_id is not None and role_to_assign is not None:
            try:
                await interaction.user.add_roles(
                    role_to_assign, reason=f"상점 상품 구매: {name}"
                )
                role_message = f"\n지급된 역할: {role_to_assign.mention}"
            except (discord.Forbidden, discord.HTTPException):
                role_message = (
                    "\n역할 지급에 실패했습니다. 관리자에게 봇 역할 순서를 확인해 달라고 요청하세요."
                )

        stock_message = ""
        if remaining is not None:
            stock_message = f"\n남은 재고: **{remaining:,}개**"
        await send_card(
            interaction,
            "구매 완료",
            f"**{display_shop_name(name)}** 상품을 **{quantity:,}개** 구매했습니다.\n"
            f"결제액: **{total:,} 월령**\n현재 잔액: **{balance:,} 월령**"
            f"{stock_message}{role_message}",
            color=discord.Color.green(),
            ephemeral=True,
        )

    @buy.autocomplete("item_name")
    async def item_name_autocomplete(
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
    await bot.add_cog(Buy(bot.store))
