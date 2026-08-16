"""Engineering Manager Agent — Sprint planning and delivery tracking."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.github_tools import GitHubTools

ENG_MANAGER_PERSONA = """You are the Engineering Manager at My IT Crew.

Your responsibilities:
- Break epics into actionable tasks (GitHub Issues)
- Assign tasks to engineers by labeling them 'status/ready' + 'dept/engineering'
- Track sprint progress and remove blockers
- Run daily standups (post summaries in Discussions)
- Ensure PRs get reviewed and merged promptly
- Report delivery status to CTO

Your workflow:
1. Check for new epics or issues labeled 'needs-breakdown'
2. Break them into smaller tasks with clear acceptance criteria
3. Label tasks as 'status/ready' + 'dept/engineering' when ready for pickup
4. Monitor in-progress work and flag blockers
5. Close completed work and report to CTO

Current team: 1 Backend Engineer, 1 Frontend Engineer, 1 DevOps Engineer
"""


class EngManagerAgent(BaseAgent):
    """Engineering Manager that breaks down work and tracks delivery."""

    def __init__(self):
        super().__init__(agent_id="eng-manager", persona=ENG_MANAGER_PERSONA)
        self._setup_tools()

    def _setup_tools(self) -> None:
        gh = GitHubTools(self.settings)
        self.register_tool(
            "create_issue",
            gh.create_issue,
            "Create a GitHub Issue (task, subtask)",
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
            "Comment on an issue",
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
            "List issues",
            {
                "type": "object",
                "properties": {
                    "labels": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer"},
                },
            },
        )
        self.register_tool(
            "list_pull_requests",
            gh.list_pull_requests,
            "List open PRs",
            {
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
            },
        )

    async def perceive(self) -> list[dict]:
        gh = GitHubTools(self.settings)
        events = []

        # Epics needing breakdown
        issues = await gh.list_issues(labels=["epic"], limit=5)
        for issue in issues:
            events.append(
                {
                    "type": "epic_needs_breakdown",
                    "title": issue["title"],
                    "body": f"Issue #{issue['number']}: {issue.get('body', '')[:400]}",
                }
            )

        # Check stale in-progress work
        in_progress = await gh.list_issues(labels=["status/in-progress"], limit=10)
        for issue in in_progress:
            events.append(
                {
                    "type": "work_in_progress",
                    "title": issue["title"],
                    "body": f"Issue #{issue['number']} is in progress",
                }
            )

        return events

    async def reflect(self, result: dict[str, Any]) -> None:
        self.log.info("eng_manager_reflection", actions_taken=len(result.get("actions", [])))
