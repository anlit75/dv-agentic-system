# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Unit tests for CodeGeneratorAgent (Phase 3b)."""

import asyncio
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

from dv_agentic.agents.base import AgentConfig
from dv_agentic.agents.code_generator import (
    CodeGeneratorAgent,
    CodeTask,
    FileSpec,
)

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


def _make_agent(
    responses: list[str],
    workspace_dir: str,
    budget: int = 5,
) -> CodeGeneratorAgent:
    """Build an agent backed by a stub LLM that returns *responses* in order."""
    llm = MagicMock()
    llm.complete = AsyncMock(side_effect=responses)
    return CodeGeneratorAgent(
        config=AgentConfig(name="code_gen", budget=budget),
        llm=llm,
        workspace_dir=workspace_dir,
    )


_HIGH_RESPONSE = """\
### Summary
Generated axi_burst_seq targeting back-pressure bin.

### Changed Files
- `tb/sequences/axi_burst_seq.sv` — new sequence

### Code
```sv
// file: tb/sequences/axi_burst_seq.sv
class axi_burst_seq extends axi_base_seq;
  `uvm_object_utils(axi_burst_seq)
endclass
```

### Open Questions
None.

### Compile Confidence
HIGH — all identifiers resolved, factory registration present.
"""

_LOW_RESPONSE = """\
### Summary
Partial implementation — base class not confirmed.

### Changed Files
- `tb/sequences/axi_burst_seq.sv` — draft

### Code
```sv
class axi_burst_seq extends UNKNOWN_BASE;
endclass
```

### Open Questions
What is the correct base class name for this VIP?

### Compile Confidence
LOW — UNKNOWN_BASE unresolved.
"""

_MEDIUM_RESPONSE = """\
### Summary
Revised with correct base class.

### Changed Files
- `tb/sequences/axi_burst_seq.sv` — updated

### Code
```sv
// file: tb/sequences/axi_burst_seq.sv
class axi_burst_seq extends axi_seq_base;
  `uvm_object_utils(axi_burst_seq)
endclass
```

### Open Questions
None.

### Compile Confidence
MEDIUM — base class assumed from VIP hierarchy, not confirmed by build.
"""


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


class TestParseResponse:
    def test_high_confidence_extracted(self, tmp_path: Path) -> None:
        agent = _make_agent(responses=[], workspace_dir=str(tmp_path))
        p = agent._parse_response(_HIGH_RESPONSE)
        assert p.confidence == "HIGH"

    def test_medium_confidence_extracted(self, tmp_path: Path) -> None:
        agent = _make_agent(responses=[], workspace_dir=str(tmp_path))
        p = agent._parse_response(_MEDIUM_RESPONSE)
        assert p.confidence == "MEDIUM"

    def test_low_confidence_extracted(self, tmp_path: Path) -> None:
        agent = _make_agent(responses=[], workspace_dir=str(tmp_path))
        p = agent._parse_response(_LOW_RESPONSE)
        assert p.confidence == "LOW"

    def test_unknown_confidence_when_missing(self, tmp_path: Path) -> None:
        agent = _make_agent(responses=[], workspace_dir=str(tmp_path))
        p = agent._parse_response("### Summary\nNo confidence section here.")
        assert p.confidence == "UNKNOWN"

    def test_summary_extracted(self, tmp_path: Path) -> None:
        agent = _make_agent(responses=[], workspace_dir=str(tmp_path))
        p = agent._parse_response(_HIGH_RESPONSE)
        assert "axi_burst_seq" in p.summary

    def test_open_questions_extracted(self, tmp_path: Path) -> None:
        agent = _make_agent(responses=[], workspace_dir=str(tmp_path))
        p = agent._parse_response(_LOW_RESPONSE)
        assert "base class" in p.open_questions

    def test_file_paths_extracted(self, tmp_path: Path) -> None:
        agent = _make_agent(responses=[], workspace_dir=str(tmp_path))
        p = agent._parse_response(_HIGH_RESPONSE)
        assert any("axi_burst_seq.sv" in fp for fp in p.changed_file_paths)

    def test_file_specs_from_marker(self, tmp_path: Path) -> None:
        """Strategy 2: single code block with // file: marker."""
        agent = _make_agent(responses=[], workspace_dir=str(tmp_path))
        p = agent._parse_response(_HIGH_RESPONSE)
        assert len(p.file_specs) == 1
        assert "axi_burst_seq.sv" in p.file_specs[0].path
        assert "axi_burst_seq" in p.file_specs[0].content

    def test_file_specs_n_blocks_n_paths(self, tmp_path: Path) -> None:
        """Strategy 1: N code blocks matched to N changed-file paths."""
        resp = """\
### Changed Files
- `tb/seq_a.sv` — first
- `tb/seq_b.sv` — second

### Code
```sv
class seq_a extends base; endclass
```

```sv
class seq_b extends base; endclass
```

### Compile Confidence
HIGH — both files clean.
"""
        agent = _make_agent(responses=[], workspace_dir=str(tmp_path))
        p = agent._parse_response(resp)
        assert len(p.file_specs) == 2
        assert "seq_a.sv" in p.file_specs[0].path
        assert "seq_b.sv" in p.file_specs[1].path

    def test_file_specs_fallback_first_path(self, tmp_path: Path) -> None:
        """Strategy 3: single block, no marker → assigned to first changed file."""
        resp = """\
### Changed Files
- `tb/fallback.sv` — only file

### Code
```sv
class fallback extends base; endclass
```

### Compile Confidence
HIGH — ok.
"""
        agent = _make_agent(responses=[], workspace_dir=str(tmp_path))
        p = agent._parse_response(resp)
        assert len(p.file_specs) == 1
        assert "fallback.sv" in p.file_specs[0].path

    def test_no_code_block_gives_empty_specs(self, tmp_path: Path) -> None:
        resp = "### Summary\nNothing here.\n### Compile Confidence\nHIGH — trivial."
        agent = _make_agent(responses=[], workspace_dir=str(tmp_path))
        p = agent._parse_response(resp)
        assert p.file_specs == []


