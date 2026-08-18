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
    "em": "agent-eng-manager",
    "nova": "agent-nova",
    "engineer": "agent-nova",
    "kai": "agent-kai",
    "frontend": "agent-kai",
    "zara": "agent-zara",
    "fullstack": "agent-zara",
    "devops": "agent-devops",
    "qa-engineer": "agent-qa-engineer",
    "qa": "agent-qa-engineer",
    "marketer": "agent-marketer",
    "marketing": "agent-marketer",
    "cigance": "agent-cigance",
    "scout": "agent-cigance",
    "ta-specialist": "agent-ta-specialist",
    "recruiter": "agent-ta-specialist",
    "tech-interviewer": "agent-tech-interviewer",
    "interviewer": "agent-tech-interviewer",
    "reporter": "agent-reporter",
}

NAMESPACE = os.environ.get("NAMESPACE", "my-it-crew")


async def trigger_agent(agent_name: str) -> bool:
    """Send HTTP trigger to an agent pod."""
    service = MENTION_MAP.get(agent_name)
    if not service:
        return False
    url = f"http://{service}.{NAMESPACE}.svc:8080/trigger"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, timeout=5)
            if resp.status_code == 200:
                logger.info("agent_triggered", agent=agent_name, service=service)
                return True
    except Exception as e:
        logger.error("trigger_failed", agent=agent_name, error=str(e))
    return False


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

    for mention in mentions:
        if await trigger_agent(mention):
            triggered.append(mention)

    if triggered:
        return web.json_response({"text": f"⚡ Triggered: {', '.join(triggered)}"})
    return web.json_response({"text": ""})


async def handle_github_webhook(request: web.Request) -> web.Response:
    """Handle GitHub Webhooks (issues, PRs, comments, workflow_run CI results)."""
    event = request.headers.get("X-GitHub-Event", "ping")
    if event == "ping":
        return web.json_response({"status": "pong"})

    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)

    logger.info("github_webhook_received", event=event)
    triggered = []

    # 1. CI / Check Run / Workflow Run Failures
    if event in ("workflow_run", "check_run", "check_suite"):
        conclusion = ""
        branch = ""
        if event == "workflow_run":
            wr = payload.get("workflow_run", {})
            conclusion = wr.get("conclusion") or ""
            branch = wr.get("head_branch") or ""
        elif event == "check_run":
            cr = payload.get("check_run", {})
            conclusion = cr.get("conclusion") or ""
            branch = cr.get("check_suite", {}).get("head_branch") or ""

        if conclusion == "failure":
            logger.warning("github_ci_failure_detected", branch=branch)
            # Route to branch author persona
            for author in ("nova", "kai", "zara"):
                if author in branch.lower():
                    if await trigger_agent(author):
                        triggered.append(author)

    # 2. Issues, PRs, Comments with @mentions
    elif event in ("issues", "pull_request", "issue_comment", "pull_request_review_comment"):
        body = ""
        if "comment" in payload:
            body = payload["comment"].get("body", "")
        elif "issue" in payload:
            body = payload["issue"].get("body", "")
        elif "pull_request" in payload:
            body = payload["pull_request"].get("body", "")

        body_lower = body.lower()
        for mention in MENTION_MAP:
            if f"@{mention}" in body_lower or mention in body_lower:
                if await trigger_agent(mention):
                    triggered.append(mention)

    return web.json_response({"event": event, "triggered": triggered})


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def main() -> None:
    app = web.Application()
    app.router.add_post("/webhook", handle_webhook)
    app.router.add_post("/github-webhook", handle_github_webhook)
    app.router.add_get("/health", handle_health)
    web.run_app(app, host="0.0.0.0", port=8090)


if __name__ == "__main__":
    main()
