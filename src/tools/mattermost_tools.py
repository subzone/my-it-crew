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
        """Get channel ID by name or display name with fallback mapping."""
        clean_name = channel_name.lstrip("#").strip().lower().replace(" ", "-")
        if clean_name in self._channel_cache:
            return self._channel_cache[clean_name]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 1. Get team ID
                resp = await client.get(f"{self.base_url}/teams", headers=self.headers)
                if resp.status_code != 200:
                    logger.warning("mattermost_get_teams_failed", status=resp.status_code)
                    return None
                teams = resp.json()
                if not teams:
                    return None
                team_id = teams[0]["id"]

                # 2. Get all public channels in team
                resp = await client.get(
                    f"{self.base_url}/teams/{team_id}/channels", headers=self.headers
                )
                if resp.status_code == 200:
                    channels = resp.json()
                    # Look for exact name or display name match
                    for ch in channels:
                        ch_name = ch.get("name", "").lower()
                        ch_display = ch.get("display_name", "").lower().replace(" ", "-")
                        self._channel_cache[ch_name] = ch["id"]
                        self._channel_cache[ch_display] = ch["id"]

                    if clean_name in self._channel_cache:
                        return self._channel_cache[clean_name]

                    # Aliases: 'general' -> 'town-square'
                    if clean_name in ("general", "main") and "town-square" in self._channel_cache:
                        self._channel_cache[clean_name] = self._channel_cache["town-square"]
                        return self._channel_cache["town-square"]

                    # Fallback to town-square or first public channel
                    if "town-square" in self._channel_cache:
                        return self._channel_cache["town-square"]
                    if channels:
                        return channels[0]["id"]

                # 3. Direct channel by name query
                url = f"{self.base_url}/teams/{team_id}/channels/name/{clean_name}"
                resp = await client.get(url, headers=self.headers)
                if resp.status_code == 200:
                    cid = resp.json()["id"]
                    self._channel_cache[clean_name] = cid
                    return cid

        except Exception as exc:
            logger.warning("mattermost_channel_lookup_error", channel=channel_name, error=str(exc))
        return None

    async def send_message(self, channel: str, text: str) -> dict[str, Any]:
        """Send a message to a Mattermost channel."""
        channel_id = await self._get_channel_id(channel)
        if not channel_id:
            logger.warning("mattermost_channel_not_found", channel=channel)
            return {"error": f"Channel '{channel}' not found"}

        url = f"{self.base_url}/posts"
        payload = {"channel_id": channel_id, "message": text}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=self.headers)
                if resp.status_code not in (200, 201):
                    logger.warning(
                        "mattermost_post_failed", status=resp.status_code, body=resp.text[:200]
                    )
                    return {"error": f"Failed to post: {resp.status_code}"}
                logger.info(
                    "mattermost_message_sent", channel=channel, post_id=resp.json().get("id")
                )
                return {"status": "sent", "channel": channel, "post_id": resp.json().get("id")}
        except Exception as e:
            logger.error("mattermost_send_error", channel=channel, error=str(e))
            return {"error": str(e)}

    async def update_message(self, post_id: str, text: str) -> dict[str, Any]:
        """Update an existing message."""
        url = f"{self.base_url}/posts/{post_id}"
        payload = {"id": post_id, "message": text}

        async with httpx.AsyncClient() as client:
            resp = await client.put(url, json=payload, headers=self.headers)
            if resp.status_code != 200:
                return {"error": f"Failed to update: {resp.status_code}"}
            return {"status": "updated", "post_id": post_id}

    async def send_thinking(self, channel: str) -> str | None:
        """Send a thinking indicator message. Returns the post ID for later update."""
        channel_id = await self._get_channel_id(channel)
        if not channel_id:
            return None

        url = f"{self.base_url}/posts"
        payload = {"channel_id": channel_id, "message": "⏳ _Thinking..._"}

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=self.headers)
            if resp.status_code not in (200, 201):
                return None
            return resp.json().get("id")

    async def send_message_with_thinking(self, channel: str, text: str) -> dict[str, Any]:
        """Send a thinking indicator, then replace it with the actual message."""
        # Post thinking indicator
        post_id = await self.send_thinking(channel)
        if not post_id:
            # Fallback to regular send
            return await self.send_message(channel=channel, text=text)

        # Update with actual content
        result = await self.update_message(post_id, text)
        if "error" in result:
            return result
        logger.info("mattermost_message_sent", channel=channel)
        return {"status": "sent", "channel": channel, "post_id": post_id}

    async def get_direct_messages(self, limit: int = 5) -> list[dict[str, Any]]:
        """Get recent direct messages sent to this bot."""
        # Get bot's own user ID
        url = f"{self.base_url}/users/me"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers)
            if resp.status_code != 200:
                return []
            bot_user_id = resp.json()["id"]

            # Get bot's channels (includes DMs)
            url = f"{self.base_url}/users/{bot_user_id}/channels"
            resp = await client.get(url, headers=self.headers)
            if resp.status_code != 200:
                return []

            channels = resp.json()
            messages = []

            for ch in channels:
                # Only check direct message channels (type "D")
                if ch.get("type") != "D":
                    continue

                # Get recent posts
                url = f"{self.base_url}/channels/{ch['id']}/posts"
                resp = await client.get(url, params={"per_page": limit}, headers=self.headers)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                for post_id in data.get("order", [])[:limit]:
                    post = data["posts"][post_id]
                    # Skip bot's own messages
                    if post.get("user_id") == bot_user_id:
                        continue
                    messages.append(
                        {
                            "text": post.get("message", ""),
                            "user": post.get("user_id", ""),
                            "channel_id": ch["id"],
                            "ts": post.get("create_at", ""),
                        }
                    )

            return messages

    async def reply_to_dm(self, channel_id: str, text: str) -> dict[str, Any]:
        """Reply to a direct message."""
        url = f"{self.base_url}/posts"
        payload = {"channel_id": channel_id, "message": text}

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=self.headers)
            if resp.status_code not in (200, 201):
                return {"error": f"Failed to reply: {resp.status_code}"}
            logger.info("mattermost_dm_replied", channel_id=channel_id)
            return {"status": "replied", "channel_id": channel_id}

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
