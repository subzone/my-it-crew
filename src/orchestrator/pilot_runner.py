"""Autonomous Pilot Runner — coordinates and demonstrates end-to-end multi-agent IT crew initiative delivery.

Walks through the complete initiative lifecycle:
Board Directive → CEO Epic → CTO Feasibility → EM Breakdown → Engineer Implementation & PR
→ QA Validation → DevOps Deployment → Marketing Broadcast & Reporter Metrics.
"""

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from src.config import Settings
from src.tools.db_tools import DBTools

logger = structlog.get_logger()


@dataclass
class PilotContext:
    """Shared state across the pilot story execution."""

    directive: str
    epic_issue: dict[str, Any] | None = None
    tasks: list[dict[str, Any]] = field(default_factory=list)
    prs: list[dict[str, Any]] = field(default_factory=list)
    chat_logs: list[dict[str, Any]] = field(default_factory=list)
    step_history: list[dict[str, Any]] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))


class MockPilotAdapter:
    """Mock GitHub & Chat adapter for offline execution / test simulation."""

    def __init__(self, ctx: PilotContext):
        self.ctx = ctx
        self._issue_counter = 100
        self._pr_counter = 200

    async def send_message(self, channel: str, text: str) -> dict[str, Any]:
        msg = {
            "channel": channel,
            "text": text,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self.ctx.chat_logs.append(msg)
        logger.info("pilot_chat", channel=f"#{channel}", message=text[:120])
        return {"status": "sent", "channel": channel}

    async def get_direct_messages(self, limit: int = 5) -> list[dict[str, Any]]:
        return []

    async def get_channel_history(self, channel: str, limit: int = 5) -> list[dict[str, Any]]:
        if channel == "general" and not self.ctx.epic_issue:
            return [{"user": "board", "text": self.ctx.directive}]
        return [m for m in self.ctx.chat_logs if m["channel"] == channel][-limit:]

    async def create_issue(
        self, title: str, body: str, labels: list[str] | None = None, assignee: str | None = None
    ) -> dict[str, Any]:
        self._issue_counter += 1
        issue = {
            "number": self._issue_counter,
            "title": title,
            "body": body,
            "labels": labels or [],
            "assignee": assignee,
            "state": "open",
            "comments": [],
        }
        if "epic" in (labels or []):
            self.ctx.epic_issue = issue
        else:
            self.ctx.tasks.append(issue)
        logger.info("pilot_issue_created", number=issue["number"], title=title, labels=labels)
        return {
            "number": issue["number"],
            "url": f"https://github.com/subzone/my-it-crew/issues/{issue['number']}",
        }

    async def comment_on_issue(self, issue_number: int, body: str) -> dict[str, Any]:
        target = self._find_issue(issue_number)
        if target:
            target.setdefault("comments", []).append(body)
        logger.info("pilot_issue_comment", issue=issue_number, body=body[:100])
        return {"status": "commented", "issue": issue_number}

    async def update_issue_labels(
        self, issue_number: int, add: list[str] | None = None, remove: list[str] | None = None
    ) -> dict[str, Any]:
        target = self._find_issue(issue_number)
        if target:
            curr = set(target.get("labels", []))
            if add:
                curr.update(add)
            if remove:
                curr.difference_update(remove)
            target["labels"] = list(curr)
        logger.info("pilot_labels_updated", issue=issue_number, added=add, removed=remove)
        return {"status": "labels_updated", "issue": issue_number}

    async def list_issues(
        self, labels: list[str] | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        all_issues = []
        if self.ctx.epic_issue:
            all_issues.append(self.ctx.epic_issue)
        all_issues.extend(self.ctx.tasks)

        if not labels:
            return all_issues[:limit]

        filtered = []
        for i in all_issues:
            i_labels = set(i.get("labels", []))
            if all(lbl in i_labels for lbl in labels):
                filtered.append(i)
        return filtered[:limit]

    async def create_pull_request(
        self, title: str, body: str, head: str, base: str = "main"
    ) -> dict[str, Any]:
        self._pr_counter += 1
        pr = {
            "number": self._pr_counter,
            "title": title,
            "body": body,
            "head": head,
            "base": base,
            "author": head.split("/")[0] if "/" in head else "engineer",
            "state": "open",
            "labels": [],
        }
        self.ctx.prs.append(pr)
        logger.info("pilot_pr_opened", number=pr["number"], title=title, head=head)
        return {
            "number": pr["number"],
            "url": f"https://github.com/subzone/my-it-crew/pull/{pr['number']}",
        }

    async def list_pull_requests(self, limit: int = 10) -> list[dict[str, Any]]:
        return self.ctx.prs[:limit]

    def _find_issue(self, num: int) -> dict[str, Any] | None:
        if self.ctx.epic_issue and self.ctx.epic_issue["number"] == num:
            return self.ctx.epic_issue
        for t in self.ctx.tasks:
            if t["number"] == num:
                return t
        return None


class AutonomousPilotRunner:
    """Coordinates and runs the full autonomous pilot simulation."""

    def __init__(self, directive: str | None = None):
        self.directive = directive or (
            "Build an autonomous AI-Powered Health & Status Dashboard for My IT Crew"
        )
        self.ctx = PilotContext(directive=self.directive)
        self.adapter = MockPilotAdapter(self.ctx)
        self.settings = Settings()

    async def run_pilot(self) -> dict[str, Any]:
        """Execute all phases of the autonomous pilot story."""
        logger.info("=== STARTING AUTONOMOUS PILOT STORY ===", directive=self.directive)

        # ─── Phase 0: Cigance AI Token Scout — Seed and Verify $0 Tokens ───
        await self._step_0_token_scout()

        # ─── Phase 1: CEO Strategic Perception & Epic Creation ───
        await self._step_1_ceo_epic()

        # ─── Phase 2: CTO Technical Feasibility Assessment ───
        await self._step_2_cto_feasibility()

        # ─── Phase 3: Engineering Manager Work Breakdown ───
        await self._step_3_em_breakdown()

        # ─── Phase 4: Parallel Engineering Implementation ───
        await self._step_4_engineers_implement()

        # ─── Phase 5: QA Testing & Validation ───
        await self._step_5_qa_validation()

        # ─── Phase 6: DevOps Deployment ───
        await self._step_6_devops_deploy()

        # ─── Phase 7: Marketing & Reporting Broadcast ───
        await self._step_7_marketing_and_reporting()

        logger.info("=== AUTONOMOUS PILOT COMPLETED SUCCESSFULLY ===")
        return {
            "status": "success",
            "epic": self.ctx.epic_issue,
            "tasks_count": len(self.ctx.tasks),
            "prs_count": len(self.ctx.prs),
            "chat_messages_count": len(self.ctx.chat_logs),
            "steps": self.ctx.step_history,
            "cost_usd": 0.0,
        }

    async def _step_0_token_scout(self) -> None:
        """Cigance scouts free AI tokens and exports LiteLLM fallback chains."""
        db = DBTools()
        # Seed known free providers
        await db.add_provider(
            name="google-ai-studio",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            free_tier_details="15 RPM, 1M TPM, 1,500 req/day (Gemini 2.0/2.5 Flash)",
        )
        await db.add_provider(
            name="groq",
            base_url="https://api.groq.com/openai/v1",
            free_tier_details="30 RPM Llama 3.3 70B",
        )
        await db.add_provider(
            name="sambanova",
            base_url="https://api.sambanova.ai/v1",
            free_tier_details="Free Developer Tier (DeepSeek-R1)",
        )

        # Seed and mark working models
        await db.add_model(
            provider_name="google-ai-studio",
            model_id="gemini-2.0-flash",
            display_name="Gemini 2.0 Flash (Free)",
            tool_calling=True,
            context_window=1048576,
        )
        await db.add_model(
            provider_name="groq",
            model_id="llama-3.3-70b-versatile",
            display_name="Groq Llama 3.3 70B (Free)",
            tool_calling=True,
            context_window=131072,
        )
        await db.add_model(
            provider_name="sambanova",
            model_id="DeepSeek-R1",
            display_name="SambaNova DeepSeek R1 (Free)",
            tool_calling=True,
            context_window=65536,
        )

        await db.update_provider_status("google-ai-studio", "working")
        await db.update_provider_status("groq", "working")
        await db.update_provider_status("sambanova", "working")

        await db.update_model_status(
            "google-ai-studio", "gemini-2.0-flash", "working", response_time_ms=180
        )
        await db.update_model_status(
            "groq", "llama-3.3-70b-versatile", "working", response_time_ms=120
        )
        await db.update_model_status("sambanova", "DeepSeek-R1", "working", response_time_ms=450)

        export = await db.export_litellm_model_list()
        await self.adapter.send_message(
            channel="engineering",
            text=f"🪙 [Cigance AI Scout] Verified {export['total_working']} free models with tool calling. "
            f"Zero-cost fallback cascade active: Groq → Cerebras → SambaNova → Google AI Studio ($0.00 spent).",
        )
        self.ctx.step_history.append(
            {"phase": "0_token_scout", "verified_models": export["total_working"]}
        )

    async def _step_1_ceo_epic(self) -> None:
        """CEO perceives directive and creates the strategic Epic."""
        epic = await self.adapter.create_issue(
            title=f"Epic: {self.directive}",
            body=f"## Strategic Directive\n\n{self.directive}\n\n"
            f"### Business Goal\nProvide real-time monitoring of all autonomous IT crew agents, "
            f"token burn rates, and system health.\n\n"
            f"Assigned to CTO for technical feasibility review.",
            labels=["epic", "needs-cto", "priority/p1"],
        )
        await self.adapter.send_message(
            channel="general",
            text=f"🎯 [CEO] Created Epic #{epic['number']}: '{self.directive}'. "
            f"Assigned to @cto for technical assessment.",
        )
        self.ctx.step_history.append({"phase": "1_ceo_epic", "epic_number": epic["number"]})

    async def _step_2_cto_feasibility(self) -> None:
        """CTO assesses feasibility and prepares architecture spec."""
        epic_num = self.ctx.epic_issue["number"]
        assessment = (
            "### 🛠️ CTO Technical Feasibility Assessment\n\n"
            "- **Complexity**: Medium (M)\n"
            "- **Target Stack**: Python FastAPI (Backend) + TypeScript/React (UI) + K8s Health Probes\n"
            "- **Architecture**: Decoupled REST health checks, Prometheus exporter metrics, LiteLLM token counter.\n"
            "- **Recommendation**: Break into Backend Service, Frontend Dashboard, and QA Test Suite.\n\n"
            "Passing to Engineering Manager for task breakdown."
        )
        await self.adapter.comment_on_issue(epic_num, assessment)
        await self.adapter.update_issue_labels(
            epic_num,
            add=["needs-breakdown"],
            remove=["needs-cto"],
        )
        await self.adapter.send_message(
            channel="c-suite",
            text=f"📐 [CTO] Completed architecture feasibility assessment for Epic #{epic_num}. "
            f"Complexity: Medium. Tagged 'needs-breakdown' for @eng-manager.",
        )
        self.ctx.step_history.append({"phase": "2_cto_feasibility", "status": "assessed"})

    async def _step_3_em_breakdown(self) -> None:
        """Engineering Manager breaks down the epic into actionable engineering tasks."""
        epic_num = self.ctx.epic_issue["number"]

        task1 = await self.adapter.create_issue(
            title="Implement Health Check & Metrics API Endpoint",
            body=f"Parent Epic: #{epic_num}\n\n"
            "Build `/healthz` and `/metrics` REST endpoints returning agent status and token counters.\n\n"
            "**Definition of Done**:\n- Pydantic models for health state\n- Unit tests covering status responses",
            labels=["dept/engineering", "status/ready", "priority/p1"],
        )

        task2 = await self.adapter.create_issue(
            title="Build Status Dashboard Web Component",
            body=f"Parent Epic: #{epic_num}\n\n"
            "Implement responsive React status dashboard displaying active agents and health badges.\n\n"
            "**Definition of Done**:\n- Accessible UI component with zero `any` types\n- Live status polling",
            labels=["dept/engineering", "dept/frontend", "status/ready", "priority/p2"],
        )

        task3 = await self.adapter.create_issue(
            title="End-to-End Health Probe Test Suite",
            body=f"Parent Epic: #{epic_num}\n\n"
            "Write pytest integration test suite verifying health check payloads and error edge cases.",
            labels=["dept/engineering", "dept/qa", "status/ready", "priority/p2"],
        )

        await self.adapter.update_issue_labels(
            epic_num, add=["status/in-progress"], remove=["needs-breakdown"]
        )

        await self.adapter.send_message(
            channel="engineering",
            text=f"📋 [Eng Manager] Breakdown complete for Epic #{epic_num}. "
            f"Created 3 tasks ready for pickup: #{task1['number']}, #{task2['number']}, #{task3['number']}.",
        )
        self.ctx.step_history.append(
            {
                "phase": "3_em_breakdown",
                "tasks": [task1["number"], task2["number"], task3["number"]],
            }
        )

    async def _step_4_engineers_implement(self) -> None:
        """Nova (Backend) and Kai (Frontend) claim tasks and open Pull Requests."""
        task1 = self.ctx.tasks[0]
        task2 = self.ctx.tasks[1]

        # Nova implements backend
        await self.adapter.update_issue_labels(
            task1["number"],
            add=["claimed-by/nova", "status/in-progress"],
            remove=["status/ready"],
        )
        await self.adapter.comment_on_issue(
            task1["number"],
            "🌟 Nova here — I'm taking this one. Starting backend implementation now.",
        )
        pr1 = await self.adapter.create_pull_request(
            title=f"feat(api): health check and metrics service (Fixes #{task1['number']})",
            body=f"Implements health monitoring endpoints.\n\nFixes #{task1['number']}\n\n— Nova 🌟",
            head="nova/issue-1-health-api",
        )
        await self.adapter.send_message(
            channel="engineering",
            text=f"🌟 [Nova] Opened PR #{pr1['number']} for issue #{task1['number']}. Ready for review.",
        )

        # Kai implements frontend
        await self.adapter.update_issue_labels(
            task2["number"],
            add=["claimed-by/kai", "status/in-progress"],
            remove=["status/ready"],
        )
        await self.adapter.comment_on_issue(
            task2["number"],
            "⚡ Kai here — picking up the dashboard UI. Shipping shortly.",
        )
        pr2 = await self.adapter.create_pull_request(
            title=f"feat(ui): status dashboard component (Fixes #{task2['number']})",
            body=f"Implements live status dashboard.\n\nFixes #{task2['number']}\n\n— Kai ⚡",
            head="kai/issue-2-health-ui",
        )
        await self.adapter.send_message(
            channel="engineering",
            text=f"⚡ [Kai] Opened PR #{pr2['number']} for issue #{task2['number']}. Ready for QA.",
        )

        self.ctx.step_history.append(
            {"phase": "4_engineers_implement", "prs": [pr1["number"], pr2["number"]]}
        )

    async def _step_5_qa_validation(self) -> None:
        """QA Engineer validates the PRs and marks quality passed."""
        for pr in self.ctx.prs:
            await self.adapter.comment_on_issue(
                pr["number"],
                f"🧪 QA Validation Passed for PR #{pr['number']}. "
                f"100% acceptance criteria satisfied, zero regressions detected.",
            )
            pr["labels"].append("status/qa-passed")

        for task in self.ctx.tasks[:2]:
            await self.adapter.update_issue_labels(
                task["number"],
                add=["status/qa-passed"],
                remove=["status/in-progress"],
            )

        await self.adapter.send_message(
            channel="engineering",
            text="✅ [QA Engineer] All PRs passed testing criteria. Code is verified and ready for deployment.",
        )
        self.ctx.step_history.append({"phase": "5_qa_validation", "status": "qa_passed"})

    async def _step_6_devops_deploy(self) -> None:
        """DevOps Agent executes deployment and verifies release."""
        epic_num = self.ctx.epic_issue["number"]

        for task in self.ctx.tasks:
            await self.adapter.update_issue_labels(
                task["number"],
                add=["status/done"],
                remove=["status/qa-passed", "status/ready"],
            )

        await self.adapter.update_issue_labels(
            epic_num,
            add=["status/done"],
            remove=["status/in-progress"],
        )

        await self.adapter.send_message(
            channel="releases",
            text=f"🚀 [DevOps] Deployment v1.1.0 successful on Kubernetes cluster. "
            f"Health endpoints active. Epic #{epic_num} marked Done.",
        )
        self.ctx.step_history.append({"phase": "6_devops_deploy", "release": "v1.1.0"})

    async def _step_7_marketing_and_reporting(self) -> None:
        """Marketing broadcasts launch and Reporter outputs scorecard."""
        epic_num = self.ctx.epic_issue["number"]

        await self.adapter.send_message(
            channel="general",
            text=f"📢 [Marketer] Milestone Announcement: 'My IT Crew launches autonomous Health & Status Dashboard!' "
            f"Delivered end-to-end autonomously under Epic #{epic_num}.",
        )

        report = (
            "📊 **Sprint Pilot Delivery Report**:\n"
            f"- **Initiative**: {self.directive}\n"
            f"- **Epic**: #{epic_num} (Done)\n"
            f"- **Tasks Completed**: {len(self.ctx.tasks)}/3\n"
            f"- **PRs Merged**: {len(self.ctx.prs)}/2\n"
            f"- **Inference Spend**: $0.00 (Powered by Cigance Free AI Tokens)\n"
            "- **Human Interventions**: 0\n"
            "- **Status**: 100% Autonomous Success 🚀"
        )
        await self.adapter.send_message(channel="c-suite", text=report)
        self.ctx.step_history.append({"phase": "7_marketing_reporting", "spend_usd": 0.0})


async def main() -> None:
    parser = argparse.ArgumentParser(description="My IT Crew Autonomous Pilot Runner")
    parser.add_argument(
        "--directive",
        type=str,
        default="Build an autonomous AI-Powered Health & Status Dashboard for My IT Crew",
        help="Strategic directive for the crew to execute",
    )
    args = parser.parse_args()

    runner = AutonomousPilotRunner(directive=args.directive)
    result = await runner.run_pilot()
    print("\n" + "=" * 60)
    print(json.dumps(result, indent=2))
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
