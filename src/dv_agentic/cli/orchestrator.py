# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""CLI entrypoint for OrchestratorAgent.

Sub-agents are wired up automatically based on ``--simulator`` and
``--adapter`` flags.  The LLM client is selected from environment variables
(see :mod:`~dv_agentic.cli._factory`).

When ``--project-config`` is provided, the three-layer configuration system
is activated: team profile, IP-type rules, and adapter settings are all
loaded from ``.agent/project.yaml`` and the profiles directory, and injected
into every agent's system prompt via :class:`~dv_agentic.prompts.prompt_loader.PromptLoader`.

Examples:
    .. code-block:: shell

        # Minimal: no profile injection
        python3 -m dv_agentic.cli.orchestrator \\
            --input-file task.txt \\
            --simulator xcelium \\
            --adapter imc

        # Full: load team + IP profiles from project.yaml
        python3 -m dv_agentic.cli.orchestrator \\
            --project-config .agent/project.yaml \\
            --profiles-dir ../team-profiles \\
            --input-file task.txt
"""

import argparse
import asyncio
from typing import Any

from ._factory import make_llm
from ._helpers import exit_with_error, read_input


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser for the Orchestrator CLI.

    Returns:
        The configured ArgumentParser instance.
    """
    p = argparse.ArgumentParser(
        prog="python3 -m dv_agentic.cli.orchestrator",
        description="Route a task across the full agent pipeline.",
    )
    p.add_argument(
        "--input-file",
        "-i",
        default="-",
        metavar="PATH",
        help="Task description file, or '-' for stdin (default: stdin).",
    )

    # --- Three-layer config ---
    p.add_argument(
        "--project-config",
        default=None,
        metavar="PATH",
        help=(
            "Path to .agent/project.yaml.  When provided, loads team profile, "
            "IP-type rules, and adapter settings, injecting them into all agent "
            "prompts.  Overrides --simulator and --adapter when set."
        ),
    )
    p.add_argument(
        "--profiles-dir",
        default=None,
        metavar="PATH",
        help=(
            "Root of the org profile repository (e.g. ../team-profiles/). "
            "Falls back to DV_PROFILES_DIR env var.  Only used with --project-config."
        ),
    )

    # --- Direct adapter flags (used when --project-config is absent) ---
    p.add_argument(
        "--simulator",
        default="xcelium",
        choices=["xcelium", "ghdl", "icarus", "verilator"],
        help="Simulator adapter for SimController (default: xcelium).",
    )
    p.add_argument(
        "--adapter",
        default="imc",
        choices=["imc", "pyuvm"],
        help="Coverage adapter for CoverageAnalyst (default: imc).",
    )
    p.add_argument(
        "--budget",
        type=int,
        default=10,
        metavar="N",
        help="Max orchestration cycles (default: 10).",
    )
    p.add_argument(
        "--sub-budget",
        type=int,
        default=5,
        metavar="N",
        help="Budget for each sub-agent (default: 5).",
    )
    p.add_argument("--model", default=None, metavar="NAME", help="Override the LLM model name.")

    p.add_argument(
        "--coverage-threshold",
        type=float,
        default=90.0,
        metavar="PCT",
        help="Coverage threshold for CoverageAnalyst (default: 90.0).",
    )
    p.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.75,
        metavar="FLOAT",
        help="Confidence threshold for BugClassifier (default: 0.75).",
    )
    return p


def _build_sub_agents(
    args: argparse.Namespace,
    llm: Any,
    project_ctx: Any = None,
) -> dict[str, Any]:
    """Instantiate LLM-powered sub-agents and return them keyed by agent name.

    The three deterministic services (SimControllerService, LogAnalyzerService,
    CoverageAnalystService) are no longer sub-agents; they are wired directly
    into OrchestratorAgent via the ``simulator``, ``coverage``, and
    ``coverage_threshold`` constructor parameters.

    Args:
        args: Parsed command-line arguments.
        llm: The LLM client to share among sub-agents.
        project_ctx: Optional :class:`~dv_agentic.prompts.context.ProjectContext`
            loaded from ``project.yaml``.  When provided, injected into every
            LLM-powered agent's :class:`~dv_agentic.prompts.prompt_loader.PromptLoader`.

    Returns:
        A dictionary mapping agent names to agent instances (4 entries:
        ``code_generator``, ``bug_classifier``, ``spec_analyst``, ``reporter``).
    """
    from dv_agentic.agents.base import AgentConfig
    from dv_agentic.agents.bug_classifier import BugClassifierAgent
    from dv_agentic.agents.code_generator import DEFAULT_TB_ALLOWED_DIRS, CodeGeneratorAgent
    from dv_agentic.agents.reporter import ReporterAgent
    from dv_agentic.agents.spec_analyst import SpecAnalystAgent

    b = args.sub_budget

    return {
        "code_generator": CodeGeneratorAgent(
            config=AgentConfig(name="code_generator", budget=b),
            llm=llm,
            workspace_dir=".",
            project_config=project_ctx,
            allowed_dirs=DEFAULT_TB_ALLOWED_DIRS,
        ),
        "bug_classifier": BugClassifierAgent(
            config=AgentConfig(name="bug_classifier", budget=b),
            llm=llm,
            confidence_threshold=args.confidence_threshold,
            project_config=project_ctx,
        ),
        "spec_analyst": SpecAnalystAgent(
            config=AgentConfig(name="spec_analyst", budget=b),
            llm=llm,
            project_config=project_ctx,
        ),
        "reporter": ReporterAgent(
            config=AgentConfig(name="reporter", budget=b),
            llm=llm,
            project_config=project_ctx,
        ),
    }


def main() -> None:
    """Main execution block of the Orchestrator CLI."""
    args = _build_parser().parse_args()

    try:
        task_input = read_input(args.input_file)
    except OSError as exc:
        exit_with_error(str(exc))

    # --- Three-layer config ---
    project_ctx = None
    project_simulator = None
    project_coverage = None
    if args.project_config:
        try:
            from dv_agentic.config import load_project

            project_ctx, project_simulator, project_coverage = load_project(
                project_yaml=args.project_config,
                profiles_dir=args.profiles_dir,
            )
        except (FileNotFoundError, ValueError) as exc:
            exit_with_error(f"Failed to load project config: {exc}")

    try:
        from dv_agentic.agents.base import AgentConfig
        from dv_agentic.agents.orchestrator import OrchestratorAgent
        from dv_agentic.tools.adapters import get_coverage_adapter, get_simulator_adapter

        llm = make_llm(model=args.model)
        sub_agents = _build_sub_agents(args, llm, project_ctx=project_ctx)

        agent = OrchestratorAgent(
            config=AgentConfig(name="orchestrator", budget=args.budget),
            llm=llm,
            sub_agents=sub_agents,
            project_config=project_ctx,
            simulator=project_simulator or get_simulator_adapter(args.simulator),
            coverage=project_coverage or get_coverage_adapter(args.adapter),
            coverage_threshold=args.coverage_threshold,
            sim_max_runs=args.sub_budget,
        )
        result = asyncio.run(agent.run(task_input))
        print(result)  # noqa: T201
    except Exception as exc:
        exit_with_error(str(exc))


if __name__ == "__main__":
    main()
