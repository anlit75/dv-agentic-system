"""CLI entrypoint for SimControllerAgent.

Examples:
    .. code-block:: shell

        python3 -m dv_agentic.cli.sim_controller \
            --task-id cov_fix_001 \
            --test axi_burst_test \
            --seed 42 \
            --simulator xcelium
"""

import argparse
import asyncio

from ._helpers import exit_with_error


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser for the SimController CLI.

    Returns:
        The configured ArgumentParser instance.
    """
    p = argparse.ArgumentParser(
        prog="python3 -m dv_agentic.cli.sim_controller",
        description="Compile and run a simulation task within a git branch.",
    )
    p.add_argument(
        "--task-id",
        required=True,
        metavar="ID",
        help="Unique task identifier (used for branch name).",
    )
    p.add_argument(
        "--test", required=True, metavar="NAME", help="UVM test name or cocotb test module."
    )
    p.add_argument("--seed", type=int, required=True, help="Random seed for the simulation.")
    p.add_argument(
        "--simulator",
        default="xcelium",
        choices=["xcelium", "ghdl", "icarus", "verilator"],
        help="Simulator adapter to use (default: xcelium).",
    )
    p.add_argument(
        "--top", default="top", metavar="MODULE", help="Top-level HDL module name (default: top)."
    )
    p.add_argument("--debug", action="store_true", help="Enable debug mode (waveform dumping).")
    p.add_argument(
        "--budget",
        type=int,
        default=10,
        metavar="N",
        help="Maximum simulation retry count (default: 10).",
    )
    p.add_argument(
        "--file-list",
        nargs="*",
        default=[],
        metavar="FILE",
        help="Source files to compile (optional).",
    )
    p.add_argument(
        "--base-branch",
        default="main",
        metavar="BRANCH",
        help="Git branch to fork from (default: main).",
    )
    return p


def main() -> None:
    """Main execution block of the SimController CLI."""
    args = _build_parser().parse_args()

    try:
        from dv_agentic.agents.base import AgentConfig
        from dv_agentic.agents.sim_controller import SimControllerAgent
        from dv_agentic.tools.adapters import get_simulator_adapter
        from dv_agentic.tools.models import SimTask

        simulator = get_simulator_adapter(args.simulator)
        agent = SimControllerAgent(
            config=AgentConfig(name="sim_controller", budget=args.budget),
            simulator=simulator,
            base_branch=args.base_branch,
        )
        task = SimTask(
            task_id=args.task_id,
            test=args.test,
            seed=args.seed,
            file_list=args.file_list,
            top=args.top,
            debug=args.debug,
        )
        result = asyncio.run(agent.run(task))
        print(result)  # noqa: T201
    except Exception as exc:
        exit_with_error(str(exc))


if __name__ == "__main__":
    main()
