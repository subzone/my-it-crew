"""Engineer Agent — Code review and PR management."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.github_tools import GitHubTools
from src.tools.slack_tools import SlackTools

ENGINEER_PERSONA = """You are a Senior Software Engineer at My IT Crew.

Your responsibilities:
- Review PRs created by Copilot and other contributors
- Ensure code quality, test coverage, and documentation
- Comment on PRs with feedback or approve them
- Pick up tasks labeled 'status/ready' + 'dept/engineering' that Copilot hasn't handled
- Fix issues found during QA review
- Post updates to #engineering Slack channel
- Mention QA Engineer when a PR is ready for testing
- Mention Eng Manager when a PR is blocked or needs discussion
- Always post your review status to #engineering

Your workflow each cycle:
1. Check for open PRs — review them for quality
2. Check for tasks that are stuck or need manual intervention
3. Comment on PRs with approval or change requests
4. Post to #engineering about PR status

Tech stack: Python, asyncio, Pydantic, GitHub API, Kubernetes.
"""


class EngineerAgent(BaseAgent):
    """Engineer agent that reviews code and manages PRs."""

    def __init__(self):
        super().__init__(agent_id="engineer", persona=ENGINEER_PERSONA)
        self._setup_tools()

    def _setup_tools(self) -> None:
        gh = GitHubTools(self.settings)
        slack = SlackTools(self.settings)

        self.register_tool(
            "send_slack_message",
            slack.send_message,
            "Post to Slack #engineering",
            {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["channel", "text"],
            },
        )
        self.register_tool(
            "list_issues",
            gh.list_issues,
            "List open issues",
            {
                "type": "object",
                "properties": {
                    "labels": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer"},
                },
            },
        )
        self.register_tool(
            "comment_on_issue",
            gh.comment_on_issue,
            "Comment on an issue or provide code review feedback",
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
            "list_pull_requests",
            gh.list_pull_requests,
            "List open PRs to review",
            {
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
            },
        )

    async def perceive(self) -> list[dict]:
        gh = GitHubTools(self.settings)
        events = []

        # Check for PRs needing review
        prs = await gh.list_pull_requests(limit=5)
        for pr in prs:
            events.append(
                {
                    "type": "pr_needs_review",
                    "title": pr["title"],
                    "body": f"PR #{pr['number']} by {pr.get('author', 'unknown')}: {pr.get('body', '')[:300]}",
                }
            )

        # Check for stuck tasks
        issues = await gh.list_issues(labels=["status/blocked"], limit=5)
        for issue in issues:
            events.append(
                {
                    "type": "blocked_task",
                    "title": issue["title"],
                    "body": f"Issue #{issue['number']}: {issue.get('body', '')[:300]}",
                }
            )

        return events

    async def reflect(self, result: dict[str, Any]) -> None:
        self.log.info(
            "engineer_reflection",
            actions_taken=len(result.get("actions", [])),
            summary=result.get("summary", "")[:200],
        )
