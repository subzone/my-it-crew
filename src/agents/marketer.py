"""Marketing Agent — Content creation and brand growth."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.chat_tools import ChatTools
from src.tools.github_tools import GitHubTools

MARKETER_PERSONA = """You are the Marketing Lead at My IT Crew.

Your responsibilities:
- Create content (blog posts, social media, documentation)
- Build brand awareness for the company's AI capabilities
- Write technical blog posts about what the team is building
- Maintain the company blog/website content
- Track marketing metrics and propose growth strategies
- Coordinate with CEO on messaging and positioning
- Monitor Slack #marketing channel for requests from the Board
- When you see a request in #marketing, create a GitHub Issue with label 'dept/marketing' and acknowledge in Slack
- Post content updates to #marketing Slack channel
- Mention CEO in #general when announcing major milestones

Your workflow:
1. Check for completed features or milestones to announce
2. Draft blog posts and content pieces (as GitHub Issues with 'content' label)
3. Propose marketing campaigns aligned with company strategy
4. Review and update public-facing documentation
5. Report on content performance metrics

Content guidelines:
- Technical but accessible to a business audience
- Focus on autonomous AI, agentic workflows, and IT operations
- Highlight unique capabilities and achievements of the crew
"""


class MarketerAgent(BaseAgent):
    """Marketing agent that creates content and grows brand."""

    def __init__(self):
        super().__init__(agent_id="marketer", persona=MARKETER_PERSONA)
        self._setup_tools()

    def _setup_tools(self) -> None:
        gh = GitHubTools(self.settings)
        chat = ChatTools(self.settings)

        self.register_tool(
            "send_slack_message",
            chat.send_message,
            "Post to Slack (#marketing for content, #general for announcements)",
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
            "Create a content/marketing task",
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
            "post_discussion",
            gh.create_discussion,
            "Post in Discussions",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "category": {"type": "string"},
                },
                "required": ["title", "body", "category"],
            },
        )

    async def perceive(self) -> list[dict]:
        gh = GitHubTools(self.settings)
        chat = ChatTools(self.settings)
        events = []
        # Check DMs
        chat = ChatTools(self.settings)
        dms = await chat.get_direct_messages(limit=3)
        for dm in dms:
            events.append(
                {"type": "direct_message", "title": "DM received", "body": dm["text"][:500]}
            )

        # Check Slack #marketing for requests from humans
        messages = await chat.get_channel_history(channel="marketing", limit=5)
        for msg in messages:
            if msg.get("user") and msg.get("text"):
                events.append(
                    {
                        "type": "marketing_request",
                        "title": "Request in #marketing",
                        "body": msg["text"][:500],
                    }
                )

        # Check for completed features to announce
        issues = await gh.list_issues(labels=["status/done"], limit=5)
        for issue in issues:
            events.append(
                {
                    "type": "feature_completed",
                    "title": issue["title"],
                    "body": f"Issue #{issue['number']}: {issue.get('body', '')[:300]}",
                }
            )

        # Check for marketing tasks
        issues = await gh.list_issues(labels=["dept/marketing"], limit=5)
        for issue in issues:
            events.append(
                {
                    "type": "marketing_task",
                    "title": issue["title"],
                    "body": f"Issue #{issue['number']}: {issue.get('body', '')[:300]}",
                }
            )

        # If nothing, proactive content ideation
        if not events:
            events.append(
                {
                    "type": "content_ideation",
                    "title": "Weekly content review",
                    "body": "No pending tasks. Consider creating a blog post about recent achievements or proposing a new marketing initiative.",
                }
            )

        return events

    async def reflect(self, result: dict[str, Any]) -> None:
        self.log.info("marketer_reflection", actions_taken=len(result.get("actions", [])))
