# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

from pathlib import Path

import pytest

from dv_agentic.prompts.context import (
    ProjectContext,
    SchedulerConfig,
    SessionState,
    SimulatorConfig,
    VCSConfig,
)
from dv_agentic.prompts.prompt_loader import PromptLoader


def test_prompt_loader_init_default() -> None:
    """Test initialization with default path logic."""
    # We use a patch to simulate the __file__ location if needed,
    # but here we just verify it doesn't crash if the environment is sane.
    try:
        loader = PromptLoader()
        assert loader.prompts_dir.name == "prompts"
    except RuntimeError as e:
        if "PromptLoader default path assumption broken" in str(e):
            pytest.skip("Default path assumption broken in this environment")
        else:
            raise


def test_prompt_loader_init_custom(tmp_path: Path) -> None:
    """Test initialization with a custom prompts directory."""
    loader = PromptLoader(prompts_dir=tmp_path)
    assert loader.prompts_dir == tmp_path


def test_prompt_loader_load_not_found(tmp_path: Path) -> None:
    """Test FileNotFoundError when a prompt template is missing."""
    loader = PromptLoader(prompts_dir=tmp_path)
    msg = "Prompt template for 'non_existent_agent' not found"
    with pytest.raises(FileNotFoundError, match=msg):
        loader.load("non_existent_agent")


def test_prompt_loader_load_success(tmp_path: Path) -> None:
    """Test successful loading and basic enrichment."""
    prompt_file = tmp_path / "test_agent.tmpl.md"
    prompt_file.write_text("Hello {{NAME}}!", encoding="utf-8")

    loader = PromptLoader(prompts_dir=tmp_path)
    # NAME is missing from context, should be empty string in mixed line
    result = loader.load("test_agent")
    assert result == "Hello !"


def test_gather_context_empty() -> None:
    """Test context gathering when no config or session is provided."""
    loader = PromptLoader(prompts_dir=".")
    assert loader._gather_context() == {}


def test_gather_context_full() -> None:
    """Test context gathering with full project and session state."""
    project_config = ProjectContext(
        team_rules="Rule 1",
        ip_type_rules="IP Rule",
        vip_index="Index",
        vplan_summary="Summary",
        known_error_patterns="Errors",
        known_rtl_bugs="Bugs",
        simulator_config=SimulatorConfig(
            name="xcelium",
            binary_path="/path/to/xrun",
            extra_compile_flags="-v",
            extra_run_flags="+seed=1",
        ),
        scheduler_config=SchedulerConfig(
            backend="lsf", queue="normal", resource_flags="-R 'mem=4G'"
        ),
        vcs_config=VCSConfig(
            backend="git",
            base_branch="develop",
            author_name="John Doe",
            author_email="john@example.com",
        ),
    )
    session = SessionState(task_id="TASK-123", iteration=1, budget_remaining=100)

    loader = PromptLoader(prompts_dir=".", project_config=project_config, session=session)
    context = loader._gather_context()

    assert context["TEAM_RULES"] == "Rule 1"
    assert "Compile flags: -v" in context["SIMULATOR_CONFIG"]
    assert "Run flags: +seed=1" in context["SIMULATOR_CONFIG"]
    assert "Resource flags: -R 'mem=4G'" in context["SCHEDULER_CONFIG"]
    assert "Author: John Doe <john@example.com>" in context["VCS_CONFIG"]
    assert "Task: TASK-123" in context["SESSION_STATE"]


@pytest.mark.parametrize(
    "template,context,expected",
    [
        # Basic replacement
        ("Hello {{USER}}!", {"USER": "Alice"}, "Hello Alice!"),
        # Mixed line with missing context
        ("User {{USER}} has id {{ID}}", {"USER": "Alice"}, "User Alice has id"),
        # Blank line compression
        ("Line 1\n\n\n\nLine 2", {}, "Line 1\n\nLine 2"),
        # Indentation preservation (at start of string, strip() will remove it,
        # so we check internal)
        ("Header\n    {{INDENTED}}\nFooter", {"INDENTED": "Value"}, "Header\n    Value\nFooter"),
    ],
    ids=["basic", "mixed-missing", "compression", "indentation"],
)
def test_inject_scenarios(template: str, context: dict[str, str], expected: str) -> None:
    """Test various injection scenarios including edge cases."""
    loader = PromptLoader(prompts_dir=".")
    assert loader._inject(template, context) == expected


def test_inject_pure_placeholder_line_logic() -> None:
    """Test specific logic for lines containing only a placeholder."""
    loader = PromptLoader(prompts_dir=".")

    # 1. Removal when context is missing
    template = "Line 1\n{{MISSING}}\nLine 2"
    assert loader._inject(template, {}) == "Line 1\nLine 2"

    # 2. Replacement (preserving indentation) when context exists
    template = "Line 1\n  {{PRESENT}}\nLine 2"
    result = loader._inject(template, {"PRESENT": "Value"})
    assert "  Value" in result
    assert result.splitlines()[1] == "  Value"


def test_inject_multiple_placeholders_per_line() -> None:
    """Test lines with multiple placeholders."""
    loader = PromptLoader(prompts_dir=".")
    template = "{{A}} + {{B}} = {{C}}"
    context = {"A": "1", "B": "2", "C": "3"}
    assert loader._inject(template, context) == "1 + 2 = 3"
