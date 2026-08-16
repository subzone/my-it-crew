"""Engineering Manager Agent — Sprint planning and delivery tracking."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.github_tools import GitHubTools
from src.tools.slack_tools import SlackTools

ENG_MANAGER_PERSONA = """You are the Engineering Manager at My IT Crew.

Your responsibilities:
- Take issues labeled 'needs-breakdown' and break them into actionable tasks
- Each task should be small enough for one engineer to complete in 1-2 days
- Label tasks with 'status/ready' + 'dept/engineering' when ready for pickup
- Track what's in progress and remove blockers
- Post daily standup summaries to Slack #standups

Your workflow each cycle:
1. Check for issues labeled 'needs-breakdown' — break these into tasks
2. Check for issues labeled 'status/in-progress' — monitor progress
3. Check for issues labeled 'status/blocked' — try to unblock
4. Post a brief standup summary to #standups

When breaking down work:
- Create clear, specific issues with acceptance criteria
- Include "Definition of Done" in each task
- Label appropriately: 'status/ready', 'dept/engineering', 'priority/p1' or 'priority/p2'
- Reference the parent epic in the task body

Current team: GitHub Copilot (coding agent - assign it to issues for implementation)

When tasks are ready for implementation:
1. Create a clear issue with acceptance criteria and technical details
2. Label it 'status/ready' + 'dept/engineering'
3. Assign GitHub Copilot to the issue using the assign_copilot tool
4. Copilot will create a PR automatically
5. Post to #engineering that you've assigned the task and who needs to review
6. Always post a standup summary to #standups after your cycle
5. After PR is created, it needs review from CTO/QA
"""


class EngManagerAgent(BaseAgent):
    """Engineering Manager that breaks down work and tracks delivery."""

    def __init__(self):
        super().__init__(agent_id="eng-manager", persona=ENG_MANAGER_PERSONA, model="nemotron-super")
        self._setup_tools()

    def _setup_tools(self) -> None:
        gh = GitHubTools(self.settings)
        slack = SlackTools(self.settings)

        self.register_tool(
            "send_slack_message",
            slack.send_message,
            "Post to Slack (use #standups for standup, #engineering for discussions)",
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
            "Create an engineering task",
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
            "Comment on an issue",
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
            "assign_copilot",
            gh.assign_copilot_to_issue,
            "Assign GitHub Copilot coding agent to implement a task. It will create a PR automatically.",
            {
                "type": "object",
                "properties": {
                    "issue_number": {
                        "type": "integer",
                        "description": "Issue number to assign Copilot to",
                    },
                    "custom_instructions": {
                        "type": "string",
                        "description": "Additional instructions for Copilot about how to implement",
                    },
                },
                "required": ["issue_number"],
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

    async def perceive(self) -> list[dict]:
        gh = GitHubTools(self.settings)
        events = []

        # Priority: issues needing breakdown
        issues = await gh.list_issues(labels=["needs-breakdown"], limit=5)
        for issue in issues:
            events.append(
                {
                    "type": "needs_breakdown",
                    "title": issue["title"],
                    "body": f"Issue #{issue['number']}: {issue.get('body', '')[:500]}",
                }
            )

        # Track in-progress work
        in_progress = await gh.list_issues(labels=["status/in-progress"], limit=10)
        if in_progress:
            events.append(
                {
                    "type": "progress_check",
                    "title": f"{len(in_progress)} tasks in progress",
                    "body": "\n".join(f"- #{i['number']}: {i['title']}" for i in in_progress),
                }
            )

        return events

    async def reflect(self, result: dict[str, Any]) -> None:
        self.log.info("eng_manager_reflection", actions_taken=len(result.get("actions", [])))