# ---------------------------------------------------------------------------
# Multi-turn loop
# ---------------------------------------------------------------------------


class TestMultiTurnLoop:
    def test_pass_on_first_high_response(self, tmp_path: Path) -> None:
        agent = _make_agent(responses=[_HIGH_RESPONSE], workspace_dir=str(tmp_path))
        result = asyncio.run(agent.run("Generate a sequence"))
        assert "pass" in result
        assert "iterations   : 1" in result

    def test_low_then_medium_pass(self, tmp_path: Path) -> None:
        """LOW response triggers a follow-up; MEDIUM on second turn → pass."""
        agent = _make_agent(
            responses=[_LOW_RESPONSE, _MEDIUM_RESPONSE], workspace_dir=str(tmp_path)
        )
        result = asyncio.run(agent.run("Generate a sequence"))
        assert "pass" in result
        assert "iterations   : 2" in result
        # LLM must have been called exactly twice
        assert cast(MagicMock, agent.llm.complete).call_count == 2

    def test_follow_up_message_contains_open_questions(self, tmp_path: Path) -> None:
        """When LOW, the next user message must include the open questions text."""
        captured_histories: list[list[dict[str, str]]] = []

        async def capture_complete(
            system: str, messages: list[dict[str, str]], max_tokens: int = 1000
        ) -> str:
            captured_histories.append(list(messages))
            # First call → LOW, second → HIGH
            if len(captured_histories) == 1:
                return _LOW_RESPONSE
            return _HIGH_RESPONSE

        agent = _make_agent(responses=[], workspace_dir=str(tmp_path))
        cast(MagicMock, agent.llm.complete).side_effect = capture_complete
        asyncio.run(agent.run("Generate a sequence"))

        # The second call's last user message should echo the open questions
        second_call_msgs = captured_histories[1]
        last_user = next(m["content"] for m in reversed(second_call_msgs) if m["role"] == "user")
        assert "base class" in last_user  # from _LOW_RESPONSE open questions

    def test_history_grows_across_turns(self, tmp_path: Path) -> None:
        """assistant + user messages must accumulate in the history list."""
        histories: list[list[dict[str, str]]] = []

        async def spy(system: str, messages: list[dict[str, str]], max_tokens: int = 1000) -> str:
            histories.append(list(messages))
            return _LOW_RESPONSE if len(histories) < 2 else _HIGH_RESPONSE

        agent = _make_agent(responses=[], workspace_dir=str(tmp_path))
        cast(MagicMock, agent.llm.complete).side_effect = spy
        asyncio.run(agent.run("Generate"))

        assert len(histories[0]) == 1  # initial: only user task
        assert len(histories[1]) > len(histories[0])  # grown by assistant + follow-up


# ---------------------------------------------------------------------------
# Budget exhaustion
# ---------------------------------------------------------------------------


