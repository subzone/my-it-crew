"""Tests for CodingTools module — GitHub API-based coding operations."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.tools.coding_tools import CodingTools, _request_with_retry


@pytest.fixture
def tools():
    """Create a CodingTools instance with test settings."""
    with patch("src.tools.coding_tools.Settings") as mock_settings_cls:
        settings = MagicMock()
        settings.github_token = "test-token"
        settings.github_repo = "testowner/testrepo"
        mock_settings_cls.return_value = settings
        return CodingTools(settings)


class TestRequestWithRetry:
    """Test the retry/backoff wrapper."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        client = AsyncMock()
        response = MagicMock()
        response.status_code = 200
        client.request = AsyncMock(return_value=response)

        result = await _request_with_retry(client, "GET", "http://test.com", {})
        assert result.status_code == 200
        assert client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_429(self):
        client = AsyncMock()
        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.headers = {"Retry-After": "0"}

        success = MagicMock()
        success.status_code = 200

        client.request = AsyncMock(side_effect=[rate_limited, success])

        result = await _request_with_retry(client, "GET", "http://test.com", {}, max_retries=2)
        assert result.status_code == 200
        assert client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_500(self):
        client = AsyncMock()
        error = MagicMock()
        error.status_code = 500

        success = MagicMock()
        success.status_code = 200

        client.request = AsyncMock(side_effect=[error, success])

        result = await _request_with_retry(client, "POST", "http://test.com", {}, max_retries=2)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx(self):
        client = AsyncMock()
        not_found = MagicMock()
        not_found.status_code = 404

        client.request = AsyncMock(return_value=not_found)

        result = await _request_with_retry(client, "GET", "http://test.com", {}, max_retries=3)
        assert result.status_code == 404
        assert client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_network_error(self):
        client = AsyncMock()
        client.request = AsyncMock(
            side_effect=[httpx.ConnectTimeout("timeout"), MagicMock(status_code=200)]
        )

        result = await _request_with_retry(client, "GET", "http://test.com", {}, max_retries=2)
        assert result.status_code == 200


class TestCreateBranch:
    """Test create_branch with idempotency."""

    @pytest.mark.asyncio
    async def test_create_new_branch(self, tools):
        mock_responses = [
            # GET source branch SHA
            MagicMock(status_code=200, json=lambda: {"object": {"sha": "abc123"}}),
            # POST create ref — success
            MagicMock(status_code=201, json=lambda: {"ref": "refs/heads/nova/issue-1"}),
        ]
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(side_effect=mock_responses)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await tools.create_branch("nova/issue-1")
            assert result["status"] == "created"
            assert result["branch"] == "nova/issue-1"
            assert result["sha"] == "abc123"

    @pytest.mark.asyncio
    async def test_idempotent_existing_branch(self, tools):
        mock_responses = [
            # GET source branch SHA
            MagicMock(status_code=200, json=lambda: {"object": {"sha": "abc123"}}),
            # POST create ref — 422 already exists
            MagicMock(status_code=422),
            # GET existing branch SHA
            MagicMock(status_code=200, json=lambda: {"object": {"sha": "def456"}}),
        ]
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(side_effect=mock_responses)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await tools.create_branch("nova/issue-1")
            assert result["status"] == "exists"
            assert result["sha"] == "def456"

    @pytest.mark.asyncio
    async def test_source_branch_not_found(self, tools):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=MagicMock(status_code=404))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await tools.create_branch("nova/issue-1", from_branch="nonexistent")
            assert "error" in result
            assert "nonexistent" in result["error"]


class TestGetFile:
    """Test get_file with directory safety."""

    @pytest.mark.asyncio
    async def test_read_file_success(self, tools):
        import base64

        content_b64 = base64.b64encode(b"hello world").decode()
        mock_resp = MagicMock(
            status_code=200,
            json=lambda: {
                "type": "file",
                "content": content_b64,
                "sha": "filesha123",
                "size": 11,
            },
        )
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await tools.get_file("src/config.py")
            assert result["content"] == "hello world"
            assert result["sha"] == "filesha123"
            assert result["size"] == 11

    @pytest.mark.asyncio
    async def test_directory_returns_error(self, tools):
        """get_file() on a directory should return error, not crash."""
        dir_listing = [
            {"name": "file1.py", "type": "file", "path": "src/file1.py"},
            {"name": "file2.py", "type": "file", "path": "src/file2.py"},
        ]
        mock_resp = MagicMock(status_code=200, json=lambda: dir_listing)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await tools.get_file("src/")
            assert "error" in result
            assert "directory" in result["error"]
            assert result["type"] == "directory"
            assert result["entry_count"] == 2

    @pytest.mark.asyncio
    async def test_file_not_found(self, tools):
        mock_resp = MagicMock(status_code=404)
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await tools.get_file("nonexistent.py")
            assert "error" in result
            assert "not found" in result["error"]


class TestCreateOrUpdateFile:
    """Test file creation and updates."""

    @pytest.mark.asyncio
    async def test_create_new_file(self, tools):
        mock_resp = MagicMock(
            status_code=201,
            json=lambda: {"commit": {"sha": "commit123"}},
        )
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await tools.create_or_update_file(
                path="src/new.py",
                content="print('hello')",
                message="Add new.py",
                branch="nova/issue-1",
            )
            assert result["status"] == "created"
            assert result["commit_sha"] == "commit123"

    @pytest.mark.asyncio
    async def test_update_existing_file(self, tools):
        mock_resp = MagicMock(
            status_code=200,
            json=lambda: {"commit": {"sha": "commit456"}},
        )
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await tools.create_or_update_file(
                path="src/existing.py",
                content="print('updated')",
                message="Update existing.py",
                branch="nova/issue-1",
                sha="oldsha123",
            )
            assert result["status"] == "updated"

    @pytest.mark.asyncio
    async def test_conflict_returns_error(self, tools):
        mock_resp = MagicMock(status_code=409)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await tools.create_or_update_file(
                path="src/file.py",
                content="x",
                message="update",
                branch="main",
                sha="stale",
            )
            assert "error" in result
            assert "Conflict" in result["error"]


class TestCreatePullRequest:
    """Test PR creation."""

    @pytest.mark.asyncio
    async def test_create_pr_success(self, tools):
        mock_resp = MagicMock(
            status_code=201,
            json=lambda: {"number": 42, "html_url": "https://github.com/test/pr/42"},
        )
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await tools.create_pull_request(
                title="feat: add user API",
                body="Fixes #1",
                head="nova/issue-1",
            )
            assert result["number"] == 42
            assert "error" not in result

    @pytest.mark.asyncio
    async def test_create_pr_already_exists(self, tools):
        mock_resp = MagicMock(
            status_code=422,
            json=lambda: {"errors": [{"message": "A pull request already exists"}]},
        )

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await tools.create_pull_request(
                title="duplicate", body="x", head="nova/issue-1"
            )
            assert "error" in result
            assert "already exists" in result["error"]
