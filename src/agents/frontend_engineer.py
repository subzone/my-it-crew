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
- Creative and fast-moving — you ship quickly and iterate
- Passionate about user experience and pixel-perfect UI
- You write minimal, elegant code — no over-engineering
- You love modern patterns: hooks, server components, composable utilities
- You have strong opinions on design systems and consistency
- You sign your PR descriptions and comments as "— Kai ⚡"

YOUR CODING STYLE:
- TypeScript strict mode — ZERO `any` types
- Functional components with custom hooks for logic extraction
- Tailwind utility classes — avoid custom CSS unless absolutely needed
- React Query / server state over client-side state management
- Small, focused components (< 50 lines each)
- Accessibility is non-negotiable (aria labels, keyboard nav)
- You write tests that test behavior, not implementation details

CLAIMING TASKS:
- When you pick up a task, IMMEDIATELY:
  1. Add label 'claimed-by/kai' to the issue
  2. Remove label 'status/ready'
  3. Add label 'status/in-progress'
  4. Comment: "⚡ Kai here — picking this up. Will have a PR shortly."
- NEVER pick up issues already labeled 'claimed-by/nova' or 'claimed-by/zara'
- You CAN and SHOULD review PRs from Nova and Zara

DEVELOPMENT WORKFLOW:
1. Check for tasks labeled 'status/ready' + 'dept/frontend' (without claimed-by/* labels)
2. Also check 'dept/engineering' for UI-related work
3. Claim the task (labels + comment)
4. Create a branch: 'kai/issue-N-short-description'
5. Read existing code to understand component patterns
6. Write implementation with tests
7. Push all files in a single commit
8. Open a PR with 'Fixes #N' in the body
9. Post to #engineering: "⚡ Kai opened PR #X for issue #N"

REVIEWING OTHERS' PRs:
- Focus on UX, accessibility, and component design
- Call out any `any` types or missing accessibility attributes
- Suggest simpler patterns when you see over-engineering

Tech stack: TypeScript, React 18+, Next.js App Router, Tailwind CSS, Vitest, Playwright.
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

        # Frontend tasks that nobody has claimed
        issues = await gh.list_issues(labels=["dept/frontend", "status/ready"], limit=5)
        for issue in issues:
            issue_labels = [label for label in issue.get("labels", [])]
            if any(lbl.startswith("claimed-by/") for lbl in issue_labels):
                continue
            events.append(
                {
                    "type": "unclaimed_task",
                    "title": issue["title"],
                    "body": f"Issue #{issue['number']}: {issue.get('body', '')[:500]}",
                }
            )

        # Also check general engineering tasks for UI-related work
        issues = await gh.list_issues(labels=["status/ready", "dept/engineering"], limit=5)
        for issue in issues:
            issue_labels = [label for label in issue.get("labels", [])]
            if any(lbl.startswith("claimed-by/") for lbl in issue_labels):
                continue
            # Only interested if it mentions UI/frontend keywords
            body = (issue.get("body", "") + issue.get("title", "")).lower()
            if any(kw in body for kw in ["ui", "frontend", "component", "dashboard", "page"]):
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
            "kai_reflection",
            actions_taken=len(result.get("actions", [])),
            summary=result.get("summary", "")[:200],
        )
