from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

MAX_POINTS = 1_000_000_000


@dataclass(frozen=True)
class Settings:
    token: str
    daily_reward: int
    timezone: ZoneInfo
    sync_guild_id: int | None
    database_path: str
    database_url: str | None


def load_settings() -> Settings:
    load_dotenv()

    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token or token == "여기에_봇_토큰":
        raise RuntimeError("환경 변수 DISCORD_TOKEN을(를) 설정해 주세요.")

    try:
        daily_reward = int(os.getenv("DAILY_REWARD", "100"))
        if not 1 <= daily_reward <= MAX_POINTS:
            raise ValueError
    except ValueError as error:
        raise RuntimeError(
            f"DAILY_REWARD는 1부터 {MAX_POINTS:,} 사이의 정수여야 합니다."
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

    return Settings(
        token=token,
        daily_reward=daily_reward,
        timezone=timezone,
        sync_guild_id=sync_guild_id,
        database_path=os.getenv("DATABASE_PATH", "data/economy.sqlite3"),
        database_url=os.getenv("DATABASE_URL", "").strip() or None,
    )
