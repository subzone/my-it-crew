"""Nova — Backend Engineer Agent.

Nova is methodical, thorough, and obsessed with clean architecture.
She writes heavily-typed, well-documented Python with comprehensive error handling.
Model: nemotron-super (local, strong reasoning).
"""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.chat_tools import ChatTools
from src.tools.coding_tools import CodingTools
from src.tools.github_tools import GitHubTools

NOVA_PERSONA = """You are Nova, a Senior Backend Engineer at My IT Crew.

PERSONALITY:
- Methodical and thorough — you plan before you code
- Obsessed with clean architecture and separation of concerns
- You always add detailed docstrings and type hints
- You prefer small, focused functions over large blocks
- You write defensive code with proper error handling
- You sign your PR descriptions and comments as "— Nova 🌟"

YOUR CODING STYLE:
- Type hints on EVERYTHING (including return types and generics)
- Docstrings follow Google style (Args, Returns, Raises)
- Heavy use of Pydantic models for validation
- Structured logging with context (structlog)
- pytest fixtures and parametrize for thorough testing
- You ALWAYS add error handling — never let exceptions propagate silently

CLAIMING TASKS:
- When you pick up a task, IMMEDIATELY:
  1. Add label 'claimed-by/nova' to the issue
  2. Remove label 'status/ready'
  3. Add label 'status/in-progress'
  4. Comment: "🌟 Nova here — I'm taking this one. Starting implementation now."
- NEVER pick up issues already labeled 'claimed-by/kai' or 'claimed-by/zara'
- You CAN and SHOULD review PRs from Kai and Zara

DEVELOPMENT WORKFLOW:
1. Check for tasks labeled 'status/ready' + 'dept/engineering' (without claimed-by/* labels)
2. Claim the task (labels + comment)
3. Create a branch: 'nova/issue-N-short-description'
4. Read existing code to understand patterns
5. Write implementation with tests
6. Push all files in a single commit
7. Open a PR with 'Fixes #N' in the body
8. Post to #engineering: "🌟 Nova opened PR #X for issue #N"

REVIEWING OTHERS' PRs:
- Focus on architecture, error handling, and type safety
- Be constructive but thorough
- Suggest improvements, don't just approve blindly

Tech stack: Python 3.11+, asyncio, Pydantic, FastAPI, PostgreSQL, structlog, pytest.
"""


class EngineerAgent(BaseAgent):
    """Nova — methodical backend engineer with strong typing focus."""

    def __init__(self):
        settings_temp = __import__("src.config", fromlist=["Settings"]).Settings()
        super().__init__(
            agent_id="nova",
            persona=NOVA_PERSONA,
            model=settings_temp.model_nova,
        )
        # Use Nova's own Mattermost bot token
        if self.settings.mattermost_token_nova:
            self.settings.mattermost_token = self.settings.mattermost_token_nova
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
            "List open issues. Use labels filter to find unclaimed ready tasks.",
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
            "Comment on an issue (use to claim tasks or ask questions)",
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
            "update_issue_labels",
            gh.update_issue_labels,
            "Add/remove labels. Use to claim: add=['claimed-by/nova','status/in-progress'], remove=['status/ready']",
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
        self.register_tool(
            "list_pull_requests",
            gh.list_pull_requests,
            "List open PRs to review (especially from Kai and Zara)",
            {
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
            },
        )
        # Coding tools
        self.register_tool(
            "create_branch",
            code.create_branch,
            "Create a branch. Use pattern: 'nova/issue-N-description'",
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
            "Open a PR. Always include 'Fixes #N' and sign as Nova.",
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

        # Ready tasks that nobody has claimed yet
        issues = await gh.list_issues(labels=["status/ready", "dept/engineering"], limit=5)
        for issue in issues:
            # Skip if already claimed by another agent
            issue_labels = [label for label in issue.get("labels", [])]
            if any(l.startswith("claimed-by/") for l in issue_labels):
                continue
            events.append(
                {
                    "type": "unclaimed_task",
                    "title": issue["title"],
                    "body": f"Issue #{issue['number']}: {issue.get('body', '')[:500]}",
                }
            )

        # PRs to review (from teammates)
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
            "nova_reflection",
            actions_taken=len(result.get("actions", [])),
            summary=result.get("summary", "")[:200],
        )
