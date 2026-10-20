from __future__ import annotations

import asyncio
import calendar
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from economy import EconomyStore
from presentation import guild_id, send_card

log = logging.getLogger("points-bot.birthday")

# Leap year, so that Feb 29 is accepted as a valid birthday.
_VALIDATION_YEAR = 2000


def _is_valid_birthday(month: int, day: int) -> bool:
    try:
        date(_VALIDATION_YEAR, month, day)
    except ValueError:
        return False
    return True


def _announcement_dates(today: date) -> list[tuple[int, int]]:
    """Return the (month, day) pairs whose birthdays are celebrated today.

    Feb 29 birthdays are celebrated on Feb 28 in non-leap years.
    """
    dates = [(today.month, today.day)]
    if today.month == 2 and today.day == 28 and not calendar.isleap(today.year):
        dates.append((2, 29))
    return dates


class Birthday(commands.Cog):
    CHECK_INTERVAL_MINUTES = 10

    def __init__(
        self,
        bot: commands.Bot,
        store: EconomyStore,
        reward: int,
        channel_id: int,
        timezone: ZoneInfo,
    ) -> None:
        self.bot = bot
        self.store = store
        self.reward = reward
        self.channel_id = channel_id
        self.timezone = timezone
        self._announce_birthdays.start()

    def cog_unload(self) -> None:
        self._announce_birthdays.cancel()

    @app_commands.command(name="생일등록", description="내 생일을 등록합니다.")
    @app_commands.guild_only()
    @app_commands.describe(month="생일 월 (1~12)", day="생일 일 (1~31)")
    @app_commands.rename(month="월", day="일")
    async def register(
        self,
        interaction: discord.Interaction,
        month: app_commands.Range[int, 1, 12],
        day: app_commands.Range[int, 1, 31],
    ) -> None:
        if not _is_valid_birthday(month, day):
            await send_card(
                interaction,
                "존재하지 않는 날짜입니다",
                f"**{month}월 {day}일**은 달력에 없어요. 날짜를 다시 확인해 주세요.",
                color=discord.Color.red(),
                ephemeral=True,
            )
            return
        await asyncio.to_thread(
            self.store.set_birthday,
            guild_id(interaction),
            interaction.user.id,
            month,
            day,
        )
        leap_note = (
            "\n2월 29일 생일은 윤년이 아닌 해에는 2월 28일에 축하받아요."
            if (month, day) == (2, 29)
            else ""
        )
        await send_card(
            interaction,
            "생일 등록 완료",
            f"생일을 **{month}월 {day}일**로 등록했습니다.\n"
            f"생일에는 **{self.reward:,} 월령**을 받고 축하 메시지가 올라가요!{leap_note}",
            color=discord.Color.green(),
            ephemeral=True,
        )

    @app_commands.command(name="생일삭제", description="등록한 생일을 삭제합니다.")
    @app_commands.guild_only()
    async def remove(self, interaction: discord.Interaction) -> None:
        removed = await asyncio.to_thread(
            self.store.remove_birthday, guild_id(interaction), interaction.user.id
        )
        if not removed:
            await send_card(
                interaction,
                "등록된 생일이 없습니다",
                "`/생일등록`으로 생일을 먼저 등록해 주세요.",
                color=discord.Color.orange(),
                ephemeral=True,
            )
            return
        await send_card(
            interaction,
            "생일 삭제 완료",
            "등록된 생일을 삭제했습니다.",
            color=discord.Color.green(),
            ephemeral=True,
        )

    @app_commands.command(name="생일확인", description="내가 등록한 생일을 확인합니다.")
    @app_commands.guild_only()
    async def show(self, interaction: discord.Interaction) -> None:
        birthday = await asyncio.to_thread(
            self.store.birthday, guild_id(interaction), interaction.user.id
        )
        if birthday is None:
            await send_card(
                interaction,
                "등록된 생일이 없습니다",
                "`/생일등록`으로 생일을 등록해 주세요.",
                color=discord.Color.orange(),
                ephemeral=True,
            )
            return
        month, day = birthday
        await send_card(
            interaction,
            "내 생일",
            f"등록된 생일: **{month}월 {day}일**",
            color=discord.Color.blurple(),
            ephemeral=True,
        )

    @tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
    async def _announce_birthdays(self) -> None:
        try:
            await self._celebrate_today()
        except Exception:
            log.exception("Could not process birthdays")

    @_announce_birthdays.before_loop
    async def _before_announce_birthdays(self) -> None:
        await self.bot.wait_until_ready()

    async def _celebrate_today(self) -> None:
        channel = self.bot.get_channel(self.channel_id)
        if not isinstance(channel, discord.TextChannel):
            log.warning("Birthday channel %s is missing or not a text channel", self.channel_id)
            return
        server_id = channel.guild.id
        if self.store.guild_ids and server_id not in self.store.guild_ids:
            return

        today = datetime.now(self.timezone).date()
        for month, day in _announcement_dates(today):
            user_ids = await asyncio.to_thread(
                self.store.unrewarded_birthday_user_ids,
                server_id,
                month,
                day,
                today.year,
            )
            for user_id in user_ids:
                await self._celebrate_user(channel, server_id, user_id, today.year)

    async def _celebrate_user(
        self,
        channel: discord.TextChannel,
        server_id: int,
        user_id: int,
        year: int,
    ) -> None:
        try:
            member = await channel.guild.fetch_member(user_id)
        except discord.NotFound:
            # Left the server; the birthday stays unrewarded until they return.
            return
        except discord.HTTPException:
            log.warning("Could not fetch member %s for birthday", user_id, exc_info=True)
            return

        rewarded = await asyncio.to_thread(
            self.store.claim_birthday_reward, server_id, user_id, year, self.reward
        )
        if not rewarded:
            return

        embed = discord.Embed(
            title="🎂 생일 축하해요!",
            description=(
                f"오늘은 **{member.display_name}**님의 생일이에요!\n"
                "보름달 마을 대원들 모두 축하해 주세요 🎉\n\n"
                f"생일 선물로 **{self.reward:,} 월령**을 지급했어요."
            ),
            color=discord.Color.gold(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        try:
            await channel.send(
                content=member.mention,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(users=[member]),
            )
        except discord.HTTPException:
            # The reward is already paid; never pay twice for the same birthday.
            log.exception("Could not send birthday message for user %s", user_id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(
        Birthday(
            bot,
            bot.store,
            bot.settings.birthday_reward,
            bot.settings.birthday_channel_id,
            bot.settings.timezone,
        )
    )
