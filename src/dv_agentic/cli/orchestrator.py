"""CLI entrypoint for OrchestratorAgent.

Sub-agents are wired up automatically based on ``--simulator`` and
``--adapter`` flags.  The LLM client is selected from environment variables
(see :mod:`~dv_agentic.cli._factory`).

Examples:
    .. code-block:: shell

        python3 -m dv_agentic.cli.orchestrator \
            --input-file task.txt \
            --simulator xcelium \
            --adapter imc
"""

import argparse
import asyncio
from typing import Any

from ._factory import make_llm
from ._helpers import die, read_input


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


def _build_sub_agents(args: argparse.Namespace, llm: Any) -> dict[str, Any]:
    """Instantiate all sub-agents and return them keyed by agent name.

    Args:
        args: Parsed command-line arguments.
        llm: The LLM client to share among sub-agents.

    Returns:
        A dictionary mapping agent names to agent instances.
    """
    from dv_agentic.agents.base import AgentConfig
    from dv_agentic.agents.bug_classifier import BugClassifierAgent
    from dv_agentic.agents.code_generator import CodeGeneratorAgent
    from dv_agentic.agents.coverage_analyst import CoverageAnalystAgent
    from dv_agentic.agents.log_analyzer import LogAnalyzerAgent
    from dv_agentic.agents.reporter import ReporterAgent
    from dv_agentic.agents.sim_controller import SimControllerAgent
    from dv_agentic.agents.spec_analyst import SpecAnalystAgent
    from dv_agentic.tools.adapters import get_coverage_adapter, get_simulator_adapter

    b = args.sub_budget

    simulator = get_simulator_adapter(args.simulator)
    coverage = get_coverage_adapter(args.adapter)

    return {
        "log_analyzer": LogAnalyzerAgent(config=AgentConfig(name="log_analyzer", budget=b)),
        "coverage_analyst": CoverageAnalystAgent(
            config=AgentConfig(name="coverage_analyst", budget=b),
            coverage=coverage,
            threshold=args.coverage_threshold,
        ),
        "sim_controller": SimControllerAgent(
            config=AgentConfig(name="sim_controller", budget=b),
            simulator=simulator,
        ),
        "code_generator": CodeGeneratorAgent(
            config=AgentConfig(name="code_generator", budget=b),
            llm=llm,
            workspace_dir=".",
        ),
        "bug_classifier": BugClassifierAgent(
            config=AgentConfig(name="bug_classifier", budget=b),
            llm=llm,
            confidence_threshold=args.confidence_threshold,
        ),
        "spec_analyst": SpecAnalystAgent(
            config=AgentConfig(name="spec_analyst", budget=b),
            llm=llm,
        ),
        "reporter": ReporterAgent(
            config=AgentConfig(name="reporter", budget=b),
            llm=llm,
        ),
    }


def main() -> None:
    """Main execution block of the Orchestrator CLI."""
    args = _build_parser().parse_args()

    try:
        task_input = read_input(args.input_file)
    except OSError as exc:
        die(str(exc))

    try:
        from dv_agentic.agents.base import AgentConfig
        from dv_agentic.agents.orchestrator import OrchestratorAgent

        llm = make_llm(model=args.model)
        sub_agents = _build_sub_agents(args, llm)

        agent = OrchestratorAgent(
            config=AgentConfig(name="orchestrator", budget=args.budget),
            llm=llm,
            sub_agents=sub_agents,
        )
        result = asyncio.run(agent.run(task_input))
        print(result)  # noqa: T201
    except Exception as exc:
        die(str(exc))


if __name__ == "__main__":
    main()
