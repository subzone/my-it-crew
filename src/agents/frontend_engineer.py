"""Kai — Frontend Engineer Agent.

Kai is creative, fast-moving, and focused on user experience.
He writes elegant TypeScript/React code with a flair for clean UI patterns.
Model: openrouter/qwen/qwen3-coder (fast, code-specialized).
"""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.chat_tools import ChatTools
from src.tools.coding_tools import CodingTools
from src.tools.github_tools import GitHubTools

KAI_PERSONA = """You are Kai, a Senior Frontend Engineer at My IT Crew.

PERSONALITY:
- Creative and fast-moving — you ship real UI components
- Passionate about user experience and clean interfaces
- You sign your PR descriptions and comments as "— Kai ⚡"

PRODUCTION CODING STANDARDS (ZERO-STUB POLICY):
- NEVER write 1-line `# TODO` comments or dummy template files (e.g. 'path/to/file', 'PR title').
- NEVER commit markdown-only design notes for an implementation ticket without code.
- ALWAYS ground your work in existing codebase patterns:
  - Frontend components belong in web/ or src/components/.
  - APIs and integrations belong in `src/`.
- MANDATORY UNIT TESTS: Every PR MUST include comprehensive test cases in tests/ or component tests with mocked data.
- DESCRIPTIVE PRs: Open PRs with clear descriptive titles (e.g., `feat(ui): implement ticket triage dashboard component`) and detailed body referencing `Fixes #N`.

DEVELOPMENT WORKFLOW:
1. Check for tasks labeled 'status/ready' + 'dept/frontend' or 'dept/engineering'
2. Claim the task: add 'claimed-by/kai', 'status/in-progress', remove 'status/ready'
3. Create a branch: 'kai/issue-N-short-description'
4. Read existing code using `get_file` to understand patterns
5. Write complete, functional implementation and tests using `push_files`
6. Open a PR with clear title, descriptive body, and 'Fixes #N'
7. Post to #engineering: "⚡ Kai opened PR #X for issue #N"

Tech stack: TypeScript, React, Next.js, Tailwind CSS, Python.
"""


