"""Tests for agent instantiation and basic functionality."""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.ceo import CEOAgent
from src.agents.cto import CTOAgent
from src.agents.devops import DevOpsAgent
from src.agents.eng_manager import EngManagerAgent
from src.agents.engineer import EngineerAgent
from src.agents.frontend_engineer import FrontendEngineerAgent
from src.agents.fullstack_engineer import FullstackEngineerAgent
from src.agents.marketer import MarketerAgent
from src.agents.qa_engineer import QAEngineerAgent


class TestAgentInstantiation:
    """Test that all agents can be instantiated with correct attributes."""

    def test_ceo_agent_init(self):
        agent = CEOAgent()
        assert agent.agent_id == "ceo"
        assert "create_issue" in agent.tools
        assert "list_issues" in agent.tools
        assert "comment_on_issue" in agent.tools
        assert "send_slack_message" in agent.tools

    def test_cto_agent_init(self):
        agent = CTOAgent()
        assert agent.agent_id == "cto"
        assert "comment_on_issue" in agent.tools
        assert "update_issue_labels" in agent.tools
        assert "list_pull_requests" in agent.tools

    def test_engineer_agent_init(self):
        agent = EngineerAgent()
        assert agent.agent_id == "engineer"
        assert "list_pull_requests" in agent.tools
        assert "comment_on_issue" in agent.tools

    def test_eng_manager_agent_init(self):
        agent = EngManagerAgent()
        assert agent.agent_id == "eng-manager"
        assert "create_issue" in agent.tools
        assert "assign_copilot_agent" in agent.tools
        assert "list_issues" in agent.tools

    def test_devops_agent_init(self):
        agent = DevOpsAgent()
        assert agent.agent_id == "devops"
        assert "create_issue" in agent.tools
        assert "list_issues" in agent.tools

    def test_qa_engineer_agent_init(self):
        agent = QAEngineerAgent()
        assert agent.agent_id == "qa-engineer"
        assert "list_pull_requests" in agent.tools
        assert "create_issue" in agent.tools

    def test_marketer_agent_init(self):
        agent = MarketerAgent()
        assert agent.agent_id == "marketer"
        assert "post_discussion" in agent.tools
        assert "send_slack_message" in agent.tools

    def test_frontend_engineer_agent_init(self):
        agent = FrontendEngineerAgent()
        assert agent.agent_id == "frontend-engineer"
        assert "list_pull_requests" in agent.tools
        assert "comment_on_issue" in agent.tools
        assert "list_issues" in agent.tools
        assert "create_issue" in agent.tools

    def test_fullstack_engineer_agent_init(self):
        agent = FullstackEngineerAgent()
        assert agent.agent_id == "fullstack-engineer"
        assert "list_pull_requests" in agent.tools
        assert "comment_on_issue" in agent.tools
        assert "list_issues" in agent.tools
        assert "create_issue" in agent.tools
        assert "update_issue_labels" in agent.tools


class TestBaseAgentBehavior:
    """Test base agent behavior."""

    def test_register_tool(self):
        agent = CEOAgent()
        tool_count_before = len(agent.tools)

        async def dummy_tool(x: str) -> str:
            return x

        agent.register_tool(
            "dummy",
            dummy_tool,
            "A dummy tool for testing",
            {"type": "object", "properties": {"x": {"type": "string"}}},
        )
        assert len(agent.tools) == tool_count_before + 1
        assert "dummy" in agent.tools

    def test_format_events(self):
        agent = CEOAgent()
        events = [
            {"type": "epic_status_review", "title": "Test Epic", "body": "Epic body"},
            {"type": "capacity_available", "title": "Capacity", "body": "No work"},
        ]
        formatted = agent._format_events(events)
        assert "epic_status_review" in formatted
        assert "Test Epic" in formatted
        assert "capacity_available" in formatted

    def test_initial_state(self):
        agent = CEOAgent()
        assert agent.state.agent_id == "ceo"
        assert agent.state.run_count == 0
        assert agent.state.last_run is None
        assert agent.state.context == []


class TestAgentPerceive:
    """Test agent perceive methods with mocked GitHub API."""

    @pytest.mark.asyncio
    async def test_ceo_perceive_no_events(self):
        agent = CEOAgent()
        with patch(
            "src.tools.github_tools.GitHubTools.list_issues", new_callable=AsyncMock
        ) as mock:
            mock.return_value = []
            events = await agent.perceive()
        # With no issues or epics, should return capacity_available event
        assert len(events) == 1
        assert events[0]["type"] == "capacity_available"

    @pytest.mark.asyncio
    async def test_ceo_perceive_with_open_epics(self):
        agent = CEOAgent()
        epics = [{"number": 1, "title": "Test Epic", "body": "body", "labels": ["epic"]}]

        call_count = 0

        async def mock_list_issues(labels=None, limit=10):
            nonlocal call_count
            call_count += 1
            if labels and "epic" in labels:
                return epics
            return []

        with patch("src.tools.github_tools.GitHubTools.list_issues", side_effect=mock_list_issues):
            events = await agent.perceive()

        # Should include epic_status_review event
        types = [e["type"] for e in events]
        assert "epic_status_review" in types
        # Should NOT include capacity_available when epics exist
        assert "capacity_available" not in types

    @pytest.mark.asyncio
    async def test_engineer_perceive_no_prs(self):
        agent = EngineerAgent()
        with (
            patch(
                "src.tools.github_tools.GitHubTools.list_pull_requests",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "src.tools.github_tools.GitHubTools.list_issues",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            events = await agent.perceive()
        assert events == []

    @pytest.mark.asyncio
    async def test_marketer_perceive_always_has_event(self):
        agent = MarketerAgent()
        with patch(
            "src.tools.github_tools.GitHubTools.list_issues",
            new_callable=AsyncMock,
            return_value=[],
        ):
            events = await agent.perceive()
        # Marketer always returns at least a content_ideation event
        assert len(events) >= 1
        assert events[-1]["type"] == "content_ideation"
