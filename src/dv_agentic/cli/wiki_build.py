# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Wiki build CLI.

Rebuilds index.md and the BM25 search index.

Usage:
    python -m dv_agentic.cli.wiki_build
"""

import argparse
import logging
import sys

from ..wiki.ingest import WikiIngestService
from ..wiki.manager import load_wiki_config
from ..wiki.search import WikiSearchIndex

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wiki_build")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the LLM Wiki indices.")
    parser.parse_args()

    config = load_wiki_config()
    if not config.enabled:
        logger.info("Wiki is disabled in project.yaml.")
        sys.exit(0)

    logger.info("Rebuilding index.md...")
    svc = WikiIngestService(config)
    # The private helpers will overwrite their respective sections in index.md
    wiki_dir = config.wiki_dir
    svc._update_index_patterns(wiki_dir / "patterns")
    svc._update_index_bugs(wiki_dir / "bugs")
    svc._update_index_coverage(wiki_dir / "coverage")

    logger.info("Rebuilding BM25 Search Index...")
    try:
        idx = WikiSearchIndex.create(backend=config.search_backend, wiki_dir=wiki_dir)
        idx.build(wiki_dir)
        logger.info("Build complete.")
    except Exception as e:
        logger.error("Failed to build search index: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
