"""Base agent class with autonomy loop."""

import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from src.config import Settings

logger = structlog.get_logger()


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


class BaseAgent(ABC):
    """Base class for all autonomous agents.

    Implements the autonomy loop:
    1. Perceive — Check for new events, messages, tasks
    2. Think — Analyze context, reason about next steps
    3. Plan — Decide on actions to take
    4. Act — Execute actions using tools
    5. Reflect — Evaluate outcomes, update memory
    """

    def __init__(self, agent_id: str, persona: str, model: str = "qwen3.5-local"):
        self.agent_id = agent_id
        self.persona = persona
        self.model = model
        self.settings = Settings()
        self.state = AgentState(agent_id=agent_id)
        self.client = AsyncOpenAI(
            base_url=self.settings.litellm_api_base,
            api_key=self.settings.litellm_api_key,
        )
        self.tools: dict[str, Any] = {}
        self.max_iterations = 5
        self.log = logger.bind(agent=agent_id)

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
        """Execute one full autonomy cycle."""
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
        """Core reasoning loop with tool use."""
        messages = [
            {"role": "system", "content": self.persona},
            {
                "role": "user",
                "content": self._format_events(events),
            },
        ]

        tool_definitions = [t["definition"] for t in self.tools.values()] or None
        actions_taken = []

        for iteration in range(self.max_iterations):
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tool_definitions,
                tool_choice="auto" if tool_definitions else None,
            )

            choice = response.choices[0]

            # If no tool calls, we're done reasoning
            if not choice.message.tool_calls:
                return {
                    "status": "completed",
                    "summary": choice.message.content,
                    "actions": actions_taken,
                    "iterations": iteration + 1,
                }

            # Execute tool calls
            messages.append(choice.message.model_dump())

            for tool_call in choice.message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)

                self.log.info("tool_call", tool=func_name, args=func_args)

                if func_name in self.tools:
                    result = await self.tools[func_name]["function"](**func_args)
                else:
                    result = f"Unknown tool: {func_name}"

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
            "actions": actions_taken,
            "iterations": self.max_iterations,
        }

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
