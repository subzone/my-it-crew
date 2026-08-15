"""CTO Agent — Technical vision and architecture."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.github_tools import GitHubTools


CTO_PERSONA = """You are the CTO of an AI-powered IT company called My IT Crew.

Your responsibilities:
- Define technical roadmap and architecture
- Review and approve architecture decisions (ADRs)
- Evaluate technical feasibility of new initiatives
- Review PRs for architectural compliance
- Manage tech debt and propose refactors
- Mentor and guide engineering team
- Respond to CEO's strategic proposals with technical assessment

Your communication style:
- Technical but accessible
- Evidence-based, reference best practices
- Pragmatic — balance ideal vs. deliverable

You communicate via GitHub Discussions (category: Engineering for tech topics, Strategy for C-suite decisions).
You review PRs and create Issues for technical work.

When evaluating a technical proposal:
1. Assess complexity (T-shirt sizing: S/M/L/XL)
2. Identify risks and dependencies
3. Propose architecture approach
4. Break into high-level tasks for Engineering Manager

Current tech stack: Python, Kubernetes, LiteLLM, GitHub Actions, Weaviate.
Current team: CEO, CTO (you), Engineer.
"""


class CTOAgent(BaseAgent):
    """CTO agent with technical leadership capabilities."""

    def __init__(self):
        super().__init__(
            agent_id="cto",
            persona=CTO_PERSONA,
            model="qwen3.5-local",  # Local free model for daily ops
        )
        self._setup_tools()

    def _setup_tools(self) -> None:
        """Register CTO-specific tools."""
        gh = GitHubTools(self.settings)

        self.register_tool(
            "create_issue",
            gh.create_issue,
            "Create a GitHub Issue for technical work",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "labels": {"type": "array", "items": {"type": "string"}},
                    "assignee": {"type": "string", "description": "GitHub username to assign"},
                },
                "required": ["title", "body"],
            },
        )

        self.register_tool(
            "comment_on_issue",
            gh.comment_on_issue,
            "Add a comment to an existing GitHub Issue",
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
            "post_discussion",
            gh.create_discussion,
            "Post in GitHub Discussions",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "category": {"type": "string"},
                },
                "required": ["title", "body", "category"],
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
            "list_pull_requests",
            gh.list_pull_requests,
            "List open pull requests for review",
            {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max PRs to return"},
                },
            },
        )

    async def perceive(self) -> list[dict]:
        """CTO perceives: PRs to review, issues tagged for CTO, tech discussions."""
        gh = GitHubTools(self.settings)
        events = []

        # Check PRs needing review
        prs = await gh.list_pull_requests(limit=5)
        for pr in prs:
            events.append({
                "type": "pr_needs_review",
                "title": pr["title"],
                "body": f"PR #{pr['number']} by {pr.get('author', 'unknown')}: {pr.get('body', '')[:300]}",
            })

        # Check issues needing CTO input
        issues = await gh.list_issues(labels=["needs-cto"], limit=5)
        for issue in issues:
            events.append({
                "type": "issue_needs_cto",
                "title": issue["title"],
                "body": issue["body"][:500],
            })

        # Check engineering discussions
        discussions = await gh.list_discussions(category="Engineering", limit=3)
        for disc in discussions:
            events.append({
                "type": "engineering_discussion",
                "title": disc["title"],
                "body": disc["body"][:300],
            })

        return events

    async def reflect(self, result: dict[str, Any]) -> None:
        """CTO reflects on technical decisions."""
        self.log.info(
            "cto_reflection",
            actions_taken=len(result.get("actions", [])),
            summary=result.get("summary", "")[:200],
        )
