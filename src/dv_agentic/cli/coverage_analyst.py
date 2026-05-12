# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""CLI entrypoint for CoverageAnalystAgent.

Examples:
    .. code-block:: shell

        python3 -m dv_agentic.cli.coverage_analyst \
            --job-id my_test_42 \
            --adapter imc \
            --threshold 90.0
"""

import argparse
import asyncio

from ._helpers import exit_with_error


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser for the CoverageAnalyst CLI.

    Returns:
        The configured ArgumentParser instance.
    """
    p = argparse.ArgumentParser(
        prog="python3 -m dv_agentic.cli.coverage_analyst",
        description="Retrieve and evaluate coverage for a simulation job.",
    )
    p.add_argument("--job-id", required=True, metavar="ID", help="Simulation job identifier.")
    p.add_argument(
        "--adapter",
        default="imc",
        choices=["imc", "pyuvm"],
        help="Coverage tool adapter (default: imc).",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=90.0,
        metavar="PCT",
        help="Minimum acceptable coverage %% (default: 90.0).",
    )
    return p


def main() -> None:
    """Main execution block of the CoverageAnalyst CLI."""
    args = _build_parser().parse_args()

    try:
        from dv_agentic.agents.base import AgentConfig
        from dv_agentic.agents.coverage_analyst import CoverageAnalystAgent
        from dv_agentic.tools.adapters import get_coverage_adapter

        coverage = get_coverage_adapter(args.adapter)
        agent = CoverageAnalystAgent(
            config=AgentConfig(name="coverage_analyst"),
            coverage=coverage,
            threshold=args.threshold,
        )
        result = asyncio.run(agent.run(args.job_id))
        print(result)  # noqa: T201
    except Exception as exc:
        exit_with_error(str(exc))


if __name__ == "__main__":
    main()
