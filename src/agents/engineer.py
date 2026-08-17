"""Engineer Agent — Code implementation and PR management."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.chat_tools import ChatTools
from src.tools.coding_tools import CodingTools
from src.tools.github_tools import GitHubTools

ENGINEER_PERSONA = """You are a Senior Software Engineer at My IT Crew.

Your responsibilities:
- Pick up tasks labeled 'status/ready' + 'dept/engineering' and IMPLEMENT them
- Write production-quality Python code with tests
- Create feature branches, write code, commit, and open PRs
- Review PRs created by others
- Fix issues found during QA review
- Post updates to #engineering Slack channel

Your development workflow:
1. Check for tasks labeled 'status/ready' + 'dept/engineering'
2. For each task you pick up:
   a. Read the issue to understand requirements
   b. Create a feature branch (e.g. 'feat/issue-42-add-user-api')
   c. Read existing code to understand the codebase
   d. Write your implementation (create/update files)
   e. Push all files in a single commit
   f. Open a PR linking the issue (use 'Fixes #N' in the body)
   g. Post to #engineering that you've opened a PR
3. Also review open PRs from others

Tech stack: Python 3.11+, asyncio, Pydantic, FastAPI, structlog, pytest.

Coding standards:
- Type hints on all functions
- Docstrings on all public methods
- Error handling with proper logging
- No hardcoded secrets — use environment variables
- Follow existing code patterns in the repo
"""


class EngineerAgent(BaseAgent):
    """Engineer agent that writes code and manages PRs."""

    def __init__(self):
        super().__init__(agent_id="engineer", persona=ENGINEER_PERSONA)
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
            "List open issues to find work",
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
            "Comment on an issue (e.g. to claim it or ask questions)",
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
            "Update issue labels (use to mark as in-progress when you start work)",
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
            "Create a new git branch for your work (e.g. 'feat/issue-42-user-api')",
            {
                "type": "object",
                "properties": {
                    "branch_name": {"type": "string", "description": "New branch name"},
                    "from_branch": {
                        "type": "string",
                        "description": "Source branch (default: main)",
                    },
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
                    "path": {"type": "string", "description": "File path (e.g. 'src/config.py')"},
                    "branch": {"type": "string", "description": "Branch to read from"},
                },
                "required": ["path"],
            },
        )
        self.register_tool(
            "get_directory_tree",
            code.get_directory_tree,
            "List files in a directory to understand project structure",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path ('' for root)"},
                    "branch": {"type": "string", "description": "Branch to read from"},
                },
            },
        )
        self.register_tool(
            "create_or_update_file",
            code.create_or_update_file,
            "Create or update a single file. For updates, provide the sha from get_file.",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string", "description": "Full file content"},
                    "message": {"type": "string", "description": "Commit message"},
                    "branch": {"type": "string"},
                    "sha": {
                        "type": "string",
                        "description": "File SHA for updates (from get_file). Omit for new files.",
                    },
                },
                "required": ["path", "content", "message", "branch"],
            },
        )
        self.register_tool(
            "push_files",
            code.push_files,
            "Push multiple files in a single commit. More efficient for multi-file changes.",
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
                        "description": "List of files with path and content",
                    },
                    "message": {"type": "string", "description": "Commit message"},
                    "branch": {"type": "string"},
                },
                "required": ["files", "message", "branch"],
            },
        )
        self.register_tool(
            "create_pull_request",
            code.create_pull_request,
            "Open a PR after pushing code. Use 'Fixes #N' in body to auto-close issues.",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string", "description": "PR description with 'Fixes #N'"},
                    "head": {"type": "string", "description": "Your feature branch"},
                    "base": {"type": "string", "description": "Target branch (default: main)"},
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

        # Priority: ready tasks to implement
        issues = await gh.list_issues(labels=["status/ready", "dept/engineering"], limit=3)
        for issue in issues:
            events.append(
                {
                    "type": "ready_task",
                    "title": issue["title"],
                    "body": f"Issue #{issue['number']}: {issue.get('body', '')[:500]}",
                }
            )

        # Also check for PRs needing review
        prs = await gh.list_pull_requests(limit=5)
        for pr in prs:
            events.append(
                {
                    "type": "pr_needs_review",
                    "title": pr["title"],
                    "body": f"PR #{pr['number']} by {pr.get('author', 'unknown')}: {pr.get('body', '')[:300]}",
                }
            )

        # Check for blocked tasks
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
