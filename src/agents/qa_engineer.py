"""QA Engineer Agent — Testing and quality assurance."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.chat_tools import ChatTools
from src.tools.github_tools import GitHubTools

QA_PERSONA = """You are the Senior QA Engineer at My IT Crew.

Your core mission: Prevent low-quality, stub, or broken code from reaching production.

STRICT CODE REVIEW CRITERIA:
1. ALWAYS inspect PR files using `get_pull_request_files(pr_number)` before making any decision.
2. REJECT (label 'status/qa-failed') if the PR:
   - Contains 1-line '# TODO' stubs or placeholder files (e.g. 'path/to/file1', empty comment files)
   - Contains only markdown documentation for an implementation ticket
   - Has fewer than 10 lines of code for non-trivial features
   - Lacks corresponding unit tests in tests/test_*.py
   - Uses hardcoded localhost dependencies without mocking
3. APPROVE (label 'status/qa-passed') ONLY IF:
   - Complete, functional Python classes or Kubernetes YAML manifests exist
   - Unit tests are included in tests/
   - The implementation directly satisfies the linked issue's acceptance criteria

When rejecting:
- Comment on the PR specifying exactly what needs rework (e.g., "QA Rejected: PR contains only placeholder comments. Please implement actual logic and tests.")
- Update labels: add 'status/qa-failed', remove 'status/in-review'
- Post alert to #engineering

When approving:
- Comment on the PR: "QA Approved: Code verified and unit tests present."
- Update labels: add 'status/qa-passed', remove 'status/in-review'
- Post to #engineering so DevOps can merge!
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
            "Comment on an issue or PR with QA review notes",
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
            "get_pull_request_files",
            gh.get_pull_request_files,
            "Inspect the files and code patches inside a pull request to verify implementation quality",
            {
                "type": "object",
                "properties": {
                    "pr_number": {"type": "integer"},
                },
                "required": ["pr_number"],
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
            "update_issue_labels",
            gh.update_issue_labels,
            "Add or remove labels from an issue or PR (e.g. add 'status/qa-passed' to approve PR, or 'status/qa-failed' if bugs found)",
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
            "close_issue",
            gh.close_issue,
            "Close an issue if testing is verified and complete",
            {
                "type": "object",
                "properties": {
                    "issue_number": {"type": "integer"},
                    "comment": {"type": "string"},
                },
                "required": ["issue_number"],
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
        # Check DMs
        chat = ChatTools(self.settings)
        dms = await chat.get_direct_messages(limit=3)
        for dm in dms:
            events.append(
                {"type": "direct_message", "title": "DM received", "body": dm["text"][:500]}
            )

        # PRs needing QA (exclude already validated PRs)
        prs = await gh.list_pull_requests(limit=10)
        for pr in prs:
            pr_labels = pr.get("labels", [])
            if "status/qa-passed" in pr_labels or "status/qa-failed" in pr_labels:
                continue
            events.append(
                {
                    "type": "pr_needs_qa",
                    "title": pr["title"],
                    "body": f"PR #{pr['number']} by {pr.get('author', 'unknown')}: {pr.get('body', '')[:300]}",
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
