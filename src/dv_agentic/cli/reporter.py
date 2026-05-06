"""CLI entrypoint for ReporterAgent.

Examples:
    .. code-block:: shell

        python3 -m dv_agentic.cli.reporter \
            --input-file session_results.txt \
            --output-path .agent/tasks/{task_id}_report.md
"""

import argparse
import asyncio

from ._factory import make_llm
from ._helpers import die, read_input


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser for the Reporter CLI.

    Returns:
        The configured ArgumentParser instance.
    """
    p = argparse.ArgumentParser(
        prog="python3 -m dv_agentic.cli.reporter",
        description="Generate a markdown report from aggregated session results.",
    )
    p.add_argument(
        "--input-file",
        "-i",
        default="-",
        metavar="PATH",
        help="Session results file, or '-' for stdin (default: stdin).",
    )
    p.add_argument(
        "--output-path",
        default=None,
        metavar="PATH",
        help="Where to write the report. Supports {task_id} placeholder.",
    )
    p.add_argument("--model", default=None, metavar="NAME", help="Override the LLM model name.")
    return p


def main() -> None:
    """Main execution block of the Reporter CLI."""
    args = _build_parser().parse_args()

    try:
        session_results = read_input(args.input_file)
    except OSError as exc:
        die(str(exc))

    output_path = args.output_path

    try:
        from dv_agentic.agents.base import AgentConfig
        from dv_agentic.agents.reporter import ReporterAgent

        llm = make_llm(model=args.model)
        agent = ReporterAgent(
            config=AgentConfig(name="reporter"),
            llm=llm,
            output_path=output_path,
        )
        result = asyncio.run(agent.run(session_results))
        print(result)  # noqa: T201
    except Exception as exc:
        die(str(exc))


if __name__ == "__main__":
    main()
