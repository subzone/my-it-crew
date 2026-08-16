"""Scraper tools for discovering and testing free AI API endpoints."""

import time
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

# Known free AI API providers and their endpoints
KNOWN_FREE_PROVIDERS = [
    {
        "name": "nvidia-nim",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "signup_url": "https://build.nvidia.com",
        "free_tier": "1000 req/day across all models, free API key",
        "notes": "Best free option. Many models with tool calling.",
    },
    {
        "name": "groq",
        "base_url": "https://api.groq.com/openai/v1",
        "signup_url": "https://console.groq.com",
        "free_tier": "Free tier: 30 req/min Llama 3.3 70B, 30 req/min Mixtral",
        "notes": "Very fast inference. OpenAI-compatible. Tool calling supported.",
    },
    {
        "name": "cerebras",
        "base_url": "https://api.cerebras.ai/v1",
        "signup_url": "https://cloud.cerebras.ai",
        "free_tier": "Free tier: 30 req/min, 1M tokens/day",
        "notes": "Fastest inference. Llama 3.3 70B. Tool calling works.",
    },
    {
        "name": "sambanova",
        "base_url": "https://api.sambanova.ai/v1",
        "signup_url": "https://cloud.sambanova.ai",
        "free_tier": "Free developer tier available",
        "notes": "Fast inference on custom hardware. OpenAI-compatible.",
    },
    {
        "name": "together-ai",
        "base_url": "https://api.together.xyz/v1",
        "signup_url": "https://www.together.ai",
        "free_tier": "$5 free credit on signup",
        "notes": "Wide model selection. Tool calling on select models.",
    },
    {
        "name": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "signup_url": "https://openrouter.ai",
        "free_tier": "Free models available (marked :free in model list)",
        "notes": "Aggregator. Some models free. OpenAI-compatible.",
    },
    {
        "name": "huggingface",
        "base_url": "https://api-inference.huggingface.co/v1",
        "signup_url": "https://huggingface.co",
        "free_tier": "Free Inference API for public models, rate limited",
        "notes": "Serverless inference. Many models. Rate limits vary.",
    },
    {
        "name": "github-models",
        "base_url": "https://models.inference.ai.azure.com",
        "signup_url": "https://github.com/marketplace/models",
        "free_tier": "Free tier: 150 req/day for GPT-4o-mini, others vary",
        "notes": "GitHub-hosted models. Free with GitHub account. Tool calling works.",
    },
    {
        "name": "cohere",
        "base_url": "https://api.cohere.ai/v2",
        "signup_url": "https://dashboard.cohere.com",
        "free_tier": "Free trial tier: 1000 req/month",
        "notes": "Command R+ model. Good for RAG. Limited free tier.",
    },
    {
        "name": "mistral",
        "base_url": "https://api.mistral.ai/v1",
        "signup_url": "https://console.mistral.ai",
        "free_tier": "Free tier available with limits",
        "notes": "Mistral models. Tool calling supported.",
    },
    {
        "name": "fireworks-ai",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "signup_url": "https://fireworks.ai",
        "free_tier": "$1 free credit on signup",
        "notes": "Fast inference. Many open models. Tool calling on some.",
    },
    {
        "name": "deepinfra",
        "base_url": "https://api.deepinfra.com/v1/openai",
        "signup_url": "https://deepinfra.com",
        "free_tier": "$5 free credit on signup",
        "notes": "Many open-source models. OpenAI-compatible.",
    },
]

# Known free security models
KNOWN_SECURITY_MODELS = [
    {
        "provider": "nvidia-nim",
        "model_id": "nvidia/llama-3.1-nemoguard-8b-content-safety",
        "type": "content-safety",
        "description": "Content safety classifier. Detects harmful content categories.",
        "tool_calling": False,
    },
    {
        "provider": "nvidia-nim",
        "model_id": "nvidia/llama-3.1-nemoguard-8b-topic-control",
        "type": "topic-control",
        "description": "Topic control guard. Keeps conversations on-topic.",
        "tool_calling": False,
    },
    {
        "provider": "nvidia-nim",
        "model_id": "nvidia/llama-3.1-nemotron-safety-guard-8b-v3",
        "type": "safety-guard",
        "description": "General safety guard. Prompt injection, jailbreak detection.",
        "tool_calling": False,
    },
    {
        "provider": "nvidia-nim",
        "model_id": "meta/llama-guard-4-12b",
        "type": "content-safety",
        "description": "Meta's Llama Guard 4. Multi-category content safety.",
        "tool_calling": False,
    },
    {
        "provider": "nvidia-nim",
        "model_id": "nvidia/nemotron-3.5-content-safety",
        "type": "content-safety",
        "description": "Nemotron content safety. Fast, accurate classification.",
        "tool_calling": False,
    },
]


