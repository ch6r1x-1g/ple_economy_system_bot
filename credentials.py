from __future__ import annotations

import os

from dotenv import load_dotenv


def load_discord_token() -> str:
    """Load the Discord token stored in the local environment or .env file."""
    load_dotenv()

    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token or token == "여기에_봇_토큰":
        raise RuntimeError("환경 변수 DISCORD_TOKEN을(를) 설정해 주세요.")
    return token
