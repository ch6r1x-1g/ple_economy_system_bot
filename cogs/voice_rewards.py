from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass

import discord
from discord.ext import commands, tasks

from economy import EconomyStore

log = logging.getLogger("points-bot.voice-rewards")


@dataclass
class _VoiceSession:
    started_at: float


@dataclass
class _PendingVoiceReward:
    units: int = 0
    ended: bool = False


class VoiceRewards(commands.Cog):
    """Reward human members for time connected to a voice or stage channel."""

    FLUSH_INTERVAL_SECONDS = 60

    def __init__(
        self,
        bot: commands.Bot,
        store: EconomyStore,
        reward_per_hour: int,
    ) -> None:
        self.bot = bot
        self.store = store
        self.reward_per_hour = reward_per_hour
        self._sessions: dict[tuple[int, int], _VoiceSession] = {}
        self._pending_rewards: dict[tuple[int, int], deque[_PendingVoiceReward]] = {}
        self._lock = asyncio.Lock()
        self._gateway_ready = False
        self._flush_loop.start()

    def cog_unload(self) -> None:
        self._flush_loop.cancel()

    @tasks.loop(seconds=FLUSH_INTERVAL_SECONDS)
    async def _flush_loop(self) -> None:
        if self._gateway_ready:
            await self._flush_active_sessions()

    @_flush_loop.before_loop
    async def _before_flush_loop(self) -> None:
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self._sync_voice_sessions()

    @commands.Cog.listener()
    async def on_disconnect(self) -> None:
        self._gateway_ready = False
        await self._flush_active_sessions()

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.bot:
            return

        key = (member.guild.id, member.id)
        now = asyncio.get_running_loop().time()
        async with self._lock:
            session = self._sessions.get(key)
            if session is not None:
                self._queue_elapsed(key, session, now)

            if after.channel is None:
                self._end_session(key)
                self._sessions.pop(key, None)
            elif session is None:
                if before.channel is None:
                    # A fresh join must not inherit a saved, older session.
                    self._end_session(key)
                self._sessions[key] = _VoiceSession(now)
            await self._flush_pending(key)

    async def _sync_voice_sessions(self) -> None:
        now = asyncio.get_running_loop().time()
        connected: dict[tuple[int, int], discord.VoiceState] = {}
        configured_guilds = set(self.bot.settings.guild_ids)

        for guild in self.bot.guilds:
            if configured_guilds and guild.id not in configured_guilds:
                continue
            channels = (*guild.voice_channels, *guild.stage_channels)
            for channel in channels:
                for user_id, voice_state in channel.voice_states.items():
                    if voice_state.channel is not None:
                        connected[(guild.id, user_id)] = voice_state

        sessions: dict[tuple[int, int], _VoiceSession] = {}
        for key in connected:
            guild_id, user_id = key
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue

            member = guild.get_member(user_id)
            if member is None:
                try:
                    member = await guild.fetch_member(user_id)
                except discord.HTTPException:
                    log.debug(
                        "Could not resolve voice member %s in guild %s",
                        user_id,
                        guild_id,
                        exc_info=True,
                    )
                    continue

            if not member.bot:
                sessions[key] = _VoiceSession(now)

        async with self._lock:
            was_gateway_ready = self._gateway_ready
            # A member may have left while the gateway was disconnected.
            for key in self._sessions.keys() - connected.keys():
                self._end_session(key)
                await self._flush_pending(key)
            # Keep a previously identified human if Discord's cache could not
            # resolve them during a reconnect, as long as they are still present.
            for key in connected:
                if key in self._sessions and (
                    key not in sessions or was_gateway_ready
                ):
                    sessions[key] = (
                        self._sessions[key]
                        if was_gateway_ready
                        else _VoiceSession(now)
                    )
            self._sessions = sessions
            self._gateway_ready = True

    def _queue_elapsed(
        self, key: tuple[int, int], session: _VoiceSession, now: float
    ) -> None:
        elapsed = max(0, int(now - session.started_at))
        if elapsed:
            self._pending_batch(key).units += elapsed * self.reward_per_hour
            session.started_at += elapsed

    def _pending_batch(self, key: tuple[int, int]) -> _PendingVoiceReward:
        pending = self._pending_rewards.setdefault(key, deque())
        if not pending or pending[-1].ended:
            pending.append(_PendingVoiceReward())
        return pending[-1]

    def _end_session(self, key: tuple[int, int]) -> None:
        # Keep the session boundary queued even if a DB write fails and the
        # member rejoins before it can be retried.
        self._pending_batch(key).ended = True

    async def _flush_pending(self, key: tuple[int, int]) -> None:
        pending = self._pending_rewards.get(key)
        guild_id, user_id = key
        while pending:
            batch = pending[0]
            try:
                reward, _ = await asyncio.to_thread(
                    self.store.accrue_voice_reward_units,
                    guild_id,
                    user_id,
                    batch.units,
                    self.reward_per_hour,
                    reset_remainder=batch.ended,
                )
            except Exception:
                log.exception(
                    "Could not save voice time for user %s in guild %s",
                    user_id,
                    guild_id,
                )
                return

            pending.popleft()
            if reward:
                log.info(
                    "Granted %s voice points to user %s in guild %s",
                    reward,
                    user_id,
                    guild_id,
                )
        self._pending_rewards.pop(key, None)

    async def _flush_active_sessions(self) -> None:
        now = asyncio.get_running_loop().time()
        async with self._lock:
            for key, session in tuple(self._sessions.items()):
                self._queue_elapsed(key, session, now)
            for key in tuple(self._pending_rewards):
                await self._flush_pending(key)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(
        VoiceRewards(
            bot,
            bot.store,
            bot.settings.voice_reward,
        )
    )
