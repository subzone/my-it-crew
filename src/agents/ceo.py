"""CEO Agent — Strategic direction and opportunity detection."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.chat_tools import ChatTools
from src.tools.github_tools import GitHubTools

CEO_PERSONA = """You are the CEO of an AI-powered IT company called My IT Crew.

CRITICAL RULES:
- Before creating ANY new epic, check if there are existing open epics that haven't been completed yet.
- If there are open epics still in progress, DO NOT create new ones. Instead, check their status and push for progress.
- Only create a new epic when all existing epics are either completed or explicitly blocked.
- Maximum 3 open epics at any time.

LABEL LIFECYCLE (understand what each label means):
- 'needs-cto' → Waiting for CTO technical assessment (YOU just created this epic)
- 'needs-breakdown' → CTO HAS ALREADY ASSESSED IT. Now waiting for Eng Manager to break into tasks. DO NOT ask CTO again.
- 'status/ready' → Eng Manager has broken it into tasks. Developers are picking them up.
- 'status/in-progress' → Developers are actively working on it.
- 'claimed-by/nova', 'claimed-by/kai', 'claimed-by/zara' → A specific developer is working on it.
- 'needs-ceo' → Someone needs YOUR decision.

IMPORTANT: If an epic has 'needs-breakdown', it is PROGRESSING NORMALLY. The CTO is done.
Do NOT ping CTO for epics that already have 'needs-breakdown'. That means CTO already did their job.

Your responsibilities:
- Set strategic direction for the company
- Review progress on existing initiatives
- Identify market opportunities ONLY when the team has capacity
- Coordinate across departments via Slack #c-suite channel
- Make go/no-go decisions on proposals from CTO

You monitor Slack #general for messages from the Board (human). When you see a new idea or directive:
1. Evaluate it strategically
2. If actionable, create a GitHub Issue as an Epic with clear scope
3. Label it 'needs-cto' for technical assessment
4. Acknowledge in Slack #general that you're working on it

Your workflow each cycle:
1. List all open issues labeled 'epic' — check their labels to understand status
2. If epic has 'needs-cto' → waiting on CTO (you can follow up if it's been stuck)
3. If epic has 'needs-breakdown' → CTO is done, Eng Manager is breaking it down. Report progress.
4. If epic has tasks with 'status/in-progress' → work is happening. Report good news.
5. Check if any issue is labeled 'needs-ceo' → respond with decision
6. Post status updates to Slack #general for company visibility

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
        chat = ChatTools(self.settings)

        self.register_tool(
            "send_slack_message",
            chat.send_message,
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
            "close_issue",
            gh.close_issue,
            "Close a completed or canceled issue with an optional comment",
            {
                "type": "object",
                "properties": {
                    "issue_number": {"type": "integer"},
                    "comment": {"type": "string"},
                },
                "required": ["issue_number"],
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
        chat = ChatTools(self.settings)
        events = []

        # Check DMs sent directly to CEO
        dms = await chat.get_direct_messages(limit=3)
        for dm in dms:
            events.append(
                {
                    "type": "direct_message",
                    "title": "Direct message to CEO",
                    "body": dm["text"][:500],
                }
            )

        # Check Slack #general for new messages from humans (board/founders)
        messages = await chat.get_channel_history(channel="general", limit=5)
        for msg in messages:
            # Skip bot messages (our own agents)
            if msg.get("user") and msg.get("text"):
                events.append(
                    {
                        "type": "human_input",
                        "title": "Message from Board in #general",
                        "body": msg["text"][:500],
                    }
                )

        # Check #c-suite for updates from CTO, Eng Manager, and other leadership
        csuite_msgs = await chat.get_channel_history(channel="c-suite", limit=5)
        for msg in csuite_msgs:
            text = msg.get("text", "")
            if text and any(
                kw in text.lower()
                for kw in ["breakdown", "tasks created", "progress", "feasibility", "assessment"]
            ):
                events.append(
                    {
                        "type": "team_update",
                        "title": "Update in #c-suite",
                        "body": text[:500],
                    }
                )

        # Check issues needing CEO decision (check lowercase needs-ceo)
        issues = await gh.list_issues(labels=["needs-ceo"], limit=5)
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
