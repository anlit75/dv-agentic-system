"""CLI entrypoint for LogAnalyzerAgent.

Examples:
    .. code-block:: shell

        python3 -m dv_agentic.cli.log_analyzer --input-file sim_test_42.log
        python3 -m dv_agentic.cli.log_analyzer --input-file -         # read stdin
        cat sim.log | python3 -m dv_agentic.cli.log_analyzer
"""

import argparse
import asyncio

from ._helpers import die, read_input


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser for the LogAnalyzer CLI.

    Returns:
        The configured ArgumentParser instance.
    """
    p = argparse.ArgumentParser(
        prog="python3 -m dv_agentic.cli.log_analyzer",
        description="Classify errors in a simulation log.",
    )
    p.add_argument(
        "--input-file",
        "-i",
        metavar="PATH",
        default="-",
        help="Log file path, or '-' for stdin (default: stdin).",
    )
    return p


def main() -> None:
    """Main execution block of the LogAnalyzer CLI."""
    args = _build_parser().parse_args()

    try:
        content = read_input(args.input_file)
    except OSError as exc:
        die(str(exc))

    from dv_agentic.agents.base import AgentConfig
    from dv_agentic.agents.log_analyzer import LogAnalyzerAgent

    agent = LogAnalyzerAgent(config=AgentConfig(name="log_analyzer"))
    result = asyncio.run(agent.run(content))
    print(result)  # noqa: T201


if __name__ == "__main__":
    main()