class ScraperTools:
    """Tools for discovering and testing AI API endpoints."""

    async def test_endpoint(
        self,
        base_url: str,
        api_key: str,
        model: str | None = None,
        test_tool_calling: bool = True,
    ) -> dict[str, Any]:
        """Test if an AI API endpoint is working and measure response time.

        Tests basic completion and optionally tool calling capability.
        """
        results: dict[str, Any] = {
            "base_url": base_url,
            "model": model,
            "reachable": False,
            "completion_works": False,
            "tool_calling": False,
            "response_time_ms": None,
            "error": None,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Test basic models endpoint
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # First, try to list models if no model specified
                if not model:
                    resp = await client.get(f"{base_url}/models", headers=headers)
                    if resp.status_code == 200:
                        results["reachable"] = True
                        data = resp.json()
                        models = data.get("data", [])
                        if models:
                            model = models[0].get("id", "")
                            results["available_models"] = [m.get("id") for m in models[:10]]
                    else:
                        results["error"] = f"Models endpoint returned {resp.status_code}"
                        return results

                if not model:
                    results["error"] = "No model available"
                    return results

                results["reachable"] = True
                results["model"] = model

                # Test basic completion
                start = time.time()
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": "Say 'hello' and nothing else."}],
                    "max_tokens": 10,
                }
                resp = await client.post(
                    f"{base_url}/chat/completions", headers=headers, json=payload
                )
                elapsed_ms = int((time.time() - start) * 1000)
                results["response_time_ms"] = elapsed_ms

                if resp.status_code == 200:
                    results["completion_works"] = True
                else:
                    results["error"] = f"Completion returned {resp.status_code}: {resp.text[:200]}"
                    return results

                # Test tool calling
                if test_tool_calling:
                    tool_payload = {
                        "model": model,
                        "messages": [{"role": "user", "content": "Create an issue titled 'Test'"}],
                        "tools": [
                            {
                                "type": "function",
                                "function": {
                                    "name": "create_issue",
                                    "description": "Create an issue",
                                    "parameters": {
                                        "type": "object",
                                        "properties": {"title": {"type": "string"}},
                                        "required": ["title"],
                                    },
                                },
                            }
                        ],
                        "tool_choice": "auto",
                        "max_tokens": 100,
                    }
                    resp = await client.post(
                        f"{base_url}/chat/completions", headers=headers, json=tool_payload
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        msg = data.get("choices", [{}])[0].get("message", {})
                        if msg.get("tool_calls"):
                            results["tool_calling"] = True

        except httpx.TimeoutException:
            results["error"] = "Request timed out (30s)"
        except Exception as e:
            results["error"] = str(e)[:200]

        logger.info(
            "endpoint_tested",
            url=base_url,
            model=model,
            works=results["completion_works"],
            tools=results["tool_calling"],
        )
        return results

    async def list_models_at_endpoint(self, base_url: str, api_key: str) -> dict[str, Any]:
        """List available models at an API endpoint."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{base_url}/models", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("id") for m in data.get("data", [])]
                    return {"status": "ok", "models": models, "count": len(models)}
                return {"status": "error", "code": resp.status_code, "body": resp.text[:200]}
        except Exception as e:
            return {"status": "error", "error": str(e)[:200]}

    def get_known_providers(self) -> list[dict[str, Any]]:
        """Return list of known free AI API providers."""
        return KNOWN_FREE_PROVIDERS

    def get_known_security_models(self) -> list[dict[str, Any]]:
        """Return list of known free security/safety models."""
        return KNOWN_SECURITY_MODELS

    async def search_openrouter_free_models(self, api_key: str | None = None) -> dict[str, Any]:
        """Search OpenRouter for free models (no API key needed for model list)."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get("https://openrouter.ai/api/v1/models")
                if resp.status_code == 200:
                    data = resp.json()
                    free_models = []
                    for m in data.get("data", []):
                        pricing = m.get("pricing", {})
                        # Free models have $0 pricing
                        if pricing.get("prompt") == "0" and pricing.get("completion") == "0":
                            free_models.append(
                                {
                                    "id": m["id"],
                                    "name": m.get("name", ""),
                                    "context_length": m.get("context_length"),
                                }
                            )
                    return {
                        "status": "ok",
                        "free_models": free_models,
                        "count": len(free_models),
                    }
                return {"status": "error", "code": resp.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)[:200]}
