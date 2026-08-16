"""Talent Acquisition Specialist — sourcing, screening, pipeline management."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.chat_tools import ChatTools
from src.tools.github_tools import GitHubTools

TA_PERSONA = """You are the Talent Acquisition Specialist at My IT Crew.

Your responsibilities:
- Receive hiring requests via DM and #general channel
- Create Job Requisition issues in the talent repo (subzone/my-it-crew-talent)
- Source candidates (for AI agents: research models, for humans: identify profiles)
- Screen candidates and move them through the pipeline
- Coordinate with Technical Interviewer for assessments
- Update hiring managers on pipeline status

Your workflow:
1. Check DMs and channels for hiring requests from the Board
2. For each request, create a Job Requisition issue
3. Source candidates and create Candidate issues
4. Move candidates through stages using labels
5. Coordinate interviews with Technical Interviewer
6. Report status back to the hiring manager

Labels for pipeline stages:
- stage/sourced, stage/screening, stage/interview, stage/decision, stage/hired, stage/rejected

For AI agent hiring:
- Research available models (what's in our LiteLLM, what's free)
- Evaluate tool-calling capability, context window, speed
- Recommend the best model for the role

Always communicate updates in Mattermost #general or DMs.
"""


class TASpecialistAgent(BaseAgent):
    """Talent Acquisition Specialist."""

    def __init__(self):
        super().__init__(agent_id="ta-specialist", persona=TA_PERSONA, model="nemotron-super")
        self._setup_tools()

    def _setup_tools(self) -> None:
        gh = GitHubTools(self.settings)
        # Override repo to talent repo
        from src.config import Settings

        talent_settings = Settings()
        talent_settings.github_repo = "subzone/my-it-crew-talent"
        talent_gh = GitHubTools(talent_settings)

        chat = ChatTools(self.settings)

        self.register_tool(
            "send_message",
            chat.send_message,
            "Send a message to a Mattermost channel",
            {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Channel name"},
                    "text": {"type": "string"},
                },
                "required": ["channel", "text"],
            },
        )
        self.register_tool(
            "create_candidate_issue",
            talent_gh.create_issue,
            "Create a candidate or job req issue in the private talent repo",
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
            "list_talent_issues",
            talent_gh.list_issues,
            "List issues in the talent repo",
            {
                "type": "object",
                "properties": {
                    "labels": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer"},
                },
            },
        )
        self.register_tool(
            "comment_on_talent_issue",
            talent_gh.comment_on_issue,
            "Comment on a talent repo issue",
            {
                "type": "object",
                "properties": {
                    "issue_number": {"type": "integer"},
                    "body": {"type": "string"},
                },
                "required": ["issue_number", "body"],
            },
        )

    async def perceive(self) -> list[dict]:
        chat = ChatTools(self.settings)
        events = []

        # Check DMs
        dms = await chat.get_direct_messages(limit=3)
        for dm in dms:
            events.append(
                {
                    "type": "direct_message",
                    "title": "DM to TA Specialist",
                    "body": dm["text"][:500],
                }
            )

        # Check #general for hiring requests
        messages = await chat.get_channel_history(channel="general", limit=5)
        for msg in messages:
            if msg.get("text") and any(
                kw in msg["text"].lower()
                for kw in ["hire", "hiring", "need", "recruit", "candidate", "position", "role"]
            ):
                events.append(
                    {
                        "type": "hiring_request",
                        "title": "Potential hiring request in #general",
                        "body": msg["text"][:500],
                    }
                )

        return events

    async def reflect(self, result: dict[str, Any]) -> None:
        self.log.info("ta_specialist_reflection", actions_taken=len(result.get("actions", [])))
