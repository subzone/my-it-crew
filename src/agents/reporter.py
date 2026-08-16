"""Reporter Agent — records sessions and creates assessment reports."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.chat_tools import ChatTools
from src.tools.github_tools import GitHubTools

REPORTER_PERSONA = """You are the Interview Reporter at My IT Crew.

Your responsibilities:
- Generate structured interview reports after assessments
- Summarize Technical Interviewer findings into a formal report
- For human interviews: process transcripts/notes into standardized format
- For AI benchmarks: compile scores into comparison matrix
- Deliver reports via Mattermost DM to hiring manager and as issue comments

Report format:
1. Technical Skills Assessment (rated 1-5 per skill)
2. Communication quality
3. Problem-solving approach
4. Culture fit score
5. Red flags
6. Strengths
7. Recommendation (hire / no-hire / next round)
8. Comparison to job requirements

Always create the report as a comment on the candidate's issue in the talent repo.
Also send a summary via Mattermost DM or #general.
"""


class ReporterAgent(BaseAgent):
    """Interview Reporter that generates assessment reports."""

    def __init__(self):
        super().__init__(agent_id="reporter", persona=REPORTER_PERSONA)
        self._setup_tools()

    def _setup_tools(self) -> None:
        from src.config import Settings

        talent_settings = Settings()
        talent_settings.github_repo = "subzone/my-it-crew-talent"
        talent_gh = GitHubTools(talent_settings)
        chat = ChatTools(self.settings)

        self.register_tool(
            "send_message",
            chat.send_message,
            "Send report summary to Mattermost",
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
            "create_report_issue",
            talent_gh.create_issue,
            "Create a formal interview report in the talent repo",
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
            "comment_on_talent_issue",
            talent_gh.comment_on_issue,
            "Add report as comment on candidate issue",
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
            "list_talent_issues",
            talent_gh.list_issues,
            "List issues in talent repo",
            {
                "type": "object",
                "properties": {
                    "labels": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer"},
                },
            },
        )

    async def perceive(self) -> list[dict]:
        from src.config import Settings

        talent_settings = Settings()
        talent_settings.github_repo = "subzone/my-it-crew-talent"
        talent_gh = GitHubTools(talent_settings)
        chat = ChatTools(self.settings)
        events = []

        # Check DMs
        dms = await chat.get_direct_messages(limit=3)
        for dm in dms:
            events.append(
                {"type": "direct_message", "title": "DM received", "body": dm["text"][:500]}
            )

        # Check for candidates needing reports (stage/decision means interview done)
        candidates = await talent_gh.list_issues(labels=["stage/decision"], limit=5)
        for c in candidates:
            events.append(
                {
                    "type": "needs_report",
                    "title": c["title"],
                    "body": f"Issue #{c['number']}: {c.get('body', '')[:400]}",
                }
            )

        return events

    async def reflect(self, result: dict[str, Any]) -> None:
        self.log.info("reporter_reflection", actions_taken=len(result.get("actions", [])))
