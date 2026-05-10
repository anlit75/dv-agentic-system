"""CLI entrypoint for the agent installer.

Generates enriched ``.agent/subagents/*.md`` files from the canonical prompt
templates and creates symlinks for Claude Code, Cursor, and OpenCode.

What it does
------------
1. Optionally loads ``project.yaml`` + org profiles to enrich prompts
   (Level 1 injection: team rules + IP-type rules; session state omitted).
2. For each of the agents, calls :class:`~dv_agentic.prompts.prompt_loader.PromptLoader`
   to produce an enriched prompt body (placeholders filled, unmatched removed).
3. Strips the OpenCode-style YAML front matter from the source template.
4. Prepends Claude Code / Cursor compatible YAML front matter.
5. Writes to ``{worktree}/.agent/subagents/{agent}.md``.
6. Creates symlinks in ``.claude/agents/`` and ``.cursor/rules/``.

Examples:
    .. code-block:: shell

        # No profile injection — raw prompts only
        python3 -m dv_agentic.cli.install_agents --worktree /path/to/project

        # Full profile injection
        python3 -m dv_agentic.cli.install_agents \\
            --worktree /path/to/project \\
            --project-config .agent/project.yaml \\
            --profiles-dir ../team-profiles

        # Overwrite existing files
        python3 -m dv_agentic.cli.install_agents --force
"""

import argparse
import logging
import os
import re
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent metadata — defines the Claude Code / Cursor front matter per agent
# ---------------------------------------------------------------------------

# Tools listed follow Claude Code sub-agent conventions.
# Agents that only analyse (no code changes) get read-only tools.
_AGENT_META: dict[str, dict[str, object]] = {
    "orchestrator": {
        "description": (
            "Route a verification task through the full agent pipeline "
            "(Workflows 1, 2, or 3). Use for complex multi-step tasks such as "
            "'develop verification for X feature', 'regression has N fails', or "
            "'coverage is 73%, find what needs to be filled'."
        ),
        "tools": ["Read", "Write", "Edit", "Bash", "Task"],
    },
    "spec_analyst": {
        "description": (
            "Parse a hardware specification document and generate a structured "
            "verification plan (vplan.yaml). Use at the start of Workflow 1 "
            "when you receive a new spec and need to plan what to verify."
        ),
        "tools": ["Read", "Write"],
    },
    "code_generator": {
        "description": (
            "Generate or modify SystemVerilog / UVM code targeting specific "
            "coverage bins or bug fixes. Use when you need new sequences, "
            "scoreboards, coverage groups, or when a compile / sim error "
            "requires a testbench fix."
        ),
        "tools": ["Read", "Write", "Edit", "Bash"],
    },
    "sim_controller": {
        "description": (
            "Compile source files and run a simulation test inside a dedicated "
            "git branch (ai-task/{task_id}). Retries up to budget times on failure. "
            "Use whenever you need to run a simulation and track results on a "
            "branch ready for PR review."
        ),
        "tools": ["Read", "Write", "Bash"],
    },
    "log_analyzer": {
        "description": (
            "Parse a simulation log file and classify the failure "
            "(compile_error, uvm_fatal, uvm_error, scoreboard_mismatch, timeout, …). "
            "Use whenever a simulation run produces a log that needs analysis."
        ),
        "tools": ["Read"],
    },
    "wave_analyzer": {
        "description": (
            "Interpret waveform signal patterns from a VCD or FSDB dump. "
            "Use when log analysis is insufficient and signal-level debug is required."
        ),
        "tools": ["Read"],
    },
    "coverage_analyst": {
        "description": (
            "Retrieve overall functional coverage for a simulation job and report "
            "whether it meets the threshold. Use after a simulation run to check "
            "coverage before deciding on next steps."
        ),
        "tools": ["Read"],
    },
    "bug_classifier": {
        "description": (
            "Classify a simulation failure as TB_BUG (testbench issue) or RTL_BUG "
            "(design bug) with a confidence score. Use after log analysis when you "
            "need to determine whether a fix goes in the testbench or requires an RTL ECO."
        ),
        "tools": ["Read"],
    },
    "reporter": {
        "description": (
            "Generate a structured markdown report from the aggregated results of "
            "a verification session. Use at the end of any workflow to produce a "
            "human-readable summary for PR review or ticket creation."
        ),
        "tools": ["Read", "Write"],
    },
}

# Canonical agent order (matches agentic-system-structure.md)
_AGENTS = [
    "orchestrator",
    "spec_analyst",
    "code_generator",
    "sim_controller",
    "log_analyzer",
    "wave_analyzer",
    "coverage_analyst",
    "bug_classifier",
    "reporter",
]

# Symlink targets per tool
_SYMLINK_DIRS = [
    ".claude/agents",
    ".cursor/rules",
]


# ---------------------------------------------------------------------------
# Front matter helpers
# ---------------------------------------------------------------------------


def _strip_front_matter(text: str) -> str:
    """Remove YAML front matter (first ``---`` … ``---`` block) from *text*.

    The PromptLoader returns the full file content including any OpenCode-style
    front matter. This strips it so we can prepend Claude Code front matter.
    """
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return text  # no front matter
    # Find the closing ---
    rest = stripped[3:]  # skip opening ---
    m = re.search(r"^\s*---\s*$", rest, re.MULTILINE)
    if not m:
        return text  # malformed — return as-is
    return rest[m.end() :].lstrip("\n")


