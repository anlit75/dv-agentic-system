# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""CLI entrypoint for the agent installer.

Materializes enriched ``.claude/agents/*.md`` (Claude Code YAML) and
``.opencode/agents/*.md`` (OpenCode YAML preserved from templates) from
``src/dv_agentic/prompts/*.tmpl.md``, and mirrors root ``tools/`` and ``skills/``
into ``.claude/`` / ``.opencode/``.

What it does
------------
1. Optionally loads ``project.yaml`` + org profiles to enrich prompts
   (Level 1 injection: team rules + IP-type rules; session state omitted).
2. For each of the agents, calls :class:`~dv_agentic.prompts.prompt_loader.PromptLoader`
   to produce an enriched prompt body (placeholders filled, unmatched removed).
3. Strips the OpenCode-style YAML front matter from the source template.
4. Prepends Claude Code compatible YAML front matter.
5. Writes to ``{project_root}/.claude/agents/{agent}.md``.
6. Writes enriched content to ``{project_root}/.opencode/agents/{agent}.md``,
   keeping the OpenCode YAML from the template.

Examples:
    .. code-block:: shell

        # No profile injection — raw prompts only
        python3 -m dv_agentic.cli.install_agents --project-root /path/to/project

        # Full profile injection
        python3 -m dv_agentic.cli.install_agents \\
            --project-root /path/to/project \\
            --project-config .agent/project.yaml \\
            --profiles-dir ../team-profiles

        # Overwrite existing files
        python3 -m dv_agentic.cli.install_agents --force
"""

import argparse
import logging
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent metadata — defines the Claude Code front matter per agent
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

# Target directories for installation
_TARGETS = {
    "agents": [".claude/agents", ".opencode/agents"],
    "tools": [".opencode/tools", ".claude/tools"],
    "skills": [".claude/skills", ".opencode/skills"],
}


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
    """Build Claude Code compatible YAML front matter block."""
    description = str(meta["description"])
    tools = meta["tools"]
    tools_str = ", ".join(str(t) for t in tools) if isinstance(tools, list) else str(tools)
    return f"---\nname: {name}\ndescription: >\n  {description}\ntools: [{tools_str}]\n---\n\n"


# ---------------------------------------------------------------------------
# Core installer helpers
# ---------------------------------------------------------------------------


def _remove_existing_link(link: Path, force: bool) -> bool:
    """Remove an existing link or directory if *force*; return True when caller should skip.

    Returns True  → link already exists and force is False (skip this target).
    Returns False → link was removed (or never existed) and caller should proceed.
    """
    if not (link.exists() or link.is_symlink()):
        return False
    if not force:
        return True
    if link.is_dir() and not link.is_symlink():
        shutil.rmtree(link)
    else:
        link.unlink()
    return False


def _symlink_asset(asset: Path, link: Path, project_root: Path, *, is_dir: bool) -> None:
    """Create a relative symlink from *link* → *asset*, falling back to a copy on OSError."""
    try:
        rel_target = os.path.relpath(asset, start=link.parent)
        link.symlink_to(rel_target, target_is_directory=is_dir)
        logger.info(
            "  symlink %s -> %s",
            link.relative_to(project_root),
            asset.relative_to(project_root),
        )
    except OSError:
        if is_dir:
            shutil.copytree(asset, link)
        else:
            shutil.copy2(asset, link)
        logger.info(
            "  copy    %s -> %s (symlink failed)",
            link.relative_to(project_root),
            asset.relative_to(project_root),
        )


def _install_asset_to_targets(
    asset: Path, targets: list[Path], project_root: Path, force: bool
) -> None:
    """Install a single asset (file or directory) to every target directory."""
    is_dir = asset.is_dir()
    for t in targets:
        link = t / asset.name
        if _remove_existing_link(link, force):
            continue
        _symlink_asset(asset, link, project_root, is_dir=is_dir)


def _install_assets(
    src_dir: Path,
    asset_type: str,
    project_root: Path,
    force: bool = False,
    targets_override: dict[str, list[str]] | None = None,
) -> None:
    """Discover and install tools or skills from *src_dir* to the configured targets."""
    if not src_dir.is_dir():
        return

    logger.info("Discovering %s in %s...", asset_type, src_dir)
    target_map = targets_override if targets_override is not None else _TARGETS
    targets = [project_root / t for t in target_map.get(asset_type, [])]
    for target in targets:
        target.mkdir(parents=True, exist_ok=True)

    for asset in src_dir.iterdir():
        if asset.name.startswith("."):
            continue
        _install_asset_to_targets(asset, targets, project_root, force)


def _load_project_context(
    project_config_path: str | None,
    profiles_dir: str | None,
    project_root: Path,
) -> Any:
    """Load a full ProjectContext from *project_config_path*, or create a minimal one."""
    if project_config_path:
        from dv_agentic.config import load_project

        config_path = Path(project_config_path).resolve()
        project_ctx, _, _ = load_project(
            project_yaml=config_path,
            profiles_dir=profiles_dir,
        )
        project_ctx.project_root = str(project_root)
        return project_ctx

    from dv_agentic.prompts.context import ProjectContext

    return ProjectContext(project_root=str(project_root))


def _write_agent_file(
    agent_name: str,
    loader: Any,
    target: Path,
    project_root: Path,
) -> None:
    """Write Claude Code format agent file: strip OpenCode YAML, prepend Claude Code YAML."""
    raw = loader.load(agent_name)
    body = _strip_front_matter(raw)
    meta = _AGENT_META.get(agent_name, {"description": f"{agent_name} agent.", "tools": ["Read"]})
    content = _build_front_matter(agent_name, meta) + body.strip() + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    logger.info("  wrote %s", target.relative_to(project_root))


def _write_opencode_agent_file(
    agent_name: str,
    loader: Any,
    target: Path,
    project_root: Path,
) -> None:
    """Write OpenCode format agent file: preserve original OpenCode YAML front matter."""
    raw = loader.load(agent_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(raw.strip() + "\n", encoding="utf-8")
    logger.info("  wrote %s", target.relative_to(project_root))


_CLAUDE_TARGETS: dict[str, list[str]] = {
    "agents": [".claude/agents"],
    "tools": [".claude/tools"],
    "skills": [".claude/skills"],
}
_OPENCODE_TARGETS: dict[str, list[str]] = {
    "agents": [".opencode/agents"],
    "tools": [".opencode/tools"],
    "skills": [".opencode/skills"],
}


def _merged_targets(target: str) -> dict[str, list[str]]:
    """Return the effective target-directory mapping for the requested *target*."""
    if target == "claude":
        return _CLAUDE_TARGETS
    if target == "opencode":
        return _OPENCODE_TARGETS
    # all
    return _TARGETS


def install(
    project_root: Path,
    project_config_path: str | None = None,
    profiles_dir: str | None = None,
    force: bool = False,
    target: str = "opencode",
) -> int:
    """Standardized installer main entry.

    Args:
        target: Which platform(s) to install to — ``"claude"``, ``"opencode"``
            (default), or ``"all"``.
    """
    project_ctx = _load_project_context(project_config_path, profiles_dir, project_root)

    from dv_agentic.prompts.prompt_loader import PromptLoader

    loader = PromptLoader(project_config=project_ctx)

    effective_targets = _merged_targets(target)
    _install_assets(
        project_root / "tools",
        "tools",
        project_root,
        force=force,
        targets_override=effective_targets,
    )
    _install_assets(
        project_root / "skills",
        "skills",
        project_root,
        force=force,
        targets_override=effective_targets,
    )

    # Agent directories: Claude Code and OpenCode each receive their own format.
    # .claude/agents/ → Claude Code YAML front matter
    # .opencode/agents/ → original OpenCode YAML front matter (from template)
    agent_writers: list[tuple[Path, Any]] = []
    if target in ("claude", "all"):
        claude_agent_dir = project_root / ".claude" / "agents"
        claude_agent_dir.mkdir(parents=True, exist_ok=True)
        agent_writers.append((claude_agent_dir, _write_agent_file))
    if target in ("opencode", "all"):
        opencode_agent_dir = project_root / ".opencode" / "agents"
        opencode_agent_dir.mkdir(parents=True, exist_ok=True)
        agent_writers.append((opencode_agent_dir, _write_opencode_agent_file))

    errors = 0
    written = 0
    skipped = 0

    for agent_name in _AGENTS:
        any_written = False
        any_error = False

        for agent_dir, write_fn in agent_writers:
            agent_md = agent_dir / f"{agent_name}.md"

            if agent_md.exists() and not force:
                logger.info("  skip  %s (exists)", agent_md.relative_to(project_root))
                skipped += 1
                continue

            try:
                write_fn(agent_name, loader, agent_md, project_root)
                any_written = True
            except FileNotFoundError:
                logger.warning("  warn %s — prompt template not found, skipping", agent_name)
                break
            except OSError as exc:
                logger.error("  ERROR writing %s: %s", agent_name, exc)
                any_error = True

        if any_written:
            written += 1
        if any_error:
            errors += 1

    print(  # noqa: T201
        f"\nInstall complete: {written} agents generated, {skipped} skipped, {errors} errors."
    )
    return 0 if errors == 0 else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python3 -m dv_agentic.cli.install_agents",
        description=(
            "Standardized Agent/Tool/Skill installer. "
            "Discovers agents/, tools/, and skills/ in the project root and "
            "installs them under .claude/ and/or .opencode/ depending on --target."
        ),
    )
    p.add_argument(
        "--project-root",
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
        help="Overwrite existing files in target directories.",
    )
    p.add_argument(
        "--target",
        choices=["claude", "opencode", "all"],
        default="opencode",
        metavar="TARGET",
        help=("Which platform(s) to install to: claude, opencode (default), or all."),
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

    # 1. Base path
    project_root = Path(args.project_root).resolve()

    # 2. Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(levelname)7s  %(message)s",
    )

    # 3. Execute
    rc = install(
        project_root=project_root,
        project_config_path=args.project_config,
        profiles_dir=args.profiles_dir,
        force=args.force,
        target=args.target,
    )
    sys.exit(rc)


if __name__ == "__main__":
    main()
