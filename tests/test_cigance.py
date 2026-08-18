"""Tests for Cigance Agent, ScraperTools, and DBTools hybrid persistence."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.cigance import CiganceAgent
from src.tools.db_tools import DBTools
from src.tools.scraper_tools import ScraperTools


@pytest.fixture
def temp_db_path(tmp_path: Path):
    """Temporary file path for DBTools fallback registry."""
    return str(tmp_path / "test_cigance_registry.json")


class TestDBToolsHybrid:
    """Test hybrid file/PG database operations."""

    @pytest.mark.asyncio
    async def test_add_and_list_provider_fallback(self, temp_db_path: str):
        db = DBTools(fallback_store_path=temp_db_path)
        # Ensure PG is skipped
        db._pg_disabled = True

        res = await db.add_provider(
            name="google-ai-studio",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            free_tier_details="15 RPM Gemini 2.0 Flash",
        )
        assert res["name"] == "google-ai-studio"
        assert res["id"] == 1

        providers = await db.list_providers()
        assert len(providers) == 1
        assert providers[0]["name"] == "google-ai-studio"

    @pytest.mark.asyncio
    async def test_add_and_list_model_fallback(self, temp_db_path: str):
        db = DBTools(fallback_store_path=temp_db_path)
        db._pg_disabled = True

        await db.add_provider(
            name="groq",
            base_url="https://api.groq.com/openai/v1",
        )
        model_res = await db.add_model(
            provider_name="groq",
            model_id="llama-3.3-70b-versatile",
            display_name="Llama 3.3 70B",
            tool_calling=True,
        )
        assert model_res["model_id"] == "llama-3.3-70b-versatile"
        assert model_res["tool_calling"] is True

        models = await db.list_models(provider_name="groq")
        assert len(models) == 1
        assert models[0]["model_id"] == "llama-3.3-70b-versatile"
        assert models[0]["provider_name"] == "groq"

    @pytest.mark.asyncio
    async def test_update_status_and_export_litellm(self, temp_db_path: str):
        db = DBTools(fallback_store_path=temp_db_path)
        db._pg_disabled = True

        await db.add_provider(name="groq", base_url="https://api.groq.com/openai/v1")
        await db.add_model(
            provider_name="groq",
            model_id="llama-3.3-70b",
            tool_calling=True,
        )
        await db.update_provider_status("groq", "working")
        await db.update_model_status("groq", "llama-3.3-70b", "working", response_time_ms=150)

        working = await db.get_working_models_for_rewire()
        assert len(working) == 1
        assert working[0]["model_id"] == "llama-3.3-70b"

        export = await db.export_litellm_model_list()
        assert export["total_working"] == 1
        assert export["tool_calling_count"] == 1
        assert len(export["model_list"]) == 1
        assert export["model_list"][0]["model_name"] == "groq/llama-3.3-70b"


class TestScraperTools:
    """Test ScraperTools known providers and endpoint checks."""

    @pytest.mark.asyncio
    async def test_known_free_providers_includes_gemini(self):
        scraper = ScraperTools()
        providers = await scraper.get_known_providers()
        names = [p["name"] for p in providers]
        assert "google-ai-studio" in names
        assert "groq" in names
        assert "sambanova" in names
        assert "cerebras" in names

    @pytest.mark.asyncio
    async def test_search_openrouter_free_models(self):
        scraper = ScraperTools()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {
                    "id": "meta-llama/llama-3-8b-instruct:free",
                    "name": "Llama 3 8B (free)",
                    "pricing": {"prompt": "0", "completion": "0"},
                },
                {
                    "id": "openai/gpt-4o",
                    "name": "GPT-4o",
                    "pricing": {"prompt": "0.000005", "completion": "0.000015"},
                },
            ]
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            res = await scraper.search_openrouter_free_models()
            assert res["status"] == "ok"
            assert res["count"] == 1
            assert res["free_models"][0]["id"] == "meta-llama/llama-3-8b-instruct:free"


class TestCiganceAgent:
    """Test Cigance Agent tools and perceive flow."""

    def test_cigance_init(self):
        agent = CiganceAgent()
        assert agent.agent_id == "cigance"
        assert "add_provider" in agent.tools
        assert "add_model" in agent.tools
        assert "list_providers" in agent.tools
        assert "test_endpoint" in agent.tools
        assert "export_litellm_config" in agent.tools

    @pytest.mark.asyncio
    async def test_cigance_perceive_empty_db(self, temp_db_path: str):
        agent = CiganceAgent()
        with patch("src.agents.cigance.DBTools") as mock_db_cls:
            mock_db = MagicMock()
            mock_db.list_providers = AsyncMock(return_value=[])
            mock_db_cls.return_value = mock_db

            with patch(
                "src.tools.chat_tools.ChatTools.get_direct_messages",
                new_callable=AsyncMock,
                return_value=[],
            ):
                events = await agent.perceive()
                assert len(events) >= 1
                assert events[0]["type"] == "task"
                assert "Empty database" in events[0]["title"]
