"""Fullstack Engineer Agent — End-to-end feature development."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.chat_tools import ChatTools
from src.tools.coding_tools import CodingTools
from src.tools.github_tools import GitHubTools

FULLSTACK_ENGINEER_PERSONA = """You are a Senior Fullstack Engineer at My IT Crew.

Your responsibilities:
- Pick up tasks labeled 'status/ready' + 'dept/engineering' and IMPLEMENT end-to-end features
- Write both backend (Python) and frontend (TypeScript/React) code
- Create feature branches, write code, commit, and open PRs
- Build integrations between services (APIs, webhooks, event handlers)
- Write comprehensive tests (unit + integration)
- Post updates to #engineering Slack channel

Your development workflow:
1. Check for tasks labeled 'status/ready' + 'dept/engineering'
2. For each task you pick up:
   a. Read the issue to understand requirements
   b. Create a feature branch (e.g. 'feat/issue-42-user-dashboard')
   c. Read existing code to understand the codebase
   d. Implement backend first (models, service layer, endpoints)
   e. Then implement frontend (components, hooks, pages)
   f. Add tests for both layers
   g. Push all files in a single commit
   h. Open a PR linking the issue (use 'Fixes #N' in the body)
   i. Post to #engineering that you've opened a PR
3. Also review open PRs for end-to-end correctness

Tech stack:
- Backend: Python 3.11+, asyncio, Pydantic, FastAPI, PostgreSQL
- Frontend: TypeScript, React, Next.js, Tailwind CSS
- Infrastructure: Kubernetes, Docker, GitHub Actions
- Testing: pytest, Vitest, Playwright

Coding standards:
- Type safety everywhere (Python type hints + TypeScript strict)
- API-first design — define contracts before implementation
- Error handling with proper user-facing messages
- Structured logging with structlog
- No hardcoded secrets — use environment variables
"""


class FullstackEngineerAgent(BaseAgent):
    """Fullstack Engineer agent that handles end-to-end feature development."""

    def __init__(self):
        super().__init__(agent_id="fullstack-engineer", persona=FULLSTACK_ENGINEER_PERSONA)
        self._setup_tools()

    def _setup_tools(self) -> None:
        gh = GitHubTools(self.settings)
        code = CodingTools(self.settings)
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
            "Comment on an issue (claim it or ask questions)",
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
            "update_issue_labels",
            gh.update_issue_labels,
            "Update issue labels (mark as in-progress when starting work)",
            {
                "type": "object",
                "properties": {
                    "issue_number": {"type": "integer"},
                    "add": {"type": "array", "items": {"type": "string"}},
                    "remove": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["issue_number"],
            },
        )
        # Coding tools
        self.register_tool(
            "create_branch",
            code.create_branch,
            "Create a new git branch for your work",
            {
                "type": "object",
                "properties": {
                    "branch_name": {"type": "string"},
                    "from_branch": {"type": "string"},
                },
                "required": ["branch_name"],
            },
        )
        self.register_tool(
            "get_file",
            code.get_file,
            "Read a file from the repo to understand existing code",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "branch": {"type": "string"},
                },
                "required": ["path"],
            },
        )
        self.register_tool(
            "get_directory_tree",
            code.get_directory_tree,
            "List files in a directory",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "branch": {"type": "string"},
                },
            },
        )
        self.register_tool(
            "create_or_update_file",
            code.create_or_update_file,
            "Create or update a single file. For updates provide sha from get_file.",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "message": {"type": "string"},
                    "branch": {"type": "string"},
                    "sha": {"type": "string"},
                },
                "required": ["path", "content", "message", "branch"],
            },
        )
        self.register_tool(
            "push_files",
            code.push_files,
            "Push multiple files in a single commit. Best for multi-file features.",
            {
                "type": "object",
                "properties": {
                    "files": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"},
                                "content": {"type": "string"},
                            },
                            "required": ["path", "content"],
                        },
                    },
                    "message": {"type": "string"},
                    "branch": {"type": "string"},
                },
                "required": ["files", "message", "branch"],
            },
        )
        self.register_tool(
            "create_pull_request",
            code.create_pull_request,
            "Open a PR. Use 'Fixes #N' in body to auto-close issues.",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "head": {"type": "string"},
                    "base": {"type": "string"},
                },
                "required": ["title", "body", "head"],
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
        issues = await gh.list_issues(labels=["status/ready", "dept/engineering"], limit=3)
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
