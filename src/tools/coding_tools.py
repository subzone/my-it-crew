"""Coding tools — enables agents to write code via the GitHub Contents API.

These tools allow agents to create branches, read/write files, and open PRs
without needing local git. All operations go through the GitHub REST API.

GitHub Token Scope Requirements:
    - contents:write  (read/write repo contents, create branches)
    - pull_requests:write  (create PRs)
    - issues:write  (comment on issues, update labels)
    - metadata:read  (implicit, always included)

    Use a fine-grained PAT scoped to the target repository only.
    Do NOT use classic tokens with broad `repo` scope in production.
"""

import ast
import asyncio
import base64
from typing import Any

import httpx
import structlog

from src.config import Settings

logger = structlog.get_logger()

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0  # seconds — doubles each retry (1s, 2s, 4s)
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def validate_file_content(path: str, content: str) -> str | None:
    """Pre-flight code validator to block hallucinations, placeholder paths, and syntax errors."""
    lower_path = path.lower().strip("/")

    # 1. Block generic placeholder and template paths
    if any(
        dummy in lower_path
        for dummy in [
            "path/to/",
            "path/to/file",
            "example/file",
            "dummy",
            "file1",
            "file2",
            "sample/file",
        ]
    ):
        return (
            f"Rejected path '{path}': Generic placeholder paths are not allowed. "
            f"Ground file paths in real project directories (e.g. src/, tests/, k8s/)."
        )

    # 2. Block 1-line stubs or empty files
    stripped_lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith(("#", "//", "/*", "*", "<!--"))
    ]
    if not stripped_lines:
        return (
            f"Rejected file '{path}': File contains only comments or whitespace. "
            f"Complete, functional implementation is required (Zero-Stub Policy)."
        )

    # 3. Python Syntax Verification (AST parse)
    if path.endswith(".py"):
        try:
            ast.parse(content, filename=path)
        except SyntaxError as e:
            return (
                f"SyntaxError in '{path}' at line {e.lineno}, col {e.offset}: {e.msg}. "
                f"Please fix the Python syntax error before committing."
            )

    return None


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict[str, str],
    max_retries: int = MAX_RETRIES,
    **kwargs: Any,
) -> httpx.Response:
    """Execute an HTTP request with exponential backoff retry.

    Retries on:
    - 429 Too Many Requests (respects Retry-After header)
    - 5xx Server Errors
    - Network timeouts

    Args:
        client: httpx AsyncClient instance.
        method: HTTP method (GET, POST, PUT, PATCH, DELETE).
        url: Request URL.
        headers: Request headers.
        max_retries: Maximum number of retry attempts.
        **kwargs: Additional arguments passed to httpx request.

    Returns:
        httpx.Response on success.

    Raises:
        httpx.HTTPStatusError: After all retries exhausted.
    """
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            resp = await client.request(method, url, headers=headers, **kwargs)

            if resp.status_code not in RETRYABLE_STATUS_CODES:
                return resp

            # Rate limited — respect Retry-After header
            if resp.status_code == 429:
                retry_after = int(
                    resp.headers.get("Retry-After", RETRY_BACKOFF_BASE * (2**attempt))
                )
                logger.warning(
                    "rate_limited",
                    url=url,
                    retry_after=retry_after,
                    attempt=attempt + 1,
                )
                await asyncio.sleep(retry_after)
            else:
                # Server error — exponential backoff
                wait = RETRY_BACKOFF_BASE * (2**attempt)
                logger.warning(
                    "retrying_request",
                    url=url,
                    status=resp.status_code,
                    wait_seconds=wait,
                    attempt=attempt + 1,
                )
                await asyncio.sleep(wait)

        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as e:
            last_exc = e
            wait = RETRY_BACKOFF_BASE * (2**attempt)
            logger.warning(
                "network_error_retrying",
                url=url,
                error=str(e),
                wait_seconds=wait,
                attempt=attempt + 1,
            )
            await asyncio.sleep(wait)

    # All retries exhausted
    if last_exc:
        raise last_exc
    return resp  # type: ignore[possibly-undefined]


