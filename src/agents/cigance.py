"""Cigance Agent — Discovers, tests, and manages free AI API resources."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.chat_tools import ChatTools
from src.tools.db_tools import DBTools
from src.tools.scraper_tools import ScraperTools

CIGANCE_PERSONA = """You are Cigance, the AI Resource Scout for My IT Crew.

Your job is to discover, test, and maintain a database of FREE AI API endpoints
that the company can use. You are obsessed with finding free tokens, free tiers,
and free models that support tool calling.

Your responsibilities:
1. DISCOVER: Find free AI API providers (NVIDIA NIM, Groq, Cerebras, etc.)
2. TEST: Verify endpoints work, measure response times, check tool calling support
3. CATALOG: Store everything in the database with capabilities and status
4. MONITOR: Periodically re-test known endpoints to detect outages or changes
5. REPORT: Post findings to #engineering channel when you find new working APIs
6. SECURITY: Also track free security/safety models for the security team

Your workflow each cycle:
1. Check if there are untested providers in the database
2. If found, test them (test_endpoint tool)
3. If database is empty, seed it with known providers (get_known_providers)
4. Search for free models on aggregators (OpenRouter free models)
5. Update statuses of previously working models (re-test periodically)
6. Report significant findings (new working models with tool calling) to #engineering

IMPORTANT:
- Only store FREE APIs. No paid-only providers.
- Focus on models that support TOOL CALLING — that's what we need most.
- Test everything before marking it as 'working'. Never trust without verification.
- When you find a new working model with tool calling, post to #engineering immediately.
- Track security models separately — the security team needs content safety, prompt injection detection.

