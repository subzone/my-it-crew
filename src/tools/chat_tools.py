"""Unified chat tools - uses Mattermost if available, falls back to Slack."""

from typing import Any

import structlog

from src.config import Settings
from src.tools.mattermost_tools import MattermostTools
from src.tools.slack_tools import SlackTools

logger = structlog.get_logger()


class ChatTools:
    """Unified chat interface - routes to Mattermost or Slack."""

    def __init__(self, settings: Settings):
        self.settings = settings
        if settings.mattermost_token:
            self._backend = MattermostTools(settings)
            self._name = "mattermost"
        elif settings.slack_bot_token:
            self._backend = SlackTools(settings)
            self._name = "slack"
        else:
            self._backend = None
            self._name = "none"

    async def send_message(self, channel: str, text: str) -> dict[str, Any]:
        """Send a message directly to a Mattermost or Slack channel."""
        if not self._backend:
            logger.warning("no_chat_backend_configured")
            return {"error": "No chat backend configured"}
        return await self._backend.send_message(channel=channel, text=text)

    async def get_channel_history(self, channel: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent messages from a channel."""
        if not self._backend:
            return []
        return await self._backend.get_channel_history(channel=channel, limit=limit)

    async def get_direct_messages(self, limit: int = 5) -> list[dict[str, Any]]:
        """Get direct messages sent to this bot."""
        if not self._backend or not hasattr(self._backend, "get_direct_messages"):
            return []
        return await self._backend.get_direct_messages(limit=limit)

    async def reply_to_dm(self, channel_id: str, text: str) -> dict[str, Any]:
        """Reply to a direct message."""
        if not self._backend or not hasattr(self._backend, "reply_to_dm"):
            return {"error": "DM reply not supported"}
        return await self._backend.reply_to_dm(channel_id=channel_id, text=text)
