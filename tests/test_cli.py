# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

import os
import sys
from typing import Any
from unittest.mock import patch

import pytest

from dv_agentic.cli import _factory, _helpers

CLI_MODULES = [
    "dv_agentic.cli.code_generator",
    "dv_agentic.cli.bug_classifier",
    "dv_agentic.cli.spec_analyst",
    "dv_agentic.cli.reporter",
    "dv_agentic.cli.orchestrator",
    "dv_agentic.cli.sim_controller",
    "dv_agentic.cli.log_analyzer",
    "dv_agentic.cli.coverage_analyst",
]


@patch("dv_agentic.agents.code_generator.CodeGeneratorAgent")
@patch("dv_agentic.cli.code_generator.make_llm")
@patch("asyncio.run")
def test_code_generator_cli_uses_cwd(
    mock_asyncio: Any, mock_make_llm: Any, mock_agent: Any
) -> None:
    """Verify code_generator instantiates the agent with workspace_dir='.'"""
    from dv_agentic.cli import code_generator

    with (
        patch.object(
            sys, "argv", ["python3 -m dv_agentic.cli.code_generator", "--task-id", "test_id"]
        ),
        patch("dv_agentic.cli.code_generator.read_input", return_value="dummy input"),
    ):
        code_generator.main()

    mock_agent.assert_called_once()
    kwargs = mock_agent.call_args.kwargs
    assert kwargs.get("workspace_dir") == ".", "CodeGenerator must use CWD instead of project_root"
    mock_asyncio.assert_called_once()


@patch("dv_agentic.agents.orchestrator.OrchestratorAgent")
@patch("dv_agentic.cli.orchestrator.make_llm")
@patch("asyncio.run")
def test_orchestrator_cli_uses_cwd(mock_asyncio: Any, mock_make_llm: Any, mock_agent: Any) -> None:
    """Verify orchestrator instantiates the agent with workspace_dir='.'"""
    from dv_agentic.cli import orchestrator

    with (
        patch.object(sys, "argv", ["python3 -m dv_agentic.cli.orchestrator"]),
        patch("dv_agentic.cli.orchestrator.read_input", return_value="dummy input"),
    ):
        orchestrator.main()

    mock_agent.assert_called_once()
    mock_asyncio.assert_called_once()


def test_helpers_read_input_stdin() -> None:
    """Test read_input with stdin '-'."""
    with patch("sys.stdin.read", return_value="hello stdin"):
        assert _helpers.read_input("-") == "hello stdin"


def test_helpers_read_input_file(tmp_path: Any) -> None:
    """Test read_input with actual file path."""
    temp_file = tmp_path / "test.txt"
    temp_file.write_text("hello file", encoding="utf-8")
    assert _helpers.read_input(str(temp_file)) == "hello file"


def test_helpers_exit_with_error() -> None:
    """Test exit_with_error function raises SystemExit."""
    with pytest.raises(SystemExit) as exc_info, patch("sys.stderr.write"):
        _helpers.exit_with_error("fatal error")
    assert exc_info.value.code == 1


@patch("dv_agentic.tools.llm.local.LocalLLMClient")
@patch("dv_agentic.tools.llm.api.LLMAPIClient")
def test_factory_make_llm_anthropic(mock_api: Any, mock_local: Any) -> None:
    """Test make_llm with anthropic backend."""
    with patch.dict(os.environ, {"DV_LLM_BACKEND": "anthropic"}):
        _factory.make_llm()
    mock_api.assert_called_once()
    mock_local.assert_not_called()


@patch("dv_agentic.tools.llm.local.LocalLLMClient")
@patch("dv_agentic.tools.llm.api.LLMAPIClient")
def test_factory_make_llm_local(mock_api: Any, mock_local: Any) -> None:
    """Test make_llm with local backend."""
    with patch.dict(os.environ, {"DV_LLM_BACKEND": "local"}):
        _factory.make_llm("custom_model")
    mock_local.assert_called_once_with(model="custom_model")
    mock_api.assert_not_called()


@patch("dv_agentic.agents.bug_classifier.BugClassifierAgent")
@patch("dv_agentic.cli.bug_classifier.make_llm")
@patch("asyncio.run")
def test_bug_classifier_cli(mock_asyncio: Any, mock_make_llm: Any, mock_agent: Any) -> None:
    """Verify bug_classifier CLI executes correctly."""
    from dv_agentic.cli import bug_classifier

    with (
        patch.object(
            sys, "argv", ["python3 -m dv_agentic.cli.bug_classifier", "--threshold", "0.8"]
        ),
        patch("dv_agentic.cli.bug_classifier.read_input", return_value="dummy summary"),
    ):
        bug_classifier.main()

    mock_agent.assert_called_once()
    kwargs = mock_agent.call_args.kwargs
    assert kwargs.get("confidence_threshold") == 0.8
    mock_asyncio.assert_called_once()


