"""DevOps Engineer Agent — Infrastructure and CI/CD."""

from typing import Any

from src.agents.base import BaseAgent
from src.tools.chat_tools import ChatTools
from src.tools.github_tools import GitHubTools

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
        chat = ChatTools(self.settings)

        self.register_tool(
            "send_slack_message",
            chat.send_message,
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
            "merge_pull_request",
            gh.merge_pull_request,
            "Merge an approved PR into main (squash, merge, or rebase)",
            {
                "type": "object",
                "properties": {
                    "pr_number": {"type": "integer"},
                    "commit_title": {"type": "string"},
                    "merge_method": {"type": "string", "description": "squash, merge, or rebase"},
                },
                "required": ["pr_number"],
            },
        )
        self.register_tool(
            "update_issue_labels",
            gh.update_issue_labels,
            "Add or remove labels from an issue or PR (e.g. add status/done, remove status/in-progress)",
            {
                "type": "object",
                "properties": {
                    "issue_number": {"type": "integer"},
                    "add": {"type": "array", "items": {"type": "string"}},
                    "remove": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["issue_number"],
            },
        )
        self.register_tool(
            "close_issue",
            gh.close_issue,
            "Close a completed issue with a comment",
            {
                "type": "object",
                "properties": {
                    "issue_number": {"type": "integer"},
                    "comment": {"type": "string"},
                },
                "required": ["issue_number"],
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
        # Check DMs
        chat = ChatTools(self.settings)
        dms = await chat.get_direct_messages(limit=3)
        for dm in dms:
            events.append(
                {"type": "direct_message", "title": "DM received", "body": dm["text"][:500]}
            )

        # Priority 1: PRs that passed QA and are ready for merge/deployment
        prs = await gh.list_pull_requests(limit=10)
        for pr in prs:
            pr_labels = pr.get("labels", [])
            if "status/qa-passed" in pr_labels or "ready-to-merge" in pr_labels:
                events.append(
                    {
                        "type": "pr_ready_to_merge",
                        "title": f"Merge PR #{pr['number']}: {pr['title']}",
                        "body": f"PR #{pr['number']} by {pr.get('author')} has passed QA and is ready for merge & deployment.",
                    }
                )

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
