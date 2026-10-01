from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from discord import app_commands

Callback = TypeVar("Callback", bound=Callable[..., Any])


def administrator_only() -> Callable[[Callback], Callback]:
    """Restrict an application command to server administrators."""

    def decorate(callback: Callback) -> Callback:
        callback = app_commands.checks.has_permissions(administrator=True)(callback)
        callback = app_commands.default_permissions(administrator=True)(callback)
        callback = app_commands.guild_only()(callback)
        return callback

    return decorate
