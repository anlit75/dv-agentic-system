"""Unit tests for Phase 2 LLM clients (api.py and local.py)."""

import json
import urllib.error
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from dv_agentic.tools.llm.api import LLMAPIClient
from dv_agentic.tools.llm.local import LocalLLMClient

# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------


def _mock_response(body: dict[str, Any]) -> MagicMock:
    """Return a mock that behaves like urllib.request.urlopen context manager."""
    m = MagicMock()
    m.__enter__ = MagicMock(return_value=m)
    m.__exit__ = MagicMock(return_value=False)
    m.read.return_value = json.dumps(body).encode()
    return m


def _http_error(code: int, message: str = "error") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="http://x",
        code=code,
        msg=message,
        hdrs=None,  # type: ignore[arg-type]
        fp=BytesIO(message.encode()),
    )


@pytest.fixture
def api_client() -> LLMAPIClient:
    """Fixture providing a configured LLMAPIClient."""
    return LLMAPIClient(api_key="test-key", model="claude-test")


@pytest.fixture
def local_client() -> LocalLLMClient:
    """Fixture providing a configured LocalLLMClient."""
    return LocalLLMClient(
        base_url="http://local-llm.internal:8080",
        api_key="internal-key",
        model="codellama",
    )


# ---------------------------------------------------------------------------
# LLMAPIClient Tests
# ---------------------------------------------------------------------------


class TestLLMAPIClient:
    def test_post_success(self, api_client: LLMAPIClient) -> None:
        body = {"content": [{"type": "text", "text": "Hello from Claude"}]}
        with patch("urllib.request.urlopen", return_value=_mock_response(body)):
            result = api_client._post("sys", [{"role": "user", "content": "hi"}], 100)
        assert result == "Hello from Claude"

    def test_post_http_error_raises_runtime(self, api_client: LLMAPIClient) -> None:
        with (
            patch("urllib.request.urlopen", side_effect=_http_error(401, "Unauthorized")),
            pytest.raises(RuntimeError, match="401"),
        ):
            api_client._post("sys", [], 100)

    def test_post_url_error_raises_runtime(self, api_client: LLMAPIClient) -> None:
        with (
            patch(
                "urllib.request.urlopen",
                side_effect=urllib.error.URLError("connection refused"),
            ),
            pytest.raises(RuntimeError, match="connection"),
        ):
            api_client._post("sys", [], 100)

    def test_request_headers_include_api_key(self, api_client: LLMAPIClient) -> None:
        """Verify that x-api-key and llm-version are set."""
        body = {"content": [{"type": "text", "text": "ok"}]}
        captured: list[Any] = []

        def fake_urlopen(req: Any, timeout: Any = None) -> MagicMock:
            captured.append(req)
            return _mock_response(body)

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            api_client._post("sys", [], 100)

        req = captured[0]
        assert req.get_header("X-api-key") == "test-key"
        assert "2023-06-01" in req.get_header("Llm-version")

    @pytest.mark.asyncio
    async def test_complete_async(self, api_client: LLMAPIClient) -> None:
        body: dict[str, Any] = {"content": [{"type": "text", "text": "async works"}]}
        with patch("urllib.request.urlopen", return_value=_mock_response(body)):
            result = await api_client.complete("sys", [{"role": "user", "content": "hi"}])
        assert result == "async works"

    def test_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_API_KEY", "env-key")
        client = LLMAPIClient()
        assert client.api_key == "env-key"


# ---------------------------------------------------------------------------
# LocalLLMClient Tests
# ---------------------------------------------------------------------------


class TestLocalLLMClient:
    def test_api_url_constructed_correctly(self, local_client: LocalLLMClient) -> None:
        assert local_client.api_url == "http://local-llm.internal:8080/v1/chat/completions"

    def test_trailing_slash_stripped(self) -> None:
        c = LocalLLMClient(base_url="http://host:9000/")
        assert c.api_url == "http://host:9000/v1/chat/completions"

    def test_post_success(self, local_client: LocalLLMClient) -> None:
        body = {"choices": [{"message": {"content": "Local LLM reply"}}]}
        with patch("urllib.request.urlopen", return_value=_mock_response(body)):
            result = local_client._post("sys", [{"role": "user", "content": "q"}], 200)
        assert result == "Local LLM reply"

    def test_system_message_prepended(self, local_client: LocalLLMClient) -> None:
        """System prompt must be the first message in the OpenAI-format payload."""
        body = {"choices": [{"message": {"content": "ok"}}]}
        sent_payloads: list[dict[str, Any]] = []

        def fake_urlopen(req: Any, timeout: Any = None) -> MagicMock:
            sent_payloads.append(json.loads(req.data))
            return _mock_response(body)

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            local_client._post("my system", [{"role": "user", "content": "hi"}], 100)

        msgs = sent_payloads[0]["messages"]
        assert msgs[0] == {"role": "system", "content": "my system"}
        assert msgs[1]["role"] == "user"

    def test_post_http_error_raises_runtime(self, local_client: LocalLLMClient) -> None:
        with (
            patch("urllib.request.urlopen", side_effect=_http_error(403, "Forbidden")),
            pytest.raises(RuntimeError, match="403"),
        ):
            local_client._post("sys", [], 100)

    def test_post_url_error_raises_runtime(self, local_client: LocalLLMClient) -> None:
        """Test URLError handling for LocalLLMClient (achieves 100% coverage)."""
        with (
            patch(
                "urllib.request.urlopen",
                side_effect=urllib.error.URLError("local host unreachable"),
            ),
            pytest.raises(RuntimeError, match="Local LLM connection error"),
        ):
            local_client._post("sys", [], 100)

    def test_base_url_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://env-host")
        client = LocalLLMClient()
        assert "env-host" in client.api_url

    def test_missing_base_url_raises_value_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LOCAL_LLM_BASE_URL", raising=False)
        with pytest.raises(ValueError, match="requires 'base_url'"):
            LocalLLMClient(base_url=None)

    @pytest.mark.asyncio
    async def test_complete_async(self, local_client: LocalLLMClient) -> None:
        body = {"choices": [{"message": {"content": "async ok"}}]}
        with patch("urllib.request.urlopen", return_value=_mock_response(body)):
            result = await local_client.complete("sys", [])
        assert result == "async ok"
