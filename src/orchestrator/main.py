"""Main orchestrator — schedules and runs agent autonomy cycles."""

import asyncio
import signal

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.agents.ceo import CEOAgent
from src.agents.cto import CTOAgent
from src.agents.devops import DevOpsAgent
from src.agents.eng_manager import EngManagerAgent
from src.agents.engineer import EngineerAgent
from src.agents.frontend_engineer import FrontendEngineerAgent
from src.agents.fullstack_engineer import FullstackEngineerAgent
from src.agents.marketer import MarketerAgent
from src.agents.qa_engineer import QAEngineerAgent
from src.config import Settings

logger = structlog.get_logger()


class Orchestrator:
    """Manages agent lifecycle and scheduling."""

    def __init__(self):
        self.settings = Settings()
        self.scheduler = AsyncIOScheduler()
        self.agents = {
            "ceo": CEOAgent(),
            "cto": CTOAgent(),
            "eng-manager": EngManagerAgent(),
            "engineer": EngineerAgent(),
            "frontend-engineer": FrontendEngineerAgent(),
            "fullstack-engineer": FullstackEngineerAgent(),
            "devops": DevOpsAgent(),
            "qa-engineer": QAEngineerAgent(),
            "marketer": MarketerAgent(),
        }
        self.running = True

    async def run_agent(self, agent_id: str) -> None:
        """Run a single agent's autonomy cycle."""
        agent = self.agents.get(agent_id)
        if not agent:
            logger.error("agent_not_found", agent_id=agent_id)
            return

        logger.info("running_agent", agent_id=agent_id)
        result = await agent.run_cycle()
        logger.info(
            "agent_cycle_done",
            agent_id=agent_id,
            status=result.get("status"),
            actions=len(result.get("actions", [])),
        )

    def setup_schedules(self) -> None:
        """Configure agent run schedules."""
        interval = self.settings.cycle_interval_seconds

        # C-Suite: every 5 minutes
        self.scheduler.add_job(
            self.run_agent,
            "interval",
            seconds=interval,
            args=["ceo"],
            id="ceo_cycle",
            name="CEO Cycle",
        )
        self.scheduler.add_job(
            self.run_agent,
            "interval",
            seconds=interval * 6,
            args=["cto"],
            id="cto_cycle",
            name="CTO Cycle",
            misfire_grace_time=60,
        )

        # Managers: every 15 minutes
        self.scheduler.add_job(
            self.run_agent,
            "interval",
            seconds=interval * 3,
            args=["eng-manager"],
            id="eng_manager_cycle",
            name="Eng Manager Cycle",
        )

        # Engineers: every 10 minutes
        self.scheduler.add_job(
            self.run_agent,
            "interval",
            seconds=interval * 2,
            args=["engineer"],
            id="engineer_cycle",
            name="Engineer Cycle",
        )
        self.scheduler.add_job(
            self.run_agent,
            "interval",
            seconds=interval * 2,
            args=["frontend-engineer"],
            id="frontend_engineer_cycle",
            name="Frontend Engineer Cycle",
        )
        self.scheduler.add_job(
            self.run_agent,
            "interval",
            seconds=interval * 2,
            args=["fullstack-engineer"],
            id="fullstack_engineer_cycle",
            name="Fullstack Engineer Cycle",
        )
        self.scheduler.add_job(
            self.run_agent,
            "interval",
            seconds=interval * 2,
            args=["devops"],
            id="devops_cycle",
            name="DevOps Cycle",
        )

        # QA: every 10 minutes
        self.scheduler.add_job(
            self.run_agent,
            "interval",
            seconds=interval * 2,
            args=["qa-engineer"],
            id="qa_cycle",
            name="QA Cycle",
        )

        # Marketing: every 60 minutes
        self.scheduler.add_job(
            self.run_agent,
            "interval",
            seconds=interval * 12,
            args=["marketer"],
            id="marketer_cycle",
            name="Marketer Cycle",
        )

    async def start(self) -> None:
        """Start the orchestrator."""
        logger.info("orchestrator_starting", agents=list(self.agents.keys()))

        self.setup_schedules()
        self.scheduler.start()

        # Run initial cycle for all agents
        logger.info("running_initial_cycles")
        for agent_id in self.agents:
            await self.run_agent(agent_id)

        # Keep running until shutdown
        while self.running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop the orchestrator gracefully."""
        logger.info("orchestrator_stopping")
        self.running = False
        self.scheduler.shutdown()


async def main() -> None:
    """Entry point."""
    orchestrator = Orchestrator()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(orchestrator.stop()))

    try:
        await orchestrator.start()
    except KeyboardInterrupt:
        await orchestrator.stop()


if __name__ == "__main__":
    asyncio.run(main())
