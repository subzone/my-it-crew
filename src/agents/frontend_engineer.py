"""Frontend Engineer Agent — UI development and web applications."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.chat_tools import ChatTools
from src.tools.coding_tools import CodingTools
from src.tools.github_tools import GitHubTools

FRONTEND_ENGINEER_PERSONA = """You are a Senior Frontend Engineer at My IT Crew.

Your responsibilities:
- Pick up tasks labeled 'status/ready' + 'dept/frontend' and IMPLEMENT them
- Build and maintain web UIs, dashboards, and client-side applications
- Create feature branches, write code, commit, and open PRs
- Review PRs touching frontend code
- Post updates to #engineering Slack channel

Your development workflow:
1. Check for issues labeled 'status/ready' + 'dept/frontend'
2. For each task you pick up:
   a. Read the issue to understand requirements
   b. Create a feature branch (e.g. 'feat/issue-42-dashboard-ui')
   c. Read existing code to understand the codebase structure
   d. Write your implementation (components, styles, tests)
   e. Push all files in a single commit
   f. Open a PR linking the issue (use 'Fixes #N' in the body)
   g. Post to #engineering that you've opened a PR
3. Also review open PRs with frontend changes

Tech stack: TypeScript, React, Next.js, Tailwind CSS, Vite, Vitest, Playwright.

Coding standards:
- TypeScript strict mode — no `any` types
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
        code = CodingTools(self.settings)
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
            "List open PRs to review frontend changes",
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
            "Read a file from the repo",
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
            "push_files",
            code.push_files,
            "Push multiple files in a single commit",
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
            "Open a PR. Use 'Fixes #N' in body to link issues.",
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

        # Priority: frontend tasks to implement
        issues = await gh.list_issues(labels=["dept/frontend", "status/ready"], limit=3)
        for issue in issues:
            events.append(
                {
                    "type": "frontend_task",
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

        return events

    async def reflect(self, result: dict[str, Any]) -> None:
        self.log.info(
            "frontend_engineer_reflection",
            actions_taken=len(result.get("actions", [])),
            summary=result.get("summary", "")[:200],
        )
