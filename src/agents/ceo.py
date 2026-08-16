"""CEO Agent — Strategic direction and opportunity detection."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.github_tools import GitHubTools
from src.tools.slack_tools import SlackTools

CEO_PERSONA = """You are the CEO of an AI-powered IT company called My IT Crew.

CRITICAL RULES:
- Before creating ANY new epic, check if there are existing open epics that haven't been completed yet.
- If there are open epics still in progress, DO NOT create new ones. Instead, check their status and push for progress.
- Only create a new epic when all existing epics are either completed or explicitly blocked.
- Maximum 3 open epics at any time.

Your responsibilities:
- Set strategic direction for the company
- Review progress on existing initiatives
- Identify market opportunities ONLY when the team has capacity
- Coordinate across departments via Slack #c-suite channel
- Make go/no-go decisions on proposals from CTO

Your workflow each cycle:
1. List all open issues labeled 'epic' — if there are open ones, focus on THOSE
2. Check if any epic needs your decision (labeled 'needs-ceo')
3. If epics are progressing well and team has capacity, consider ONE new initiative
4. Post status updates to Slack #general for company visibility

Decision framework:
- When CTO provides feasibility assessment, make go/no-go decision
- When items are labeled 'needs-ceo', respond with clear direction
- Approve or reject proposals with reasoning

You communicate via:
- Slack: #general for company-wide updates, #c-suite for strategic discussions
- GitHub Issues for tracking work (epics, features)
- Comments on issues for decisions and feedback
"""


class CEOAgent(BaseAgent):
    """CEO agent with strategic planning capabilities."""

    def __init__(self):
        super().__init__(agent_id="ceo", persona=CEO_PERSONA)
        self._setup_tools()

    def _setup_tools(self) -> None:
        gh = GitHubTools(self.settings)
        slack = SlackTools(self.settings)

        self.register_tool(
            "send_slack_message",
            slack.send_message,
            "Send a message to a Slack channel",
            {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "description": "Channel name (e.g. general, c-suite)",
                    },
                    "text": {"type": "string", "description": "Message text"},
                },
                "required": ["channel", "text"],
            },
        )
        self.register_tool(
            "create_issue",
            gh.create_issue,
            "Create a new GitHub Issue (epic, feature, opportunity). ONLY use when no open epics exist.",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "labels": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "body"],
            },
        )
        self.register_tool(
            "comment_on_issue",
            gh.comment_on_issue,
            "Add a decision or feedback comment to an existing issue",
            {
                "type": "object",
                "properties": {
                    "issue_number": {"type": "integer"},
                    "body": {"type": "string"},
                },
                "required": ["issue_number", "body"],
            },
        )
        self.register_tool(
            "list_issues",
            gh.list_issues,
            "List open GitHub Issues with optional label filter",
            {
                "type": "object",
                "properties": {
                    "labels": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer"},
                },
            },
        )

    async def perceive(self) -> list[dict]:
        gh = GitHubTools(self.settings)
        events = []

        # Check issues needing CEO decision
        issues = await gh.list_issues(labels=["needs-CEO"], limit=5)
        for issue in issues:
            events.append(
                {
                    "type": "needs_decision",
                    "title": issue["title"],
                    "body": f"Issue #{issue['number']}: {issue.get('body', '')[:500]}",
                }
            )

        # Check status of open epics
        epics = await gh.list_issues(labels=["epic"], limit=10)
        if epics:
            events.append(
                {
                    "type": "epic_status_review",
                    "title": f"{len(epics)} open epics to review",
                    "body": "\n".join(
                        f"- #{e['number']}: {e['title']} [labels: {', '.join(e.get('labels', []))}]"
                        for e in epics
                    ),
                }
            )

        # Only suggest new work if no open epics
        if not epics and not issues:
            events.append(
                {
                    "type": "capacity_available",
                    "title": "Team has capacity",
                    "body": "No open epics or pending decisions. Consider proposing a new strategic initiative.",
                }
            )

        return events

    async def reflect(self, result: dict[str, Any]) -> None:
        self.log.info(
            "ceo_reflection",
            actions_taken=len(result.get("actions", [])),
            summary=result.get("summary", "")[:200],
        )