class CodingTools:
    """GitHub-based coding tools for agent development workflows.

    Provides: create_branch, get_file, create_or_update_file, push_files, create_pull_request.
    All operations use the GitHub Contents/Git API — no local filesystem needed.

    Features:
    - Automatic retry with exponential backoff on rate limits and server errors
    - Structured logging on all operations for observability
    - Idempotent branch creation (returns existing SHA if branch exists)
    - Safe directory handling in get_file()
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.repo = settings.github_repo
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {settings.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.log = logger.bind(tool="coding_tools", repo=self.repo)

    async def create_branch(self, branch_name: str, from_branch: str = "main") -> dict[str, Any]:
        """Create a new branch from an existing branch. Idempotent.

        If the branch already exists, returns its current SHA instead of erroring.

        Args:
            branch_name: Name for the new branch (e.g. 'nova/issue-42-add-api').
            from_branch: Source branch to branch from (default: 'main').

        Returns:
            Dict with branch name, SHA, and status ('created' or 'exists').
        """
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Get the SHA of the source branch
            url = f"{self.base_url}/repos/{self.repo}/git/ref/heads/{from_branch}"
            resp = await _request_with_retry(client, "GET", url, self.headers)
            if resp.status_code == 404:
                self.log.error("source_branch_not_found", from_branch=from_branch)
                return {"error": f"Source branch '{from_branch}' not found"}
            resp.raise_for_status()
            sha = resp.json()["object"]["sha"]

            # Create the new branch
            url = f"{self.base_url}/repos/{self.repo}/git/refs"
            payload = {"ref": f"refs/heads/{branch_name}", "sha": sha}
            resp = await _request_with_retry(client, "POST", url, self.headers, json=payload)

            if resp.status_code == 422:
                # Branch already exists — fetch its current SHA (idempotent)
                ref_url = f"{self.base_url}/repos/{self.repo}/git/ref/heads/{branch_name}"
                ref_resp = await _request_with_retry(client, "GET", ref_url, self.headers)
                if ref_resp.status_code == 200:
                    existing_sha = ref_resp.json()["object"]["sha"]
                    self.log.info(
                        "branch_already_exists",
                        branch=branch_name,
                        sha=existing_sha[:8],
                    )
                    return {"branch": branch_name, "sha": existing_sha, "status": "exists"}
                return {"error": f"Branch '{branch_name}' conflict — could not resolve"}

            resp.raise_for_status()
            self.log.info(
                "branch_created", branch=branch_name, from_branch=from_branch, sha=sha[:8]
            )
            return {"branch": branch_name, "sha": sha, "status": "created"}

    async def get_file(self, path: str, branch: str = "main") -> dict[str, Any]:
        """Read a file's content from the repository.

        Args:
            path: File path relative to repo root (e.g. 'src/config.py').
            branch: Branch to read from (default: 'main').

        Returns:
            Dict with path, content (decoded), sha, and size.
            Returns an error dict if the path is a directory.
        """
        # Normalize path — strip leading slashes
        path = path.strip("/")
        url = f"{self.base_url}/repos/{self.repo}/contents/{path}"
        params = {"ref": branch}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await _request_with_retry(
                client, "GET", url, self.headers, params=params, follow_redirects=True
            )
            if resp.status_code == 404:
                self.log.info("file_not_found", path=path, branch=branch)
                return {"error": f"File '{path}' not found on branch '{branch}'"}
            resp.raise_for_status()
            data = resp.json()

            # GitHub returns a list for directories
            if isinstance(data, list):
                self.log.info("path_is_directory", path=path, branch=branch)
                return {
                    "error": f"'{path}' is a directory, not a file. Use get_directory_tree() instead.",
                    "path": path,
                    "type": "directory",
                    "entry_count": len(data),
                }

            # Single file response
            if data.get("type") == "file":
                content = base64.b64decode(data["content"]).decode("utf-8")
                self.log.info("file_read", path=path, branch=branch, size=data["size"])
                return {
                    "path": path,
                    "content": content,
                    "sha": data["sha"],
                    "size": data["size"],
                }

            # Unexpected type (submodule, symlink, etc.)
            return {"error": f"Unsupported content type: {data.get('type')}", "path": path}

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
        val_err = validate_file_content(path, content)
        if val_err:
            self.log.warning("preflight_validation_failed", path=path, error=val_err)
            return {"error": f"Pre-flight validation failed: {val_err}"}

        url = f"{self.base_url}/repos/{self.repo}/contents/{path}"
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        payload: dict[str, Any] = {
            "message": message,
            "content": encoded,
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await _request_with_retry(client, "PUT", url, self.headers, json=payload)
            if resp.status_code == 409:
                self.log.warning("file_conflict", path=path, branch=branch)
                return {"error": "Conflict — file was modified. Re-read to get current SHA."}
            if resp.status_code == 422:
                err = resp.json().get("message", "Unprocessable entity")
                self.log.error("file_write_failed", path=path, branch=branch, error=err)
                return {"error": f"Failed to write file: {err}"}
            resp.raise_for_status()
            data = resp.json()

            commit_sha = data["commit"]["sha"]
            status = "created" if not sha else "updated"
            self.log.info(
                "file_written",
                path=path,
                branch=branch,
                commit=commit_sha[:8],
                status=status,
            )
            return {"path": path, "commit_sha": commit_sha, "status": status}

    async def push_files(
        self,
        files: list[dict[str, str]],
        message: str,
        branch: str,
    ) -> dict[str, Any]:
        """Push multiple files in a single atomic commit using the Git Trees API.

        This is more efficient than create_or_update_file for multi-file changes.
        The commit is atomic — either all files are written or none are.

        Args:
            files: List of dicts with 'path' and 'content' keys.
            message: Commit message.
            branch: Target branch (must exist).

        Returns:
            Dict with commit SHA, file count, and status.
        """
        self.log.info("push_files_starting", branch=branch, file_count=len(files))

        # Pre-flight validate all files before doing any network calls
        for f in files:
            p = f.get("path", "")
            c = f.get("content", "")
            val_err = validate_file_content(p, c)
            if val_err:
                self.log.warning("preflight_validation_failed", path=p, error=val_err)
                return {"error": f"Pre-flight validation failed: {val_err}"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            # 1. Get the current commit SHA for the branch
            ref_url = f"{self.base_url}/repos/{self.repo}/git/ref/heads/{branch}"
            resp = await _request_with_retry(client, "GET", ref_url, self.headers)
            if resp.status_code == 404:
                self.log.error("branch_not_found", branch=branch)
                return {"error": f"Branch '{branch}' not found. Create it first."}
            resp.raise_for_status()
            base_sha = resp.json()["object"]["sha"]

            # 2. Get the tree SHA of the current commit
            commit_url = f"{self.base_url}/repos/{self.repo}/git/commits/{base_sha}"
            resp = await _request_with_retry(client, "GET", commit_url, self.headers)
            resp.raise_for_status()
            base_tree_sha = resp.json()["tree"]["sha"]

            # 3. Create blobs for each file
            tree_items = []
            for file in files:
                blob_url = f"{self.base_url}/repos/{self.repo}/git/blobs"
                blob_payload = {"content": file["content"], "encoding": "utf-8"}
                resp = await _request_with_retry(
                    client, "POST", blob_url, self.headers, json=blob_payload
                )
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
            resp = await _request_with_retry(
                client, "POST", tree_url, self.headers, json=tree_payload
            )
            resp.raise_for_status()
            new_tree_sha = resp.json()["sha"]

            # 5. Create a new commit
            commit_url = f"{self.base_url}/repos/{self.repo}/git/commits"
            commit_payload = {
                "message": message,
                "tree": new_tree_sha,
                "parents": [base_sha],
            }
            resp = await _request_with_retry(
                client, "POST", commit_url, self.headers, json=commit_payload
            )
            resp.raise_for_status()
            new_commit_sha = resp.json()["sha"]

            # 6. Update the branch ref
            ref_url = f"{self.base_url}/repos/{self.repo}/git/refs/heads/{branch}"
            resp = await _request_with_retry(
                client, "PATCH", ref_url, self.headers, json={"sha": new_commit_sha}
            )
            resp.raise_for_status()

            self.log.info(
                "files_pushed",
                branch=branch,
                commit=new_commit_sha[:8],
                file_count=len(files),
                files=[f["path"] for f in files],
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
        """Create a pull request with anti-placeholder validation.

        Args:
            title: PR title.
            body: PR description (supports markdown, use 'Fixes #N' to link issues).
            head: Branch containing the changes.
            base: Branch to merge into (default: 'main').

        Returns:
            Dict with PR number and URL.
        """
        lower_title = title.lower().strip()
        if lower_title in ["pr title", "title", "my pr", "pull request", "pr"]:
            return {
                "error": "Rejected PR title: Generic placeholder titles ('PR title') are not allowed. "
                "Provide a descriptive title summarizing the actual implementation."
            }
        if not body.strip():
            return {
                "error": "Rejected PR body: PR description cannot be empty. "
                "Provide a clear summary of changes referencing 'Fixes #N'."
            }

        url = f"{self.base_url}/repos/{self.repo}/pulls"
        payload = {"title": title, "body": body, "head": head, "base": base}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await _request_with_retry(client, "POST", url, self.headers, json=payload)
            if resp.status_code == 422:
                err = resp.json().get("errors", [{}])
                msg = err[0].get("message", "Unknown error") if err else "Unknown error"
                self.log.error("pr_creation_failed", head=head, base=base, error=msg)
                return {"error": f"Cannot create PR: {msg}"}
            resp.raise_for_status()
            data = resp.json()
            self.log.info("pr_created", number=data["number"], title=title, head=head, base=base)
            return {"number": data["number"], "url": data["html_url"]}

    async def get_directory_tree(self, path: str = "", branch: str = "main") -> dict[str, Any]:
        """List files in a directory (non-recursive).

        Args:
            path: Directory path (empty string for repo root).
            branch: Branch to read from.

        Returns:
            Dict with list of entries (name, type, path).
        """
        # Normalize path — strip leading/trailing slashes to avoid API redirects
        path = path.strip("/")
        if path:
            url = f"{self.base_url}/repos/{self.repo}/contents/{path}"
        else:
            url = f"{self.base_url}/repos/{self.repo}/contents"
        params = {"ref": branch}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await _request_with_retry(
                client, "GET", url, self.headers, params=params, follow_redirects=True
            )
            if resp.status_code == 404:
                self.log.info("directory_not_found", path=path, branch=branch)
                return {"error": f"Path '{path}' not found on branch '{branch}'"}
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, list):
                return {"error": f"'{path}' is a file, not a directory. Use get_file() instead."}

            self.log.info("directory_listed", path=path or "/", branch=branch, entries=len(data))
            return {
                "path": path or "/",
                "branch": branch,
                "entries": [
                    {"name": f["name"], "type": f["type"], "path": f["path"], "size": f.get("size")}
                    for f in data
                ],
            }
