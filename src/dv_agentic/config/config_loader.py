"""Project configuration loader.

Reads ``.agent/project.yaml`` and the referenced team/IP-type profiles,
assembles a :class:`~dv_agentic.prompts.context.ProjectContext` for
:class:`~dv_agentic.prompts.prompt_loader.PromptLoader` injection, and instantiates
the correct :class:`~dv_agentic.tools.interface.SimulatorTool` and
:class:`~dv_agentic.tools.interface.CoverageTool` adapters.

Three-layer loading
-------------------
1. ``.agent/project.yaml``           — names the team, IP types, and adapters.
2. ``{profiles_dir}/teams/{team}/``  — team coding rules, VIP index, tool config.
3. ``{profiles_dir}/ip-types/{ip}/`` — protocol rules and coverage taxonomy.

``profiles_dir`` resolution order
----------------------------------
1. Explicit ``profiles_dir`` argument to :class:`ProjectLoader` or
   :func:`load_project`.
2. ``DV_PROFILES_DIR`` environment variable.
3. ``profiles.dir`` field inside ``project.yaml`` itself.
4. ``None`` — profile injection is silently skipped; adapters still work.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from ..prompts.context import (
    ProjectContext,
    SchedulerConfig,
    SimulatorConfig,
    VCSConfig,
)
from ..tools.adapters import get_coverage_adapter, get_simulator_adapter
from ..tools.interface import CoverageTool, SimulatorTool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Typed representation of project.yaml
# ---------------------------------------------------------------------------


@dataclass
class ProjectConfig:
    """Typed, validated representation of a parsed ``.agent/project.yaml``.

    Attributes:
        name: Human-readable project name.
        environment: ``"internal"`` or ``"external"``.
        team: Team profile key, e.g. ``"team_io"``.  ``None`` means no profile.
        ip_types: List of IP-type profile keys, e.g. ``["axi", "pcie"]``.
        simulator: Simulator key (see :data:`~dv_agentic.tools.adapters._SIMULATOR_REGISTRY`).
        coverage: Coverage key (see :data:`~dv_agentic.tools.adapters._COVERAGE_REGISTRY`).
        profiles_dir: Optional override path to the org profile repository.
    """

    name: str
    environment: str  # "internal" | "external"
    team: str | None = None
    ip_types: list[str] = field(default_factory=list)
    simulator: str = "xcelium"
    coverage: str = "imc"
    profiles_dir: str | None = None


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class ProjectLoader:
    """Loads project configuration from ``project.yaml`` and profile directories.

    Args:
        profiles_dir: Root of the org profile repository, e.g.
            ``"sample/sample-org-dv-profiles/"``.  Falls back to
            ``DV_PROFILES_DIR`` environment variable, then ``None``
            (profile injection silently skipped; adapters still instantiated).
    """

    def __init__(self, profiles_dir: str | Path | None = None) -> None:
        resolved: str | Path | None = profiles_dir or os.environ.get("DV_PROFILES_DIR")
        self._profiles_dir: Path | None = Path(resolved) if resolved else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(
        self,
        project_yaml_path: str | Path = ".agent/project.yaml",
    ) -> tuple[ProjectContext, SimulatorTool, CoverageTool]:
        """Load and assemble project configuration.

        Args:
            project_yaml_path: Path to ``.agent/project.yaml``.

        Returns:
            ``(ProjectContext, SimulatorTool, CoverageTool)``

        Raises:
            FileNotFoundError: If *project_yaml_path* does not exist.
            ValueError: If required fields are missing or have invalid values.
        """
        path = Path(project_yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"project.yaml not found: {path}")

        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"project.yaml must be a YAML mapping, got {type(raw).__name__}")

        config = self._parse_project_yaml(raw)

        # project.yaml can carry a profiles.dir override (lowest priority)
        if config.profiles_dir and self._profiles_dir is None:
            self._profiles_dir = Path(config.profiles_dir)

        context = self._build_context(config)
        simulator = self._build_simulator(config)
        coverage_tool = self._build_coverage(config)

        logger.info(
            "ProjectLoader: loaded '%s' (env=%s sim=%s cov=%s team=%s ip_types=%s)",
            config.name,
            config.environment,
            config.simulator,
            config.coverage,
            config.team,
            config.ip_types,
        )
        return context, simulator, coverage_tool

    # ------------------------------------------------------------------
    # project.yaml parsing
    # ------------------------------------------------------------------

    def _parse_project_yaml(self, raw: dict[str, Any]) -> ProjectConfig:
        project: dict[str, Any] = raw.get("project") or {}
        composition: dict[str, Any] = raw.get("composition") or {}

        name = str(project.get("name") or "unnamed")
        environment = str(project.get("environment") or "external")
        if environment not in ("internal", "external"):
            raise ValueError(
                f"project.environment must be 'internal' or 'external', got {environment!r}"
            )

        team: str | None = composition.get("team") or None

        raw_ips: Any = composition.get("ip_types") or []
        ip_types: list[str] = (
            [str(raw_ips)] if isinstance(raw_ips, str) else [str(x) for x in raw_ips]
        )

        simulator = str(composition.get("simulator") or "xcelium")
        coverage = str(composition.get("coverage") or "imc")

        profiles_section: dict[str, Any] = raw.get("profiles") or {}
        profiles_dir: str | None = profiles_section.get("dir") or None

        return ProjectConfig(
            name=name,
            environment=environment,
            team=team,
            ip_types=ip_types,
            simulator=simulator,
            coverage=coverage,
            profiles_dir=profiles_dir,
        )

    # ------------------------------------------------------------------
    # Building ProjectContext
    # ------------------------------------------------------------------

    def _build_context(self, config: ProjectConfig) -> ProjectContext:
        team_raw: dict[str, Any] = {}
        if config.team:
            team_raw = self._load_team_yaml(config.team)

        return ProjectContext(
            team_rules=(self._load_prompt_patch(config.team) if config.team else None),
            ip_type_rules=(self._load_ip_rules(config.ip_types) if config.ip_types else None),
            vip_index=(self._load_vip_index(config.team) if config.team else None),
            simulator_config=self._build_simulator_config(config.simulator, team_raw),
            scheduler_config=self._build_scheduler_config(team_raw),
            vcs_config=self._build_vcs_config(team_raw),
        )

    # ------------------------------------------------------------------
    # Building adapters
    # ------------------------------------------------------------------

    def _build_simulator(self, config: ProjectConfig) -> SimulatorTool:
        try:
            return get_simulator_adapter(config.simulator)
        except ValueError:
            logger.warning("Unknown simulator %r; falling back to 'xcelium'.", config.simulator)
            return get_simulator_adapter("xcelium")

    def _build_coverage(self, config: ProjectConfig) -> CoverageTool:
        try:
            return get_coverage_adapter(config.coverage)
        except ValueError:
            logger.warning("Unknown coverage adapter %r; falling back to 'imc'.", config.coverage)
            return get_coverage_adapter("imc")

    # ------------------------------------------------------------------
    # Building config dataclasses from team.yaml
    # ------------------------------------------------------------------

    def _build_simulator_config(
        self, simulator_name: str, team_raw: dict[str, Any]
    ) -> SimulatorConfig:
        sim: dict[str, Any] = team_raw.get("simulator") or {}
        return SimulatorConfig(
            name=simulator_name,
            binary_path=sim.get("binary_path") or None,
            extra_compile_flags=sim.get("extra_compile_flags") or None,
            extra_run_flags=sim.get("extra_run_flags") or None,
            collect_coverage=bool(sim.get("collect_coverage", True)),
            cov_work_dir=str(sim.get("cov_work_dir") or "cov_work"),
        )

    def _build_scheduler_config(self, team_raw: dict[str, Any]) -> SchedulerConfig | None:
        sch: dict[str, Any] = team_raw.get("scheduler") or {}
        backend: str | None = sch.get("backend") or None
        if not backend:
            return None
        return SchedulerConfig(
            backend=backend,
            queue=sch.get("queue") or None,
            resource_flags=sch.get("resource_flags") or None,
            default_wall_time_sec=int(sch.get("default_wall_time_sec") or 3600),
            poll_interval_sec=int(sch.get("poll_interval_sec") or 30),
        )

    def _build_vcs_config(self, team_raw: dict[str, Any]) -> VCSConfig | None:
        vcs: dict[str, Any] = team_raw.get("vcs") or {}
        if not vcs:
            return None
        return VCSConfig(
            backend=str(vcs.get("backend") or "git"),
            base_branch=str(vcs.get("base_branch") or "main"),
            remote=str(vcs.get("remote") or "origin"),
            author_name=vcs.get("author_name") or None,
            author_email=vcs.get("author_email") or None,
        )

    # ------------------------------------------------------------------
    # Profile file loading — all methods degrade gracefully on missing files
    # ------------------------------------------------------------------

    def _team_dir(self, team: str) -> Path | None:
        if self._profiles_dir is None:
            return None
        d = self._profiles_dir / "teams" / team
        return d if d.is_dir() else None

    def _ip_dir(self, ip_type: str) -> Path | None:
        if self._profiles_dir is None:
            return None
        d = self._profiles_dir / "ip-types" / ip_type
        return d if d.is_dir() else None

    def _load_team_yaml(self, team: str) -> dict[str, Any]:
        d = self._team_dir(team)
        if d is None:
            logger.debug("Team profile directory not found for team '%s'", team)
            return {}
        team_file = d / "team.yaml"
        if not team_file.exists():
            logger.debug("team.yaml not found for team '%s'", team)
            return {}
        raw: Any = yaml.safe_load(team_file.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}

    def _load_prompt_patch(self, team: str) -> str | None:
        """Return the contents of ``prompt_patch.md`` for *team*, or ``None``."""
        d = self._team_dir(team)
        if d is None:
            return None
        patch_file = d / "prompt_patch.md"
        if not patch_file.exists():
            return None
        return patch_file.read_text(encoding="utf-8").strip() or None

    def _load_vip_index(self, team: str) -> str | None:
        """Return the raw text of ``vip_index.yaml`` for *team*, or ``None``."""
        d = self._team_dir(team)
        if d is None:
            return None
        vip_file = d / "vip_index.yaml"
        if not vip_file.exists():
            return None
        return vip_file.read_text(encoding="utf-8").strip() or None

    def _load_ip_rules(self, ip_types: list[str]) -> str | None:
        """Concatenate protocol rules for all *ip_types*, or return ``None``."""
        blocks: list[str] = []
        for ip in ip_types:
            d = self._ip_dir(ip)
            if d is None:
                logger.debug("IP-type profile directory not found: '%s'", ip)
                continue
            rules_file = d / "protocol_rules.yaml"
            if not rules_file.exists():
                logger.debug("protocol_rules.yaml not found for ip-type '%s'", ip)
                continue
            raw: Any = yaml.safe_load(rules_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and raw.get("rules"):
                text = str(raw["rules"]).strip()
            else:
                # Fallback: inject the whole file as-is
                text = rules_file.read_text(encoding="utf-8").strip()
            if text:
                blocks.append(f"## {ip.upper()} Protocol Rules\n\n{text}")
        return "\n\n".join(blocks) if blocks else None


# ---------------------------------------------------------------------------
# Public convenience function
# ---------------------------------------------------------------------------


def load_project(
    project_yaml: str | Path = ".agent/project.yaml",
    profiles_dir: str | Path | None = None,
) -> tuple[ProjectContext, SimulatorTool, CoverageTool]:
    """Load project config and return assembled context and adapters.

    Convenience wrapper around :class:`ProjectLoader`.

    Args:
        project_yaml: Path to ``.agent/project.yaml``.
        profiles_dir: Root of the org profile repository.
            Falls back to ``DV_PROFILES_DIR`` env var, then ``None``.

    Returns:
        ``(ProjectContext, SimulatorTool, CoverageTool)``

    Example::

        ctx, simulator, coverage = load_project(".agent/project.yaml")
        # ctx → pass to PromptLoader for prompt enrichment
        # simulator → pass to SimControllerAgent
        # coverage → pass to CoverageAnalystAgent
    """
    return ProjectLoader(profiles_dir=profiles_dir).load(project_yaml)
