from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from economy import EconomyStore, ShopItemNameTaken
from presentation import guild_id, send_card
from shop_names import display_shop_name, normalize_shop_name
from settings import MAX_POINTS


class ProductEdit(commands.Cog):
    def __init__(self, store: EconomyStore) -> None:
        self.store = store

    @app_commands.command(name="상품수정", description="상점 상품 정보를 수정합니다. (관리자)")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        name="수정할 상품 이름",
        new_name="새 상품 이름 (띄어쓰기 포함)",
        price="새 가격",
        description="새 설명",
        stock="새 재고 수량",
        unlimited_stock="재고를 무제한으로 변경",
        role="구매 시 지급할 역할 변경",
        remove_role="상품의 역할 연결 해제",
    )
    @app_commands.rename(
        name="상품",
        new_name="새이름",
        price="가격",
        description="설명",
        stock="재고",
        unlimited_stock="무제한재고",
        role="역할",
        remove_role="역할해제",
    )
    async def product_edit(
        self,
        interaction: discord.Interaction,
        name: str,
        price: app_commands.Range[int, 1, MAX_POINTS] | None = None,
        description: str | None = None,
        stock: app_commands.Range[int, 0, 1_000_000] | None = None,
        unlimited_stock: bool = False,
        role: discord.Role | None = None,
        remove_role: bool = False,
        new_name: str | None = None,
    ) -> None:
        name = normalize_shop_name(name)
        new_name = None if new_name is None else normalize_shop_name(new_name)
        if not name or len(name) > 50:
            await send_card(
                interaction,
                "상품 이름이 올바르지 않습니다",
                "상품 이름은 1자부터 50자까지 입력해 주세요.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        if new_name is not None and (not new_name or len(new_name) > 50):
            await send_card(
                interaction,
                "새 상품 이름이 올바르지 않습니다",
                "새 상품 이름은 1자부터 50자까지 입력해 주세요.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        if all(
            value is None and not flag
            for value, flag in (
                (price, False),
                (description, False),
                (stock, unlimited_stock),
                (role, remove_role),
                (new_name, False),
            )
        ):
            await send_card(
                interaction,
                "변경할 내용이 없습니다",
                "새 이름, 가격, 설명, 재고, 역할 중 수정할 항목을 입력해 주세요.",
                color=discord.Color.orange(),
                ephemeral=True,
            )
            return
        if description is not None and len(description) > 100:
            await send_card(
                interaction,
                "상품 설명이 너무 깁니다",
                "상품 설명은 100자 이하로 입력해 주세요.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        if stock is not None and unlimited_stock:
            await send_card(
                interaction,
                "재고 옵션을 확인해 주세요",
                "재고 수량을 입력하거나 무제한 재고를 선택해 주세요.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        if role is not None and remove_role:
            await send_card(
                interaction,
                "역할 옵션을 확인해 주세요",
                "새 역할을 지정하거나 기존 역할 연결을 해제해 주세요.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        if role is not None:
            bot_member = interaction.guild.me
            if role.is_default():
                await send_card(
                    interaction,
                    "역할을 지급할 수 없습니다",
                    "서버 기본 역할(@everyone)은 상품 역할로 사용할 수 없습니다.",
                    color=discord.Color.red(),
                    ephemeral=True,
                )
                return
            if bot_member is None or not bot_member.guild_permissions.manage_roles:
                await send_card(
                    interaction,
                    "봇에 역할 관리 권한이 없습니다",
                    "서버 설정에서 봇 역할에 `역할 관리` 권한을 부여해 주세요.",
                    color=discord.Color.red(),
                    ephemeral=True,
                )
                return
            if not role.is_assignable():
                await send_card(
                    interaction,
                    "역할을 지급할 수 없습니다",
                    "봇의 가장 높은 역할을 상품 역할보다 위로 올려 주세요. "
                    "연동 관리 역할은 상품 역할로 사용할 수 없습니다.",
                    color=discord.Color.red(),
                    ephemeral=True,
                )
                return

        try:
            updated = await asyncio.to_thread(
                self.store.update_shop_item,
                guild_id(interaction),
                name,
                new_name=new_name,
                price=price,
                description=description,
                stock=stock,
                unlimited_stock=unlimited_stock,
                role_id=role.id if role is not None else None,
                remove_role=remove_role,
            )
        except ShopItemNameTaken:
            await send_card(
                interaction,
                "이미 등록된 상품 이름입니다",
                "상점에 없는 이름으로 변경해 주세요.",
                color=discord.Color.orange(),
                ephemeral=True,
            )
            return
        if updated is None:
            await send_card(
                interaction,
                "상품을 찾을 수 없습니다",
                "`/상점`에서 등록된 상품 이름을 확인해 주세요.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return

        stock_text = "무제한" if updated.stock is None else f"{updated.stock:,}개"
        role_text = f"<@&{updated.role_id}>" if updated.role_id is not None else "없음"
        description_text = updated.description or "설명 없음"
        await send_card(
            interaction,
            "상품 수정 완료",
            f"**{display_shop_name(updated.name)}**\n가격: **{updated.price:,} P** · 재고: **{stock_text}**\n"
            f"역할: {role_text}\n설명: {description_text}\n"
            "역할 변경은 이후 구매부터 적용됩니다.",
            color=discord.Color.green(),
            ephemeral=True,
        )

    @product_edit.autocomplete("name")
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
    await bot.add_cog(ProductEdit(bot.store))
