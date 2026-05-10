"""Path validation tests for CodeGeneratorAgent.

These tests cover the TB boundary enforcement added to _validate_path()
and _write_files(). All existing tests remain unaffected because they use
agents with allowed_dirs=None (no restriction).
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from dv_agentic.agents.base import AgentConfig
from dv_agentic.agents.code_generator import (
    DEFAULT_TB_ALLOWED_DIRS,
    CodeGeneratorAgent,
    FileSpec,
)


def _make_agent_with_whitelist(
    workspace_dir: str,
    allowed_dirs: frozenset[str] | None = DEFAULT_TB_ALLOWED_DIRS,
    responses: list[str] | None = None,
) -> CodeGeneratorAgent:
    llm = MagicMock()
    llm.complete = AsyncMock(side_effect=responses or [])
    return CodeGeneratorAgent(
        config=AgentConfig(name="code_gen", budget=3),
        llm=llm,
        workspace_dir=workspace_dir,
        allowed_dirs=allowed_dirs,
    )


# ---------------------------------------------------------------------------
# _validate_path — unit tests (no filesystem needed)
# ---------------------------------------------------------------------------


class TestValidatePath:
    """_validate_path() is called before any write; test it directly."""

    def test_traversal_always_blocked(self, tmp_path: Path) -> None:
        """.. must be rejected even when allowed_dirs is None."""
        agent = _make_agent_with_whitelist(str(tmp_path), allowed_dirs=None)
        with pytest.raises(ValueError, match="traversal"):
            agent._validate_path("../rtl/dut.sv")

    def test_traversal_mid_path_blocked(self, tmp_path: Path) -> None:
        agent = _make_agent_with_whitelist(str(tmp_path), allowed_dirs=None)
        with pytest.raises(ValueError, match="traversal"):
            agent._validate_path("tb/../../rtl/dut.sv")

    def test_rtl_dir_blocked_when_whitelist_set(self, tmp_path: Path) -> None:
        agent = _make_agent_with_whitelist(str(tmp_path))
        with pytest.raises(ValueError, match="read-only"):
            agent._validate_path("rtl/dut.sv")

    def test_src_dir_blocked_when_whitelist_set(self, tmp_path: Path) -> None:
        agent = _make_agent_with_whitelist(str(tmp_path))
        with pytest.raises(ValueError, match="read-only"):
            agent._validate_path("src/top.sv")

    def test_design_dir_blocked_when_whitelist_set(self, tmp_path: Path) -> None:
        agent = _make_agent_with_whitelist(str(tmp_path))
        with pytest.raises(ValueError, match="outside"):
            agent._validate_path("design/cpu.sv")

    def test_tb_dir_allowed(self, tmp_path: Path) -> None:
        agent = _make_agent_with_whitelist(str(tmp_path))
        agent._validate_path("tb/sequences/axi_burst_seq.sv")  # must not raise

    def test_tests_dir_allowed(self, tmp_path: Path) -> None:
        agent = _make_agent_with_whitelist(str(tmp_path))
        agent._validate_path("tests/axi_write_test.sv")

    def test_env_dir_allowed(self, tmp_path: Path) -> None:
        agent = _make_agent_with_whitelist(str(tmp_path))
        agent._validate_path("env/axi_env.sv")

    def test_all_default_tb_dirs_allowed(self, tmp_path: Path) -> None:
        agent = _make_agent_with_whitelist(str(tmp_path))
        for d in DEFAULT_TB_ALLOWED_DIRS:
            agent._validate_path(f"{d}/some_file.sv")  # none should raise

    def test_flat_path_allowed_even_with_whitelist(self, tmp_path: Path) -> None:
        """A file directly in workspace root has no top-level dir to check."""
        agent = _make_agent_with_whitelist(str(tmp_path))
        agent._validate_path("some_seq.sv")  # must not raise

    def test_no_whitelist_allows_any_dir(self, tmp_path: Path) -> None:
        """allowed_dirs=None means no directory restriction (backward compat)."""
        agent = _make_agent_with_whitelist(str(tmp_path), allowed_dirs=None)
        # These would be blocked with a whitelist but must pass here
        agent._validate_path("rtl/dut.sv")
        agent._validate_path("design/cpu.sv")
        agent._validate_path("custom_dir/file.sv")


# ---------------------------------------------------------------------------
# _write_files — integration (hits filesystem)
# ---------------------------------------------------------------------------


class TestWriteFilesEnforcement:
    def test_rtl_path_raises_before_write(self, tmp_path: Path) -> None:
        agent = _make_agent_with_whitelist(str(tmp_path))
        specs = [FileSpec(path="rtl/dut.sv", content="module dut(); endmodule")]
        with pytest.raises(ValueError, match="read-only"):
            agent._write_files(specs, str(tmp_path))
        # Nothing should have been written
        assert not list(tmp_path.rglob("*.sv"))

    def test_traversal_raises_before_write(self, tmp_path: Path) -> None:
        agent = _make_agent_with_whitelist(str(tmp_path), allowed_dirs=None)
        specs = [FileSpec(path="../escaped.sv", content="oops")]
        with pytest.raises(ValueError, match="traversal"):
            agent._write_files(specs, str(tmp_path))

    def test_mixed_specs_atomic_on_first_bad_path(self, tmp_path: Path) -> None:
        """If ANY path is invalid, we raise before writing anything.

        _validate_path is called per-spec in order, so the first bad path
        stops execution before that file (and any subsequent files) is written.
        """
        agent = _make_agent_with_whitelist(str(tmp_path))
        (tmp_path / "tb").mkdir()
        specs = [
            FileSpec(path="rtl/dut.sv", content="bad"),  # blocked first
            FileSpec(path="tb/seq.sv", content="good"),
        ]
        with pytest.raises(ValueError, match="read-only"):
            agent._write_files(specs, str(tmp_path))
        assert not list(tmp_path.rglob("*.sv"))

    def test_valid_tb_path_written_successfully(self, tmp_path: Path) -> None:
        agent = _make_agent_with_whitelist(str(tmp_path))
        specs = [FileSpec(path="tb/sequences/seq.sv", content="class seq; endclass")]
        written = agent._write_files(specs, str(tmp_path))
        assert len(written) == 1
        assert (tmp_path / "tb" / "sequences" / "seq.sv").exists()

    def test_no_whitelist_allows_any_write(self, tmp_path: Path) -> None:
        """Backward compatibility: allowed_dirs=None disables the check."""
        agent = _make_agent_with_whitelist(str(tmp_path), allowed_dirs=None)
        specs = [FileSpec(path="rtl/dut.sv", content="module dut(); endmodule")]
        written = agent._write_files(specs, str(tmp_path))
        assert len(written) == 1


# ---------------------------------------------------------------------------
# DEFAULT_TB_ALLOWED_DIRS — sanity checks on the constant itself
# ---------------------------------------------------------------------------


class TestDefaultTbAllowedDirs:
    def test_is_frozenset(self) -> None:
        assert isinstance(DEFAULT_TB_ALLOWED_DIRS, frozenset)

    def test_contains_expected_dirs(self) -> None:
        for d in ("tb", "tests", "env", "sequences", "agents", "scoreboards"):
            assert d in DEFAULT_TB_ALLOWED_DIRS, f"'{d}' missing from DEFAULT_TB_ALLOWED_DIRS"

    def test_does_not_contain_rtl_dirs(self) -> None:
        for d in ("rtl", "src", "design", "dut", "hdl"):
            assert d not in DEFAULT_TB_ALLOWED_DIRS, f"'{d}' must not be in DEFAULT_TB_ALLOWED_DIRS"


# ---------------------------------------------------------------------------
# End-to-end: LLM returns RTL path → agent raises before writing
# ---------------------------------------------------------------------------

_RTL_PATH_RESPONSE = """\
### Summary
Generated DUT fix — targets back-pressure bin.

### Changed Files
- `rtl/axi_slave.sv` — fixed back-pressure handling

### Code
```sv
// file: rtl/axi_slave.sv
module axi_slave();
endmodule
```

### Open Questions
None.

### Compile Confidence
HIGH — identifiers resolved.
"""


class TestEndToEndRTLRejection:
    def test_high_confidence_with_rtl_path_raises(self, tmp_path: Path) -> None:
        """Even HIGH confidence must not write to RTL directories."""
        agent = _make_agent_with_whitelist(
            str(tmp_path),
            responses=[_RTL_PATH_RESPONSE],
        )
        with pytest.raises(ValueError, match="read-only"):
            asyncio.run(agent.run("Fix the back-pressure bug"))

    def test_error_message_names_the_bad_path(self, tmp_path: Path) -> None:
        agent = _make_agent_with_whitelist(
            str(tmp_path),
            responses=[_RTL_PATH_RESPONSE],
        )
        with pytest.raises(ValueError, match="rtl"):
            asyncio.run(agent.run("Fix"))
