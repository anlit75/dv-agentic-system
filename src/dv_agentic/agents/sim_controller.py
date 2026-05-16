# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

# Compatibility shim — implementation moved to tools/services/sim_controller.py
from typing import Any

from ..tools.services.sim_controller import SimControllerService, SimReport

__all__ = ["SimControllerAgent", "SimReport"]


class SimControllerAgent(SimControllerService):
    """Backward-compatible alias.  New code should use SimControllerService directly."""

    def __init__(
        self,
        config: Any = None,
        simulator: Any = None,
        coverage: Any = None,
        base_branch: str = "main",
    ) -> None:
        if simulator is None:
            raise ValueError("SimControllerAgent requires a 'simulator' adapter")
        super().__init__(simulator=simulator, coverage=coverage, base_branch=base_branch)
