from __future__ import annotations

import asyncio
import logging
import re

import discord
from discord import app_commands
from discord.ext import commands

from economy import (
    AUTORESPONDER_LIMIT,
    AutoResponderEntry,
    AutoResponderLimitReached,
    EconomyStore,
)
from permissions import administrator_only
from presentation import guild_id, send_card

log = logging.getLogger(__name__)

MATCH_MODE_LABELS = {
    "exact": "완전 일치",
    "startswith": "앞부분 일치",
    "endswith": "뒷부분 일치",
    "includes": "문장 포함",
}
MATCH_MODE_CHOICES = [
    app_commands.Choice(name=label, value=value)
    for value, label in MATCH_MODE_LABELS.items()
]
DEFAULT_EMBED_COLOR = 0x5865F2


def parse_embed_color(value: str) -> int | None:
    color = value.strip().removeprefix("#")
    if len(color) == 3:
        color = "".join(character * 2 for character in color)
    if len(color) != 6 or any(
        character not in "0123456789abcdefABCDEF" for character in color
    ):
        return None
    return int(color, 16)


class AutoResponder(commands.Cog):
    autoresponder = app_commands.Group(
        name="자동응답", description="서버 자동 응답을 관리합니다."
    )

    def __init__(self, store: EconomyStore) -> None:
        self.store = store
        self._cache: dict[int, list[AutoResponderEntry]] = {}
        self._cache_lock = asyncio.Lock()

    @autoresponder.command(name="추가", description="자동 응답을 추가합니다. (관리자)")
    @administrator_only()
    @app_commands.describe(trigger="응답을 시작할 단어나 문장", response="보낼 응답 (최대 2,000자)")
    @app_commands.rename(trigger="트리거", response="응답")
    async def add(
        self, interaction: discord.Interaction, trigger: str, response: str
    ) -> None:
        trigger = trigger.strip()
        response = response.strip()
        if not 1 <= len(trigger) <= 100:
            await send_card(
                interaction,
                "트리거 길이를 확인해 주세요",
                "트리거는 공백을 제외하고 1자부터 100자까지 입력할 수 있습니다.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        if not 1 <= len(response) <= 2000:
            await send_card(
                interaction,
                "응답 길이를 확인해 주세요",
                "응답은 공백을 제외하고 1자부터 2,000자까지 입력할 수 있습니다.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return

        server_id = guild_id(interaction)
        try:
            created = await asyncio.to_thread(
                self.store.add_autoresponder, server_id, trigger, response
            )
        except AutoResponderLimitReached:
            await send_card(
                interaction,
                "자동 응답 한도에 도달했습니다",
                f"서버에는 자동 응답을 최대 {AUTORESPONDER_LIMIT}개까지 등록할 수 있습니다.",
                color=discord.Color.orange(),
                ephemeral=True,
            )
            return
        if not created:
            await send_card(
                interaction,
                "이미 등록된 트리거입니다",
                "트리거는 대소문자를 구분하지 않습니다. 기존 자동 응답을 수정하거나 삭제해 주세요.",
                color=discord.Color.orange(),
                ephemeral=True,
            )
            return

        self._cache.pop(server_id, None)
        await send_card(
            interaction,
            "자동 응답 추가 완료",
            f"트리거 **{trigger}**에 대한 응답을 등록했습니다. 기본 방식은 완전 일치입니다.",
            color=discord.Color.green(),
            ephemeral=True,
        )

    @autoresponder.command(
        name="임베드추가", description="임베드 형식의 자동 응답을 추가합니다. (관리자)"
    )
    @administrator_only()
    @app_commands.describe(
        trigger="응답을 시작할 단어나 문장",
        title="임베드 제목 (최대 256자)",
        description="임베드 설명 (최대 2,000자)",
        color="색상 HEX 코드 (예: #5865F2)",
    )
    @app_commands.rename(
        trigger="트리거", title="제목", description="설명", color="색상"
    )
    async def add_embed(
        self,
        interaction: discord.Interaction,
        trigger: str,
        title: str,
        description: str,
        color: str = "#5865F2",
    ) -> None:
        trigger = trigger.strip()
        title = title.strip()
        description = description.strip()
        color_value = parse_embed_color(color)
        if not 1 <= len(trigger) <= 100:
            await send_card(
                interaction,
                "트리거 길이를 확인해 주세요",
                "트리거는 공백을 제외하고 1자부터 100자까지 입력할 수 있습니다.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        if not 1 <= len(title) <= 256:
            await send_card(
                interaction,
                "임베드 제목 길이를 확인해 주세요",
                "임베드 제목은 1자부터 256자까지 입력할 수 있습니다.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        if not 1 <= len(description) <= 2000:
            await send_card(
                interaction,
                "임베드 설명 길이를 확인해 주세요",
                "임베드 설명은 1자부터 2,000자까지 입력할 수 있습니다.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        if color_value is None:
            await send_card(
                interaction,
                "색상 코드를 확인해 주세요",
                "색상은 `#5865F2`처럼 HEX 코드로 입력해 주세요.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return

        server_id = guild_id(interaction)
        try:
            created = await asyncio.to_thread(
                self.store.add_autoresponder,
                server_id,
                trigger,
                description,
                response_type="embed",
                embed_title=title,
                embed_color=color_value,
            )
        except AutoResponderLimitReached:
            await send_card(
                interaction,
                "자동 응답 한도에 도달했습니다",
                f"서버에는 자동 응답을 최대 {AUTORESPONDER_LIMIT}개까지 등록할 수 있습니다.",
                color=discord.Color.orange(),
                ephemeral=True,
            )
            return
        if not created:
            await send_card(
                interaction,
                "이미 등록된 트리거입니다",
                "트리거는 대소문자를 구분하지 않습니다. 기존 자동 응답을 수정하거나 삭제해 주세요.",
                color=discord.Color.orange(),
                ephemeral=True,
            )
            return

        self._cache.pop(server_id, None)
        await send_card(
            interaction,
            "임베드 자동 응답 추가 완료",
            f"트리거 **{trigger}**에 임베드 응답을 등록했습니다.",
            color=discord.Color.green(),
            ephemeral=True,
        )

    @autoresponder.command(name="목록", description="서버 자동 응답을 확인합니다. (관리자)")
    @administrator_only()
    @app_commands.describe(page="확인할 페이지 (페이지당 20개)")
    @app_commands.rename(page="페이지")
    async def list_entries(
        self, interaction: discord.Interaction, page: app_commands.Range[int, 1, 1000] = 1
    ) -> None:
        entries, total = await asyncio.to_thread(
            self.store.list_autoresponders,
            guild_id(interaction),
            page=page,
            page_size=20,
        )
        if total == 0:
            await send_card(
                interaction,
                "등록된 자동 응답이 없습니다",
                "`/자동응답 추가`로 트리거와 응답을 등록할 수 있습니다.",
                color=discord.Color.orange(),
                ephemeral=True,
            )
            return
        if not entries:
            await send_card(
                interaction,
                "페이지를 찾을 수 없습니다",
                f"등록된 자동 응답은 {total}개입니다. 1부터 {(total + 19) // 20} 사이의 페이지를 선택해 주세요.",
                color=discord.Color.orange(),
                ephemeral=True,
            )
            return

        lines = [
            f"• `{entry.trigger.replace('`', 'ˋ')}` · "
            f"{'임베드' if entry.response_type == 'embed' else '텍스트'} · "
            f"{MATCH_MODE_LABELS[entry.match_mode]}"
            for entry in entries
        ]
        await send_card(
            interaction,
            f"자동 응답 목록 · {page}/{(total + 19) // 20}페이지",
            "\n".join(lines),
            color=discord.Color.blurple(),
            ephemeral=True,
        )

    @autoresponder.command(name="수정", description="자동 응답 문구를 수정합니다. (관리자)")
    @administrator_only()
    @app_commands.describe(trigger="수정할 트리거", response="새 응답 문구")
    @app_commands.rename(trigger="트리거", response="응답")
    async def edit(
        self, interaction: discord.Interaction, trigger: str, response: str
    ) -> None:
        response = response.strip()
        if not 1 <= len(response) <= 2000:
            await send_card(
                interaction,
                "응답 길이를 확인해 주세요",
                "응답은 공백을 제외하고 1자부터 2,000자까지 입력할 수 있습니다.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        server_id = guild_id(interaction)
        updated = await asyncio.to_thread(
            self.store.edit_autoresponder, server_id, trigger.strip(), response
        )
        if not updated:
            await self._not_found(interaction)
            return
        self._cache.pop(server_id, None)
        await send_card(
            interaction,
            "자동 응답 수정 완료",
            f"트리거 **{trigger.strip()}**를 텍스트 응답으로 변경했습니다.",
            color=discord.Color.green(),
            ephemeral=True,
        )

    @autoresponder.command(
        name="임베드수정", description="자동 응답을 임베드 형식으로 바꾸거나 수정합니다. (관리자)"
    )
    @administrator_only()
    @app_commands.describe(
        trigger="수정할 트리거",
        title="임베드 제목 (최대 256자)",
        description="임베드 설명 (최대 2,000자)",
        color="색상 HEX 코드 (예: #5865F2)",
    )
    @app_commands.rename(
        trigger="트리거", title="제목", description="설명", color="색상"
    )
    async def edit_embed(
        self,
        interaction: discord.Interaction,
        trigger: str,
        title: str,
        description: str,
        color: str = "#5865F2",
    ) -> None:
        title = title.strip()
        description = description.strip()
        color_value = parse_embed_color(color)
        if not 1 <= len(title) <= 256:
            await send_card(
                interaction,
                "임베드 제목 길이를 확인해 주세요",
                "임베드 제목은 1자부터 256자까지 입력할 수 있습니다.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        if not 1 <= len(description) <= 2000:
            await send_card(
                interaction,
                "임베드 설명 길이를 확인해 주세요",
                "임베드 설명은 1자부터 2,000자까지 입력할 수 있습니다.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        if color_value is None:
            await send_card(
                interaction,
                "색상 코드를 확인해 주세요",
                "색상은 `#5865F2`처럼 HEX 코드로 입력해 주세요.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return

        server_id = guild_id(interaction)
        updated = await asyncio.to_thread(
            self.store.edit_autoresponder_embed,
            server_id,
            trigger.strip(),
            title,
            description,
            color_value,
        )
        if not updated:
            await self._not_found(interaction)
            return
        self._cache.pop(server_id, None)
        await send_card(
            interaction,
            "임베드 자동 응답 수정 완료",
            f"트리거 **{trigger.strip()}**의 임베드 응답을 변경했습니다.",
            color=discord.Color.green(),
            ephemeral=True,
        )

    @autoresponder.command(name="방식", description="트리거 일치 방식을 설정합니다. (관리자)")
    @administrator_only()
    @app_commands.choices(mode=MATCH_MODE_CHOICES)
    @app_commands.describe(trigger="방식을 바꿀 트리거", mode="응답을 실행할 조건")
    @app_commands.rename(trigger="트리거", mode="일치방식")
    async def set_mode(
        self,
        interaction: discord.Interaction,
        trigger: str,
        mode: app_commands.Choice[str],
    ) -> None:
        server_id = guild_id(interaction)
        updated = await asyncio.to_thread(
            self.store.set_autoresponder_match_mode,
            server_id,
            trigger.strip(),
            mode.value,
        )
        if not updated:
            await self._not_found(interaction)
            return
        self._cache.pop(server_id, None)
        await send_card(
            interaction,
            "일치 방식 변경 완료",
            f"트리거 **{trigger.strip()}**의 방식: **{mode.name}**",
            color=discord.Color.green(),
            ephemeral=True,
        )

    @autoresponder.command(name="삭제", description="자동 응답을 삭제합니다. (관리자)")
    @administrator_only()
    @app_commands.describe(trigger="삭제할 트리거")
    @app_commands.rename(trigger="트리거")
    async def remove(self, interaction: discord.Interaction, trigger: str) -> None:
        server_id = guild_id(interaction)
        deleted = await asyncio.to_thread(
            self.store.remove_autoresponder, server_id, trigger.strip()
        )
        if not deleted:
            await self._not_found(interaction)
            return
        self._cache.pop(server_id, None)
        await send_card(
            interaction,
            "자동 응답 삭제 완료",
            f"트리거 **{trigger.strip()}**를 삭제했습니다.",
            color=discord.Color.green(),
            ephemeral=True,
        )

    @staticmethod
    async def _not_found(interaction: discord.Interaction) -> None:
        await send_card(
            interaction,
            "트리거를 찾을 수 없습니다",
            "등록된 트리거인지 확인해 주세요. 트리거는 대소문자를 구분하지 않습니다.",
            color=discord.Color.orange(),
            ephemeral=True,
        )

    async def _load_cache(self, server_id: int) -> list[AutoResponderEntry]:
        if server_id not in self._cache:
            async with self._cache_lock:
                if server_id not in self._cache:
                    self._cache[server_id] = await asyncio.to_thread(
                        self.store.all_autoresponders, server_id
                    )
        return self._cache[server_id]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot or not message.content:
            return
        if self.store.guild_ids and message.guild.id not in self.store.guild_ids:
            return

        entries = await self._load_cache(message.guild.id)
        content = message.content.casefold()
        matches = [
            entry
            for entry in entries
            if (
                (entry.match_mode == "exact" and content == entry.trigger_key)
                or (entry.match_mode == "startswith" and content.startswith(entry.trigger_key))
                or (entry.match_mode == "endswith" and content.endswith(entry.trigger_key))
                or (entry.match_mode == "includes" and entry.trigger_key in content)
            )
        ]
        if not matches:
            return

        mode_priority = {"exact": 0, "startswith": 1, "endswith": 1, "includes": 2}
        entry = min(
            matches,
            key=lambda value: (mode_priority[value.match_mode], -len(value.trigger_key)),
        )
        channel_name = getattr(message.channel, "name", "")
        replacements = {
            "{user}": message.author.mention,
            "{user_mention}": message.author.mention,
            "{user_id}": str(message.author.id),
            "{user_name}": message.author.display_name,
            "{server}": message.guild.name,
            "{server_name}": message.guild.name,
            "{channel}": getattr(message.channel, "mention", channel_name),
            "{channel_name}": channel_name,
            "{message_content}": message.content,
            "{message_link}": message.jump_url,
            "{newline}": "\n",
        }

        def expand(template: str) -> str:
            return re.sub(
                r"\{[^{}]+\}",
                lambda match: replacements.get(match.group(0), match.group(0)),
                template,
            )

        try:
            if entry.response_type == "embed":
                embed = discord.Embed(
                    title=expand(entry.embed_title or "")[:256],
                    description=expand(entry.response)[:4096],
                    color=discord.Color(
                        entry.embed_color
                        if entry.embed_color is not None
                        else DEFAULT_EMBED_COLOR
                    ),
                )
                await message.channel.send(
                    embed=embed, allowed_mentions=discord.AllowedMentions.none()
                )
            else:
                await message.channel.send(
                    expand(entry.response)[:2000],
                    allowed_mentions=discord.AllowedMentions.none(),
                )
        except (discord.Forbidden, discord.HTTPException):
            log.warning(
                "Could not send autoresponder in guild %s, channel %s",
                message.guild.id,
                message.channel.id,
                exc_info=True,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoResponder(bot.store))
