"""Database tools for storing and managing discovered AI API providers."""

import json
import os
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger()

# We use httpx + raw SQL via a lightweight helper since asyncpg
# would require an additional dependency. Instead we talk to the
# postgres directly using the `psycopg` approach via aiohttp, or
# simpler: we bundle a tiny async PG client using the already-available
# httpx for HTTP-based testing and keep provider data in a JSON file
# as a bootstrap, with proper PG integration.

# Actually let's use asyncpg — it's the right tool.
try:
    import asyncpg
except ImportError:
    asyncpg = None  # type: ignore[assignment]


DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://cigance:c1g4nc3-s3cr3t-2024@cigance-db:5432/cigance"
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS providers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    api_key TEXT,
    models JSONB DEFAULT '[]'::jsonb,
    capabilities JSONB DEFAULT '{}'::jsonb,
    status TEXT DEFAULT 'untested',
    rate_limit_info TEXT,
    free_tier_details TEXT,
    last_checked TIMESTAMP WITH TIME ZONE,
    last_working TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notes TEXT,
    UNIQUE(name, base_url)
);

CREATE TABLE IF NOT EXISTS models (
    id SERIAL PRIMARY KEY,
    provider_id INTEGER REFERENCES providers(id) ON DELETE CASCADE,
    model_id TEXT NOT NULL,
    display_name TEXT,
    capabilities JSONB DEFAULT '{}'::jsonb,
    context_window INTEGER,
    tool_calling BOOLEAN DEFAULT FALSE,
    vision BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'untested',
    last_tested TIMESTAMP WITH TIME ZONE,
    last_working TIMESTAMP WITH TIME ZONE,
    response_time_ms INTEGER,
    notes TEXT,
    UNIQUE(provider_id, model_id)
);

