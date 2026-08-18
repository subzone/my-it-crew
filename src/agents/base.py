"""Base agent class with autonomy loop."""

import enum
import inspect
import json
import re
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from src.config import Settings

logger = structlog.get_logger()


class AgentStatus(str, enum.Enum):
    """Lifecycle status of an agent."""

    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"


class AgentMessage(BaseModel):
    """A message in the agent's context."""

    role: str
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentState(BaseModel):
    """Persistent state for an agent."""

    agent_id: str
    last_run: datetime | None = None
    run_count: int = 0
    context: list[AgentMessage] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkillPlugin(ABC):
    """Base class for skill plugins.

    Skills extend an agent's capabilities with domain-specific behaviours.
    Each skill declares the tools it provides; the agent registers them
    during :meth:`BaseAgent.load_skill`.
    """

    #: Unique identifier for this skill (e.g. ``"it_ticket_triage"``).
    name: str

    @abstractmethod
    def get_tools(self) -> list[dict[str, Any]]:
        """Return a list of tool descriptors.

        Each descriptor is a dict with keys:
        ``name``, ``func``, ``description``, ``parameters``.
        """
        ...

    async def on_load(self, agent: "BaseAgent") -> None:
        """Called after the skill has been loaded into *agent*.  Override as needed."""

    async def on_unload(self, agent: "BaseAgent") -> None:
        """Called before the skill is removed from *agent*.  Override as needed."""


