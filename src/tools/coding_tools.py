"""Coding tools — enables agents to write code via the GitHub Contents API.

These tools allow agents to create branches, read/write files, and open PRs
without needing local git. All operations go through the GitHub REST API.
"""

import base64
from typing import Any

import httpx
import structlog

from src.config import Settings

logger = structlog.get_logger()


class CodingTools:
    """GitHub-based coding tools for agent development workflows.

    Provides: create_branch, get_file, create_or_update_file, push_files, create_pull_request.
    All operations use the GitHub Contents/Git API — no local filesystem needed.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.repo = settings.github_repo
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {settings.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

    async def create_branch(self, branch_name: str, from_branch: str = "main") -> dict[str, Any]:
        """Create a new branch from an existing branch.

        Args:
            branch_name: Name for the new branch (e.g. 'feat/add-user-api').
            from_branch: Source branch to branch from (default: 'main').

        Returns:
            Dict with branch name and ref, or error.
        """
        async with httpx.AsyncClient() as client:
            # Get the SHA of the source branch
            url = f"{self.base_url}/repos/{self.repo}/git/ref/heads/{from_branch}"
            resp = await client.get(url, headers=self.headers)
            if resp.status_code == 404:
                return {"error": f"Source branch '{from_branch}' not found"}
            resp.raise_for_status()
            sha = resp.json()["object"]["sha"]

            # Create the new branch
            url = f"{self.base_url}/repos/{self.repo}/git/refs"
            payload = {"ref": f"refs/heads/{branch_name}", "sha": sha}
            resp = await client.post(url, json=payload, headers=self.headers)
            if resp.status_code == 422:
                return {"error": f"Branch '{branch_name}' already exists"}
            resp.raise_for_status()

            logger.info("branch_created", branch=branch_name, from_branch=from_branch)
            return {"branch": branch_name, "sha": sha, "status": "created"}

    async def get_file(self, path: str, branch: str = "main") -> dict[str, Any]:
        """Read a file's content from the repository.

        Args:
            path: File path relative to repo root (e.g. 'src/config.py').
            branch: Branch to read from (default: 'main').

        Returns:
            Dict with path, content (decoded), sha, and size.
        """
        url = f"{self.base_url}/repos/{self.repo}/contents/{path}"
        params = {"ref": branch}

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=self.headers)
            if resp.status_code == 404:
                return {"error": f"File '{path}' not found on branch '{branch}'"}
            resp.raise_for_status()
            data = resp.json()

            if data.get("type") == "dir":
                # Return directory listing
                return {
                    "path": path,
                    "type": "directory",
                    "entries": [
                        {"name": f["name"], "type": f["type"], "path": f["path"]}
                        for f in data
                    ]
                    if isinstance(data, list)
                    else [],
                }

            content = base64.b64decode(data["content"]).decode("utf-8")
            return {
                "path": path,
                "content": content,
                "sha": data["sha"],
                "size": data["size"],
            }

    async def create_or_update_file(
        self,
        path: str,
        content: str,
        message: str,
        branch: str,
        sha: str | None = None,
    ) -> dict[str, Any]:
        """Create or update a single file in the repository.

        Args:
            path: File path relative to repo root.
            content: The full file content (text, not base64).
            message: Commit message.
            branch: Target branch.
            sha: The blob SHA of the file being replaced (required for updates).
                 Get this from get_file(). Omit for new files.

        Returns:
            Dict with path, commit SHA, and status.
        """
        url = f"{self.base_url}/repos/{self.repo}/contents/{path}"
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        payload: dict[str, Any] = {
            "message": message,
            "content": encoded,
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        async with httpx.AsyncClient() as client:
            resp = await client.put(url, json=payload, headers=self.headers)
            if resp.status_code == 409:
                return {"error": "Conflict — file was modified. Re-read to get current SHA."}
            if resp.status_code == 422:
                err = resp.json().get("message", "Unprocessable entity")
                return {"error": f"Failed to write file: {err}"}
            resp.raise_for_status()
            data = resp.json()

            commit_sha = data["commit"]["sha"]
            logger.info("file_written", path=path, branch=branch, commit=commit_sha[:8])
            return {
                "path": path,
                "commit_sha": commit_sha,
                "status": "created" if not sha else "updated",
            }

    async def push_files(
        self,
        files: list[dict[str, str]],
        message: str,
        branch: str,
    ) -> dict[str, Any]:
        """Push multiple files in a single commit using the Git Trees API.

        This is more efficient than create_or_update_file for multi-file changes.

        Args:
            files: List of dicts with 'path' and 'content' keys.
            message: Commit message.
            branch: Target branch (must exist).

        Returns:
            Dict with commit SHA, file count, and status.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Get the current commit SHA for the branch
            ref_url = f"{self.base_url}/repos/{self.repo}/git/ref/heads/{branch}"
            resp = await client.get(ref_url, headers=self.headers)
            if resp.status_code == 404:
                return {"error": f"Branch '{branch}' not found. Create it first."}
            resp.raise_for_status()
            base_sha = resp.json()["object"]["sha"]

            # 2. Get the tree SHA of the current commit
            commit_url = f"{self.base_url}/repos/{self.repo}/git/commits/{base_sha}"
            resp = await client.get(commit_url, headers=self.headers)
            resp.raise_for_status()
            base_tree_sha = resp.json()["tree"]["sha"]

            # 3. Create blobs for each file
            tree_items = []
            for file in files:
                blob_url = f"{self.base_url}/repos/{self.repo}/git/blobs"
                blob_payload = {
                    "content": file["content"],
                    "encoding": "utf-8",
                }
                resp = await client.post(blob_url, json=blob_payload, headers=self.headers)
                resp.raise_for_status()
                blob_sha = resp.json()["sha"]

                tree_items.append(
                    {
                        "path": file["path"],
                        "mode": "100644",
                        "type": "blob",
                        "sha": blob_sha,
                    }
                )

            # 4. Create a new tree
            tree_url = f"{self.base_url}/repos/{self.repo}/git/trees"
            tree_payload = {"base_tree": base_tree_sha, "tree": tree_items}
            resp = await client.post(tree_url, json=tree_payload, headers=self.headers)
            resp.raise_for_status()
            new_tree_sha = resp.json()["sha"]

            # 5. Create a new commit
            commit_url = f"{self.base_url}/repos/{self.repo}/git/commits"
            commit_payload = {
                "message": message,
                "tree": new_tree_sha,
                "parents": [base_sha],
            }
            resp = await client.post(commit_url, json=commit_payload, headers=self.headers)
            resp.raise_for_status()
            new_commit_sha = resp.json()["sha"]

            # 6. Update the branch ref
            ref_url = f"{self.base_url}/repos/{self.repo}/git/refs/heads/{branch}"
            resp = await client.patch(
                ref_url, json={"sha": new_commit_sha}, headers=self.headers
            )
            resp.raise_for_status()

            logger.info(
                "files_pushed",
                branch=branch,
                commit=new_commit_sha[:8],
                file_count=len(files),
            )
            return {
                "commit_sha": new_commit_sha,
                "files_written": len(files),
                "branch": branch,
                "status": "pushed",
            }

    async def create_pull_request(
        self, title: str, body: str, head: str, base: str = "main"
    ) -> dict[str, Any]:
        """Create a pull request.

        Args:
            title: PR title.
            body: PR description (supports markdown, use 'Fixes #N' to link issues).
            head: Branch containing the changes.
            base: Branch to merge into (default: 'main').

        Returns:
            Dict with PR number and URL.
        """
        url = f"{self.base_url}/repos/{self.repo}/pulls"
        payload = {"title": title, "body": body, "head": head, "base": base}

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=self.headers)
            if resp.status_code == 422:
                err = resp.json().get("errors", [{}])
                msg = err[0].get("message", "Unknown error") if err else "Unknown error"
                return {"error": f"Cannot create PR: {msg}"}
            resp.raise_for_status()
            data = resp.json()
            logger.info("pr_created", number=data["number"], title=title)
            return {"number": data["number"], "url": data["html_url"]}

    async def get_directory_tree(self, path: str = "", branch: str = "main") -> dict[str, Any]:
        """List files in a directory (non-recursive).

        Args:
            path: Directory path (empty string for repo root).
            branch: Branch to read from.

        Returns:
            Dict with list of entries (name, type, path).
        """
        url = f"{self.base_url}/repos/{self.repo}/contents/{path}"
        params = {"ref": branch}

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=self.headers)
            if resp.status_code == 404:
                return {"error": f"Path '{path}' not found on branch '{branch}'"}
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, list):
                return {"error": f"'{path}' is a file, not a directory"}

            return {
                "path": path or "/",
                "branch": branch,
                "entries": [
                    {"name": f["name"], "type": f["type"], "path": f["path"], "size": f.get("size")}
                    for f in data
                ],
            }
