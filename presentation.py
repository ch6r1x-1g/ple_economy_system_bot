from __future__ import annotations

import discord
from discord import app_commands

COMMAND_TIPS = {
    "가방": "네 월령 잔액과 보유한 보급품을 한눈에 확인할 수 있어!",
    "일일": "하루 한 번 여기서 월령 보급을 챙길 수 있어! 히히!",
    "송금": "다른 대원에게 월령을 보낼 땐 이 명령을 쓰면 돼!",
    "공동계좌": "우리 마을 공동 계좌에 모인 월령을 확인하는 명령이야!",
    "공동입금": "네 월령을 마을 공동 계좌에 맡길 수 있어!",
    "공동출금": "공동 계좌의 월령을 네 잔액으로 옮기는 명령이야!",
    "지급": "대원에게 월령을 지급하는 관리자 작전이야!",
    "차감": "대원의 잔액에서 월령을 차감하는 관리자 작전이야!",
    "잔액설정": "대원의 월령 잔액을 원하는 값으로 맞추는 관리자 명령이야!",
    "상점": "보급 상점의 상품과 가격, 재고를 정찰해!",
    "구매": "월령으로 상점 보급품을 구매하는 명령이야!",
    "판매": "인벤토리 상품을 원가의 80%에 상점으로 되파는 명령이야!",
    "상품등록": "상점에 새 상품을 등록하는 관리자 작전이야!",
    "상품수정": "상점 상품의 가격, 재고, 설명, 역할 설정을 바꾸는 명령이야!",
    "상품삭제": "상점에서 상품을 제거하는 관리자 명령이야!",
}


class CardView(discord.ui.LayoutView):
    """Embed-like card rendered with Discord Components V2."""

    def __init__(
        self, title: str, body: str, color: discord.Color, command_tip: str
    ) -> None:
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(f"## {title}"),
                discord.ui.TextDisplay(f"*“{command_tip}”*"),
                discord.ui.Separator(),
                discord.ui.TextDisplay(body),
                accent_color=color,
            )
        )


async def send_card(
    interaction: discord.Interaction,
    title: str,
    body: str,
    *,
    color: discord.Color = discord.Color.blurple(),
    ephemeral: bool = False,
) -> None:
    command_name = getattr(interaction.command, "name", None)
    command_tip = COMMAND_TIPS.get(
        command_name, "명령 결과를 확인했어! 다음 정찰도 부탁해!"
    )
    view = CardView(title, body, color, command_tip)
    send_options = {
        "view": view,
        "ephemeral": ephemeral,
        "allowed_mentions": discord.AllowedMentions.none(),
    }
    if interaction.response.is_done():
        await interaction.followup.send(**send_options)
    else:
        await interaction.response.send_message(**send_options)


def guild_id(interaction: discord.Interaction) -> int:
    if interaction.guild_id is None:
        raise app_commands.NoPrivateMessage()
    return interaction.guild_id
