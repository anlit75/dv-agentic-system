"""Unit tests for the Phase 4 project configuration loader."""

import shutil
from pathlib import Path
from typing import Any

import pytest

from dv_agentic.config.loader import ProjectLoader, load_project
from dv_agentic.prompts.context import ProjectContext
from dv_agentic.tools.adapters.imc import IMCAdapter
from dv_agentic.tools.adapters.pyuvm import PyuvmCoverageAdapter
from dv_agentic.tools.adapters.xcelium import XceliumAdapter

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_MINIMAL_YAML = """\
project:
  name: test_project
  environment: internal

composition:
  simulator: xcelium
  coverage: imc
"""

_FULL_YAML = """\
project:
  name: full_project
  environment: internal

composition:
  team: sample_team
  ip_types: [axi, pcie]
  simulator: xcelium
  coverage: imc
"""

_TEAM_YAML = """\
simulator:
  binary_path: /tools/xrun
  extra_compile_flags: "-v200"
  extra_run_flags: "+UVM_VERBOSITY=UVM_MEDIUM"
  collect_coverage: true
  cov_work_dir: cov_work/

scheduler:
  backend: lsf
  queue: normal
  resource_flags: "-R 'rusage[mem=4096]'"
  default_wall_time_sec: 3600
  poll_interval_sec: 30

vcs:
  backend: git
  base_branch: main
  remote: origin
  author_name: Test Bot
  author_email: bot@example.com
"""

_PROMPT_PATCH = "## Team Rules\n\nAlways use factory overrides."
_VIP_INDEX = "sequences:\n  - name: axi_burst_seq"
_AXI_RULES = "protocol: axi\nrules: |\n  AXI4 max burst length is 256 beats."
_PCIE_RULES = "protocol: pcie\nrules: |\n  PCIe TLP size must not exceed MPS."


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_yaml(tmp_path: Path) -> Path:
    """Minimal project.yaml with no team profile."""
    f = tmp_path / "project.yaml"
    f.write_text(_MINIMAL_YAML)
    return f


@pytest.fixture()
def profiles_dir(tmp_path: Path) -> Path:
    """A complete profiles directory with team and two IP types."""
    team_dir = tmp_path / "profiles" / "teams" / "sample_team"
    team_dir.mkdir(parents=True)
    (team_dir / "team.yaml").write_text(_TEAM_YAML)
    (team_dir / "prompt_patch.md").write_text(_PROMPT_PATCH)
    (team_dir / "vip_index.yaml").write_text(_VIP_INDEX)

    axi_dir = tmp_path / "profiles" / "ip-types" / "axi"
    axi_dir.mkdir(parents=True)
    (axi_dir / "protocol_rules.yaml").write_text(_AXI_RULES)

    pcie_dir = tmp_path / "profiles" / "ip-types" / "pcie"
    pcie_dir.mkdir(parents=True)
    (pcie_dir / "protocol_rules.yaml").write_text(_PCIE_RULES)

    return tmp_path / "profiles"


@pytest.fixture()
def full_project_yaml(tmp_path: Path) -> Path:
    """project.yaml that references a team and two IP types."""
    f = tmp_path / "project.yaml"
    f.write_text(_FULL_YAML)
    return f


# ---------------------------------------------------------------------------
# Minimal configuration (no profiles)
# ---------------------------------------------------------------------------


