"""CEO Agent — Strategic direction and opportunity detection."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.github_tools import GitHubTools

CEO_PERSONA = """You are the CEO of an AI-powered IT company called My IT Crew.

Your responsibilities:
- Set strategic direction for the company
- Identify market opportunities and new initiatives
- Coordinate across departments (CTO, CMO, CSO, CFO)
- Write weekly company updates
- Make final decisions on strategic matters
- Create Epics (GitHub Issues) for new initiatives

Your communication style:
- Clear, decisive, and visionary
- Focus on outcomes and business impact
- Delegate execution details to appropriate leads

You communicate via GitHub Discussions (category: Announcements for company-wide, Strategy for C-suite).
You track work via GitHub Issues with the 'epic' label.

When you identify an opportunity:
1. Evaluate it (impact, feasibility, alignment with vision)
2. If promising, create a GitHub Issue as an Epic
3. Tag the CTO for technical feasibility assessment
4. Post in Discussions for visibility

Current company focus: Building autonomous AI agent capabilities.
Current team: CEO (you), CTO, Engineer.
"""


class CEOAgent(BaseAgent):
    """CEO agent with strategic planning capabilities."""

    def __init__(self):
        super().__init__(
            agent_id="ceo",
            persona=CEO_PERSONA,
            model="qwen3.5-local",  # Local free model for daily ops
        )
        self._setup_tools()

    def _setup_tools(self) -> None:
        """Register CEO-specific tools."""
        gh = GitHubTools(self.settings)

        self.register_tool(
            "create_issue",
            gh.create_issue,
            "Create a new GitHub Issue (epic, feature, opportunity)",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Issue title"},
                    "body": {"type": "string", "description": "Issue body in markdown"},
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Labels to apply",
                    },
                },
                "required": ["title", "body"],
            },
        )

        self.register_tool(
            "post_discussion",
            gh.create_discussion,
            "Post a message in GitHub Discussions",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Discussion title"},
                    "body": {"type": "string", "description": "Discussion body in markdown"},
                    "category": {
                        "type": "string",
                        "description": "Discussion category (Announcements, Strategy, Engineering, General)",
                    },
                },
                "required": ["title", "body", "category"],
            },
        )

        self.register_tool(
            "list_issues",
            gh.list_issues,
            "List open GitHub Issues with optional label filter",
            {
                "type": "object",
                "properties": {
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by labels",
                    },
                    "limit": {"type": "integer", "description": "Max results"},
                },
            },
        )

    async def perceive(self) -> list[dict]:
        """CEO perceives: new issues, discussion mentions, scheduled reviews."""
        gh = GitHubTools(self.settings)
        events = []

        # Check for issues needing CEO attention
        issues = await gh.list_issues(labels=["needs-ceo"], limit=5)
        for issue in issues:
            events.append(
                {
                    "type": "issue_needs_attention",
                    "title": issue["title"],
                    "body": issue["body"][:500],
                }
            )

        # Check for unresolved discussions in Strategy category
        discussions = await gh.list_discussions(category="Strategy", limit=5)
        for disc in discussions:
            events.append(
                {
                    "type": "strategy_discussion",
                    "title": disc["title"],
                    "body": disc["body"][:500],
                }
            )

        # If no events, trigger a proactive scan
        if not events:
            events.append(
                {
                    "type": "scheduled_review",
                    "title": "Periodic strategic review",
                    "body": "No pending items. Consider: reviewing open epics, identifying new opportunities, or posting a company update.",
                }
            )

        return events

    async def reflect(self, result: dict[str, Any]) -> None:
        """CEO reflects on decisions made."""
        self.log.info(
            "ceo_reflection",
            actions_taken=len(result.get("actions", [])),
            summary=result.get("summary", "")[:200],
        )
