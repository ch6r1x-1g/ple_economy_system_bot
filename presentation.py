from __future__ import annotations

import discord
from discord import app_commands


class CardView(discord.ui.LayoutView):
    """Embed-like card rendered with Discord Components V2."""

    def __init__(self, title: str, body: str, color: discord.Color) -> None:
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(f"## {title}"),
                discord.ui.Separator(),
                discord.ui.TextDisplay(body),
                accent_color=color,
            )
        )


async def send_card(
    interaction: discord.Interaction,
    title: str,
    body: str,
    *,
    color: discord.Color = discord.Color.blurple(),
    ephemeral: bool = False,
) -> None:
    view = CardView(title, body, color)
    send_options = {
        "view": view,
        "ephemeral": ephemeral,
        "allowed_mentions": discord.AllowedMentions.none(),
    }
    if interaction.response.is_done():
        await interaction.followup.send(**send_options)
    else:
        await interaction.response.send_message(**send_options)


def guild_id(interaction: discord.Interaction) -> int:
    if interaction.guild_id is None:
        raise app_commands.NoPrivateMessage()
    return interaction.guild_id
