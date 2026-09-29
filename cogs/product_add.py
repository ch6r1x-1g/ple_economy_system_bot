from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from economy import EconomyStore, ShopLimitReached
from presentation import guild_id, send_card
from shop_names import display_shop_name, normalize_shop_name
from settings import MAX_POINTS


class ProductAdd(commands.Cog):
    def __init__(self, store: EconomyStore) -> None:
        self.store = store

    @app_commands.command(name="상품등록", description="상점에 상품을 등록합니다. (관리자)")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        name="상품 이름 (최대 50자)",
        price="상품 가격 (포인트)",
        description="상품 설명 (선택)",
        stock="재고 수량 (비우면 무제한)",
        role="구매 시 지급할 역할 (선택)",
    )
    @app_commands.rename(
        name="상품", price="가격", description="설명", stock="재고", role="역할"
    )
    async def product_add(
        self,
        interaction: discord.Interaction,
        name: str,
        price: app_commands.Range[int, 1, MAX_POINTS],
        description: str | None = None,
        stock: app_commands.Range[int, 0, 1_000_000] | None = None,
        role: discord.Role | None = None,
    ) -> None:
        name = normalize_shop_name(name)
        if not name or len(name) > 50:
            await send_card(
                interaction,
                "상품 이름이 올바르지 않습니다",
                "상품 이름은 1자부터 50자까지 입력해 주세요.",
                color=discord.Color.red(),
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
        if role is not None and role.is_default():
            await send_card(
                interaction,
                "역할을 등록할 수 없습니다",
                "서버의 기본 역할(@everyone)은 상품 역할로 사용할 수 없습니다.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        if role is not None:
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
            created = await asyncio.to_thread(
                self.store.add_shop_item,
                guild_id(interaction),
                name,
                (description or "").strip(),
                price,
                stock,
                role.id if role is not None else None,
            )
        except ShopLimitReached:
            await send_card(
                interaction,
                "상점 상품 한도에 도달했습니다",
                "상점에는 최대 20개까지 등록할 수 있습니다. 먼저 사용하지 않는 상품을 삭제해 주세요.",
                color=discord.Color.orange(),
                ephemeral=True,
            )
            return
        if not created:
            await send_card(
                interaction,
                "이미 등록된 상품입니다",
                "같은 이름의 상품이 상점에 있습니다. 먼저 `/상품삭제`로 제거해 주세요.",
                color=discord.Color.orange(),
                ephemeral=True,
            )
            return

        stock_text = "무제한" if stock is None else f"{stock:,}개"
        role_text = f" · 구매 시 역할: {role.mention}" if role is not None else ""
        await send_card(
            interaction,
            "상품 등록 완료",
            f"**{display_shop_name(name)}** 상품을 등록했습니다.\n가격: **{price:,} P** · 재고: **{stock_text}**{role_text}",
            color=discord.Color.green(),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ProductAdd(bot.store))
