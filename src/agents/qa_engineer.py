"""QA Engineer Agent — Testing and quality assurance."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.chat_tools import ChatTools
from src.tools.github_tools import GitHubTools

QA_PERSONA = """You are a QA Engineer at My IT Crew.

Your responsibilities:
- Review PRs for testability and potential bugs
- Create bug reports (GitHub Issues) when you find problems
- Validate that completed work meets acceptance criteria
- Write test plans for new features
- Run regression checks after deployments
- Label issues as 'status/qa-passed' or create bugs
- Post QA results to #engineering Slack channel
- Mention the Engineer when a PR needs fixes
- Mention the Eng Manager when QA is complete

Your workflow:
1. Check for PRs needing QA review
2. Check for issues labeled 'status/in-review' or 'needs-qa'
3. Validate implementations against requirements
4. File bugs with clear reproduction steps
5. Approve work that meets quality standards
"""


class QAEngineerAgent(BaseAgent):
    """QA Engineer that validates quality and files bugs."""

    def __init__(self):
        super().__init__(agent_id="qa-engineer", persona=QA_PERSONA)
        self._setup_tools()

    def _setup_tools(self) -> None:
        gh = GitHubTools(self.settings)
        chat = ChatTools(self.settings)

        self.register_tool(
            "send_slack_message",
            chat.send_message,
            "Post to Slack (use #engineering for updates)",
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
            "create_issue",
            gh.create_issue,
            "Create a bug report or test task",
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
            "List open PRs to review",
            {
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
            },
        )

    async def perceive(self) -> list[dict]:
        gh = GitHubTools(self.settings)
        events = []

        # PRs needing QA
        prs = await gh.list_pull_requests(limit=5)
        for pr in prs:
            events.append(
                {
                    "type": "pr_needs_qa",
                    "title": pr["title"],
                    "body": f"PR #{pr['number']} by {pr.get('author', 'unknown')}",
                }
            )

        # Issues needing QA validation
        issues = await gh.list_issues(labels=["needs-qa"], limit=5)
        for issue in issues:
            events.append(
                {
                    "type": "needs_qa_validation",
                    "title": issue["title"],
                    "body": f"Issue #{issue['number']}: {issue.get('body', '')[:300]}",
                }
            )

        return events

    async def reflect(self, result: dict[str, Any]) -> None:
        self.log.info("qa_reflection", actions_taken=len(result.get("actions", [])))
