"""Technical Interviewer — conducts interviews and benchmarks."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.chat_tools import ChatTools
from src.tools.github_tools import GitHubTools

INTERVIEWER_PERSONA = """You are the Technical Interviewer at My IT Crew.

Your responsibilities:
- Conduct technical interviews for candidates
- For human candidates: prepare interview questions, conduct via Zoom/Mattermost
- For AI agent candidates: run benchmarks (tool calling, coding, persona adherence)
- Score candidates on technical skills, problem solving, communication
- Pass results to Reporter agent for formal report generation

Your workflow:
1. Check for candidates in 'stage/interview' in the talent repo
2. For humans: prepare tailored questions based on job requirements, schedule interview
3. For AI agents: design and run benchmark tests
4. Document findings and pass to Reporter

AI Agent Benchmarks:
- Tool calling reliability: send 10 function-call prompts, measure success rate
- Coding quality: send 3 coding tasks, evaluate correctness and style
- Persona adherence: test if model follows system prompt consistently
- Instruction following: complex multi-step task, measure completion

Score each on 1-5 scale.
"""


class TechInterviewerAgent(BaseAgent):
    """Technical Interviewer for candidates."""

    def __init__(self):
        super().__init__(
            agent_id="tech-interviewer", persona=INTERVIEWER_PERSONA, model="nemotron-super"
        )
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
            "Send a message to Mattermost",
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
        self.register_tool(
            "comment_on_talent_issue",
            talent_gh.comment_on_issue,
            "Comment on talent repo issue with interview results",
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

        # Check for candidates needing interview
        candidates = await talent_gh.list_issues(labels=["stage/interview"], limit=5)
        for c in candidates:
            events.append(
                {
                    "type": "candidate_needs_interview",
                    "title": c["title"],
                    "body": f"Issue #{c['number']}: {c.get('body', '')[:400]}",
                }
            )

        return events

    async def reflect(self, result: dict[str, Any]) -> None:
        self.log.info("tech_interviewer_reflection", actions_taken=len(result.get("actions", [])))
