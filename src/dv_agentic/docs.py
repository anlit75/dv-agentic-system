import subprocess
import sys
from pathlib import Path


def build() -> None:
    """Build the Sphinx documentation."""
    root = Path(__file__).parent.parent.parent
    docs_dir = root / "docs"
    build_dir = docs_dir / "_build" / "html"

    print("--- Generating API documentation RST files ---")  # noqa: T201
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "sphinx.ext.apidoc", "-o", str(docs_dir), "src/dv_agentic", "-f"],
        check=True,
    )

    print(f"--- Building Sphinx HTML documentation in {build_dir} ---")  # noqa: T201
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "sphinx.cmd.build", "-b", "html", str(docs_dir), str(build_dir)],
        check=True,
    )
    print(f"\nDone! Documentation available at: {build_dir / 'index.html'}")  # noqa: T201


if __name__ == "__main__":
    build()
