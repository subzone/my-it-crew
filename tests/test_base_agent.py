"""Tests for BaseAgent lifecycle, health check, and skill plugin architecture."""

import pytest

from src.agents.base import AgentStatus, BaseAgent, SkillPlugin
from src.agents.ceo import CEOAgent


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


class _ConcreteAgent(BaseAgent):
    """Minimal concrete agent for testing abstract methods."""

    def __init__(self):
        super().__init__(agent_id="test-agent", persona="Test persona")

    async def perceive(self):
        return []

    async def reflect(self, result):
        pass


class _SimpleSkill(SkillPlugin):
    name = "simple_skill"

    def get_tools(self):
        async def noop(x: str) -> str:
            return x

        return [
            {
                "name": "noop_tool",
                "func": noop,
                "description": "Does nothing",
                "parameters": {
                    "type": "object",
                    "properties": {"x": {"type": "string"}},
                    "required": ["x"],
                },
            }
        ]


class _LifecycleSkill(SkillPlugin):
    """Skill that records on_load / on_unload calls."""

    name = "lifecycle_skill"
    loaded: bool = False
    unloaded: bool = False

    def get_tools(self):
        async def dummy() -> str:
            return "ok"

        return [
            {
                "name": "lifecycle_dummy",
                "func": dummy,
                "description": "Lifecycle test tool",
                "parameters": {"type": "object", "properties": {}},
            }
        ]

    async def on_load(self, agent):
        self.loaded = True

    async def on_unload(self, agent):
        self.unloaded = True


# ---------------------------------------------------------------------------
# AgentStatus enum
# ---------------------------------------------------------------------------


class TestAgentStatus:
    def test_enum_values(self):
        assert AgentStatus.STOPPED == "stopped"
        assert AgentStatus.RUNNING == "running"
        assert AgentStatus.PAUSED == "paused"


# ---------------------------------------------------------------------------
# Lifecycle: start / stop / pause / resume
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_initial_status_is_stopped(self):
        agent = _ConcreteAgent()
        assert agent.status == AgentStatus.STOPPED

    def test_start_transitions_to_running(self):
        agent = _ConcreteAgent()
        agent.start()
        assert agent.status == AgentStatus.RUNNING

    def test_start_is_idempotent(self):
        agent = _ConcreteAgent()
        agent.start()
        agent.start()  # second call must not raise
        assert agent.status == AgentStatus.RUNNING

    def test_stop_transitions_to_stopped(self):
        agent = _ConcreteAgent()
        agent.start()
        agent.stop()
        assert agent.status == AgentStatus.STOPPED

    def test_pause_requires_running_state(self):
        agent = _ConcreteAgent()  # STOPPED
        with pytest.raises(RuntimeError, match="not in RUNNING state"):
            agent.pause()

    def test_pause_transitions_to_paused(self):
        agent = _ConcreteAgent()
        agent.start()
        agent.pause()
        assert agent.status == AgentStatus.PAUSED

    def test_resume_requires_paused_state(self):
        agent = _ConcreteAgent()
        agent.start()
        with pytest.raises(RuntimeError, match="not in PAUSED state"):
            agent.resume()

    def test_resume_transitions_to_running(self):
        agent = _ConcreteAgent()
        agent.start()
        agent.pause()
        agent.resume()
        assert agent.status == AgentStatus.RUNNING

    def test_started_at_set_on_first_start(self):
        agent = _ConcreteAgent()
        assert agent._started_at is None
        agent.start()
        assert agent._started_at is not None

    def test_started_at_not_reset_on_resume(self):
        agent = _ConcreteAgent()
        agent.start()
        first_start = agent._started_at
        agent.pause()
        agent.resume()
        assert agent._started_at == first_start


# ---------------------------------------------------------------------------
# run_cycle respects lifecycle state
# ---------------------------------------------------------------------------