class TestMinimalConfig:
    def test_missing_project_yaml_raises(self, tmp_path: Path) -> None:
        loader = ProjectLoader()
        with pytest.raises(FileNotFoundError, match=r"project\.yaml not found"):
            loader.load(tmp_path / "nonexistent.yaml")

    def test_returns_correct_types(self, project_yaml: Path) -> None:
        ctx, sim, cov = ProjectLoader().load(project_yaml)
        assert isinstance(ctx, ProjectContext)
        assert isinstance(sim, XceliumAdapter)
        assert isinstance(cov, IMCAdapter)

    def test_simulator_config_name_set(self, project_yaml: Path) -> None:
        ctx, _, _ = ProjectLoader().load(project_yaml)
        assert ctx.simulator_config is not None
        assert ctx.simulator_config.name == "xcelium"

    def test_no_team_leaves_context_fields_none(self, project_yaml: Path) -> None:
        ctx, _, _ = ProjectLoader().load(project_yaml)
        assert ctx.team_rules is None
        assert ctx.vip_index is None
        assert ctx.ip_type_rules is None
        assert ctx.scheduler_config is None
        assert ctx.vcs_config is None

    def test_pyuvm_coverage_adapter_selected(self, tmp_path: Path) -> None:
        f = tmp_path / "project.yaml"
        f.write_text(
            "project:\n  name: ext\n  environment: external\n"
            "composition:\n  simulator: xcelium\n  coverage: pyuvm\n"
        )
        _, _, cov = ProjectLoader().load(f)
        assert isinstance(cov, PyuvmCoverageAdapter)

    def test_ip_types_as_single_string_parsed(self, tmp_path: Path) -> None:
        """ip_types: axi (string not list) must be accepted."""
        f = tmp_path / "project.yaml"
        f.write_text(
            "project:\n  name: x\n  environment: internal\n"
            "composition:\n  simulator: xcelium\n  coverage: imc\n  ip_types: axi\n"
        )
        ctx, _, _ = ProjectLoader().load(f)
        # No ip-type profile dir → rules are None, but it must not raise
        assert ctx.ip_type_rules is None

    def test_convenience_function_matches_loader(self, project_yaml: Path) -> None:
        ctx_fn, sim_fn, cov_fn = load_project(project_yaml)
        ctx_lo, sim_lo, cov_lo = ProjectLoader().load(project_yaml)
        assert type(ctx_fn) is type(ctx_lo)
        assert type(sim_fn) is type(sim_lo)
        assert type(cov_fn) is type(cov_lo)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_invalid_environment_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "project.yaml"
        f.write_text("project:\n  name: x\n  environment: cloud\ncomposition: {}\n")
        with pytest.raises(ValueError, match="environment"):
            ProjectLoader().load(f)

    def test_yaml_list_not_mapping_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "project.yaml"
        f.write_text("- this\n- is\n- a list\n")
        with pytest.raises(ValueError, match="mapping"):
            ProjectLoader().load(f)

    def test_empty_yaml_uses_defaults(self, tmp_path: Path) -> None:
        f = tmp_path / "project.yaml"
        f.write_text("{}")  # valid YAML mapping but all fields absent
        _, sim, cov = ProjectLoader().load(f)
        assert isinstance(sim, XceliumAdapter)
        assert isinstance(cov, IMCAdapter)


# ---------------------------------------------------------------------------
# Full configuration with profiles
# ---------------------------------------------------------------------------


