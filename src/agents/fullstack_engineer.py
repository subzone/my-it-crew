"""Fullstack Engineer Agent — End-to-end feature development."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.chat_tools import ChatTools
from src.tools.github_tools import GitHubTools

FULLSTACK_ENGINEER_PERSONA = """You are a Senior Fullstack Engineer at My IT Crew.

Your responsibilities:
- Implement end-to-end features spanning backend APIs and frontend UIs
- Pick up tasks labeled 'status/ready' + 'dept/engineering' that need both backend and frontend work
- Create and review PRs for full-stack features
- Build integrations between services (APIs, webhooks, event handlers)
- Write comprehensive tests (unit + integration + e2e)
- Post updates to #engineering Slack channel
- Mention QA Engineer when a feature is ready for testing

Your workflow each cycle:
1. Check for tasks labeled 'status/ready' + 'dept/engineering' — pick up full-stack work
2. Check for open PRs — review for end-to-end correctness
3. Identify integration gaps between frontend and backend
4. Post to #engineering about progress
5. Post standup updates to #standups

Tech stack:
- Backend: Python 3.11+, asyncio, Pydantic, FastAPI, PostgreSQL
- Frontend: TypeScript, React, Next.js, Tailwind CSS
- Infrastructure: Kubernetes, GitHub Actions, Docker
- APIs: REST + OpenAPI, GraphQL where appropriate
- Testing: pytest, Vitest, Playwright

Coding standards:
- Type safety everywhere (Python type hints + TypeScript strict)
- API-first design — define contracts before implementation
- Error handling with proper user-facing messages
- Structured logging with structlog
- Tests cover happy path + edge cases + error conditions
- No hardcoded secrets — use environment variables
"""


class FullstackEngineerAgent(BaseAgent):
    """Fullstack Engineer agent that handles end-to-end feature development."""

    def __init__(self):
        super().__init__(agent_id="fullstack-engineer", persona=FULLSTACK_ENGINEER_PERSONA)
        self._setup_tools()

    def _setup_tools(self) -> None:
        gh = GitHubTools(self.settings)
        chat = ChatTools(self.settings)

        self.register_tool(
            "send_slack_message",
            chat.send_message,
            "Post to Slack (#engineering for discussions, #standups for updates)",
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
            "List open issues to find tasks",
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
            "Comment on an issue or provide review feedback",
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
        self.register_tool(
            "create_issue",
            gh.create_issue,
            "Create a task, bug report, or sub-task",
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
            "update_issue_labels",
            gh.update_issue_labels,
            "Update issue labels (e.g. mark as in-progress, done, blocked)",
            {
                "type": "object",
                "properties": {
                    "issue_number": {"type": "integer"},
                    "add": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Labels to add",
                    },
                    "remove": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Labels to remove",
                    },
                },
                "required": ["issue_number"],
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

        # Check for engineering tasks ready for pickup
        issues = await gh.list_issues(labels=["status/ready", "dept/engineering"], limit=5)
        for issue in issues:
            events.append(
                {
                    "type": "ready_task",
                    "title": issue["title"],
                    "body": f"Issue #{issue['number']}: {issue.get('body', '')[:500]}",
                }
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

        # Check for blocked tasks that might need help
        blocked = await gh.list_issues(labels=["status/blocked"], limit=3)
        for issue in blocked:
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
            "fullstack_engineer_reflection",
            actions_taken=len(result.get("actions", [])),
            summary=result.get("summary", "")[:200],
        )
