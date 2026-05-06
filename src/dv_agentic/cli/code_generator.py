"""CLI entrypoint for CodeGeneratorAgent.

Examples:
    .. code-block:: shell

        python3 -m dv_agentic.cli.code_generator \
            --task-id cov_fix_001 \
            --input-file task_description.txt
"""

import argparse
import asyncio

from ._factory import make_llm
from ._helpers import die, read_input


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser for the CodeGenerator CLI.

    Returns:
        The configured ArgumentParser instance.
    """
    p = argparse.ArgumentParser(
        prog="python3 -m dv_agentic.cli.code_generator",
        description="Generate or modify SV/UVM code via multi-turn LLM dialogue.",
    )
    p.add_argument(
        "--task-id",
        default="codegen_task",
        metavar="ID",
        help="Task identifier used in reports (default: codegen_task).",
    )
    p.add_argument(
        "--input-file",
        "-i",
        default="-",
        metavar="PATH",
        help="File containing the task description, or '-' for stdin.",
    )
    p.add_argument(
        "--budget", type=int, default=5, metavar="N", help="Maximum LLM iterations (default: 5)."
    )
    p.add_argument("--model", default=None, metavar="NAME", help="Override the LLM model name.")
    return p


def main() -> None:
    """Main execution block of the CodeGenerator CLI."""
    args = _build_parser().parse_args()

    try:
        description = read_input(args.input_file)
    except OSError as exc:
        die(str(exc))

    try:
        from dv_agentic.agents.base import AgentConfig
        from dv_agentic.agents.code_generator import CodeGeneratorAgent, CodeTask

        llm = make_llm(model=args.model)
        agent = CodeGeneratorAgent(
            config=AgentConfig(name="code_generator", budget=args.budget),
            llm=llm,
            workspace_dir=".",
        )
        task = CodeTask(task_id=args.task_id, description=description)
        result = asyncio.run(agent.run(task))
        print(result)  # noqa: T201
    except Exception as exc:
        die(str(exc))


if __name__ == "__main__":
    main()
