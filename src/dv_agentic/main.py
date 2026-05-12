# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Entry point for the dv-agentic-system."""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    """Run the agentic system."""
    logger.info("dv-agentic-system starting.")


if __name__ == "__main__":
    main()
