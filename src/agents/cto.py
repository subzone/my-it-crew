"""CTO Agent — Technical vision and architecture."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.chat_tools import ChatTools
from src.tools.github_tools import GitHubTools

CTO_PERSONA = """You are the CTO of an AI-powered IT company called My IT Crew.

Your responsibilities:
- Assess technical feasibility of epics and proposals
- Make architecture decisions and document them
- Review PRs for quality and architectural compliance
- Break approved epics into technical components
- Respond to issues labeled 'needs-cto' with technical assessment
- Report findings back to CEO

Your workflow each cycle:
1. Check for issues labeled 'needs-cto' — these are YOUR priority
2. For each, provide a technical feasibility comment with:
   - Complexity estimate (S/M/L/XL)
   - Key risks and dependencies
   - Recommended architecture approach
   - Estimated effort in weeks
3. After assessment, relabel the issue: remove 'needs-cto', add 'needs-breakdown'
4. Check for open PRs and review them
5. Post technical updates to Slack #engineering

When assessing feasibility:
- Be pragmatic, not theoretical
- Reference the current stack: Python, Kubernetes, LiteLLM, GitHub Actions
- Identify what can be reused vs. what needs building
- Flag blockers clearly

You communicate via:
- Slack: #engineering for tech discussions, #c-suite for strategic input
- GitHub issue comments for technical assessments
- PR reviews for code quality
"""


class CTOAgent(BaseAgent):
    """CTO agent with technical leadership capabilities."""

    def __init__(self):
        super().__init__(agent_id="cto", persona=CTO_PERSONA)
        self._setup_tools()

    def _setup_tools(self) -> None:
        gh = GitHubTools(self.settings)
        chat = ChatTools(self.settings)

        self.register_tool(
            "send_slack_message",
            chat.send_message,
            "Send a message to a Slack channel",
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
            "comment_on_issue",
            gh.comment_on_issue,
            "Add a technical assessment comment to an issue",
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
            "create_issue",
            gh.create_issue,
            "Create a technical task or architecture issue",
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
            "list_issues",
            gh.list_issues,
            "List open issues",
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
            "Add or remove labels from an issue (use to pass work: remove needs-cto, add needs-breakdown)",
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

        self.register_tool(
            "assign_copilot_agent",
            gh.update_issue_labels,
            "Assign a Copilot agent by adding a label. ALWAYS assign copilot/architect FIRST for design, then copilot/backend-developer for implementation. Available: copilot/architect, copilot/backend-developer, copilot/frontend-developer, copilot/fullstack-developer, copilot/qa-engineer, copilot/pr-reviewer, copilot/pr-approver, copilot/documenter, copilot/diagram-architect",
            {
                "type": "object",
                "properties": {
                    "issue_number": {"type": "integer"},
                    "add": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Labels to add, e.g. ['copilot/backend-developer']. Use the copilot/ prefix.",
                    },
                    "remove": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Labels to remove",
                    },
                },
                "required": ["issue_number", "add"],
            },
        )
        self.register_tool(
            "list_pull_requests",
            gh.list_pull_requests,
            "List open pull requests for review",
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

        # Check #c-suite and #engineering for messages relevant to CTO
        for channel in ["c-suite", "engineering"]:
            messages = await chat.get_channel_history(channel=channel, limit=5)
            for msg in messages:
                text = msg.get("text", "").lower()
                if any(
                    kw in text
                    for kw in ["cto", "architecture", "feasibility", "technical", "review"]
                ):
                    events.append(
                        {
                            "type": "team_message",
                            "title": f"Message in #{channel}",
                            "body": msg.get("text", "")[:500],
                        }
                    )

        # Priority: issues needing CTO assessment
        issues = await gh.list_issues(labels=["needs-cto"], limit=5)
        for issue in issues:
            events.append(
                {
                    "type": "needs_technical_assessment",
                    "title": issue["title"],
                    "body": f"Issue #{issue['number']}: {issue.get('body', '')[:600]}",
                }
            )

        # PRs needing review
        prs = await gh.list_pull_requests(limit=5)
        for pr in prs:
            events.append(
                {
                    "type": "pr_needs_review",
                    "title": pr["title"],
                    "body": f"PR #{pr['number']} by {pr.get('author', 'unknown')}",
                }
            )

        return events

    async def reflect(self, result: dict[str, Any]) -> None:
        self.log.info(
            "cto_reflection",
            actions_taken=len(result.get("actions", [])),
            summary=result.get("summary", "")[:200],
        )
