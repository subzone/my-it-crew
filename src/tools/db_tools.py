"""Database tools for storing and managing discovered AI API providers."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

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
    """Database operations for AI provider/model registry with hybrid PG/file fallback."""

    def __init__(self, fallback_store_path: str = "data/cigance_registry.json"):
        self._pool: Any = None
        self._pg_disabled: bool = False
        self._fallback_path = Path(fallback_store_path)
        self._file_store: dict[str, Any] = {"providers": [], "models": []}
        self._load_file_store()

    def _load_file_store(self) -> None:
        """Load file-backed registry if present."""
        if self._fallback_path.exists():
            try:
                self._file_store = json.loads(self._fallback_path.read_text())
            except Exception as e:
                logger.warning("file_store_load_failed", error=str(e))
                self._file_store = {"providers": [], "models": []}

    def _save_file_store(self) -> None:
        """Persist in-memory store atomically to file."""
        try:
            self._fallback_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._fallback_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(self._file_store, indent=2))
            tmp_path.replace(self._fallback_path)
        except Exception as e:
            logger.warning("file_store_save_failed", error=str(e))

    async def _get_pool(self):
        if self._pg_disabled:
            return None
        if self._pool is None:
            if asyncpg is None:
                self._pg_disabled = True
                return None
            try:
                self._pool = await asyncpg.create_pool(
                    DATABASE_URL, min_size=1, max_size=5, timeout=2.0
                )
                async with self._pool.acquire() as conn:
                    await conn.execute(SCHEMA_SQL)
                logger.info("db_initialized")
            except Exception as exc:
                logger.warning("pg_connect_failed_using_file_fallback", error=str(exc))
                self._pg_disabled = True
                self._pool = None
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
        if pool:
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
                logger.info("provider_added_pg", name=name, id=row["id"])
                return {"id": row["id"], "name": row["name"], "base_url": row["base_url"]}

        # File-backed fallback
        providers = self._file_store["providers"]
        existing = next(
            (p for p in providers if p["name"] == name and p["base_url"] == base_url), None
        )
        if existing:
            if api_key:
                existing["api_key"] = api_key
            if free_tier_details:
                existing["free_tier_details"] = free_tier_details
            if notes:
                existing["notes"] = notes
            p_id = existing["id"]
        else:
            p_id = len(providers) + 1
            providers.append(
                {
                    "id": p_id,
                    "name": name,
                    "base_url": base_url,
                    "api_key": api_key,
                    "status": "untested",
                    "free_tier_details": free_tier_details,
                    "notes": notes,
                    "last_checked": None,
                    "last_working": None,
                }
            )
        self._save_file_store()
        logger.info("provider_added_file", name=name, id=p_id)
        return {"id": p_id, "name": name, "base_url": base_url}

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
        if pool:
            async with pool.acquire() as conn:
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
                logger.info("model_added_pg", model=model_id, provider=provider_name)
                return {
                    "id": row["id"],
                    "model_id": row["model_id"],
                    "tool_calling": row["tool_calling"],
                }

        # File-backed fallback
        providers = self._file_store["providers"]
        provider = next((p for p in providers if p["name"] == provider_name), None)
        if not provider:
            return {"error": f"Provider '{provider_name}' not found. Add it first."}

        models = self._file_store["models"]
        existing = next(
            (m for m in models if m["provider_id"] == provider["id"] and m["model_id"] == model_id),
            None,
        )
        if existing:
            existing["display_name"] = display_name or existing.get("display_name")
            existing["tool_calling"] = tool_calling
            existing["vision"] = vision
            existing["context_window"] = context_window or existing.get("context_window")
            existing["capabilities"] = capabilities or existing.get("capabilities", {})
            existing["notes"] = notes or existing.get("notes")
            m_id = existing["id"]
        else:
            m_id = len(models) + 1
            models.append(
                {
                    "id": m_id,
                    "provider_id": provider["id"],
                    "provider_name": provider_name,
                    "model_id": model_id,
                    "display_name": display_name,
                    "tool_calling": tool_calling,
                    "vision": vision,
                    "context_window": context_window,
                    "capabilities": capabilities or {},
                    "status": "untested",
                    "response_time_ms": None,
                    "last_tested": None,
                    "last_working": None,
                    "notes": notes,
                }
            )
        self._save_file_store()
        logger.info("model_added_file", model=model_id, provider=provider_name)
        return {"id": m_id, "model_id": model_id, "tool_calling": tool_calling}

    async def list_providers(self, status: str | None = None) -> list[dict[str, Any]]:
        """List all providers, optionally filtered by status."""
        pool = await self._get_pool()
        if pool:
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

        providers = self._file_store["providers"]
        if status:
            return [p for p in providers if p.get("status") == status]
        return list(providers)

    async def list_models(
        self,
        provider_name: str | None = None,
        tool_calling_only: bool = False,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List models with optional filters."""
        pool = await self._get_pool()
        if pool:
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

        models = []
        providers_map = {p["id"]: p for p in self._file_store["providers"]}
        for m in self._file_store["models"]:
            p = providers_map.get(m["provider_id"], {})
            p_name = p.get("name", "")
            if provider_name and p_name != provider_name:
                continue
            if tool_calling_only and not m.get("tool_calling"):
                continue
            if status and m.get("status") != status:
                continue
            item = dict(m)
            item["provider_name"] = p_name
            item["base_url"] = p.get("base_url", "")
            models.append(item)
        return models

    async def update_model_status(
        self,
        provider_name: str,
        model_id: str,
        status: str,
        response_time_ms: int | None = None,
    ) -> dict[str, Any]:
        """Update model status after testing."""
        now = datetime.now(UTC)
        pool = await self._get_pool()
        if pool:
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
                return {"updated": str(result), "model": model_id, "status": status}

        providers_map = {p["name"]: p["id"] for p in self._file_store["providers"]}
        p_id = providers_map.get(provider_name)
        if p_id:
            for m in self._file_store["models"]:
                if m["provider_id"] == p_id and m["model_id"] == model_id:
                    m["status"] = status
                    m["last_tested"] = now.isoformat()
                    if status == "working":
                        m["last_working"] = now.isoformat()
                    if response_time_ms is not None:
                        m["response_time_ms"] = response_time_ms
            self._save_file_store()
        return {"updated": "file_updated", "model": model_id, "status": status}

    async def update_provider_status(self, name: str, status: str) -> dict[str, Any]:
        """Update provider status."""
        now = datetime.now(UTC)
        pool = await self._get_pool()
        if pool:
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

        for p in self._file_store["providers"]:
            if p["name"] == name:
                p["status"] = status
                p["last_checked"] = now.isoformat()
                if status == "working":
                    p["last_working"] = now.isoformat()
        self._save_file_store()
        return {"provider": name, "status": status}

    async def get_working_models_for_rewire(self) -> list[dict[str, Any]]:
        """Get all working models suitable for LiteLLM rewiring."""
        pool = await self._get_pool()
        if pool:
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

        working = []
        providers_map = {
            p["id"]: p for p in self._file_store["providers"] if p.get("status") == "working"
        }
        for m in self._file_store["models"]:
            if m.get("status") == "working" and m["provider_id"] in providers_map:
                p = providers_map[m["provider_id"]]
                working.append(
                    {
                        "model_id": m["model_id"],
                        "tool_calling": m.get("tool_calling", False),
                        "vision": m.get("vision", False),
                        "context_window": m.get("context_window"),
                        "response_time_ms": m.get("response_time_ms"),
                        "provider": p["name"],
                        "base_url": p["base_url"],
                        "api_key": p.get("api_key"),
                    }
                )
        working.sort(
            key=lambda x: (not x.get("tool_calling", False), x.get("response_time_ms") or 99999)
        )
        return working

    async def export_litellm_model_list(self) -> dict[str, Any]:
        """Generate a LiteLLM proxy model_list and fallbacks from working verified models."""
        working = await self.get_working_models_for_rewire()
        model_list = []
        fallbacks: dict[str, list[str]] = {}

        tool_calling_models = [m for m in working if m.get("tool_calling")]

        for m in working:
            name = f"{m['provider']}/{m['model_id']}"
            entry = {
                "model_name": name,
                "litellm_params": {
                    "model": f"{m['provider']}/{m['model_id']}",
                    "api_base": m["base_url"],
                },
            }
            if m.get("api_key"):
                entry["litellm_params"]["api_key"] = m["api_key"]
            model_list.append(entry)

        # Fallback cascades for primary routing
        if tool_calling_models:
            primary_fast = (
                f"{tool_calling_models[0]['provider']}/{tool_calling_models[0]['model_id']}"
            )
            fallback_chain = [f"{m['provider']}/{m['model_id']}" for m in tool_calling_models[1:4]]
            if fallback_chain:
                fallbacks[primary_fast] = fallback_chain

        return {
            "model_list": model_list,
            "fallbacks": fallbacks,
            "total_working": len(working),
            "tool_calling_count": len(tool_calling_models),
        }
