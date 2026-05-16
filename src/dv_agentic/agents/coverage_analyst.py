# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

# Compatibility shim — implementation moved to tools/services/coverage_analyst.py
from typing import Any

from ..tools.services.coverage_analyst import CoverageAnalystService, CoverageSummary

__all__ = ["CoverageAnalystAgent", "CoverageSummary"]


class CoverageAnalystAgent(CoverageAnalystService):
    """Backward-compatible alias.  New code should use CoverageAnalystService directly."""

    def __init__(
        self,
        config: Any = None,
        coverage: Any = None,
        threshold: float = 90.0,
        wiki_config: Any = None,
    ) -> None:
        if coverage is None:
            raise ValueError("CoverageAnalystAgent requires a 'coverage' adapter")
        super().__init__(coverage=coverage, threshold=threshold, wiki_config=wiki_config)
