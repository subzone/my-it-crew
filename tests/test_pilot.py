"""Integration tests for Autonomous Pilot Runner and multi-agent workflow."""

import pytest

from src.orchestrator.pilot_runner import AutonomousPilotRunner


class TestAutonomousPilot:
    """Test full initiative lifecycle coordination in the autonomous pilot."""

    @pytest.mark.asyncio
    async def test_full_pilot_execution_mocked(self):
        directive = "Deploy multi-agent cluster health probe"
        runner = AutonomousPilotRunner(directive=directive)

        result = await runner.run_pilot()

        assert result["status"] == "success"
        assert result["cost_usd"] == 0.0

        # Verify Epic creation
        assert runner.ctx.epic_issue is not None
        assert "Epic:" in runner.ctx.epic_issue["title"]
        assert "status/done" in runner.ctx.epic_issue["labels"]

        # Verify task breakdown
        assert len(runner.ctx.tasks) == 3
        task_titles = [t["title"] for t in runner.ctx.tasks]
        assert any("API" in t for t in task_titles)
        assert any("UI" in t or "Dashboard" in t for t in task_titles)
        assert any("Test" in t for t in task_titles)

        # Verify PRs opened
        assert len(runner.ctx.prs) == 2
        pr_titles = [p["title"] for p in runner.ctx.prs]
        assert any("api" in p.lower() for p in pr_titles)
        assert any("ui" in p.lower() for p in pr_titles)

        # Verify chat communication
        channels_contacted = {m["channel"] for m in runner.ctx.chat_logs}
        assert "general" in channels_contacted
        assert "c-suite" in channels_contacted
        assert "engineering" in channels_contacted
        assert "releases" in channels_contacted

        # Verify all 8 phases completed
        phases = [s["phase"] for s in runner.ctx.step_history]
        assert "0_token_scout" in phases
        assert "1_ceo_epic" in phases
        assert "2_cto_feasibility" in phases
        assert "3_em_breakdown" in phases
        assert "4_engineers_implement" in phases
        assert "5_qa_validation" in phases
        assert "6_devops_deploy" in phases
        assert "7_marketing_reporting" in phases
