# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""LLM client factory for CLI entrypoints.

Selection priority:
1. ``DV_LLM_BACKEND=anthropic`` → :class:`~dv_agentic.tools.llm.api.LLMAPIClient`
2. ``DV_LLM_BACKEND=local``     → :class:`~dv_agentic.tools.llm.local.LocalLLMClient`
3. ``LOCAL_LLM_BASE_URL`` set   → :class:`~dv_agentic.tools.llm.local.LocalLLMClient`
4. Fallback                     → :class:`~dv_agentic.tools.llm.api.LLMAPIClient`
"""

import os

from ..tools.llm.interface import BaseLLMClient


def make_llm(model: str | None = None) -> BaseLLMClient:
    """Return the appropriate LLM client based on environment variables.

    Args:
        model: Optional model name to override the default.

    Returns:
        The instantiated LLM client.
    """
    backend = os.environ.get("DV_LLM_BACKEND", "").lower()

    if backend == "local" or (backend != "anthropic" and os.environ.get("LOCAL_LLM_BASE_URL")):
        from ..tools.llm.local import LocalLLMClient

        return LocalLLMClient(model=model or "default")

    from ..tools.llm.api import LLMAPIClient

    return LLMAPIClient(model=model or "claude-sonnet-4-20250514")