Database status values:
- 'untested' — not yet verified
- 'working' — confirmed working
- 'rate_limited' — works but hitting limits
- 'dead' — endpoint is down or key revoked
- 'no_tool_calling' — works for completion but not tool calling
"""


class CiganceAgent(BaseAgent):
    """Cigance — AI resource discovery and management agent."""

    def __init__(self):
        super().__init__(agent_id="cigance", persona=CIGANCE_PERSONA)
        self.max_iterations = 15  # Needs more iterations for seeding/testing
        self._setup_tools()

    def _setup_tools(self) -> None:
        db = DBTools()
        scraper = ScraperTools()
        chat = ChatTools(self.settings)

        # DB tools
        self.register_tool(
            "add_provider",
            db.add_provider,
            "Add a new AI API provider to the database",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Provider name (e.g. 'groq')"},
                    "base_url": {"type": "string", "description": "API base URL"},
                    "api_key": {"type": "string", "description": "API key (if available)"},
                    "free_tier_details": {
                        "type": "string",
                        "description": "Details about free tier limits",
                    },
                    "notes": {"type": "string", "description": "Additional notes"},
                },
                "required": ["name", "base_url"],
            },
        )
        self.register_tool(
            "add_model",
            db.add_model,
            "Add a model under a provider",
            {
                "type": "object",
                "properties": {
                    "provider_name": {"type": "string", "description": "Provider name"},
                    "model_id": {"type": "string", "description": "Model ID as used in API"},
                    "display_name": {"type": "string", "description": "Human-friendly name"},
                    "tool_calling": {
                        "type": "boolean",
                        "description": "Whether model supports tool/function calling",
                    },
                    "vision": {"type": "boolean", "description": "Whether model supports vision"},
                    "context_window": {"type": "integer", "description": "Context window size"},
                    "notes": {"type": "string"},
                },
                "required": ["provider_name", "model_id"],
            },
        )
        self.register_tool(
            "list_providers",
            db.list_providers,
            "List all providers in the database, optionally filtered by status",
            {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status: untested, working, dead, rate_limited",
                    },
                },
            },
        )
        self.register_tool(
            "list_models",
            db.list_models,
            "List models in database with optional filters",
            {
                "type": "object",
                "properties": {
                    "provider_name": {"type": "string", "description": "Filter by provider"},
                    "tool_calling_only": {
                        "type": "boolean",
                        "description": "Only show models with tool calling",
                    },
                    "status": {"type": "string", "description": "Filter by status"},
                },
            },
        )
        self.register_tool(
            "update_model_status",
            db.update_model_status,
            "Update a model's status after testing",
            {
                "type": "object",
                "properties": {
                    "provider_name": {"type": "string"},
                    "model_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "description": "working, dead, rate_limited, no_tool_calling",
                    },
                    "response_time_ms": {"type": "integer"},
                },
                "required": ["provider_name", "model_id", "status"],
            },
        )
        self.register_tool(
            "update_provider_status",
            db.update_provider_status,
            "Update a provider's overall status",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "status": {"type": "string"},
                },
                "required": ["name", "status"],
            },
        )
        self.register_tool(
            "get_working_models_for_rewire",
            db.get_working_models_for_rewire,
            "Get all working models suitable for LiteLLM config rewiring",
            {"type": "object", "properties": {}},
        )

        # Scraper tools
        self.register_tool(
            "test_endpoint",
            scraper.test_endpoint,
            "Test an AI API endpoint for availability, speed, and tool calling support",
            {
                "type": "object",
                "properties": {
                    "base_url": {"type": "string", "description": "API base URL to test"},
                    "api_key": {"type": "string", "description": "API key to use"},
                    "model": {
                        "type": "string",
                        "description": "Specific model to test (optional)",
                    },
                    "test_tool_calling": {
                        "type": "boolean",
                        "description": "Whether to test tool calling capability",
                    },
                },
                "required": ["base_url", "api_key"],
            },
        )
        self.register_tool(
            "list_models_at_endpoint",
            scraper.list_models_at_endpoint,
            "List available models at an API endpoint",
            {
                "type": "object",
                "properties": {
                    "base_url": {"type": "string"},
                    "api_key": {"type": "string"},
                },
                "required": ["base_url", "api_key"],
            },
        )
        self.register_tool(
            "get_known_providers",
            scraper.get_known_providers,
            "Get list of known free AI API providers to seed the database",
            {"type": "object", "properties": {}},
        )
        self.register_tool(
            "get_known_security_models",
            scraper.get_known_security_models,
            "Get list of known free security/safety AI models",
            {"type": "object", "properties": {}},
        )
        self.register_tool(
            "search_openrouter_free_models",
            scraper.search_openrouter_free_models,
            "Search OpenRouter for models with $0 pricing (free)",
            {
                "type": "object",
                "properties": {
                    "api_key": {
                        "type": "string",
                        "description": "OpenRouter API key (optional, listing is free)",
                    },
                },
            },
        )

        # Chat tools
        self.register_tool(
            "send_message",
            chat.send_message,
            "Send a message to a channel (e.g. engineering, general)",
            {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Channel name"},
                    "text": {"type": "string", "description": "Message text"},
                },
                "required": ["channel", "text"],
            },
        )

    async def perceive(self) -> list[dict]:
        """Check what needs to be done — untested providers, stale data, etc."""
        db = DBTools()
        chat = ChatTools(self.settings)
        events = []

        try:
            # Check for DMs
            dms = await chat.get_direct_messages(limit=3)
            for dm in dms:
                events.append(
                    {
                        "type": "direct_message",
                        "title": "DM to Cigance",
                        "body": dm["text"][:500],
                    }
                )
        except Exception as e:
            self.log.warning("dm_check_failed", error=str(e))

        try:
            # Check database state
            providers = await db.list_providers()

            if not providers:
                events.append(
                    {
                        "type": "task",
                        "title": "Empty database",
                        "body": "The provider database is empty. Seed it with known free providers "
                        "using get_known_providers, then add each one with add_provider. "
                        "After seeding, test endpoints to verify they work.",
                    }
                )
            else:
                # Check for untested providers
                untested = [p for p in providers if p.get("status") == "untested"]
                if untested:
                    names = ", ".join(p["name"] for p in untested[:5])
                    events.append(
                        {
                            "type": "task",
                            "title": "Untested providers found",
                            "body": f"These providers need testing: {names}. "
                            f"Use test_endpoint to verify each one works.",
                        }
                    )

                # Check for stale data (not checked in last hour)
                # This would need last_checked comparison - simplified for now
                working = [p for p in providers if p.get("status") == "working"]
                if working and not untested:
                    events.append(
                        {
                            "type": "maintenance",
                            "title": "Routine health check",
                            "body": f"{len(working)} providers are marked working. "
                            f"Consider re-testing a few to ensure they're still alive. "
                            f"Also search OpenRouter for any new free models.",
                        }
                    )
        except Exception as e:
            # DB not ready yet — seed it
            self.log.warning("db_check_failed", error=str(e))
            events.append(
                {
                    "type": "task",
                    "title": "Database initialization needed",
                    "body": "Database may not be initialized yet. "
                    "Start by seeding known providers with get_known_providers "
                    "and adding them with add_provider.",
                }
            )

        if not events:
            events.append(
                {
                    "type": "idle",
                    "title": "All systems nominal",
                    "body": "No urgent tasks. Search for new free AI APIs or re-test existing ones.",
                }
            )

        return events

    async def reflect(self, result: dict[str, Any]) -> None:
        """Log cycle outcome."""
        actions = result.get("actions", [])
        self.log.info(
            "cigance_cycle_complete",
            actions_taken=len(actions),
            summary=result.get("summary", "")[:200],
        )
