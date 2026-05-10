"""CLI entrypoint for SpecAnalystAgent.

Examples:
    .. code-block:: shell

        python3 -m dv_agentic.cli.spec_analyst --input-file spec.txt --output-path .agent/vplan.yaml
"""

import argparse
import asyncio

from ._factory import make_llm
from ._helpers import exit_with_error, read_input


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser for the SpecAnalyst CLI.

    Returns:
        The configured ArgumentParser instance.
    """
    p = argparse.ArgumentParser(
        prog="python3 -m dv_agentic.cli.spec_analyst",
        description="Parse a spec document and generate a vplan.yaml.",
    )
    p.add_argument(
        "--input-file",
        "-i",
        default="-",
        metavar="PATH",
        help="Spec document file, or '-' for stdin (default: stdin).",
    )
    p.add_argument(
        "--output-path",
        default=".agent/vplan.yaml",
        metavar="PATH",
        help="Where to write the vplan (default: .agent/vplan.yaml).",
    )
    p.add_argument(
        "--budget", type=int, default=5, metavar="N", help="Maximum LLM iterations (default: 5)."
    )
    p.add_argument("--model", default=None, metavar="NAME", help="Override the LLM model name.")
    return p


def main() -> None:
    """Main execution block of the SpecAnalyst CLI."""
    args = _build_parser().parse_args()

    try:
        spec_text = read_input(args.input_file)
    except OSError as exc:
        exit_with_error(str(exc))

    output_path = args.output_path

    try:
        from dv_agentic.agents.base import AgentConfig
        from dv_agentic.agents.spec_analyst import SpecAnalystAgent

        llm = make_llm(model=args.model)
        agent = SpecAnalystAgent(
            config=AgentConfig(name="spec_analyst", budget=args.budget),
            llm=llm,
            output_path=output_path,
        )
        result = asyncio.run(agent.run(spec_text))
        print(result)  # noqa: T201
    except Exception as exc:
        exit_with_error(str(exc))


if __name__ == "__main__":
    main()
