"""Project configuration loading for the dv-agentic-system.

Primary entry point::

    from dv_agentic.config import load_project

    ctx, simulator, coverage = load_project(".agent/project.yaml")
"""

from .loader import ProjectConfig, ProjectLoader, load_project

__all__ = ["ProjectConfig", "ProjectLoader", "load_project"]
