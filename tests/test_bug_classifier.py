# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Unit tests for BugClassifierAgent (Phase 3b)."""

import asyncio
from typing import cast
from unittest.mock import AsyncMock, MagicMock

from dv_agentic.agents.base import AgentConfig
from dv_agentic.agents.bug_classifier import BugClassifierAgent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TB_RESPONSE = """\
BUG_TYPE: TB_BUG
CONFIDENCE: 0.92
EVIDENCE:
- Scoreboard expected value hardcoded to 0xAA, does not match DUT output
- RTL waveform shows correct data; monitor captures wrong byte lane
- No RTL ECO in this revision; same test passed in previous regression

### Summary
The testbench monitor is sampling the wrong byte lane.
The RTL output is correct per the spec.
"""

_RTL_RESPONSE = """\
BUG_TYPE: RTL_BUG
CONFIDENCE: 0.85
EVIDENCE:
- AXI BRESP shows SLVERR on all write transactions above 256-byte boundary
- Spec section 3.4 mandates OKAY for legal burst lengths
- Identical failure reproduced with two independent testbench configurations

### Summary
RTL does not handle burst transactions crossing a 256-byte boundary correctly.
"""

_LOW_CONFIDENCE_RESPONSE = """\
BUG_TYPE: TB_BUG
CONFIDENCE: 0.40
EVIDENCE:
- Limited log information available

### Summary
Cannot determine root cause with confidence from the current log.
"""

_HIGH_AFTER_RETRY = """\
BUG_TYPE: RTL_BUG
CONFIDENCE: 0.88
EVIDENCE:
- Additional signals confirmed RTL state machine stalls on back-pressure

### Summary
RTL bug confirmed after re-analysing back-pressure signals.
"""


def _make_agent(
    responses: list[str], threshold: float = 0.75, budget: int = 5
) -> BugClassifierAgent:
    llm = MagicMock()
    llm.complete = AsyncMock(side_effect=responses)
    return BugClassifierAgent(
        config=AgentConfig(name="bug_clf", budget=budget),
        llm=llm,
        confidence_threshold=threshold,
    )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


class TestParseResponse:
    def setup_method(self) -> None:
        self.agent = _make_agent(responses=[])

    def test_tb_bug_extracted(self) -> None:
        r = self.agent._parse_response(_TB_RESPONSE, 1)
        assert r.bug_type == "TB_BUG"

    def test_rtl_bug_extracted(self) -> None:
        r = self.agent._parse_response(_RTL_RESPONSE, 1)
        assert r.bug_type == "RTL_BUG"

    def test_confidence_extracted(self) -> None:
        r = self.agent._parse_response(_TB_RESPONSE, 1)
        assert abs(r.confidence - 0.92) < 0.001

    def test_confidence_percentage_normalised(self) -> None:
        # Some LLMs return 92 instead of 0.92
        resp = "BUG_TYPE: TB_BUG\nCONFIDENCE: 92\n### Summary\nok"
        r = self.agent._parse_response(resp, 1)
        assert abs(r.confidence - 0.92) < 0.001

    def test_evidence_extracted(self) -> None:
        r = self.agent._parse_response(_TB_RESPONSE, 1)
        assert len(r.evidence) == 3
        assert any("byte lane" in e for e in r.evidence)

    def test_summary_extracted(self) -> None:
        r = self.agent._parse_response(_TB_RESPONSE, 1)
        assert "monitor" in r.summary.lower()

    def test_unknown_when_no_bug_type(self) -> None:
        r = self.agent._parse_response("No structured output here.", 1)
        assert r.bug_type == "UNKNOWN"
        assert r.confidence == 0.0

    def test_requires_review_when_low_confidence(self) -> None:
        r = self.agent._parse_response(_LOW_CONFIDENCE_RESPONSE, 1)
        assert r.requires_human_review is True

    def test_no_review_when_high_confidence(self) -> None:
        r = self.agent._parse_response(_TB_RESPONSE, 1)
        assert r.requires_human_review is False


# ---------------------------------------------------------------------------
# Multi-turn loop
# ---------------------------------------------------------------------------


class TestMultiTurnLoop:
    def test_pass_on_first_high_confidence(self) -> None:
        agent = _make_agent([_TB_RESPONSE])
        result = asyncio.run(agent.run("UVM_ERROR: scoreboard mismatch"))
        assert "TB_BUG" in result
        assert cast(MagicMock, agent.llm.complete).call_count == 1

    def test_retry_on_low_confidence(self) -> None:
        agent = _make_agent([_LOW_CONFIDENCE_RESPONSE, _HIGH_AFTER_RETRY])
        result = asyncio.run(agent.run("UVM_ERROR: back-pressure stall"))
        assert "RTL_BUG" in result
        assert cast(MagicMock, agent.llm.complete).call_count == 2

    def test_follow_up_message_references_confidence(self) -> None:
        histories: list[list[dict[str, str]]] = []

        async def spy(system: str, messages: list[dict[str, str]], max_tokens: int = 1000) -> str:
            histories.append(list(messages))
            return _LOW_CONFIDENCE_RESPONSE if len(histories) < 2 else _TB_RESPONSE

        agent = _make_agent([])
        cast(MagicMock, agent.llm.complete).side_effect = spy
        asyncio.run(agent.run("failure log"))

        # Second call's last user message should mention confidence
        last_user = next(m["content"] for m in reversed(histories[1]) if m["role"] == "user")
        assert "confidence" in last_user.lower() or "threshold" in last_user.lower()


# ---------------------------------------------------------------------------
# Budget exhaustion
# ---------------------------------------------------------------------------


class TestBudgetExhaustion:
    def test_requires_review_on_budget_exhausted(self) -> None:
        agent = _make_agent([_LOW_CONFIDENCE_RESPONSE] * 10, budget=3)
        result = asyncio.run(agent.run("failure"))
        assert "YES" in result  # human_review: YES

    def test_exactly_budget_calls(self) -> None:
        agent = _make_agent([_LOW_CONFIDENCE_RESPONSE] * 10, budget=3)
        asyncio.run(agent.run("failure"))
        assert cast(MagicMock, agent.llm.complete).call_count == 3

    def test_review_reason_mentions_threshold(self) -> None:
        agent = _make_agent([_LOW_CONFIDENCE_RESPONSE] * 10, budget=2)
        result = asyncio.run(agent.run("failure"))
        assert "threshold" in result.lower() or "below" in result.lower()


# ---------------------------------------------------------------------------
# Output format
# ---------------------------------------------------------------------------


class TestOutputFormat:
    def test_to_str_contains_sections(self) -> None:
        agent = _make_agent([_TB_RESPONSE])
        result = asyncio.run(agent.run("failure"))
        assert "### Bug Classification" in result
        assert "TB_BUG" in result
        assert "### Summary" in result

    def test_evidence_listed_in_output(self) -> None:
        agent = _make_agent([_TB_RESPONSE])
        result = asyncio.run(agent.run("failure"))
        assert "byte lane" in result

    def test_custom_threshold(self) -> None:
        # Threshold 0.95 → 0.92 confidence is still too low → budget exhausted → human review
        agent = _make_agent([_TB_RESPONSE], threshold=0.95, budget=1)
        result = asyncio.run(agent.run("failure"))
        assert "YES" in result  # requires human review
