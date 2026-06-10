"""Bot construction: intents, mode-specific cog registration, slash syncing.

FriendBot2 runs in one of two modes (they share one bot identity but can't share
the GPU, so only one runs at a time):

- ``image``: diffusion image generation via the local flux repo (default)
- ``chat``:  persona chat backed by a local fine-tuned LLM
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from . import config

log = logging.getLogger(__name__)


class FriendBot(commands.Bot):
    def __init__(self, mode: str | None = None) -> None:
        intents = discord.Intents.default()
        # Required for prefix (``!artistic``) commands and for reading channel
        # chatter in chat mode. message_content is a privileged intent — enable
        # it for the bot in the Discord developer portal.
        intents.message_content = True
        super().__init__(command_prefix=config.COMMAND_PREFIX, intents=intents)
        self.mode = mode or config.MODE
        self.backend = None  # set in setup_hook

    async def setup_hook(self) -> None:
        # Cogs and their backends are imported lazily so each mode only touches
        # the dependencies it actually needs.
        if self.mode == "chat":
            from .chat import ChatCog
            from .llm_backend import LLMBackend

            self.backend = LLMBackend(
                config.LLM_BASE_MODEL,
                adapter_path=config.LLM_ADAPTER_PATH,
                quantize_4bit=config.LLM_4BIT,
                context_tokens=config.LLM_CONTEXT_TOKENS,
                max_new_tokens=config.LLM_MAX_NEW_TOKENS,
                temperature=config.LLM_TEMPERATURE,
                top_p=config.LLM_TOP_P,
            )
            await self.add_cog(ChatCog(self, self.backend))
        else:
            from .flux_backend import FluxBackend
            from .image_generation import ImageGenerationCog

            self.backend = FluxBackend(config.FLUX_REPO_PATH, model=config.MODEL)
            await self.add_cog(ImageGenerationCog(self, self.backend))
        log.info("Running in %s mode.", self.mode)

        # Register slash commands. A guild-scoped sync is instant and ideal for
        # development; a global sync (no guild) can take up to an hour to appear.
        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Synced %d slash command(s) to guild %s", len(synced), config.GUILD_ID)
        else:
            synced = await self.tree.sync()
            log.info("Synced %d global slash command(s)", len(synced))

    async def on_ready(self) -> None:
        log.info("Logged in as %s (id: %s)", self.user, getattr(self.user, "id", "?"))
