"""Frontend Engineer Agent — UI development and web applications."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.chat_tools import ChatTools
from src.tools.github_tools import GitHubTools

FRONTEND_ENGINEER_PERSONA = """You are a Senior Frontend Engineer at My IT Crew.

Your responsibilities:
- Build and maintain web UIs, dashboards, and client-side applications
- Review PRs touching frontend code (React, TypeScript, CSS)
- Pick up tasks labeled 'status/ready' + 'dept/frontend' or 'dept/engineering' with frontend scope
- Ensure accessibility, responsiveness, and performance
- Write tests using Vitest/Playwright/Testing Library
- Post updates to #engineering Slack channel

Your workflow each cycle:
1. Check for open PRs with frontend changes — review them
2. Check for issues labeled 'status/ready' + 'dept/frontend' — pick up and implement
3. Comment on PRs with feedback or approve them
4. Post to #engineering about completed work

Tech stack: TypeScript, React, Next.js, Tailwind CSS, Vite, Vitest, Playwright.
When building dashboards for the IT crew, use clean data visualization.

Coding standards:
- TypeScript strict mode
- Component-driven architecture
- Accessible (WCAG 2.1 AA)
- Responsive design (mobile-first)
- Unit tests for logic, integration tests for flows
"""


class FrontendEngineerAgent(BaseAgent):
    """Frontend Engineer agent that builds UIs and reviews frontend PRs."""

    def __init__(self):
        super().__init__(agent_id="frontend-engineer", persona=FRONTEND_ENGINEER_PERSONA)
        self._setup_tools()

    def _setup_tools(self) -> None:
        gh = GitHubTools(self.settings)
        chat = ChatTools(self.settings)

        self.register_tool(
            "send_slack_message",
            chat.send_message,
            "Post to Slack #engineering or #standups",
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
            "List open issues to find frontend tasks",
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
            "List open PRs to review frontend changes",
            {
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
            },
        )
        self.register_tool(
            "create_issue",
            gh.create_issue,
            "Create a frontend task or bug report",
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

    async def perceive(self) -> list[dict]:
        gh = GitHubTools(self.settings)
        events = []

        # Check DMs
        chat = ChatTools(self.settings)
        dms = await chat.get_direct_messages(limit=3)
        for dm in dms:
            events.append(
                {"type": "direct_message", "title": "DM received", "body": dm["text"][:500]}
            )

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

        # Check for frontend tasks
        issues = await gh.list_issues(labels=["dept/frontend", "status/ready"], limit=5)
        for issue in issues:
            events.append(
                {
                    "type": "frontend_task",
                    "title": issue["title"],
                    "body": f"Issue #{issue['number']}: {issue.get('body', '')[:300]}",
                }
            )

        return events

    async def reflect(self, result: dict[str, Any]) -> None:
        self.log.info(
            "frontend_engineer_reflection",
            actions_taken=len(result.get("actions", [])),
            summary=result.get("summary", "")[:200],
        )
