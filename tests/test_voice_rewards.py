import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cogs.voice_rewards import VoiceRewards, _VoiceSession
from economy import EconomyStore


class VoiceRewardStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "economy.sqlite3")
        self.store = EconomyStore(self.path)
        self.store.initialize()

    def accrue(self, seconds, guild_id=1, user_id=10):
        return self.store.accrue_voice_reward_units(guild_id, user_id, seconds * 100)

    def test_minute_flushes_pay_only_at_full_hour(self):
        for _ in range(59):
            self.assertEqual(self.accrue(60), (0, 0))
        self.assertEqual(self.accrue(59), (0, 0))
        self.assertEqual(self.accrue(1), (100, 100))
        self.assertEqual(self.accrue(0), (0, 100))
        self.assertEqual(self.accrue(3600), (100, 200))

    def test_remainder_survives_restart_and_multiple_hours(self):
        self.assertEqual(self.accrue(9000), (200, 200))
        self.store = EconomyStore(self.path)
        self.store.initialize()
        self.assertEqual(self.accrue(1799), (0, 200))
        self.assertEqual(self.accrue(1), (100, 300))

    def test_guilds_and_users_accumulate_independently(self):
        self.assertEqual(self.accrue(1800), (0, 0))
        self.assertEqual(self.accrue(1800, user_id=11), (0, 0))
        self.assertEqual(self.accrue(1800, guild_id=2), (0, 0))
        self.assertEqual(self.accrue(1800), (100, 100))
        self.assertEqual(self.store.balance(1, 11), 0)
        self.assertEqual(self.store.balance(2, 10), 0)

    def test_old_unpaid_units_are_preserved(self):
        with self.store._connect(1) as connection:
            connection.execute(
                "INSERT INTO voice_activity VALUES (?, ?, ?)", (1, 10, 3500)
            )
        self.assertEqual(self.accrue(3564), (0, 0))
        self.assertEqual(self.accrue(1), (100, 100))

    def test_leave_settles_full_hours_and_discards_remainder(self):
        self.assertEqual(self.accrue(3500), (0, 0))
        self.assertEqual(
            self.store.accrue_voice_reward_units(
                1, 10, 700 * 100, reset_remainder=True
            ),
            (100, 100),
        )
        self.assertEqual(self.accrue(3000), (0, 100))
        self.assertEqual(self.accrue(600), (100, 200))

    def test_leave_clears_saved_time_without_new_elapsed_seconds(self):
        self.accrue(1800)
        self.assertEqual(
            self.store.accrue_voice_reward_units(1, 10, 0, reset_remainder=True),
            (0, 0),
        )
        self.assertEqual(self.accrue(1800), (0, 0))


class VoiceSessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = EconomyStore(str(Path(self.temp.name) / "economy.sqlite3"))
        self.store.initialize()
        with patch.object(VoiceRewards, "_flush_loop"):
            self.cog = VoiceRewards(SimpleNamespace(), self.store, 100)
        self.member = SimpleNamespace(bot=False, guild=SimpleNamespace(id=1), id=10)

    async def test_mute_move_keep_progress_but_leave_resets_it(self):
        disconnected = SimpleNamespace(channel=None)
        connected = SimpleNamespace(channel=1, self_mute=False, mute=False)
        muted = SimpleNamespace(channel=2, self_mute=True, mute=True)
        with patch("cogs.voice_rewards.asyncio", wraps=asyncio) as clock:
            now = 0
            clock.get_running_loop.return_value = SimpleNamespace(time=lambda: now)
            await self.cog.on_voice_state_update(self.member, disconnected, connected)
            now = 1200.5
            await self.cog.on_voice_state_update(self.member, connected, muted)
            self.assertEqual(self.cog._sessions[(1, 10)].started_at, 1200)
            now = 1800
            await self.cog.on_voice_state_update(self.member, muted, disconnected)
            self.assertEqual(self.store.balance(1, 10), 0)
            now = 5000
            await self.cog.on_voice_state_update(self.member, disconnected, muted)
            now = 6800
            await self.cog._flush_active_sessions()
            self.assertEqual(self.store.balance(1, 10), 0)
            now = 8600
            await self.cog._flush_active_sessions()
        self.assertEqual(self.store.balance(1, 10), 100)

    async def test_failed_save_is_retried_without_double_payment(self):
        key = (1, 10)
        self.cog._queue_elapsed(key, _VoiceSession(0), 3600)
        with patch.object(self.store, "accrue_voice_reward_units", side_effect=RuntimeError):
            with self.assertLogs("points-bot.voice-rewards", level="ERROR"):
                await self.cog._flush_pending(key)
        self.assertEqual(self.cog._pending_rewards[key][0].units, 360000)
        await self.cog._flush_pending(key)
        await self.cog._flush_pending(key)
        self.assertEqual(self.store.balance(1, 10), 100)

    async def test_leave_failure_and_rejoin_do_not_combine_partial_hours(self):
        disconnected = SimpleNamespace(channel=None)
        connected = SimpleNamespace(channel=1)
        with patch("cogs.voice_rewards.asyncio", wraps=asyncio) as clock:
            now = 0
            clock.get_running_loop.return_value = SimpleNamespace(time=lambda: now)
            await self.cog.on_voice_state_update(self.member, disconnected, connected)
            now = 1800
            # The first half hour has already been persisted by a periodic flush.
            await self.cog._flush_active_sessions()
            with patch.object(self.store, "accrue_voice_reward_units", side_effect=RuntimeError):
                with self.assertLogs("points-bot.voice-rewards", level="ERROR"):
                    await self.cog.on_voice_state_update(self.member, connected, disconnected)
                    now = 2000
                    await self.cog.on_voice_state_update(self.member, disconnected, connected)
                    now = 3800
                    await self.cog._flush_active_sessions()
            await self.cog._flush_active_sessions()
            self.assertEqual(self.store.balance(1, 10), 0)
            now = 5600
            await self.cog._flush_active_sessions()
            self.assertEqual(self.store.balance(1, 10), 100)

    async def test_leaving_after_hour_pays_before_reset(self):
        disconnected = SimpleNamespace(channel=None)
        connected = SimpleNamespace(channel=1)
        with patch("cogs.voice_rewards.asyncio", wraps=asyncio) as clock:
            now = 0
            clock.get_running_loop.return_value = SimpleNamespace(time=lambda: now)
            await self.cog.on_voice_state_update(self.member, disconnected, connected)
            now = 4200
            await self.cog.on_voice_state_update(self.member, connected, disconnected)
            self.assertEqual(self.store.balance(1, 10), 100)
            now = 5000
            await self.cog.on_voice_state_update(self.member, disconnected, connected)
            now = 8000
            await self.cog._flush_active_sessions()
            self.assertEqual(self.store.balance(1, 10), 100)
            now = 8600
            await self.cog._flush_active_sessions()
            self.assertEqual(self.store.balance(1, 10), 200)

    async def test_mute_and_channel_move_preserve_full_hour(self):
        disconnected = SimpleNamespace(channel=None)
        connected = SimpleNamespace(channel=1, self_mute=False)
        muted = SimpleNamespace(channel=2, self_mute=True)
        with patch("cogs.voice_rewards.asyncio", wraps=asyncio) as clock:
            now = 0
            clock.get_running_loop.return_value = SimpleNamespace(time=lambda: now)
            await self.cog.on_voice_state_update(self.member, disconnected, connected)
            now = 1800
            await self.cog.on_voice_state_update(self.member, connected, muted)
            now = 3600
            await self.cog._flush_active_sessions()
            self.assertEqual(self.store.balance(1, 10), 100)

    async def test_bots_are_excluded(self):
        self.member.bot = True
        await self.cog.on_voice_state_update(
            self.member, SimpleNamespace(channel=None), SimpleNamespace(channel=1)
        )
        self.assertFalse(self.cog._sessions)


if __name__ == "__main__":
    unittest.main()