class BaseAgent(ABC):
    """Base class for all autonomous agents.

    Implements the autonomy loop:
    1. Perceive — Check for new events, messages, tasks
    2. Think — Analyze context, reason about next steps
    3. Plan — Decide on actions to take
    4. Act — Execute actions using tools
    5. Reflect — Evaluate outcomes, update memory

    Lifecycle
    ---------
    Call :meth:`start` before running cycles and :meth:`stop` when done.
    Use :meth:`pause` / :meth:`resume` to temporarily suspend cycle
    execution without tearing down the agent.

    Plugin architecture
    -------------------
    Register domain-specific :class:`SkillPlugin` instances with
    :meth:`load_skill`.  Their tools are automatically registered and
    available to the reasoning loop.
    """

    def __init__(self, agent_id: str, persona: str, model: str | None = None):
        self.agent_id = agent_id
        self.persona = persona
        self.settings = Settings()
        self.model = model or self.settings.default_model
        self.state = AgentState(agent_id=agent_id)
        self.client = AsyncOpenAI(
            base_url=self.settings.litellm_api_base,
            api_key=self.settings.litellm_api_key,
        )
        self.tools: dict[str, Any] = {}
        self.skills: dict[str, SkillPlugin] = {}
        self._skill_tool_names: dict[str, list[str]] = {}
        self.max_iterations = 15
        self.log = logger.bind(agent=agent_id)
        self._status: AgentStatus = AgentStatus.STOPPED
        self._started_at: datetime | None = None

    # ------------------------------------------------------------------
    # Lifecycle management
    # ------------------------------------------------------------------

    @property
    def status(self) -> AgentStatus:
        """Current lifecycle status."""
        return self._status

    def start(self) -> None:
        """Transition the agent to the RUNNING state.

        Safe to call from STOPPED or PAUSED.
        """
        if self._status == AgentStatus.RUNNING:
            return
        self._status = AgentStatus.RUNNING
        if self._started_at is None:
            self._started_at = datetime.now(UTC)
        self.log.info("agent_started")

    def stop(self) -> None:
        """Transition the agent to the STOPPED state."""
        self._status = AgentStatus.STOPPED
        self.log.info("agent_stopped")

    def pause(self) -> None:
        """Pause the agent without stopping it.

        A paused agent will skip :meth:`run_cycle` execution and return an
        ``{"status": "paused"}`` result immediately.
        """
        if self._status != AgentStatus.RUNNING:
            raise RuntimeError(
                f"Cannot pause agent '{self.agent_id}': not in RUNNING state (current: {self._status.value})"
            )
        self._status = AgentStatus.PAUSED
        self.log.info("agent_paused")

    def resume(self) -> None:
        """Resume a paused agent, transitioning back to RUNNING state."""
        if self._status != AgentStatus.PAUSED:
            raise RuntimeError(
                f"Cannot resume agent '{self.agent_id}': not in PAUSED state (current: {self._status})"
            )
        self._status = AgentStatus.RUNNING
        self.log.info("agent_resumed")

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Return a health-check snapshot for this agent.

        The dict is safe to serialise as JSON and suitable for use in a
        ``/healthz`` HTTP endpoint or a monitoring probe.
        """
        return {
            "agent_id": self.agent_id,
            "status": self._status.value,
            "run_count": self.state.run_count,
            "last_run": self.state.last_run.isoformat() if self.state.last_run else None,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "tools": list(self.tools.keys()),
            "skills": list(self.skills.keys()),
        }

    # ------------------------------------------------------------------
    # Skill plugin architecture
    # ------------------------------------------------------------------

    async def load_skill(self, skill: SkillPlugin) -> None:
        """Register a skill plugin and its tools into this agent.

        If a skill with the same name is already loaded it is first
        unloaded before the new one is registered.  Tool names provided by
        this skill are recorded so that :meth:`unload_skill` can remove them
        precisely without re-invoking ``get_tools()``.
        """
        if skill.name in self.skills:
            await self.unload_skill(skill.name)

        tools = skill.get_tools()
        tool_names: list[str] = []
        try:
            for tool in tools:
                tool_name = tool["name"]
                if tool_name in self.tools:
                    raise ValueError(
                        f"Cannot load skill '{skill.name}': tool '{tool_name}' is already registered"
                    )
                self.register_tool(
                    tool_name,
                    tool["func"],
                    tool["description"],
                    tool["parameters"],
                )
                tool_names.append(tool_name)

            self._skill_tool_names[skill.name] = tool_names
            self.skills[skill.name] = skill
            await skill.on_load(self)
        except Exception:
            for tool_name in tool_names:
                self.tools.pop(tool_name, None)
            self._skill_tool_names.pop(skill.name, None)
            self.skills.pop(skill.name, None)
            raise

        self.log.info("skill_loaded", skill=skill.name)

    async def unload_skill(self, skill_name: str) -> None:
        """Remove a previously loaded skill and its tools from this agent."""
        skill = self.skills.pop(skill_name, None)
        if skill is None:
            return
        for tool_name in self._skill_tool_names.pop(skill_name, []):
            self.tools.pop(tool_name, None)
        await skill.on_unload(self)
        self.log.info("skill_unloaded", skill=skill_name)

    # ------------------------------------------------------------------
    # Tool registry
    # ------------------------------------------------------------------

    def register_tool(self, name: str, func: Any, description: str, parameters: dict) -> None:
        """Register a tool the agent can use."""
        self.tools[name] = {
            "function": func,
            "definition": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            },
        }

    async def run_cycle(self) -> dict[str, Any]:
        """Execute one full autonomy cycle.

        Returns immediately with ``{"status": "paused"}`` when the agent is
        paused, or ``{"status": "stopped"}`` when it is stopped.
        """
        if self._status == AgentStatus.PAUSED:
            self.log.info("cycle_skipped_paused")
            return {"status": "paused"}
        if self._status == AgentStatus.STOPPED:
            self.log.info("cycle_skipped_stopped")
            return {"status": "stopped"}

        self.log.info("starting_cycle", run_count=self.state.run_count)
        self.state.run_count += 1
        self.state.last_run = datetime.now(UTC)

        try:
            # 1. Perceive
            events = await self.perceive()
            self.log.info("perceived", event_count=len(events))

            if not events:
                self.log.info("no_events_skipping")
                return {"status": "idle", "events": 0}

            # 2. Think + Plan + Act (LLM-driven loop)
            result = await self._reasoning_loop(events)

            # 3. Reflect
            await self.reflect(result)
            self.log.info("cycle_complete", result=result.get("summary", "done"))

            return result

        except Exception as e:
            self.log.error("cycle_failed", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _reasoning_loop(self, events: list[dict]) -> dict[str, Any]:
        """Core reasoning loop with tool use, exception isolation, and context safety."""
        grounded_system_prompt = f"""{self.persona}

