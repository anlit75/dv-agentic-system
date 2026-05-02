"""Internal LLM client for the local/internal endpoint (OpenAI-compatible).

Reads LOCAL_LLM_BASE_URL and LOCAL_LLM_API_KEY from the environment,
or accept them explicitly.  The endpoint is assumed to follow the
OpenAI Chat Completions API shape (``POST /v1/chat/completions``).
"""

import asyncio
import json
import os
import urllib.error
import urllib.request
from typing import Any

from .interface import BaseLLMClient


class LocalLLMClient(BaseLLMClient):
    """Calls an internal LLM endpoint that speaks OpenAI Chat Completions.

    All network I/O runs in a thread-pool executor so the async caller
    is never blocked.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str = "default",
        timeout: int = 120,
    ) -> None:
        """Initialise the client.

        Args:
            base_url: Base URL of the local LLM service, e.g.
                ``"http://localhost:8080"``.
                Falls back to ``LOCAL_LLM_BASE_URL`` environment variable.
            api_key: Bearer token for the internal service.
                Falls back to ``LOCAL_LLM_API_KEY`` environment variable.
            model: Model name to send in the request body.
            timeout: Socket timeout in seconds.
        """
        raw_url = base_url or os.environ.get("LOCAL_LLM_BASE_URL", "")
        if not raw_url:
            msg = (
                "LocalLLMClient requires 'base_url' or 'LOCAL_LLM_BASE_URL' "
                "environment variable to be set."
            )
            raise ValueError(msg)

        self.api_url = raw_url.rstrip("/") + "/v1/chat/completions"
        self.api_key = api_key or os.environ.get("LOCAL_LLM_API_KEY", "")
        self.model = model
        self.timeout = timeout

    async def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 1000,
    ) -> str:
        """Send a chat-completion request to the local LLM endpoint.

        Args:
            system: System prompt string (prepended as a ``"system"`` role message).
            messages: Conversation turns in ``[{"role": ..., "content": ...}]`` form.
            max_tokens: Maximum tokens to generate.

        Returns:
            The assistant's reply text.

        Raises:
            RuntimeError: On non-2xx HTTP response or connection failure.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._post, system, messages, max_tokens)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _post(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int,
    ) -> str:
        """Blocking HTTP POST — runs in a thread-pool executor."""
        all_messages = [{"role": "system", "content": system}, *messages]
        payload = json.dumps(
            {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": all_messages,
            }
        ).encode()

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(  # noqa: S310
            self.api_url,
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                body: dict[str, Any] = json.loads(resp.read())
                return str(body["choices"][0]["message"]["content"])
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"Local LLM API error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Local LLM connection error: {exc.reason}") from exc
