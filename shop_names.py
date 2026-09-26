"""Normalization and display helpers for shop item names."""

from __future__ import annotations

import re

import discord


def normalize_shop_name(value: str) -> str:
    """Normalize visible whitespace while preserving word separators."""
    value = value.replace("\u200b", " ").replace("\ufeff", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def display_shop_name(value: str) -> str:
    """Escape markup and use nonbreaking spaces so names render literally."""
    escaped = discord.utils.escape_markdown(value)
    return escaped.replace(" ", "\u00a0")