REPOSITORY ARCHITECTURE & GROUNDING:
- Main Repo: subzone/my-it-crew
- Settings: src/config.py (Pydantic SettingsConfigDict)
- Agents: src/agents/base.py, src/agents/*.py
- Tools: src/tools/github_tools.py, src/tools/coding_tools.py, src/tools/chat_tools.py
- Unit Tests: tests/test_*.py (pytest, always mock network/DB)
- Kubernetes Manifests: k8s/base/*.yaml
- Zero-Stub Policy: Never create 1-line # TODO stubs or placeholder paths (path/to/file). All code must be complete and pass syntax checks."""

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": grounded_system_prompt},
            {
                "role": "user",
                "content": self._format_events(events),
            },
        ]

        tool_definitions = [t["definition"] for t in self.tools.values()] or None
        actions_taken: list[dict[str, Any]] = []

        for iteration in range(self.max_iterations):
            # Context window protection: keep system + user + last 8 messages if history grows long
            if len(messages) > 12:
                messages = [messages[0], messages[1]] + messages[-8:]

            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tool_definitions,
                    temperature=0.1,
                    tool_choice="auto" if tool_definitions else None,
                )
            except Exception as e:
                self.log.error("llm_call_failed", error=str(e), model=self.model)
                return {
                    "status": "error",
                    "error": f"LLM call failed: {e}",
                    "actions": actions_taken,
                    "iterations": iteration + 1,
                }

            choice = response.choices[0]

            # If no tool calls, we're done reasoning
            if not choice.message.tool_calls:
                return {
                    "status": "completed",
                    "summary": choice.message.content or "Completed without text summary.",
                    "actions": actions_taken,
                    "iterations": iteration + 1,
                }

            # Serialize assistant message cleanly
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": choice.message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in choice.message.tool_calls
                ],
            }
            messages.append(assistant_msg)

            # Execute tool calls with full exception isolation
            for tool_call in choice.message.tool_calls:
                func_name = tool_call.function.name
                raw_args = tool_call.function.arguments or "{}"
                func_args = self._safe_parse_json(raw_args)

                self.log.info("tool_call", tool=func_name, args=func_args)

                if func_name in self.tools:
                    try:
                        func = self.tools[func_name]["function"]
                        if inspect.iscoroutinefunction(func):
                            result = await func(**func_args)
                        else:
                            result = func(**func_args)
                    except Exception as exc:
                        self.log.warning("tool_execution_error", tool=func_name, error=str(exc))
                        result = f"Error executing {func_name}: {exc}"
                else:
                    result = f"Unknown tool: {func_name}. Available: {list(self.tools.keys())}"

                actions_taken.append(
                    {
                        "tool": func_name,
                        "args": func_args,
                        "result": str(result)[:500],
                    }
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result),
                    }
                )

        return {
            "status": "max_iterations",
            "summary": "Reached maximum allowed tool iterations for this cycle.",
            "actions": actions_taken,
            "iterations": self.max_iterations,
        }

    @staticmethod
    def _safe_parse_json(raw: str) -> dict[str, Any]:
        """Safely parse JSON arguments, repairing common formatting flaws."""
        if not raw or not raw.strip():
            return {}
        cleaned = raw.strip()
        # Strip markdown code fencing if model wrapped JSON in ```json ... ```
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
            return {"value": parsed}
        except Exception:
            # Fallback: attempt to find outermost { ... }
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass
            return {"raw_input": cleaned}

    def _format_events(self, events: list[dict]) -> str:
        """Format events into a prompt for the agent."""
        now = datetime.now(UTC).isoformat()
        lines = [f"Current time: {now}\n\nNew events to process:\n"]
        for i, event in enumerate(events, 1):
            lines.append(
                f"{i}. [{event.get('type', 'unknown')}] {event.get('title', '')}: "
                f"{event.get('body', '')}"
            )
        lines.append("\nBased on your role and responsibilities, decide what actions to take.")
        return "\n".join(lines)

    @abstractmethod
    async def perceive(self) -> list[dict]:
        """Check for new events, messages, and tasks. Returns list of events."""
        ...

    @abstractmethod
    async def reflect(self, result: dict[str, Any]) -> None:
        """Reflect on the cycle outcome. Update memory, log decisions."""
        ...
