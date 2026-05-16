# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

import re
from pathlib import Path

from .context import ProjectContext, SessionState


class PromptLoader:
    """Loads and enriches agent prompt templates.

    This loader follows the "Prompt is First-Class Citizen" principle:
    1. Standalone Ready: The source prompts in src/dv_agentic/prompts/ are valid markdown.
    2. Augmented: Placeholders are filled with context from profiles and session state.
    3. Clean: Unmatched placeholder lines are removed to keep the prompt tidy.
    """

    def __init__(
        self,
        prompts_dir: Path | str | None = None,
        project_config: ProjectContext | None = None,
        session: SessionState | None = None,
    ) -> None:
        """Initialize the PromptLoader.

        Args:
            prompts_dir: Path to the directory containing canonical prompts.
                Defaults to the package-relative prompts/ directory.
            project_config: Optional project configuration object for Level 1/2 injection.
            session: Optional session state object for Level 2 injection.
        """
        if prompts_dir is None:
            # Discovery logic:
            # 1. Check if project_config provides a project_root with an agents/ folder
            # 2. Fall back to package-relative prompts/ directory
            package_default = Path(__file__).parent
            project_agents = None
            # Level 1: Project-level overrides (if project_root is provided)
            if project_config and project_config.project_root:
                project_agents_dir = Path(project_config.project_root) / "agents"
                if project_agents_dir.is_dir():
                    project_agents = project_agents_dir

            self.prompts_dir = project_agents or package_default

            if self.prompts_dir.name not in ("prompts", "agents"):
                msg = f"PromptLoader path discovery failed: {self.prompts_dir}"
                raise RuntimeError(msg)
        else:
            self.prompts_dir = Path(prompts_dir)

        self.project_config = project_config
        self.session = session

    def load(self, agent_name: str) -> str:
        """Return the final system prompt string for the given agent.

        Args:
            agent_name: Name of the agent (e.g., "code_generator").

        Returns:
            The enriched system prompt string.
        """
        prompt_path = self.prompts_dir / f"{agent_name}.tmpl.md"
        if not prompt_path.exists():
            msg = f"Prompt template for '{agent_name}' not found at {prompt_path}"
            raise FileNotFoundError(msg)

        with prompt_path.open(encoding="utf-8") as f:
            template = f.read()

        context = self._gather_context()
        return self._inject(template, context)

    def _gather_context(self) -> dict[str, str]:
        """Gather all available context from config and session for injection."""
        context: dict[str, str] = {}

        if self.project_config:
            pc = self.project_config
            if pc.team_rules:
                context["TEAM_RULES"] = pc.team_rules
            if pc.ip_type_rules:
                context["IP_TYPE_RULES"] = pc.ip_type_rules
            if pc.vip_index:
                context["VIP_INDEX"] = pc.vip_index
            if pc.vplan_summary:
                context["PROJECT_VPLAN_SUMMARY"] = pc.vplan_summary
            if pc.known_error_patterns:
                context["KNOWN_ERROR_PATTERNS"] = pc.known_error_patterns
            if pc.known_rtl_bugs:
                context["KNOWN_RTL_BUGS"] = pc.known_rtl_bugs

            # Infrastructure Config Mapping
            if pc.simulator_config:
                sc = pc.simulator_config
                lines = [f"Simulator: {sc.name}"]
                if sc.binary_path:
                    lines.append(f"Binary: {sc.binary_path}")
                if sc.extra_compile_flags:
                    lines.append(f"Compile flags: {sc.extra_compile_flags}")
                if sc.extra_run_flags:
                    lines.append(f"Run flags: {sc.extra_run_flags}")
                lines.append(f"Coverage: {'enabled' if sc.collect_coverage else 'disabled'}")
                lines.append(f"Coverage DB root: {sc.cov_work_dir}")
                context["SIMULATOR_CONFIG"] = "\n".join(lines)

            if pc.scheduler_config:
                sch = pc.scheduler_config
                if sch.backend:
                    lines = [
                        f"Scheduler: {sch.backend.upper()}",
                        f"Queue: {sch.queue or 'default'}",
                        f"Resource flags: {sch.resource_flags or 'none'}",
                        f"Default wall time: {sch.default_wall_time_sec}s",
                        f"Poll interval: {sch.poll_interval_sec}s",
                    ]
                    context["SCHEDULER_CONFIG"] = "\n".join(lines)

            if pc.vcs_config:
                vc = pc.vcs_config
                lines = [
                    f"VCS: {vc.backend}",
                    f"Base branch: {vc.base_branch}",
                    f"Remote: {vc.remote}",
                ]
                if vc.author_name:
                    lines.append(f"Author: {vc.author_name} <{vc.author_email}>")
                context["VCS_CONFIG"] = "\n".join(lines)

        if self.session:
            s = self.session
            context["SESSION_STATE"] = (
                f"Task: {s.task_id or 'N/A'} | "
                f"Iteration: {s.iteration} | "
                f"Budget remaining: {s.budget_remaining or 'N/A'}"
            )

        return context

    def _inject(self, template: str, context: dict[str, str]) -> str:
        """Replace {{KEY}} with context[KEY], remove unmatched placeholder lines."""
        # 1. Replace placeholders
        lines = template.splitlines()
        result_lines = []
        placeholder_pattern = re.compile(r"\{\{([A-Z0-9_]+)\}\}")

        for line in lines:
            matches = placeholder_pattern.findall(line)
            if not matches:
                result_lines.append(line)
                continue

            # Pure placeholder line check: strip whitespace and check if it exactly
            # matches one {{KEY}} (pattern matches the stripped string fully)
            stripped = line.strip()
            is_pure_placeholder = placeholder_pattern.fullmatch(stripped) is not None

            if is_pure_placeholder:
                key = matches[0]
                if key in context:
                    # Replace in the original line (preserving indentation)
                    result_lines.append(line.replace(f"{{{{{key}}}}}", context[key]))
                # else: Pure placeholder line with missing context is REMOVED entirely
            else:
                # Mixed line: replace values if they exist, otherwise use empty string
                new_line = line
                for key in matches:
                    new_line = new_line.replace(f"{{{{{key}}}}}", context.get(key, ""))
                result_lines.append(new_line)

        # 2. Compress consecutive blank lines (max 2 consecutive newlines)
        result = "\n".join(result_lines)
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip()