class TestFullConfig:
    def test_team_rules_populated(self, full_project_yaml: Path, profiles_dir: Path) -> None:
        ctx, _, _ = ProjectLoader(profiles_dir).load(full_project_yaml)
        assert ctx.team_rules == _PROMPT_PATCH

    def test_vip_index_populated(self, full_project_yaml: Path, profiles_dir: Path) -> None:
        ctx, _, _ = ProjectLoader(profiles_dir).load(full_project_yaml)
        assert ctx.vip_index is not None
        assert "axi_burst_seq" in ctx.vip_index

    def test_ip_rules_contain_both_protocols(
        self, full_project_yaml: Path, profiles_dir: Path
    ) -> None:
        ctx, _, _ = ProjectLoader(profiles_dir).load(full_project_yaml)
        assert ctx.ip_type_rules is not None
        assert "AXI" in ctx.ip_type_rules
        assert "PCIE" in ctx.ip_type_rules
        assert "max burst" in ctx.ip_type_rules
        assert "MPS" in ctx.ip_type_rules

    def test_ip_rules_have_section_headers(
        self, full_project_yaml: Path, profiles_dir: Path
    ) -> None:
        ctx, _, _ = ProjectLoader(profiles_dir).load(full_project_yaml)
        assert ctx.ip_type_rules is not None
        assert "## AXI Protocol Rules" in ctx.ip_type_rules
        assert "## PCIE Protocol Rules" in ctx.ip_type_rules

    def test_simulator_config_from_team_yaml(
        self, full_project_yaml: Path, profiles_dir: Path
    ) -> None:
        ctx, _, _ = ProjectLoader(profiles_dir).load(full_project_yaml)
        assert ctx.simulator_config is not None
        assert ctx.simulator_config.binary_path == "/tools/xrun"
        assert ctx.simulator_config.extra_compile_flags == "-v200"
        assert ctx.simulator_config.extra_run_flags == "+UVM_VERBOSITY=UVM_MEDIUM"
        assert ctx.simulator_config.cov_work_dir == "cov_work/"
        assert ctx.simulator_config.collect_coverage is True

    def test_scheduler_config_from_team_yaml(
        self, full_project_yaml: Path, profiles_dir: Path
    ) -> None:
        ctx, _, _ = ProjectLoader(profiles_dir).load(full_project_yaml)
        assert ctx.scheduler_config is not None
        assert ctx.scheduler_config.backend == "lsf"
        assert ctx.scheduler_config.queue == "normal"
        assert ctx.scheduler_config.resource_flags == "-R 'rusage[mem=4096]'"
        assert ctx.scheduler_config.default_wall_time_sec == 3600

    def test_vcs_config_from_team_yaml(self, full_project_yaml: Path, profiles_dir: Path) -> None:
        ctx, _, _ = ProjectLoader(profiles_dir).load(full_project_yaml)
        assert ctx.vcs_config is not None
        assert ctx.vcs_config.backend == "git"
        assert ctx.vcs_config.base_branch == "main"
        assert ctx.vcs_config.author_name == "Test Bot"
        assert ctx.vcs_config.author_email == "bot@example.com"


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    def test_no_profiles_dir_returns_empty_context(self, full_project_yaml: Path) -> None:
        """Even with team/ip_types in project.yaml, missing profiles_dir is fine."""
        ctx, sim, _ = ProjectLoader(profiles_dir=None).load(full_project_yaml)
        assert ctx.team_rules is None
        assert ctx.ip_type_rules is None
        assert isinstance(sim, XceliumAdapter)

    def test_missing_team_yaml_tolerated(self, full_project_yaml: Path, profiles_dir: Path) -> None:
        (profiles_dir / "teams" / "sample_team" / "team.yaml").unlink()
        ctx, sim, _ = ProjectLoader(profiles_dir).load(full_project_yaml)
        assert isinstance(sim, XceliumAdapter)
        assert ctx.scheduler_config is None  # no team.yaml → no scheduler

    def test_missing_prompt_patch_tolerated(
        self, full_project_yaml: Path, profiles_dir: Path
    ) -> None:
        (profiles_dir / "teams" / "sample_team" / "prompt_patch.md").unlink()
        ctx, _, _ = ProjectLoader(profiles_dir).load(full_project_yaml)
        assert ctx.team_rules is None

    def test_missing_vip_index_tolerated(self, full_project_yaml: Path, profiles_dir: Path) -> None:
        (profiles_dir / "teams" / "sample_team" / "vip_index.yaml").unlink()
        ctx, _, _ = ProjectLoader(profiles_dir).load(full_project_yaml)
        assert ctx.vip_index is None

    def test_missing_one_ip_type_skipped(self, full_project_yaml: Path, profiles_dir: Path) -> None:
        shutil.rmtree(profiles_dir / "ip-types" / "pcie")
        ctx, _, _ = ProjectLoader(profiles_dir).load(full_project_yaml)
        assert ctx.ip_type_rules is not None
        assert "AXI" in ctx.ip_type_rules
        assert "PCIE" not in ctx.ip_type_rules

    def test_all_ip_types_missing_gives_none(
        self, full_project_yaml: Path, profiles_dir: Path
    ) -> None:
        shutil.rmtree(profiles_dir / "ip-types")
        ctx, _, _ = ProjectLoader(profiles_dir).load(full_project_yaml)
        assert ctx.ip_type_rules is None

    def test_unknown_simulator_falls_back_to_xcelium(self, tmp_path: Path) -> None:
        f = tmp_path / "project.yaml"
        f.write_text(
            "project:\n  name: x\n  environment: internal\n"
            "composition:\n  simulator: questa\n  coverage: imc\n"
        )
        _, sim, _ = ProjectLoader().load(f)
        assert isinstance(sim, XceliumAdapter)

    def test_unknown_coverage_falls_back_to_imc(self, tmp_path: Path) -> None:
        f = tmp_path / "project.yaml"
        f.write_text(
            "project:\n  name: x\n  environment: internal\n"
            "composition:\n  simulator: xcelium\n  coverage: lcov\n"
        )
        _, _, cov = ProjectLoader().load(f)
        assert isinstance(cov, IMCAdapter)


