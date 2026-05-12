# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

import subprocess
import sys
from pathlib import Path


def build() -> None:
    """Build the MkDocs documentation."""
    root = Path(__file__).parent.parent.parent
    build_dir = root / "_build" / "html"

    print(f"--- Building MkDocs HTML documentation in {build_dir} ---")  # noqa: T201
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "mkdocs", "build", "-d", str(build_dir)],
        check=True,
    )
    print(f"\nDone! Documentation available at: {build_dir / 'index.html'}")  # noqa: T201


if __name__ == "__main__":
    build()
