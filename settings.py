from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

MAX_POINTS = 1_000_000_000


@dataclass(frozen=True)
class Settings:
    daily_reward: int
    voice_reward: int
    voice_no_mic_reward: int
    timezone: ZoneInfo
    sync_guild_id: int | None
    database_path: str
    database_url: str | None
    guild_ids: tuple[int, ...]


def load_settings() -> Settings:
    load_dotenv()

    try:
        daily_reward = int(os.getenv("DAILY_REWARD", "100"))
        if not 1 <= daily_reward <= MAX_POINTS:
            raise ValueError
    except ValueError as error:
        raise RuntimeError(
            f"DAILY_REWARD는 1부터 {MAX_POINTS:,} 사이의 정수여야 합니다."
        ) from error

    try:
        voice_reward = int(os.getenv("VOICE_REWARD", "100"))
        if not 1 <= voice_reward <= MAX_POINTS:
            raise ValueError
    except ValueError as error:
        raise RuntimeError(
            f"VOICE_REWARD는 1부터 {MAX_POINTS:,} 사이의 정수여야 합니다."
        ) from error

    try:
        voice_no_mic_reward = int(os.getenv("VOICE_NO_MIC_REWARD", "50"))
        if not 1 <= voice_no_mic_reward <= MAX_POINTS:
            raise ValueError
    except ValueError as error:
        raise RuntimeError(
            f"VOICE_NO_MIC_REWARD는 1부터 {MAX_POINTS:,} 사이의 정수여야 합니다."
        ) from error

    timezone_name = os.getenv("TIMEZONE", "Asia/Seoul")
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise RuntimeError(f"TIMEZONE을 찾을 수 없습니다: {timezone_name}") from error

    try:
        sync_guild_id = int(os.getenv("SYNC_GUILD_ID", "").strip() or "0") or None
    except ValueError as error:
        raise RuntimeError("SYNC_GUILD_ID는 숫자 서버 ID여야 합니다.") from error

    raw_guild_ids = os.getenv("GUILD_IDS", "").strip()
    try:
        guild_ids = (
            tuple(int(value.strip()) for value in raw_guild_ids.split(","))
            if raw_guild_ids
            else ()
        )
        if any(guild_id <= 0 for guild_id in guild_ids):
            raise ValueError
        if len(set(guild_ids)) != len(guild_ids):
            raise ValueError
    except ValueError as error:
        raise RuntimeError(
            "GUILD_IDS는 중복 없이 쉼표로 구분한 양수 Discord 서버 ID여야 합니다."
        ) from error

    return Settings(
        daily_reward=daily_reward,
        voice_reward=voice_reward,
        voice_no_mic_reward=voice_no_mic_reward,
        timezone=timezone,
        sync_guild_id=sync_guild_id,
        database_path=os.getenv("DATABASE_PATH", "data/economy.sqlite3"),
        database_url=os.getenv("DATABASE_URL", "").strip() or None,
        guild_ids=guild_ids,
    )