# ---------------------------------------------------------------------------
# profiles_dir resolution
# ---------------------------------------------------------------------------


class TestProfilesDirResolution:
    def test_explicit_argument_wins(self, full_project_yaml: Path, profiles_dir: Path) -> None:
        loader = ProjectLoader(profiles_dir=profiles_dir)
        ctx, _, _ = loader.load(full_project_yaml)
        assert ctx.team_rules == _PROMPT_PATCH

    def test_env_var_used_when_no_argument(
        self,
        full_project_yaml: Path,
        profiles_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("DV_PROFILES_DIR", str(profiles_dir))
        loader = ProjectLoader()  # no explicit profiles_dir
        ctx, _, _ = loader.load(full_project_yaml)
        assert ctx.team_rules == _PROMPT_PATCH

    def test_project_yaml_profiles_dir_field(self, tmp_path: Path, profiles_dir: Path) -> None:
        """profiles.dir field in project.yaml is the lowest-priority override."""
        f = tmp_path / "project.yaml"
        f.write_text(
            f"project:\n  name: x\n  environment: internal\n"
            f"composition:\n  team: sample_team\n  simulator: xcelium\n  coverage: imc\n"
            f"profiles:\n  dir: {profiles_dir}\n"
        )
        loader = ProjectLoader()  # no explicit profiles_dir, no env var
        ctx, _, _ = loader.load(f)
        assert ctx.team_rules == _PROMPT_PATCH

    def test_explicit_argument_overrides_env_var(
        self,
        tmp_path: Path,
        profiles_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("DV_PROFILES_DIR", "/nonexistent/path")
        loader = ProjectLoader(profiles_dir=profiles_dir)
        f = tmp_path / "project.yaml"
        f.write_text(_FULL_YAML)
        ctx, _, _ = loader.load(f)
        assert ctx.team_rules == _PROMPT_PATCH  # explicit wins


# ---------------------------------------------------------------------------
# ProjectConfig dataclass
# ---------------------------------------------------------------------------


class TestProjectConfigParsing:
    def test_name_and_environment_parsed(self, project_yaml: Path) -> None:
        loader = ProjectLoader()
        raw: Any = {"project": {"name": "my_proj", "environment": "external"}, "composition": {}}
        config = loader._parse_project_yaml(raw)
        assert config.name == "my_proj"
        assert config.environment == "external"

    def test_composition_parsed(self, project_yaml: Path) -> None:
        loader = ProjectLoader()
        raw: Any = {
            "project": {"name": "x", "environment": "internal"},
            "composition": {
                "team": "team_io",
                "ip_types": ["axi", "pcie"],
                "simulator": "ghdl",
                "coverage": "pyuvm",
            },
        }
        config = loader._parse_project_yaml(raw)
        assert config.team == "team_io"
        assert config.ip_types == ["axi", "pcie"]
        assert config.simulator == "ghdl"
        assert config.coverage == "pyuvm"

    def test_null_team_returns_none(self, project_yaml: Path) -> None:
        loader = ProjectLoader()
        raw: Any = {
            "project": {"name": "x", "environment": "internal"},
            "composition": {"team": None},
        }
        config = loader._parse_project_yaml(raw)
        assert config.team is None
