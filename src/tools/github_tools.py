"""GitHub integration tools for agents."""

from typing import Any

import httpx
import structlog

from src.config import Settings

logger = structlog.get_logger()


class GitHubTools:
    """GitHub API wrapper for agent tools."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.repo = settings.github_repo
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {settings.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

    async def create_issue(
        self, title: str, body: str, labels: list[str] | None = None, assignee: str | None = None
    ) -> dict[str, Any]:
        """Create a GitHub Issue."""
        url = f"{self.base_url}/repos/{self.repo}/issues"
        payload: dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        if assignee:
            payload["assignees"] = [assignee]

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=self.headers)
            resp.raise_for_status()
            data = resp.json()
            logger.info("issue_created", number=data["number"], title=title)
            return {"number": data["number"], "url": data["html_url"]}

    async def comment_on_issue(self, issue_number: int, body: str) -> dict[str, Any]:
        """Add a comment to a GitHub Issue."""
        url = f"{self.base_url}/repos/{self.repo}/issues/{issue_number}/comments"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={"body": body}, headers=self.headers)
            resp.raise_for_status()
            return {"status": "commented", "issue": issue_number}

    async def close_issue(self, issue_number: int, comment: str | None = None) -> dict[str, Any]:
        """Close an issue with an optional closing comment."""
        if comment:
            await self.comment_on_issue(issue_number, comment)
        url = f"{self.base_url}/repos/{self.repo}/issues/{issue_number}"
        async with httpx.AsyncClient() as client:
            resp = await client.patch(url, json={"state": "closed"}, headers=self.headers)
            resp.raise_for_status()
            logger.info("issue_closed", issue=issue_number)
            return {"status": "closed", "issue": issue_number}

    async def get_issue(self, issue_number: int) -> dict[str, Any]:
        """Get details for a specific issue."""
        url = f"{self.base_url}/repos/{self.repo}/issues/{issue_number}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers)
            resp.raise_for_status()
            data = resp.json()
            return {
                "number": data["number"],
                "title": data["title"],
                "body": data.get("body", ""),
                "state": data.get("state", "open"),
                "labels": [label["name"] for label in data.get("labels", [])],
                "assignee": data.get("assignee", {}).get("login") if data.get("assignee") else None,
            }

    async def list_issues(
        self, labels: list[str] | None = None, state: str = "open", limit: int = 10
    ) -> list[dict[str, Any]]:
        """List issues with optional label and state filter."""
        url = f"{self.base_url}/repos/{self.repo}/issues"
        params: dict[str, Any] = {"state": state, "per_page": limit}
        if labels:
            params["labels"] = ",".join(labels)

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=self.headers)
            resp.raise_for_status()
            issues = resp.json()
            return [
                {
                    "number": i["number"],
                    "title": i["title"],
                    "body": i.get("body", ""),
                    "state": i.get("state", "open"),
                    "labels": [label["name"] for label in i.get("labels", [])],
                    "assignee": (i.get("assignee", {}).get("login") if i.get("assignee") else None),
                    "closed_at": i.get("closed_at"),
                    "updated_at": i.get("updated_at"),
                }
                for i in issues
                if "pull_request" not in i  # Exclude PRs
            ]

    async def list_closed_issues(self, limit: int = 10) -> list[dict[str, Any]]:
        """List recently closed issues."""
        return await self.list_issues(state="closed", limit=limit)

    async def get_daily_activity_summary(self) -> dict[str, Any]:
        """Aggregate 24-hour activity across PRs, in-progress tasks, and blockers."""
        open_prs = await self.list_pull_requests(limit=10)
        in_progress = await self.list_issues(labels=["status/in-progress"], limit=10)
        blocked = await self.list_issues(labels=["status/blocked"], limit=10)
        ready = await self.list_issues(labels=["status/ready"], limit=10)
        closed = await self.list_closed_issues(limit=10)

        return {
            "closed_issues_recent": [
                {"number": i["number"], "title": i["title"]} for i in closed[:5]
            ],
            "open_prs_in_review": [
                {"number": p["number"], "title": p["title"], "author": p["author"]}
                for p in open_prs
            ],
            "tasks_in_progress": [
                {"number": i["number"], "title": i["title"], "labels": i["labels"]}
                for i in in_progress
            ],
            "tasks_blocked": [{"number": i["number"], "title": i["title"]} for i in blocked],
            "tasks_ready_next": [{"number": i["number"], "title": i["title"]} for i in ready[:5]],
        }

    async def create_pull_request(
        self, title: str, body: str, head: str, base: str = "main"
    ) -> dict[str, Any]:
        """Create a pull request."""
        url = f"{self.base_url}/repos/{self.repo}/pulls"
        payload = {"title": title, "body": body, "head": head, "base": base}

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=self.headers)
            resp.raise_for_status()
            data = resp.json()
            return {"number": data["number"], "url": data["html_url"]}

    async def list_pull_requests(self, limit: int = 10) -> list[dict[str, Any]]:
        """List open pull requests."""
        url = f"{self.base_url}/repos/{self.repo}/pulls"
        params = {"state": "open", "per_page": limit}

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=self.headers)
            resp.raise_for_status()
            prs = resp.json()
            return [
                {
                    "number": pr["number"],
                    "title": pr["title"],
                    "body": pr.get("body", ""),
                    "author": pr["user"]["login"],
                    "labels": [lbl["name"] for lbl in pr.get("labels", [])],
                    "review_comments": pr.get("review_comments", 0),
                    "head": pr.get("head", {}).get("ref", ""),
                    "base": pr.get("base", {}).get("ref", "main"),
                }
                for pr in prs
            ]

    async def get_pull_request_files(self, pr_number: int) -> list[dict[str, Any]]:
        """Get the list of files modified in a pull request including code patches."""
        url = f"{self.base_url}/repos/{self.repo}/pulls/{pr_number}/files"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers)
            resp.raise_for_status()
            files = resp.json()
            return [
                {
                    "filename": f["filename"],
                    "status": f["status"],
                    "additions": f["additions"],
                    "deletions": f["deletions"],
                    "changes": f["changes"],
                    "patch": f.get("patch", "")[:1200],
                }
                for f in files
            ]

    async def merge_pull_request(
        self,
        pr_number: int,
        commit_title: str | None = None,
        commit_message: str | None = None,
        merge_method: str = "squash",
    ) -> dict[str, Any]:
        """Merge an approved pull request into main."""
        url = f"{self.base_url}/repos/{self.repo}/pulls/{pr_number}/merge"
        payload: dict[str, Any] = {"merge_method": merge_method}
        if commit_title:
            payload["commit_title"] = commit_title
        if commit_message:
            payload["commit_message"] = commit_message

        async with httpx.AsyncClient() as client:
            resp = await client.put(url, json=payload, headers=self.headers)
            if resp.status_code == 200:
                logger.info("pr_merged", pr=pr_number)
                return {"status": "merged", "pr": pr_number, "sha": resp.json().get("sha")}
            logger.warning(
                "pr_merge_failed", pr=pr_number, status=resp.status_code, body=resp.text[:200]
            )
            return {
                "status": "merge_failed",
                "pr": pr_number,
                "code": resp.status_code,
                "body": resp.text[:200],
            }

    async def get_issue_comments(self, issue_number: int, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent comments on an issue or PR."""
        url = f"{self.base_url}/repos/{self.repo}/issues/{issue_number}/comments"
        params = {"per_page": limit}
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=self.headers)
            resp.raise_for_status()
            comments = resp.json()
            return [
                {
                    "id": c["id"],
                    "user": c.get("user", {}).get("login", "unknown"),
                    "body": c.get("body", ""),
                    "created_at": c.get("created_at", ""),
                }
                for c in comments
            ]

    async def delete_branch(self, branch_name: str) -> dict[str, Any]:
        """Delete a git branch after PR merge."""
        clean_branch = branch_name.removeprefix("refs/heads/")
        if clean_branch in ("main", "master", "develop"):
            return {"error": "Cannot delete protected default branch"}
        url = f"{self.base_url}/repos/{self.repo}/git/refs/heads/{clean_branch}"
        async with httpx.AsyncClient() as client:
            resp = await client.delete(url, headers=self.headers)
            if resp.status_code in (204, 200, 404):
                logger.info("branch_deleted", branch=clean_branch)
                return {"status": "deleted", "branch": clean_branch}
            return {"status": "error", "code": resp.status_code}

    async def create_discussion(
        self, title: str, body: str, category: str = "General"
    ) -> dict[str, Any]:
        """Create a GitHub Discussion using GraphQL API."""
        query = """
        query($owner: String!, $name: String!) {
            repository(owner: $owner, name: $name) {
                id
                discussionCategories(first: 10) {
                    nodes {
                        id
                        name
                    }
                }
            }
        }
        """
        owner, name = self.repo.split("/")
        variables = {"owner": owner, "name": name}

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.github.com/graphql",
                json={"query": query, "variables": variables},
                headers=self.headers,
            )
            resp.raise_for_status()
            data = resp.json()

            repo_id = data["data"]["repository"]["id"]
            categories = data["data"]["repository"]["discussionCategories"]["nodes"]

            # Find matching category
            category_id = None
            for cat in categories:
                if cat["name"].lower() == category.lower():
                    category_id = cat["id"]
                    break

            if not category_id and categories:
                category_id = categories[0]["id"]

            if not category_id:
                return {"error": "No discussion categories found. Create them in repo settings."}

            # Create discussion
            mutation = """
            mutation($input: CreateDiscussionInput!) {
                createDiscussion(input: $input) {
                    discussion {
                        id
                        url
                        number
                    }
                }
            }
            """
            create_vars = {
                "input": {
                    "repositoryId": repo_id,
                    "categoryId": category_id,
                    "title": title,
                    "body": body,
                }
            }

            resp = await client.post(
                "https://api.github.com/graphql",
                json={"query": mutation, "variables": create_vars},
                headers=self.headers,
            )
            resp.raise_for_status()
            result = resp.json()

            if "errors" in result:
                return {"error": str(result["errors"])}

            disc = result["data"]["createDiscussion"]["discussion"]
            logger.info("discussion_created", number=disc["number"], title=title)
            return {"number": disc["number"], "url": disc["url"]}

    async def list_discussions(
        self, category: str | None = None, limit: int = 5
    ) -> list[dict[str, Any]]:
        """List recent discussions."""
        query = """
        query($owner: String!, $name: String!, $limit: Int!) {
            repository(owner: $owner, name: $name) {
                discussions(first: $limit, orderBy: {field: CREATED_AT, direction: DESC}) {
                    nodes {
                        number
                        title
                        body
                        category {
                            name
                        }
                        author {
                            login
                        }
                    }
                }
            }
        }
        """
        owner, name = self.repo.split("/")
        variables = {"owner": owner, "name": name, "limit": limit}

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.github.com/graphql",
                json={"query": query, "variables": variables},
                headers=self.headers,
            )
            resp.raise_for_status()
            data = resp.json()

            discussions = (
                data.get("data", {}).get("repository", {}).get("discussions", {}).get("nodes", [])
            )

            results = []
            for d in discussions:
                cat_name = d.get("category", {}).get("name", "")
                if category and cat_name.lower() != category.lower():
                    continue
                results.append(
                    {
                        "number": d["number"],
                        "title": d["title"],
                        "body": d.get("body", ""),
                        "category": cat_name,
                        "author": d.get("author", {}).get("login", "unknown"),
                    }
                )

            return results

    async def assign_copilot_to_issue(
        self,
        issue_number: int,
        agent_name: str = "backend-developer",
        custom_instructions: str | None = None,
    ) -> dict[str, Any]:
        """Assign GitHub Copilot coding agent to work on an issue.

        Available agents: backend-developer, qa-engineer, pr-reviewer, pr-approver, documenter, diagram-architect
        """
        url = f"{self.base_url}/repos/{self.repo}/issues/{issue_number}/assignees"
        payload = {"assignees": ["Copilot"]}

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=self.headers)
            if resp.status_code in (404, 422):
                # Try lowercase
                payload = {"assignees": ["copilot"]}
                resp = await client.post(url, json=payload, headers=self.headers)

            data = resp.json()
            assignees = [a["login"] for a in data.get("assignees", [])]
            if "Copilot" in assignees or "copilot" in assignees:
                logger.info("copilot_assigned", issue=issue_number)
                return {"status": "copilot_assigned", "issue": issue_number}
            else:
                logger.warning("copilot_assignment_failed", issue=issue_number, assignees=assignees)
                return {"status": "failed", "issue": issue_number, "assignees": assignees}

    async def update_issue_labels(
        self, issue_number: int, add: list[str] | None = None, remove: list[str] | None = None
    ) -> dict[str, Any]:
        """Add or remove labels from an issue."""
        async with httpx.AsyncClient() as client:
            if add:
                url = f"{self.base_url}/repos/{self.repo}/issues/{issue_number}/labels"
                resp = await client.post(url, json={"labels": add}, headers=self.headers)
                resp.raise_for_status()

            if remove:
                for label in remove:
                    url = f"{self.base_url}/repos/{self.repo}/issues/{issue_number}/labels/{label}"
                    await client.delete(url, headers=self.headers)

            logger.info("labels_updated", issue=issue_number, added=add, removed=remove)
            return {
                "status": "labels_updated",
                "issue": issue_number,
                "added": add,
                "removed": remove,
            }
