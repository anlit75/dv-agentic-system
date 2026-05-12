# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Project configuration loading for the dv-agentic-system.

Primary entry point::

    from dv_agentic.config import load_project

    ctx, simulator, coverage = load_project(".agent/project.yaml")
"""

from .config_loader import ProjectConfig, ProjectLoader, load_project

__all__ = ["ProjectConfig", "ProjectLoader", "load_project"]
