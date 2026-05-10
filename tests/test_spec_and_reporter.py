"""Unit tests for SpecAnalystAgent and ReporterAgent (Phase 3b)."""

import asyncio
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock

from dv_agentic.agents.base import AgentConfig
from dv_agentic.agents.reporter import ReporterAgent
from dv_agentic.agents.spec_analyst import SpecAnalystAgent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VPLAN_YAML = """\
features:
  - name: axi_write_burst
    description: Verify AXI write burst transactions up to max length
    priority: mandatory
    bins:
      - single_beat
      - max_burst_256
      - back_pressure
  - name: axi_read_response
    description: Verify all AXI read response codes
    priority: mandatory
    bins:
      - okay
      - slverr
      - decerr
"""

_VPLAN_RESPONSE = f"""\
I have analysed the specification and identified 2 mandatory features.

```yaml
{_VPLAN_YAML}```

The plan covers all transaction types described in sections 3.1-3.4.
"""

_NO_YAML_RESPONSE = "I need more context about the protocol before generating the vplan."

_REPORT_RESPONSE = """\
## Summary
Session completed successfully. Coverage increased from 73% to 91%.

## Simulation Results
| Test | Status | Seed |
|------|--------|------|
| axi_burst_test | PASS | 42 |

## Issues Found
None.

## Recommended Next Steps
Merge ai-task/cov_fix_001 branch after review.
"""


def _make_spec_agent(
    responses: list[str], output_path: str | None = None, budget: int = 5
) -> SpecAnalystAgent:
    llm = MagicMock()
    llm.complete = AsyncMock(side_effect=responses)
    return SpecAnalystAgent(
        config=AgentConfig(name="spec_analyst", budget=budget),
        llm=llm,
        output_path=output_path,
    )


def _make_reporter(responses: list[str], output_path: str | None = None) -> ReporterAgent:
    llm = MagicMock()
    llm.complete = AsyncMock(side_effect=responses)
    return ReporterAgent(
        config=AgentConfig(name="reporter", budget=5),
        llm=llm,
        output_path=output_path,
    )


# ===========================================================================
# SpecAnalystAgent
# ===========================================================================


class TestSpecAnalystYAMLExtraction:
    def setup_method(self) -> None:
        self.agent = _make_spec_agent(responses=[])

    def test_yaml_extracted_from_fenced_block(self) -> None:
        yaml = self.agent._extract_yaml(_VPLAN_RESPONSE)
        assert "features:" in yaml
        assert "axi_write_burst" in yaml

    def test_no_yaml_returns_empty(self) -> None:
        yaml = self.agent._extract_yaml("No yaml here.")
        assert yaml == ""

    def test_yml_extension_also_accepted(self) -> None:
        resp = "```yml\nfeatures:\n  - name: foo\n```"
        yaml = self.agent._extract_yaml(resp)
        assert "features:" in yaml


class TestSpecAnalystRun:
    def test_pass_on_first_yaml(self) -> None:
        agent = _make_spec_agent([_VPLAN_RESPONSE])
        result = asyncio.run(agent.run("AXI spec text..."))
        assert "feature_count" in result
        assert "2" in result

    def test_retry_when_no_yaml_first(self) -> None:
        agent = _make_spec_agent([_NO_YAML_RESPONSE, _VPLAN_RESPONSE])
        result = asyncio.run(agent.run("spec"))
        assert "feature_count" in result
        assert cast(MagicMock, agent.llm.complete).call_count == 2

    def test_follow_up_message_asks_for_yaml(self) -> None:
        histories: list[list[dict[str, str]]] = []

        async def spy(system: str, messages: list[dict[str, str]], max_tokens: int = 1000) -> str:
            histories.append(list(messages))
            return _NO_YAML_RESPONSE if len(histories) < 2 else _VPLAN_RESPONSE

        agent = _make_spec_agent([])
        cast(MagicMock, agent.llm.complete).side_effect = spy
        asyncio.run(agent.run("spec"))

        last_user = next(m["content"] for m in reversed(histories[1]) if m["role"] == "user")
        assert "yaml" in last_user.lower()

    def test_budget_exhausted_returns_empty_vplan(self) -> None:
        agent = _make_spec_agent([_NO_YAML_RESPONSE] * 10, budget=3)
        result = asyncio.run(agent.run("spec"))
        assert "Budget exhausted" in result or "feature_count : 0" in result

    def test_writes_vplan_to_disk(self, tmp_path: Path) -> None:
        out = str(tmp_path / ".agent" / "vplan.yaml")
        agent = _make_spec_agent([_VPLAN_RESPONSE], output_path=out)
        asyncio.run(agent.run("spec"))
        assert (tmp_path / ".agent" / "vplan.yaml").exists()
        content = (tmp_path / ".agent" / "vplan.yaml").read_text()
        assert "axi_write_burst" in content

    def test_skip_write_when_output_path_none(self, tmp_path: Path) -> None:
        agent = _make_spec_agent([_VPLAN_RESPONSE], output_path=None)
        result = asyncio.run(agent.run("spec"))
        assert "(not written)" in result


# ===========================================================================
# ReporterAgent
# ===========================================================================


class TestReporterRun:
    def test_returns_markdown(self) -> None:
        agent = _make_reporter([_REPORT_RESPONSE])
        result = asyncio.run(agent.run("session results..."))
        assert "## Summary" in result
        assert "Coverage" in result

    def test_single_llm_call(self) -> None:
        agent = _make_reporter([_REPORT_RESPONSE])
        asyncio.run(agent.run("results"))
        assert cast(MagicMock, agent.llm.complete).call_count == 1

    def test_writes_report_to_disk(self, tmp_path: Path) -> None:
        out = str(tmp_path / "report.md")
        agent = _make_reporter([_REPORT_RESPONSE], output_path=out)
        asyncio.run(agent.run("results"))
        assert (tmp_path / "report.md").exists()
        assert "Summary" in (tmp_path / "report.md").read_text()

    def test_task_id_extracted_from_input(self) -> None:
        agent = _make_reporter([_REPORT_RESPONSE])
        task_id = agent._extract_task_id("task_id: cov_fix_001\nresults here")
        assert task_id == "cov_fix_001"

    def test_task_id_fallback(self) -> None:
        agent = _make_reporter([_REPORT_RESPONSE])
        task_id = agent._extract_task_id("no id in here")
        assert task_id == "session"

    def test_output_path_with_task_id_template(self, tmp_path: Path) -> None:
        out = str(tmp_path / "{task_id}_report.md")
        agent = _make_reporter([_REPORT_RESPONSE], output_path=out)
        asyncio.run(agent.run("task_id: t001\nresults"))
        assert (tmp_path / "t001_report.md").exists()

    def test_skip_write_when_output_path_none(self) -> None:
        agent = _make_reporter([_REPORT_RESPONSE], output_path=None)
        result = asyncio.run(agent.run("results"))
        assert result  # still returns content
