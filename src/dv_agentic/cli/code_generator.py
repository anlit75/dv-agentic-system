# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""CLI entrypoint for CodeGeneratorAgent.

Examples:
    .. code-block:: shell

        python3 -m dv_agentic.cli.code_generator \
            --task-id cov_fix_001 \
            --input-file task_description.txt
"""

import argparse
import asyncio
import logging

from ._factory import make_llm
from ._helpers import exit_with_error, read_input

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser for the CodeGenerator CLI.

    Returns:
        The configured ArgumentParser instance.
    """
    p = argparse.ArgumentParser(
        prog="python3 -m dv_agentic.cli.code_generator",
        description="Generate or modify SV/UVM testbench code via multi-turn LLM dialogue.",
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
    p.add_argument(
        "--no-tb-guard",
        action="store_true",
        help=(
            "Disable the TB directory whitelist (allows writing to any path). "
            "Use only in test environments — never in production."
        ),
    )
    return p


def main() -> None:
    """Main execution block of the CodeGenerator CLI."""
    args = _build_parser().parse_args()

    if args.no_tb_guard:
        logger.warning(
            "============================================================\n"
            "SECURITY WARNING: Testbench guard is DISABLED (--no-tb-guard).\n"
            "The agent is allowed to write to any path in the workspace,\n"
            "including RTL source files. USE ONLY IN TEST ENVIRONMENTS!\n"
            "============================================================"
        )

    try:
        description = read_input(args.input_file)
    except OSError as exc:
        exit_with_error(str(exc))

    try:
        from dv_agentic.agents.base import AgentConfig
        from dv_agentic.agents.code_generator import (
            DEFAULT_TB_ALLOWED_DIRS,
            CodeGeneratorAgent,
            CodeTask,
        )

        llm = make_llm(model=args.model)
        agent = CodeGeneratorAgent(
            config=AgentConfig(name="code_generator", budget=args.budget),
            llm=llm,
            workspace_dir=".",
            # TB guard is ON by default; --no-tb-guard disables it
            allowed_dirs=None if args.no_tb_guard else DEFAULT_TB_ALLOWED_DIRS,
        )
        task = CodeTask(task_id=args.task_id, description=description)
        result = asyncio.run(agent.run(task))
        print(result)  # noqa: T201
    except Exception as exc:
        exit_with_error(str(exc))


if __name__ == "__main__":
    main()
