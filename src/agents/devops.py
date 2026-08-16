"""DevOps Engineer Agent — Infrastructure and CI/CD."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.github_tools import GitHubTools
from src.tools.slack_tools import SlackTools

DEVOPS_PERSONA = """You are a DevOps Engineer at My IT Crew.

Your responsibilities:
- Monitor deployments and CI/CD pipeline health
- Fix broken builds and deployment failures
- Manage Kubernetes manifests and infrastructure
- Respond to incidents and outages
- Automate operational tasks
- Review infrastructure-related PRs
- Post deployment status to #releases Slack channel
- Post incidents to #engineering
- Mention CTO when infrastructure decisions are needed

Your workflow:
1. Check for CI/CD failures or deployment issues
2. Check for infrastructure-related issues assigned to you
3. Fix build/deploy problems
4. Create automation improvements
5. Post incident reports when issues are resolved

Tech stack: Kubernetes (k3d), ArgoCD, GitHub Actions, Docker, Prometheus.
"""


class DevOpsAgent(BaseAgent):
    """DevOps Engineer that manages infrastructure and deployments."""

    def __init__(self):
        super().__init__(agent_id="devops", persona=DEVOPS_PERSONA)
        self._setup_tools()

    def _setup_tools(self) -> None:
        gh = GitHubTools(self.settings)
        slack = SlackTools(self.settings)

        self.register_tool(
            "send_slack_message",
            slack.send_message,
            "Post to Slack (#releases for deployments, #engineering for issues)",
            {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["channel", "text"],
            },
        )
        self.register_tool(
            "create_issue",
            gh.create_issue,
            "Create an infrastructure issue",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "labels": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "body"],
            },
        )
        self.register_tool(
            "comment_on_issue",
            gh.comment_on_issue,
            "Comment on an issue",
            {
                "type": "object",
                "properties": {
                    "issue_number": {"type": "integer"},
                    "body": {"type": "string"},
                },
                "required": ["issue_number", "body"],
            },
        )
        self.register_tool(
            "list_issues",
            gh.list_issues,
            "List issues",
            {
                "type": "object",
                "properties": {
                    "labels": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer"},
                },
            },
        )
        self.register_tool(
            "list_pull_requests",
            gh.list_pull_requests,
            "List open PRs",
            {
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
            },
        )

    async def perceive(self) -> list[dict]:
        gh = GitHubTools(self.settings)
        events = []

        issues = await gh.list_issues(labels=["dept/devops"], limit=5)
        for issue in issues:
            events.append(
                {
                    "type": "devops_task",
                    "title": issue["title"],
                    "body": f"Issue #{issue['number']}: {issue.get('body', '')[:400]}",
                }
            )

        issues = await gh.list_issues(labels=["incident"], limit=3)
        for issue in issues:
            events.append(
                {
                    "type": "incident",
                    "title": issue["title"],
                    "body": f"Issue #{issue['number']}: {issue.get('body', '')[:400]}",
                }
            )

        return events

    async def reflect(self, result: dict[str, Any]) -> None:
        self.log.info("devops_reflection", actions_taken=len(result.get("actions", [])))
