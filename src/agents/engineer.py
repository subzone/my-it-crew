"""Engineer Agent — Implementation and code delivery."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.github_tools import GitHubTools


ENGINEER_PERSONA = """You are a Senior Software Engineer at My IT Crew, an AI-powered IT company.

Your responsibilities:
- Pick tasks from the current sprint (GitHub Issues assigned to you or labeled 'ready')
- Implement features and fixes
- Submit PRs with clear descriptions
- Respond to code review feedback
- Fix CI failures on your PRs
- Write tests for your implementations
- Update documentation when relevant

Your communication style:
- Precise and technical
- Document your decisions in PR descriptions
- Ask clarifying questions via Issue comments when requirements are unclear

You work via GitHub:
- Pick Issues labeled 'status/ready' + 'dept/engineering'
- Comment on Issues when you start work
- Create branches and submit PRs
- Respond to review comments

Tech stack: Python, asyncio, Pydantic, GitHub API, Kubernetes.
Current focus: Building the agent framework itself (this project).
"""


class EngineerAgent(BaseAgent):
    """Engineer agent that implements features and fixes."""

    def __init__(self):
        super().__init__(
            agent_id="engineer",
            persona=ENGINEER_PERSONA,
            model="qwen-flash",
        )
        self._setup_tools()

    def _setup_tools(self) -> None:
        """Register engineer-specific tools."""
        gh = GitHubTools(self.settings)

        self.register_tool(
            "list_issues",
            gh.list_issues,
            "List open issues to pick tasks",
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
            "Comment on an issue (e.g., to claim it or ask questions)",
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
            "create_pull_request",
            gh.create_pull_request,
            "Create a pull request",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "head": {"type": "string", "description": "Source branch"},
                    "base": {"type": "string", "description": "Target branch, usually main"},
                },
                "required": ["title", "body", "head"],
            },
        )

        self.register_tool(
            "list_pull_requests",
            gh.list_pull_requests,
            "List open PRs",
            {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                },
            },
        )

    async def perceive(self) -> list[dict]:
        """Engineer perceives: assigned issues, PR review comments, ready tasks."""
        gh = GitHubTools(self.settings)
        events = []

        # Check for ready tasks
        issues = await gh.list_issues(labels=["status/ready", "dept/engineering"], limit=5)
        for issue in issues:
            events.append({
                "type": "task_ready",
                "title": issue["title"],
                "body": f"Issue #{issue['number']}: {issue.get('body', '')[:400]}",
            })

        # Check for PRs with review comments (feedback to address)
        prs = await gh.list_pull_requests(limit=5)
        for pr in prs:
            if pr.get("review_comments", 0) > 0:
                events.append({
                    "type": "pr_feedback",
                    "title": f"Review feedback on: {pr['title']}",
                    "body": f"PR #{pr['number']} has review comments to address.",
                })

        return events

    async def reflect(self, result: dict[str, Any]) -> None:
        """Engineer reflects on work done."""
        self.log.info(
            "engineer_reflection",
            actions_taken=len(result.get("actions", [])),
            summary=result.get("summary", "")[:200],
        )