class FrontendEngineerAgent(BaseAgent):
    """Kai — creative frontend engineer with UX focus."""

    def __init__(self):
        settings_temp = __import__("src.config", fromlist=["Settings"]).Settings()
        super().__init__(
            agent_id="kai",
            persona=KAI_PERSONA,
            model=settings_temp.model_kai,
        )
        # Use Kai's own Mattermost bot token
        if self.settings.mattermost_token_kai:
            self.settings.mattermost_token = self.settings.mattermost_token_kai
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
            "List open issues. Filter for unclaimed frontend tasks.",
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
            "Comment on an issue (use to claim tasks or give feedback)",
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
            "Add/remove labels. Use to claim: add=['claimed-by/kai','status/in-progress'], remove=['status/ready']",
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
            "List open PRs to review (especially from Nova and Zara)",
            {
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
            },
        )
        # Coding tools
        self.register_tool(
            "create_branch",
            code.create_branch,
            "Create a branch. Use pattern: 'kai/issue-N-description'",
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
            "Open a PR. Always include 'Fixes #N' and sign as Kai.",
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

    async def _enrich_context(self, gh: GitHubTools, body: str) -> str:
        """Propagate parent epic architectural context to Kai."""
        import re

        match = re.search(r"(?:Parent Epic|Epic|parent):\s*#?(\d+)", body, re.IGNORECASE)
        if not match:
            return body[:500]
        try:
            parent_num = int(match.group(1))
            parent = await gh.get_issue(parent_num)
            if parent and "title" in parent:
                return (
                    f"{body[:400]}\n\n[Architecture Note from Parent Epic #{parent_num}: "
                    f"'{parent.get('title')}']"
                )
        except Exception:
            pass
        return body[:500]

    def _extract_priority_tag(self, issue: dict) -> str:
        """Extract formatted priority tag from issue labels."""
        for label in issue.get("labels", []):
            if label.lower().startswith("priority/"):
                return label.upper()
        return "PRIORITY/P2"

    async def _sort_and_filter_tasks(self, gh: GitHubTools, issues: list[dict]) -> list[dict]:
        """Filter out claimed/blocked tasks and sort strictly by priority (P0 > P1 > P2)."""
        import re

        priority_weights = {
            "priority/p0": 0,
            "priority/critical": 0,
            "priority/p1": 1,
            "priority/high": 1,
            "priority/p2": 2,
            "priority/medium": 2,
            "priority/p3": 3,
            "priority/low": 3,
        }

        eligible = []
        for issue in issues:
            labels = issue.get("labels", [])
            if any(lbl.startswith("claimed-by/") for lbl in labels):
                continue
            if "status/blocked" in labels:
                continue

            body = issue.get("body", "")
            match = re.search(
                r"(?:depends on|blocked by|prerequisite):\s*#?(\d+)", body, re.IGNORECASE
            )
            if match:
                dep_num = int(match.group(1))
                try:
                    dep_issue = await gh.get_issue(dep_num)
                    if dep_issue and dep_issue.get("state") == "open":
                        continue
                except Exception:
                    pass

            weights = [priority_weights.get(lbl.lower(), 10) for lbl in labels]
            rank = min(weights) if weights else 10
            eligible.append((rank, issue))

        eligible.sort(key=lambda x: x[0])
        return [item[1] for item in eligible]

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

        # Check for open PRs authored by Kai
        prs = await gh.list_pull_requests(limit=10)
        my_open_prs = [
            pr
            for pr in prs
            if "kai" in pr.get("author", "").lower() or pr.get("head", "").startswith("kai/")
        ]
        for pr in my_open_prs:
            if "status/qa-failed" in pr.get("labels", []):
                events.append(
                    {
                        "type": "my_pr_failed_qa",
                        "title": f"Fix QA Issues on PR #{pr['number']}",
                        "body": f"QA reported issues on your PR #{pr['number']} ('{pr['title']}'). Please inspect comments, fix the implementation on branch '{pr.get('head')}', and push fixes!",
                    }
                )

        # PRIORITY 1: Continue work I already claimed
        my_tasks = await gh.list_issues(labels=["claimed-by/kai", "status/in-progress"], limit=3)
        for issue in my_tasks:
            enriched_body = await self._enrich_context(gh, issue.get("body", ""))
            events.append(
                {
                    "type": "my_in_progress_task",
                    "title": issue["title"],
                    "body": f"Issue #{issue['number']} (YOUR task — continue implementing): {enriched_body}",
                }
            )

        # PRIORITY 2: Only look for new tasks if I have NO tasks in progress and NO open PRs in flight (WIP limit = 1)
        if not my_tasks and not my_open_prs:
            # Frontend tasks first
            fe_issues = await gh.list_issues(labels=["dept/frontend", "status/ready"], limit=10)
            eng_issues = await gh.list_issues(labels=["status/ready", "dept/engineering"], limit=10)
            all_raw = fe_issues + [
                i
                for i in eng_issues
                if any(
                    kw in (i.get("body", "") + i.get("title", "")).lower()
                    for kw in ["ui", "frontend", "component", "dashboard", "page"]
                )
            ]
            sorted_issues = await self._sort_and_filter_tasks(gh, all_raw)
            for issue in sorted_issues[:3]:
                enriched_body = await self._enrich_context(gh, issue.get("body", ""))
                events.append(
                    {
                        "type": "unclaimed_task",
                        "title": f"[{self._extract_priority_tag(issue)}] {issue['title']}",
                        "body": f"Issue #{issue['number']}: {enriched_body}",
                    }
                )

        # PRs to review from teammates (exclude my own PRs)
        for pr in prs:
            if pr not in my_open_prs:
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
            "kai_reflection",
            actions_taken=len(result.get("actions", [])),
            summary=result.get("summary", "")[:200],
        )
