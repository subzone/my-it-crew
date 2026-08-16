"""Single-agent worker — runs one agent in its own pod with HTTP trigger support."""

import asyncio
import os
import signal

import structlog
from aiohttp import web

from src.agents.ceo import CEOAgent
from src.agents.cigance import CiganceAgent
from src.agents.cto import CTOAgent
from src.agents.devops import DevOpsAgent
from src.agents.eng_manager import EngManagerAgent
from src.agents.engineer import EngineerAgent
from src.agents.marketer import MarketerAgent
from src.agents.qa_engineer import QAEngineerAgent
from src.agents.reporter import ReporterAgent
from src.agents.ta_specialist import TASpecialistAgent
from src.agents.tech_interviewer import TechInterviewerAgent
from src.config import Settings

logger = structlog.get_logger()

AGENT_REGISTRY = {
    "ceo": CEOAgent,
    "cigance": CiganceAgent,
    "cto": CTOAgent,
    "eng-manager": EngManagerAgent,
    "engineer": EngineerAgent,
    "devops": DevOpsAgent,
    "qa-engineer": QAEngineerAgent,
    "marketer": MarketerAgent,
    "ta-specialist": TASpecialistAgent,
    "tech-interviewer": TechInterviewerAgent,
    "reporter": ReporterAgent,
}


async def run_worker() -> None:
    """Run a single agent in a loop with HTTP trigger support."""
    agent_id = os.environ.get("AGENT_ID")
    if not agent_id:
        logger.error("AGENT_ID env var not set")
        return

    if agent_id not in AGENT_REGISTRY:
        logger.error("unknown_agent", agent_id=agent_id, available=list(AGENT_REGISTRY.keys()))
        return

    settings = Settings()
    interval = settings.cycle_interval_seconds
    agent = AGENT_REGISTRY[agent_id]()
    agent.start()
    running = True
    trigger_event = asyncio.Event()

    def stop() -> None:
        nonlocal running
        running = False
        trigger_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop)

    # HTTP trigger endpoint
    async def handle_trigger(request: web.Request) -> web.Response:
        """Trigger an immediate agent cycle via HTTP."""
        logger.info("trigger_received", agent_id=agent_id)
        trigger_event.set()
        return web.json_response({"status": "triggered", "agent": agent_id})

    async def handle_health(request: web.Request) -> web.Response:
        """Health check."""
        return web.json_response({"status": "ok", "agent": agent_id})

    # Start HTTP server
    app = web.Application()
    app.router.add_post("/trigger", handle_trigger)
    app.router.add_get("/health", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()

    logger.info("worker_starting", agent_id=agent_id, interval=interval, http_port=8080)

    # Run initial cycle
    try:
        result = await agent.run_cycle()
        logger.info(
            "cycle_done",
            agent_id=agent_id,
            status=result.get("status"),
            actions=len(result.get("actions", [])),
        )
    except Exception as e:
        logger.error("cycle_error", agent_id=agent_id, error=str(e))

    while running:
        # Wait for either timer or trigger
        trigger_event.clear()
        try:
            await asyncio.wait_for(trigger_event.wait(), timeout=interval)
            logger.info("triggered_early", agent_id=agent_id)
        except TimeoutError:
            pass  # Normal timer expiry

        if not running:
            break

        try:
            result = await agent.run_cycle()
            logger.info(
                "cycle_done",
                agent_id=agent_id,
                status=result.get("status"),
                actions=len(result.get("actions", [])),
            )
        except Exception as e:
            logger.error("cycle_error", agent_id=agent_id, error=str(e))

    await runner.cleanup()
    logger.info("worker_stopped", agent_id=agent_id)


if __name__ == "__main__":
    asyncio.run(run_worker())