class TestRunCycleLifecycle:
    @pytest.mark.asyncio
    async def test_run_cycle_stopped_returns_stopped(self):
        agent = _ConcreteAgent()
        result = await agent.run_cycle()
        assert result == {"status": "stopped"}

    @pytest.mark.asyncio
    async def test_run_cycle_paused_returns_paused(self):
        agent = _ConcreteAgent()
        agent.start()
        agent.pause()
        result = await agent.run_cycle()
        assert result == {"status": "paused"}

    @pytest.mark.asyncio
    async def test_run_cycle_stopped_does_not_increment_run_count(self):
        agent = _ConcreteAgent()
        await agent.run_cycle()
        assert agent.state.run_count == 0

    @pytest.mark.asyncio
    async def test_run_cycle_paused_does_not_increment_run_count(self):
        agent = _ConcreteAgent()
        agent.start()
        agent.pause()
        await agent.run_cycle()
        assert agent.state.run_count == 0


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_health_returns_dict(self):
        agent = _ConcreteAgent()
        h = agent.health()
        assert isinstance(h, dict)

    def test_health_contains_expected_keys(self):
        agent = _ConcreteAgent()
        h = agent.health()
        for key in ("agent_id", "status", "run_count", "last_run", "started_at", "tools", "skills"):
            assert key in h

    def test_health_initial_state(self):
        agent = _ConcreteAgent()
        h = agent.health()
        assert h["agent_id"] == "test-agent"
        assert h["status"] == "stopped"
        assert h["run_count"] == 0
        assert h["last_run"] is None
        assert h["started_at"] is None
        assert h["tools"] == []
        assert h["skills"] == []

    def test_health_reflects_status_change(self):
        agent = _ConcreteAgent()
        agent.start()
        assert agent.health()["status"] == "running"
        agent.pause()
        assert agent.health()["status"] == "paused"
        agent.resume()
        agent.stop()
        assert agent.health()["status"] == "stopped"

    def test_health_started_at_present_after_start(self):
        agent = _ConcreteAgent()
        agent.start()
        assert agent.health()["started_at"] is not None

    def test_health_lists_registered_tools(self):
        agent = CEOAgent()
        h = agent.health()
        assert "create_issue" in h["tools"]
        assert "send_slack_message" in h["tools"]


# ---------------------------------------------------------------------------
# Skill plugin architecture
# ---------------------------------------------------------------------------


class TestSkillPlugin:
    @pytest.mark.asyncio
    async def test_load_skill_registers_tools(self):
        agent = _ConcreteAgent()
        skill = _SimpleSkill()
        await agent.load_skill(skill)
        assert "noop_tool" in agent.tools

    @pytest.mark.asyncio
    async def test_load_skill_tracks_skill_name(self):
        agent = _ConcreteAgent()
        skill = _SimpleSkill()
        await agent.load_skill(skill)
        assert "simple_skill" in agent.skills

    @pytest.mark.asyncio
    async def test_unload_skill_removes_tools(self):
        agent = _ConcreteAgent()
        skill = _SimpleSkill()
        await agent.load_skill(skill)
        await agent.unload_skill("simple_skill")
        assert "noop_tool" not in agent.tools
        assert "simple_skill" not in agent.skills

    @pytest.mark.asyncio
    async def test_unload_nonexistent_skill_is_noop(self):
        agent = _ConcreteAgent()
        # Must not raise
        await agent.unload_skill("does_not_exist")

    @pytest.mark.asyncio
    async def test_skill_on_load_callback_called(self):
        agent = _ConcreteAgent()
        skill = _LifecycleSkill()
        await agent.load_skill(skill)
        assert skill.loaded is True

    @pytest.mark.asyncio
    async def test_skill_on_unload_callback_called(self):
        agent = _ConcreteAgent()
        skill = _LifecycleSkill()
        await agent.load_skill(skill)
        await agent.unload_skill("lifecycle_skill")
        assert skill.unloaded is True

    @pytest.mark.asyncio
    async def test_loading_same_skill_replaces_previous(self):
        agent = _ConcreteAgent()
        skill1 = _LifecycleSkill()
        skill2 = _LifecycleSkill()
        await agent.load_skill(skill1)
        await agent.load_skill(skill2)  # replaces skill1
        assert skill1.unloaded is True
        assert skill2.loaded is True
        assert len([k for k in agent.skills if k == "lifecycle_skill"]) == 1

    @pytest.mark.asyncio
    async def test_health_lists_loaded_skills(self):
        agent = _ConcreteAgent()
        skill = _SimpleSkill()
        await agent.load_skill(skill)
        h = agent.health()
        assert "simple_skill" in h["skills"]
