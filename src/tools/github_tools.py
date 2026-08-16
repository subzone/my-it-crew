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

    async def list_issues(
        self, labels: list[str] | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """List open issues with optional label filter."""
        url = f"{self.base_url}/repos/{self.repo}/issues"
        params: dict[str, Any] = {"state": "open", "per_page": limit}
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
                    "labels": [label["name"] for label in i.get("labels", [])],
                    "assignee": (i.get("assignee", {}).get("login") if i.get("assignee") else None),
                }
                for i in issues
                if "pull_request" not in i  # Exclude PRs
            ]

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
                    "review_comments": pr.get("review_comments", 0),
                }
                for pr in prs
            ]

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
        self, issue_number: int, custom_instructions: str | None = None
    ) -> dict[str, Any]:
        """Assign GitHub Copilot coding agent to work on an issue."""
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
