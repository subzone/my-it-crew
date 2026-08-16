"""Mattermost integration tools for agents."""

from typing import Any

import httpx
import structlog

from src.config import Settings

logger = structlog.get_logger()


class MattermostTools:
    """Mattermost API wrapper for agent communication."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = f"{settings.mattermost_url}/api/v4"
        self.headers = {
            "Authorization": f"Bearer {settings.mattermost_token}",
            "Content-Type": "application/json",
        }
        self._channel_cache: dict[str, str] = {}

    async def _get_channel_id(self, channel_name: str) -> str | None:
        """Get channel ID by name."""
        if channel_name in self._channel_cache:
            return self._channel_cache[channel_name]

        # Get team ID first
        url = f"{self.base_url}/teams"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers)
            if resp.status_code != 200:
                return None
            teams = resp.json()
            if not teams:
                return None
            team_id = teams[0]["id"]

            # Get channel by name
            url = f"{self.base_url}/teams/{team_id}/channels/name/{channel_name}"
            resp = await client.get(url, headers=self.headers)
            if resp.status_code != 200:
                return None
            channel_id = resp.json()["id"]
            self._channel_cache[channel_name] = channel_id
            return channel_id

    async def send_message(self, channel: str, text: str) -> dict[str, Any]:
        """Send a message to a Mattermost channel."""
        channel_id = await self._get_channel_id(channel)
        if not channel_id:
            return {"error": f"Channel '{channel}' not found"}

        url = f"{self.base_url}/posts"
        payload = {"channel_id": channel_id, "message": text}

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=self.headers)
            if resp.status_code not in (200, 201):
                return {"error": f"Failed to post: {resp.status_code}"}
            logger.info("mattermost_message_sent", channel=channel)
            return {"status": "sent", "channel": channel}

    async def get_channel_history(self, channel: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent messages from a channel."""
        channel_id = await self._get_channel_id(channel)
        if not channel_id:
            return []

        url = f"{self.base_url}/channels/{channel_id}/posts"
        params = {"per_page": limit}

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=self.headers)
            if resp.status_code != 200:
                return []
            data = resp.json()
            posts = []
            for post_id in data.get("order", []):
                post = data["posts"][post_id]
                posts.append(
                    {
                        "text": post.get("message", ""),
                        "user": post.get("user_id", ""),
                        "ts": post.get("create_at", ""),
                    }
                )
            return posts