CREATE INDEX IF NOT EXISTS idx_models_tool_calling ON models(tool_calling) WHERE tool_calling = TRUE;
CREATE INDEX IF NOT EXISTS idx_models_status ON models(status);
CREATE INDEX IF NOT EXISTS idx_providers_status ON providers(status);
"""


class DBTools:
    """Database operations for AI provider/model registry."""

    def __init__(self):
        self._pool: Any = None

    async def _get_pool(self):
        if self._pool is None:
            if asyncpg is None:
                raise RuntimeError("asyncpg not installed")
            self._pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
            # Initialize schema
            async with self._pool.acquire() as conn:
                await conn.execute(SCHEMA_SQL)
            logger.info("db_initialized")
        return self._pool

    async def add_provider(
        self,
        name: str,
        base_url: str,
        api_key: str | None = None,
        free_tier_details: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Add or update an AI API provider."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO providers (name, base_url, api_key, free_tier_details, notes)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (name, base_url) DO UPDATE SET
                    api_key = COALESCE(EXCLUDED.api_key, providers.api_key),
                    free_tier_details = COALESCE(EXCLUDED.free_tier_details, providers.free_tier_details),
                    notes = COALESCE(EXCLUDED.notes, providers.notes)
                RETURNING id, name, base_url
                """,
                name,
                base_url,
                api_key,
                free_tier_details,
                notes,
            )
            logger.info("provider_added", name=name, id=row["id"])
            return {"id": row["id"], "name": row["name"], "base_url": row["base_url"]}

    async def add_model(
        self,
        provider_name: str,
        model_id: str,
        display_name: str | None = None,
        tool_calling: bool = False,
        vision: bool = False,
        context_window: int | None = None,
        capabilities: dict | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Add or update a model under a provider."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Find provider
            provider = await conn.fetchrow(
                "SELECT id FROM providers WHERE name = $1", provider_name
            )
            if not provider:
                return {"error": f"Provider '{provider_name}' not found. Add it first."}

            row = await conn.fetchrow(
                """
                INSERT INTO models (provider_id, model_id, display_name, tool_calling, vision,
                                   context_window, capabilities, notes)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (provider_id, model_id) DO UPDATE SET
                    display_name = COALESCE(EXCLUDED.display_name, models.display_name),
                    tool_calling = EXCLUDED.tool_calling,
                    vision = EXCLUDED.vision,
                    context_window = COALESCE(EXCLUDED.context_window, models.context_window),
                    capabilities = EXCLUDED.capabilities,
                    notes = COALESCE(EXCLUDED.notes, models.notes)
                RETURNING id, model_id, tool_calling
                """,
                provider["id"],
                model_id,
                display_name,
                tool_calling,
                vision,
                context_window,
                json.dumps(capabilities or {}),
                notes,
            )
            logger.info("model_added", model=model_id, provider=provider_name)
            return {
                "id": row["id"],
                "model_id": row["model_id"],
                "tool_calling": row["tool_calling"],
            }

    async def list_providers(self, status: str | None = None) -> list[dict[str, Any]]:
        """List all providers, optionally filtered by status."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    "SELECT id, name, base_url, status, free_tier_details, last_checked "
                    "FROM providers WHERE status = $1 ORDER BY name",
                    status,
                )
            else:
                rows = await conn.fetch(
                    "SELECT id, name, base_url, status, free_tier_details, last_checked "
                    "FROM providers ORDER BY name"
                )
            return [dict(r) for r in rows]

    async def list_models(
        self,
        provider_name: str | None = None,
        tool_calling_only: bool = False,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List models with optional filters."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            query = """
                SELECT m.id, m.model_id, m.display_name, m.tool_calling, m.vision,
                       m.context_window, m.status, m.response_time_ms, m.last_working,
                       p.name as provider_name, p.base_url
                FROM models m JOIN providers p ON m.provider_id = p.id
                WHERE 1=1
            """
            params: list[Any] = []
            idx = 1

            if provider_name:
                query += f" AND p.name = ${idx}"
                params.append(provider_name)
                idx += 1
            if tool_calling_only:
                query += " AND m.tool_calling = TRUE"
            if status:
                query += f" AND m.status = ${idx}"
                params.append(status)
                idx += 1

            query += " ORDER BY p.name, m.model_id"
            rows = await conn.fetch(query, *params)
            return [dict(r) for r in rows]

    async def update_model_status(
        self,
        provider_name: str,
        model_id: str,
        status: str,
        response_time_ms: int | None = None,
    ) -> dict[str, Any]:
        """Update model status after testing."""
        pool = await self._get_pool()
        now = datetime.now(UTC)
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE models SET status = $1, last_tested = $2,
                    last_working = CASE WHEN $1 = 'working' THEN $2 ELSE last_working END,
                    response_time_ms = COALESCE($3, response_time_ms)
                FROM providers p
                WHERE models.provider_id = p.id AND p.name = $4 AND models.model_id = $5
                """,
                status,
                now,
                response_time_ms,
                provider_name,
                model_id,
            )
            return {"updated": result, "model": model_id, "status": status}

    async def update_provider_status(self, name: str, status: str) -> dict[str, Any]:
        """Update provider status."""
        pool = await self._get_pool()
        now = datetime.now(UTC)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE providers SET status = $1, last_checked = $2,
                    last_working = CASE WHEN $1 = 'working' THEN $2 ELSE last_working END
                WHERE name = $3
                """,
                status,
                now,
                name,
            )
            return {"provider": name, "status": status}

    async def get_working_models_for_rewire(self) -> list[dict[str, Any]]:
        """Get all working models suitable for LiteLLM rewiring."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT m.model_id, m.tool_calling, m.vision, m.context_window,
                       m.response_time_ms, p.name as provider, p.base_url, p.api_key
                FROM models m JOIN providers p ON m.provider_id = p.id
                WHERE m.status = 'working' AND p.status = 'working'
                ORDER BY m.tool_calling DESC, m.response_time_ms ASC NULLS LAST
                """
            )
            return [dict(r) for r in rows]
