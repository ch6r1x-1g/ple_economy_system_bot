"""Parse and roll administrator-configured autoresponder rewards."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass

from settings import MAX_POINTS

MAX_REWARD_CHOICES = 20
MAX_REWARD_SPEC_LENGTH = 256
REWARD_HELP = (
    "고정값 `100`, 범위 `10~100`, 후보 목록 `10,50,100` 중 하나로 입력해 주세요.\n"
    f"수량은 0~{MAX_POINTS:,}의 정수, 후보는 최대 {MAX_REWARD_CHOICES}개입니다. "
    "`0`은 지급 안 함입니다. 쉼표는 천 단위 구분이 아닌 후보 구분입니다."
)


@dataclass(frozen=True)
class RewardSpec:
    values: tuple[int, ...]
    is_range: bool = False

    def __str__(self) -> str:
        return ("~" if self.is_range else ",").join(map(str, self.values))

    def roll(self) -> int:
        if self.is_range:
            minimum, maximum = self.values
            return minimum + secrets.randbelow(maximum - minimum + 1)
        if len(self.values) == 1:
            return self.values[0]
        return secrets.choice(self.values)


def parse_reward_spec(value: str) -> RewardSpec:
    value = value.strip()
    if not value or len(value) > MAX_REWARD_SPEC_LENGTH:
        raise ValueError(REWARD_HELP)
    range_match = re.fullmatch(r"([0-9]+)\s*[~-]\s*([0-9]+)", value)
    if range_match:
        values = tuple(int(part) for part in range_match.groups())
        is_range = True
    elif re.fullmatch(r"[0-9]+(?:\s*,\s*[0-9]+)*", value):
        values = tuple(int(part.strip()) for part in value.split(","))
        is_range = False
    else:
        raise ValueError(REWARD_HELP)
    if (
        len(values) > MAX_REWARD_CHOICES
        or any(amount > MAX_POINTS for amount in values)
        or (is_range and values[0] > values[1])
    ):
        raise ValueError(REWARD_HELP)
    # Each distinct candidate has an equal chance, even if entered twice.
    return RewardSpec(values if is_range else tuple(dict.fromkeys(values)), is_range)
