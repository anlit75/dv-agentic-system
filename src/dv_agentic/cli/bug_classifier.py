"""CLI entrypoint for BugClassifierAgent.

Examples:
    .. code-block:: shell

        python3 -m dv_agentic.cli.bug_classifier --input-file failure_summary.txt --threshold 0.75
        cat failure.txt | python3 -m dv_agentic.cli.bug_classifier
"""

import argparse
import asyncio

from ._factory import make_llm
from ._helpers import die, read_input


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser for the BugClassifier CLI.

    Returns:
        The configured ArgumentParser instance.
    """
    p = argparse.ArgumentParser(
        prog="python3 -m dv_agentic.cli.bug_classifier",
        description="Classify a simulation failure as TB_BUG or RTL_BUG.",
    )
    p.add_argument(
        "--input-file",
        "-i",
        default="-",
        metavar="PATH",
        help="Failure summary file, or '-' for stdin (default: stdin).",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        metavar="FLOAT",
        help="Minimum confidence to accept a classification (default: 0.75).",
    )
    p.add_argument(
        "--budget", type=int, default=5, metavar="N", help="Maximum LLM iterations (default: 5)."
    )
    p.add_argument("--model", default=None, metavar="NAME", help="Override the LLM model name.")
    return p


def main() -> None:
    """Main execution block of the BugClassifier CLI."""
    args = _build_parser().parse_args()

    try:
        failure_summary = read_input(args.input_file)
    except OSError as exc:
        die(str(exc))

    try:
        from dv_agentic.agents.base import AgentConfig
        from dv_agentic.agents.bug_classifier import BugClassifierAgent

        llm = make_llm(model=args.model)
        agent = BugClassifierAgent(
            config=AgentConfig(name="bug_classifier", budget=args.budget),
            llm=llm,
            confidence_threshold=args.threshold,
        )
        result = asyncio.run(agent.run(failure_summary))
        print(result)  # noqa: T201
    except Exception as exc:
        die(str(exc))


if __name__ == "__main__":
    main()
