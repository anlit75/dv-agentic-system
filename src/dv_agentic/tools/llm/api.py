# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""External LLM client for the LLM Messages API.

Uses only Python stdlib (urllib) — no third-party SDK required.
Set LLM_API_KEY in the environment or pass it explicitly.
"""

import asyncio
import json
import os
import urllib.error
import urllib.request
from typing import Any

from .interface import BaseLLMClient


class LLMAPIClient(BaseLLMClient):
    """Calls the LLM /v1/messages endpoint over raw HTTP.

    All network I/O runs in a thread-pool executor so the async caller
    is never blocked.
    """

    DEFAULT_URL = "https://api.anthropic.com/v1/messages"
    LLM_VERSION = "2023-06-01"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-3-5-sonnet-latest",
        api_url: str = DEFAULT_URL,
        timeout: int = 120,
    ) -> None:
        """Initialise the client.

        Args:
            api_key: LLM API key.  Falls back to ``LLM_API_KEY``
                environment variable.
            model: Model identifier to send in every request.
            api_url: Full URL of the messages endpoint (override for testing).
            timeout: Socket timeout in seconds for each HTTP call.
        """
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.model = model
        self.api_url = api_url
        self.timeout = timeout

    async def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 1000,
        temperature: float | None = None,
    ) -> str:
        """Send a request to the LLM API and return the assistant reply.

        Args:
            system: System prompt string.
            messages: Conversation turns in ``[{"role": ..., "content": ...}]`` form.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.  ``None`` omits the field from
                the request body, deferring to the API default.

        Returns:
            The text content of the first content block in the response.

        Raises:
            RuntimeError: On non-2xx HTTP response.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._post, system, messages, max_tokens, temperature
        )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _post(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float | None = None,
    ) -> str:
        """Blocking HTTP POST — runs in a thread-pool executor."""
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        if temperature is not None:
            body["temperature"] = temperature
        payload = json.dumps(body).encode()

        req = urllib.request.Request(  # noqa: S310
            self.api_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "llm-version": self.LLM_VERSION,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                response: dict[str, Any] = json.loads(resp.read())
                return str(response["content"][0]["text"])
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"LLM API error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM API connection error: {exc.reason}") from exc