def _build_front_matter(name: str, meta: dict[str, object]) -> str:
    """Build Claude Code / Cursor compatible YAML front matter block."""
    description = str(meta["description"])
    tools = meta["tools"]
    tools_str = ", ".join(str(t) for t in tools) if isinstance(tools, list) else str(tools)
    return f"---\nname: {name}\ndescription: >\n  {description}\ntools: [{tools_str}]\n---\n\n"


# ---------------------------------------------------------------------------
# Core installer
# ---------------------------------------------------------------------------


def install(
    worktree: Path,
    project_yaml: Path | None,
    profiles_dir: Path | None,
    force: bool,
) -> int:
    """Generate enriched subagent files and create symlinks.

    Args:
        worktree: Root of the verification project (contains ``.agent/``).
        project_yaml: Optional path to ``.agent/project.yaml``.
        profiles_dir: Optional root of the org profile repository.
        force: Overwrite existing ``.md`` files if ``True``.

    Returns:
        Exit code: 0 on success, 1 if any agent failed.
    """
    # 1. Load ProjectContext (optional)
    project_ctx = None
    if project_yaml:
        try:
            from dv_agentic.config import load_project

            project_ctx, _, _ = load_project(
                project_yaml=project_yaml,
                profiles_dir=profiles_dir,
            )
            logger.info("Loaded project config from %s", project_yaml)
        except (FileNotFoundError, ValueError) as exc:
            logger.error("Failed to load project config: %s", exc)
            return 1

    # 2. PromptLoader — uses package-default prompts directory
    from dv_agentic.prompts.prompt_loader import PromptLoader

    loader = PromptLoader(project_config=project_ctx)

    # 3. Prepare output directories
    subagents_dir = worktree / ".agent" / "subagents"
    subagents_dir.mkdir(parents=True, exist_ok=True)

    symlink_dirs: list[Path] = []
    for rel in _SYMLINK_DIRS:
        d = worktree / rel
        d.mkdir(parents=True, exist_ok=True)
        symlink_dirs.append(d)

    # 4. Generate each agent
    errors = 0
    written = 0
    skipped = 0

    for agent_name in _AGENTS:
        target = subagents_dir / f"{agent_name}.md"

        if target.exists() and not force:
            logger.info("  skip  %s (exists — use --force to overwrite)", agent_name)
            skipped += 1
            continue

        # Load and enrich the prompt body
        try:
            enriched = loader.load(agent_name)
        except FileNotFoundError:
            logger.warning("  warn  %s — no prompt template found, skipping", agent_name)
            continue

        body = _strip_front_matter(enriched)
        meta = _AGENT_META.get(
            agent_name,
            {
                "description": f"{agent_name} agent.",
                "tools": ["Read"],
            },
        )
        content = _build_front_matter(agent_name, meta) + body.strip() + "\n"

        try:
            target.write_text(content, encoding="utf-8")
            logger.info("  wrote %s", target)
            written += 1
        except OSError as exc:
            logger.error("  error writing %s: %s", target, exc)
            errors += 1
            continue

        # Symlinks → relative path so they survive directory moves
        for link_dir in symlink_dirs:
            link = link_dir / f"{agent_name}.md"
            try:
                if link.exists() or link.is_symlink():
                    link.unlink()
                # Compute relative path from the symlink's directory to the target file
                rel_target = os.path.relpath(target, start=link_dir)
                link.symlink_to(rel_target)
            except OSError as exc:
                logger.warning("  warn  symlink %s → %s failed: %s", link, target, exc)

    # 5. Summary
    print(  # noqa: T201
        f"\nInstall complete: {written} written, {skipped} skipped, {errors} errors."
        f"\nSubagents: {subagents_dir}"
    )
    if symlink_dirs:
        for d in symlink_dirs:
            print(f"Symlinks:  {d}")  # noqa: T201

    return 0 if errors == 0 else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python3 -m dv_agentic.cli.install_agents",
        description=(
            "Generate enriched .agent/subagents/*.md files and create symlinks "
            "for Claude Code, Cursor, and OpenCode."
        ),
    )
    p.add_argument(
        "--worktree",
        default=".",
        metavar="PATH",
        help="Root of the verification project (default: current directory).",
    )
    p.add_argument(
        "--project-config",
        default=None,
        metavar="PATH",
        help=(
            "Path to .agent/project.yaml for Level 1 profile injection. "
            "When omitted, raw prompts are used (no team/IP rules injected)."
        ),
    )
    p.add_argument(
        "--profiles-dir",
        default=None,
        metavar="PATH",
        help=(
            "Root of the org profile repository. "
            "Falls back to DV_PROFILES_DIR env var. Only used with --project-config."
        ),
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing .md files in .agent/subagents/.",
    )
    p.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show debug-level log messages.",
    )
    return p


def main() -> None:
    """Main execution block for the install-agents CLI."""
    args = _build_parser().parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    worktree = Path(args.worktree).resolve()
    project_yaml = Path(args.project_config).resolve() if args.project_config else None
    profiles_dir = Path(args.profiles_dir).resolve() if args.profiles_dir else None

    rc = install(
        worktree=worktree,
        project_yaml=project_yaml,
        profiles_dir=profiles_dir,
        force=args.force,
    )
    sys.exit(rc)


if __name__ == "__main__":
    main()