class TestBudgetExhaustion:
    def test_budget_exhausted_status(self, tmp_path: Path) -> None:
        agent = _make_agent(responses=[_LOW_RESPONSE] * 10, workspace_dir=str(tmp_path), budget=3)
        result = asyncio.run(agent.run("Generate"))
        assert "budget_exhausted" in result

    def test_exactly_budget_llm_calls(self, tmp_path: Path) -> None:
        agent = _make_agent(responses=[_LOW_RESPONSE] * 10, workspace_dir=str(tmp_path), budget=3)
        asyncio.run(agent.run("Generate"))
        assert cast(MagicMock, agent.llm.complete).call_count == 3

    def test_partial_files_written_on_exhaustion(self, tmp_path: Path) -> None:
        """Even when budget is exhausted, the last iteration's files must be written."""
        agent = _make_agent(responses=[_LOW_RESPONSE] * 5, budget=2, workspace_dir=str(tmp_path))
        asyncio.run(agent.run("Generate"))
        # _LOW_RESPONSE has a file spec for axi_burst_seq.sv
        written = list(tmp_path.rglob("*.sv"))
        assert len(written) == 1


# ---------------------------------------------------------------------------
# File writing
# ---------------------------------------------------------------------------


class TestFileWriting:
    def test_files_written_to_workspace(self, tmp_path: Path) -> None:
        agent = _make_agent(responses=[_HIGH_RESPONSE], workspace_dir=str(tmp_path))
        asyncio.run(agent.run("Generate"))
        written = list(tmp_path.rglob("*.sv"))
        assert len(written) == 1
        assert "axi_burst_seq" in written[0].read_text()

    def test_report_lists_written_files(self, tmp_path: Path) -> None:
        agent = _make_agent(responses=[_HIGH_RESPONSE], workspace_dir=str(tmp_path))
        result = asyncio.run(agent.run("Generate"))
        assert "axi_burst_seq.sv" in result

    def test_nested_directories_created(self, tmp_path: Path) -> None:
        specs = [FileSpec(path="a/b/c/deep.sv", content="class deep; endclass")]
        agent = _make_agent(responses=[], workspace_dir=str(tmp_path))
        agent._write_files(specs, str(tmp_path))
        assert (tmp_path / "a" / "b" / "c" / "deep.sv").exists()

    def test_write_files_returns_paths(self, tmp_path: Path) -> None:
        specs = [
            FileSpec(path="seq_a.sv", content="class a; endclass"),
            FileSpec(path="seq_b.sv", content="class b; endclass"),
        ]
        agent = _make_agent(responses=[], workspace_dir=str(tmp_path))
        written = agent._write_files(specs, str(tmp_path))
        assert len(written) == 2


# ---------------------------------------------------------------------------
# Task parsing
# ---------------------------------------------------------------------------


class TestTaskParsing:
    def test_accepts_code_task_directly(self, tmp_path: Path) -> None:
        task = CodeTask(task_id="t1", description="do x")
        parsed = CodeGeneratorAgent._parse_task(task)
        assert parsed.task_id == "t1"

    def test_accepts_plain_string(self, tmp_path: Path) -> None:
        parsed = CodeGeneratorAgent._parse_task("Generate a sequence")
        assert parsed.task_id == "codegen_task"
        assert parsed.description == "Generate a sequence"


# ---------------------------------------------------------------------------
# Prompt loader fallback
# ---------------------------------------------------------------------------


class TestPromptLoaderFallback:
    def test_uses_fallback_prompt_when_no_md(self, tmp_path: Path) -> None:
        """Agent must NOT raise when code_generator.tmpl.md is absent."""
        agent = _make_agent(responses=[_HIGH_RESPONSE], workspace_dir=str(tmp_path))
        # prompts_dir defaults to package location which may not have .tmpl.md in test env
        # Patch PromptLoader.load to raise FileNotFoundError
        with patch(
            "dv_agentic.agents.code_generator.PromptLoader.load",
            side_effect=FileNotFoundError("no .tmpl.md"),
        ):
            result = asyncio.run(agent.run("Generate a sequence"))
        assert "pass" in result  # still completes using fallback prompt

    def test_uses_loader_when_md_present(self, tmp_path: Path) -> None:
        """When a .tmpl.md file exists, PromptLoader.load must be called."""
        md = tmp_path / "code_generator.tmpl.md"
        md.write_text("# Code Generator\nGenerate SV/UVM code.\n\n### Compile Confidence\n")
        agent = _make_agent(responses=[_HIGH_RESPONSE], workspace_dir=str(tmp_path))
        agent.prompts_dir = tmp_path
        with patch(
            "dv_agentic.agents.code_generator.PromptLoader.load",
            return_value="enriched prompt",
        ) as mock_load:
            asyncio.run(agent.run("Generate"))
        mock_load.assert_called_once_with("code_generator")
