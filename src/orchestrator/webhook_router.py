"""Webhook router — receives Mattermost outgoing webhooks and triggers the right agent."""

import os

import httpx
import structlog
from aiohttp import web

logger = structlog.get_logger()

# Map @mention keywords to agent service names
MENTION_MAP = {
    "ceo": "agent-ceo",
    "cto": "agent-cto",
    "eng-manager": "agent-eng-manager",
    "engineer": "agent-engineer",
    "devops": "agent-devops",
    "qa-engineer": "agent-qa-engineer",
    "qa": "agent-qa-engineer",
    "marketer": "agent-marketer",
    "marketing": "agent-marketer",
}

NAMESPACE = os.environ.get("NAMESPACE", "my-it-crew")


async def handle_webhook(request: web.Request) -> web.Response:
    """Handle Mattermost outgoing webhook — trigger mentioned agents."""
    data = await request.post()
    text = data.get("text", "")
    user_name = data.get("user_name", "unknown")

    logger.info("webhook_received", user=user_name, text=text[:100])

    # Find agent mentions (with or without @)
    text_lower = text.lower()
    triggered = []
    mentions = [name for name in MENTION_MAP if name in text_lower]

    async with httpx.AsyncClient() as client:
        for mention in mentions:
            service = MENTION_MAP.get(mention)
            if service:
                url = f"http://{service}.{NAMESPACE}.svc:8080/trigger"
                try:
                    resp = await client.post(url, timeout=5)
                    if resp.status_code == 200:
                        triggered.append(mention)
                        logger.info("agent_triggered", agent=mention, service=service)
                except Exception as e:
                    logger.error("trigger_failed", agent=mention, error=str(e))

    if triggered:
        return web.json_response({"text": f"⚡ Triggered: {', '.join(triggered)}"})
    return web.json_response({"text": ""})


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def main() -> None:
    app = web.Application()
    app.router.add_post("/webhook", handle_webhook)
    app.router.add_get("/health", handle_health)
    web.run_app(app, host="0.0.0.0", port=8090)


if __name__ == "__main__":
    main()
