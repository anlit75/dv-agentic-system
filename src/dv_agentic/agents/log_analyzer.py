# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

# Compatibility shim — implementation moved to tools/services/log_analyzer.py
from typing import Any

from ..tools.services.log_analyzer import FailureSummary, LogAnalyzerService

__all__ = ["FailureSummary", "LogAnalyzerAgent"]


class LogAnalyzerAgent(LogAnalyzerService):
    """Backward-compatible alias.  New code should use LogAnalyzerService directly."""

    def __init__(self, config: Any = None, wiki_config: Any = None) -> None:
        super().__init__(wiki_config=wiki_config)
