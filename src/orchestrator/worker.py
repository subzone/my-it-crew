"""Single-agent worker — runs one agent in its own pod."""

import asyncio
import os
import signal

import structlog

from src.agents.ceo import CEOAgent
from src.agents.cto import CTOAgent
from src.agents.devops import DevOpsAgent
from src.agents.eng_manager import EngManagerAgent
from src.agents.engineer import EngineerAgent
from src.agents.marketer import MarketerAgent
from src.agents.qa_engineer import QAEngineerAgent
from src.config import Settings

logger = structlog.get_logger()

AGENT_REGISTRY = {
    "ceo": CEOAgent,
    "cto": CTOAgent,
    "eng-manager": EngManagerAgent,
    "engineer": EngineerAgent,
    "devops": DevOpsAgent,
    "qa-engineer": QAEngineerAgent,
    "marketer": MarketerAgent,
}


async def run_worker() -> None:
    """Run a single agent in a loop."""
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
    running = True

    def stop() -> None:
        nonlocal running
        running = False

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop)

    logger.info("worker_starting", agent_id=agent_id, interval=interval)

    while running:
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

        # Wait for next cycle
        for _ in range(interval):
            if not running:
                break
            await asyncio.sleep(1)

    logger.info("worker_stopped", agent_id=agent_id)


if __name__ == "__main__":
    asyncio.run(run_worker())
