"""Slack integration tools for agents."""

from typing import Any

import httpx
import structlog

from src.config import Settings

logger = structlog.get_logger()


class SlackTools:
    """Slack API wrapper for agent communication."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = "https://slack.com/api"
        self.headers = {
            "Authorization": f"Bearer {settings.slack_bot_token}",
            "Content-Type": "application/json",
        }

    async def send_message(self, channel: str, text: str) -> dict[str, Any]:
        """Send a message to a Slack channel."""
        url = f"{self.base_url}/chat.postMessage"
        payload = {"channel": channel, "text": text}

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=self.headers)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                return {"error": data.get("error", "unknown")}
            logger.info("slack_message_sent", channel=channel)
            return {"status": "sent", "channel": channel, "ts": data.get("ts")}

    async def create_channel(self, name: str) -> dict[str, Any]:
        """Create a Slack channel."""
        url = f"{self.base_url}/conversations.create"
        payload = {"name": name}

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=self.headers)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                if data.get("error") == "name_taken":
                    return {"status": "already_exists", "name": name}
                return {"error": data.get("error", "unknown")}
            channel_id = data["channel"]["id"]
            logger.info("slack_channel_created", name=name, id=channel_id)
            return {"status": "created", "name": name, "id": channel_id}

    async def list_channels(self, limit: int = 20) -> list[dict[str, Any]]:
        """List Slack channels."""
        url = f"{self.base_url}/conversations.list"
        params = {"limit": limit, "types": "public_channel"}

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=self.headers)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                return []
            return [{"id": ch["id"], "name": ch["name"]} for ch in data.get("channels", [])]

    async def get_channel_history(self, channel: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent messages from a channel."""
        url = f"{self.base_url}/conversations.history"
        params = {"channel": channel, "limit": limit}

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=self.headers)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                return []
            return [
                {"text": msg.get("text", ""), "user": msg.get("user", ""), "ts": msg.get("ts", "")}
                for msg in data.get("messages", [])
            ]