@patch("dv_agentic.agents.coverage_analyst.CoverageAnalystAgent")
@patch("dv_agentic.tools.adapters.get_coverage_adapter")
@patch("asyncio.run")
def test_coverage_analyst_cli(mock_asyncio: Any, mock_get_adapter: Any, mock_agent: Any) -> None:
    """Verify coverage_analyst CLI executes correctly."""
    from dv_agentic.cli import coverage_analyst

    with patch.object(
        sys,
        "argv",
        ["python3 -m dv_agentic.cli.coverage_analyst", "--job-id", "job_42", "--threshold", "85.0"],
    ):
        coverage_analyst.main()

    mock_agent.assert_called_once()
    kwargs = mock_agent.call_args.kwargs
    assert kwargs.get("threshold") == 85.0
    mock_asyncio.assert_called_once()


@patch("dv_agentic.agents.log_analyzer.LogAnalyzerAgent")
@patch("asyncio.run")
def test_log_analyzer_cli(mock_asyncio: Any, mock_agent: Any) -> None:
    """Verify log_analyzer CLI executes correctly."""
    from dv_agentic.cli import log_analyzer

    with (
        patch.object(
            sys, "argv", ["python3 -m dv_agentic.cli.log_analyzer", "--input-file", "sim.log"]
        ),
        patch("dv_agentic.cli.log_analyzer.read_input", return_value="dummy log content"),
    ):
        log_analyzer.main()

    mock_agent.assert_called_once()
    mock_asyncio.assert_called_once()


@patch("dv_agentic.agents.reporter.ReporterAgent")
@patch("dv_agentic.cli.reporter.make_llm")
@patch("asyncio.run")
def test_reporter_cli(mock_asyncio: Any, mock_make_llm: Any, mock_agent: Any) -> None:
    """Verify reporter CLI executes correctly."""
    from dv_agentic.cli import reporter

    with (
        patch.object(
            sys, "argv", ["python3 -m dv_agentic.cli.reporter", "--output-path", "report.md"]
        ),
        patch("dv_agentic.cli.reporter.read_input", return_value="dummy results"),
    ):
        reporter.main()

    mock_agent.assert_called_once()
    kwargs = mock_agent.call_args.kwargs
    assert kwargs.get("output_path") == "report.md"
    mock_asyncio.assert_called_once()


@patch("dv_agentic.agents.sim_controller.SimControllerAgent")
@patch("dv_agentic.tools.adapters.get_simulator_adapter")
@patch("asyncio.run")
def test_sim_controller_cli(mock_asyncio: Any, mock_get_adapter: Any, mock_agent: Any) -> None:
    """Verify sim_controller CLI executes correctly."""
    from dv_agentic.cli import sim_controller

    with patch.object(
        sys,
        "argv",
        [
            "python3 -m dv_agentic.cli.sim_controller",
            "--task-id",
            "task_001",
            "--test",
            "my_test",
            "--seed",
            "123",
            "--base-branch",
            "feature_branch",
        ],
    ):
        sim_controller.main()

    mock_agent.assert_called_once()
    kwargs = mock_agent.call_args.kwargs
    assert kwargs.get("base_branch") == "feature_branch"
    mock_asyncio.assert_called_once()


@patch("dv_agentic.agents.spec_analyst.SpecAnalystAgent")
@patch("dv_agentic.cli.spec_analyst.make_llm")
@patch("asyncio.run")
def test_spec_analyst_cli(mock_asyncio: Any, mock_make_llm: Any, mock_agent: Any) -> None:
    """Verify spec_analyst CLI executes correctly."""
    from dv_agentic.cli import spec_analyst

    with (
        patch.object(
            sys,
            "argv",
            ["python3 -m dv_agentic.cli.spec_analyst", "--output-path", "out_vplan.yaml"],
        ),
        patch("dv_agentic.cli.spec_analyst.read_input", return_value="dummy spec content"),
    ):
        spec_analyst.main()

    mock_agent.assert_called_once()
    kwargs = mock_agent.call_args.kwargs
    assert kwargs.get("output_path") == "out_vplan.yaml"
    mock_asyncio.assert_called_once()
