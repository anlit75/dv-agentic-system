# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Wiki linting CLI.

Usage:
    python -m dv_agentic.cli.wiki_lint [--depth quick|full]
"""

import argparse
import sys

from ..wiki.lint import WikiLintService
from ..wiki.manager import load_wiki_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Lint the LLM Wiki.")
    parser.add_argument(
        "--depth",
        choices=["quick", "full"],
        default="quick",
        help="Depth of linting. Quick only checks mapping, full parses contents.",
    )
    args = parser.parse_args()

    config = load_wiki_config()
    if not config.enabled:
        print("Wiki is disabled in project.yaml.")  # noqa: T201
        sys.exit(0)

    svc = WikiLintService(config)
    report = svc.run(depth=args.depth)

    print(report.to_str())  # noqa: T201
    if report.human_review_required:
        sys.exit(1)


if __name__ == "__main__":
    main()
