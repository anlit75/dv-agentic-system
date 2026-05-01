from dataclasses import dataclass


@dataclass
class SimulatorConfig:
    """Injected as {{SIMULATOR_CONFIG}}."""

    name: str  # "xcelium" | "ghdl" | "icarus" | "verilator"
    binary_path: str | None = None  # e.g. "/tools/cadence/xcelium/bin/xrun"
    extra_compile_flags: str | None = None
    extra_run_flags: str | None = None
    collect_coverage: bool = True
    cov_work_dir: str = "cov_work"


@dataclass
class SchedulerConfig:
    """Injected as {{SCHEDULER_CONFIG}}."""

    backend: str | None = None  # "lsf" | "sge" | None (direct subprocess)
    queue: str | None = None  # e.g. "normal", "short"
    resource_flags: str | None = None  # e.g. "-R 'rusage[mem=4096]'" for LSF
    default_wall_time_sec: int = 3600
    poll_interval_sec: int = 30


@dataclass
class VCSConfig:
    """Injected as {{VCS_CONFIG}}."""

    backend: str = "git"  # "git" | "svn" (svn reserved for later)
    base_branch: str = "main"
    remote: str = "origin"
    author_name: str | None = None
    author_email: str | None = None


@dataclass
class ProjectContext:
    """Project-level rules and environment data for prompt enrichment."""

    # General Rules
    team_rules: str | None = None
    ip_type_rules: str | None = None
    vip_index: str | None = None
    vplan_summary: str | None = None
    known_error_patterns: str | None = None
    known_rtl_bugs: str | None = None

    # Infrastructure Configs
    simulator_config: SimulatorConfig | None = None
    scheduler_config: SchedulerConfig | None = None
    vcs_config: VCSConfig | None = None


@dataclass
class SessionState:
    """Run-time session data for prompt enrichment."""

    task_id: str | None = None
    iteration: int = 0
    budget_remaining: int | None = None
