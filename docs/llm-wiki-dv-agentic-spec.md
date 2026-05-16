# LLM Wiki × DV Agentic System Integration Design Specification

**Version**: 1.0.0
**Status**: Published (v0.7.0 implementation complete)
**Date**: 2026-05-11
**Updated**: 2026-05-16
**Audience**: DV Agentic System Development Team

---

## Table of Contents

1. [Background and Motivation](#1-background-and-motivation)
2. [Search-First Research Summary](#2-search-first-research-summary)
3. [Decision Matrix](#3-decision-matrix)
4. [Architecture Design](#4-architecture-design)
5. [Directory Structure Specification](#5-directory-structure-specification)
6. [Data Model Specification](#6-data-model-specification)
7. [Core Component Specification](#7-core-component-specification)
8. [Agent Integration Specification](#8-agent-integration-specification)
9. [PromptLoader Extension Specification](#9-promptloader-extension-specification)
10. [CLI Extension Specification](#10-cli-extension-specification)
11. [Wiki Page Schema](#11-wiki-page-schema)
12. [Search Layer Specification](#12-search-layer-specification)
13. [Phased Implementation Plan](#13-phased-implementation-plan)
14. [Test Strategy](#14-test-strategy)
15. [Anti-Patterns and Prohibitions](#15-anti-patterns-and-prohibitions)

---

## 1. Background and Motivation

### 1.1 Current Pain Points

The DV Agentic System currently starts from scratch each session. Accumulated verification knowledge is lost in three ways:

| Loss Type | Manifestation | Impact |
|-----------|---------------|--------|
| **Session Reset** | BugClassifier re-analyzes the same error codes every time | Repeatedly consumes token budget |
| **Knowledge Gap** | LogAnalyzer has no memory of known `missing_timescale` patterns | Cannot leverage historical insights |
| **Pattern Drift** | OrchestratorAgent cannot detect cross-session bug trends | Misses systemic issues |

### 1.2 Problem Solved by the LLM Wiki Pattern

The core insight of the LLM Wiki pattern (Andrej Karpathy, 2025): **knowledge should be compiled at write time, not re-derived on every query**.

```
Traditional RAG Pattern (Current State):
  Each session → reasoning from scratch → insights lost in chat history

LLM Wiki Pattern (Target):
  Each session → results archived to wiki → knowledge compounds
  Next session → wiki provides prior knowledge → faster convergence → results re-archived
```

### 1.3 Design Principles

This specification adheres to the core principles of `AGENTS.md`:

- **Simplicity First**: wiki is pure Markdown files, no external database service required
- **Surgical Changes**: no modification to existing Agent logic; knowledge is injected via `PromptLoader`
- **Goal-Driven**: every wiki page must be traceable to a specific DV task output

---

## 2. Search-First Research Summary

### 2.1 Research Scope

Research conducted covering the following requirements:
- Local Markdown search engine (BM25 + semantic search)
- Agent persistent memory frameworks
- Knowledge base version control patterns
- Air-gapped environment compatibility

### 2.2 Candidate Tool Evaluation

| Tool | Type | License | Air-gapped | Python | Score |
|------|------|---------|------------|--------|-------|
| **bm25s** | Search engine | MIT | ✅ Pure Python | ✅ | 9/10 |
| **qmd (Python)** | Search engine | MIT | ⚠️ Requires model download | ✅ | 7/10 |
| **MEM.md pattern** | Architecture pattern | — | ✅ | N/A | Reference |
| **memsearch** | Full framework | Apache 2.0 | ❌ Requires Milvus | ✅ | 5/10 |
| **swarmvault** | Full framework | MIT | ⚠️ | ❌ (Node) | 4/10 |
| **DiffMem** | Git-based | MIT | ✅ | ✅ | 6/10 |
| **agentmemory** | Full framework | MIT | ⚠️ | ❌ (Node) | 4/10 |

### 2.3 Key Findings

**bm25s is the best choice for air-gapped environments:**
- Pure Python, no Java/PyTorch dependencies
- Sparse matrix-based, orders of magnitude faster than `rank-bm25`
- `pip install "bm25s[core]"` works fully offline
- Supports index persistence (`retriever.save()`)

**MEM.md pattern provides the architectural blueprint:**
- Bootstrap file (`MEM.md`) tells the Agent how to load knowledge
- Knowledge stored as Markdown, human-readable and Git-trackable
- Compatible with any AI tool that can read Markdown

**DiffMem's git-native insight:**
- Uses `git log`, `git diff`, `git blame` for temporal reasoning
- "Current state" and "historical evolution" stored separately to avoid context bloat

---

## 3. Decision Matrix

### 3.1 Search Backend

| Condition | Action | Notes |
|-----------|--------|-------|
| Air-gapped RHEL 8.4 (Internal) | **Adopt bm25s** | Pure Python, no external dependencies |
| Network-connected (External) | **Adopt qmd[mcp]** | BM25 + vector + LLM reranking |
| Scale > 1000 pages | **Upgrade to qmd** | Better semantic search quality |

**Final decision**: Phase A adopts `bm25s` (keyword search) as an optional extra dependency; architecture reserves the `qmd` upgrade path.

### 3.2 Storage Backend

| Condition | Action |
|-----------|--------|
| Task state and history trail | **tasks/{task_id}.yaml** (Git-tracked, plain text, no SQLite dependency) |
| Wiki content | **Git-versioned Markdown**, human-readable and reviewable |
| Search index | **bm25s persistent index** (`.agent/wiki/.search_index/`) |

### 3.3 Architecture Pattern

| Pattern | Adopted | Notes |
|---------|---------|-------|
| MEM.md bootstrap | ✅ Adopted | Using `wiki/WIKI.md` as knowledge base schema declaration |
| DiffMem git-native | ✅ Partially adopted | `log.md` as append-only operation log |
| Karpathy LLM Wiki | ✅ Core architecture | Strict three-layer separation (raw / wiki / schema) |
| Vector embedding | ❌ Not in Phase A | Avoids model dependencies in air-gapped environments |

---

## 4. Architecture Design

### 4.1 Three-Layer Architecture Mapping

```
┌──────────────────────────────────────────────────────────────────────┐
│                         SCHEMA LAYER                                 │
│  .agent/wiki/WIKI.md          ← Wiki structure declaration & naming  │
│  project.yaml                 ← Existing (controls wiki integration) │
│  PromptLoader                 ← Injects wiki knowledge into system   │
│                                  prompt                              │
├──────────────────────────────────────────────────────────────────────┤
│                         WIKI LAYER                                   │
│  .agent/wiki/                 ← LLM-maintained Markdown knowledge    │
│  ├── index.md                 ← Table of contents (LLM-updated)      │
│  ├── log.md                   ← Append-only operation log            │
│  ├── bugs/                    ← Bug knowledge pages                  │
│  ├── patterns/                ← Error pattern knowledge pages        │
│  ├── coverage/                ← Coverage hole analysis pages         │
│  └── specs/                   ← Spec interpretation notes            │
├──────────────────────────────────────────────────────────────────────┤
│                       RAW SOURCE LAYER                               │
│  Simulation logs              ← Immutable, generated by SimController│
│  Coverage reports             ← Immutable, generated by              │
│                                  IMCAdapter/PyuvmAdapter             │
│  Spec PDFs                    ← Immutable, processed by SpecAnalyst  │
│  .agent/tasks/{task_id}.yaml  ← Existing task records                │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.2 Knowledge Flow Diagram

```
Simulation Run (SimController)
        │
        ▼
Log Analysis (LogAnalyzer)  ───────────────────────────┐
        │                                              │
        ▼                                              ▼
Bug Classification (BugClassifier)           WikiIngestService
        │                                     ├── Update patterns/*.md
        ▼                                     ├── Update bugs/*.md (if new bug)
Coverage Analysis (CoverageAnalyst)           ├── Update coverage/*.md
        │                                     └── Append to log.md
        ▼
Reporter (generates Markdown report)
        │
        ├────────────────────────────────────────────────────────────┐
        │ Existing: outputs report to humans                         │
        └──► New: triggers WikiIngestService._ingest_session_report()│
                                                                     │
        ┌────────────────────────────────────────────────────────────┘
        ▼
Next Session Start
        │
        ▼
WikiQueryService (called by PromptLoader)
        │  Queries wiki/patterns/, wiki/bugs/
        ▼
PromptLoader._load_wiki_context()
        │  Fills {{KNOWN_ERROR_PATTERNS}}, {{KNOWN_RTL_BUGS}},
        │  and other placeholders
        ▼
LLM's system prompt automatically carries accumulated knowledge
```

### 4.3 Existing System Integration Points (Non-Breaking)

```
No existing Agent logic is modified. Integration is achieved via three seam points:

Seam 1: After ReporterAgent.run() completes
  → Triggers WikiIngestService (non-blocking, asyncio.to_thread)

Seam 2: PromptLoader._gather_context()
  → Adds _load_wiki_context(wiki_dir) method
  → Injects wiki knowledge via existing placeholder {{KNOWN_ERROR_PATTERNS}}

Seam 3: config_loader.ProjectLoader._build_context()
  → Parses new wiki.enabled field in project.yaml
  → Determines whether to enable wiki integration
```

---

## 5. Directory Structure Specification

### 5.1 Complete Directory Tree

```
{project}/.agent/
│
├── project.yaml                    ← Existing (new wiki: block added)
├── vplan.yaml                      ← Existing, unchanged
│
├── wiki/                           ← New: knowledge base root (git-tracked)
│   │
│   ├── WIKI.md                     ← Schema declaration (bootstrap file)
│   ├── index.md                    ← All-pages index (LLM updates after every ingest)
│   ├── log.md                      ← Append-only operation log (never deleted)
│   │
│   ├── bugs/                       ← Bug knowledge pages
│   │   ├── _index.md               ← bugs/ sub-index
│   │   ├── RTL_{date}_{id}.md      ← Each confirmed RTL bug
│   │   └── TB_{date}_{id}.md       ← Each confirmed TB bug
│   │
│   ├── patterns/                   ← Error pattern knowledge pages (corresponds to LogAnalyzer._PATTERNS)
│   │   ├── _index.md               ← patterns/ sub-index
│   │   ├── missing_timescale.md    ← compile_error subtype
│   │   ├── unmatched_block.md
│   │   ├── mixed_assignment.md
│   │   ├── multiple_drivers.md
│   │   ├── width_mismatch.md
│   │   ├── interface_mismatch.md
│   │   ├── scoreboard_fail.md      ← sim_error subtype
│   │   ├── coverage_miss.md
│   │   ├── timing_offset.md
│   │   └── protocol_violation.md
│   │
│   ├── coverage/                   ← Coverage hole analysis pages
│   │   ├── _index.md
│   │   └── {feature}_{bin}.md      ← One page per actionable hole
│   │
│   └── specs/                      ← Spec interpretation supplementary notes
│       ├── _index.md
│       └── {feature}_clarification.md
│
├── tasks/                          ← Existing, unchanged
│   └── {task_id}.yaml
│
└── subagents/                      ← Existing, unchanged
    └── *.md
```

### 5.2 Naming Convention

| Page Type | Naming Rule | Example |
|-----------|-------------|---------|
| RTL Bug | `RTL_{YYYYMMDD}_{3-digit ID}.md` | `RTL_20260510_001.md` |
| TB Bug | `TB_{YYYYMMDD}_{3-digit ID}.md` | `TB_20260511_003.md` |
| Error pattern | `{failure_subtype}.md` (snake_case) | `missing_timescale.md` |
| Coverage hole | `{covergroup}_{bin}.md` | `axi_write_cov_back_pressure.md` |
| Spec clarification | `{feature}_clarification.md` | `axi_burst_len_clarification.md` |

---

## 6. Data Model Specification

### 6.1 WIKI.md (Bootstrap Schema Declaration)

```markdown
# DV Agentic Wiki Schema

## Purpose
This wiki is the persistent, compounding knowledge base for the DV verification
project. It is maintained by LLM agents and reviewed by human engineers.

## Structure
- bugs/      : Confirmed TB and RTL bugs with evidence and resolution status
- patterns/  : Known failure patterns with regex signatures and fix templates
- coverage/  : Coverage hole analysis and filling history
- specs/     : Spec clarifications and vplan amendments

## Update Protocol
Agents MUST update this wiki after every completed session via WikiIngestService.
Agents MUST read relevant wiki pages before classifying a new failure.
Humans MUST review bugs/ entries before RTL ECO is filed.

## Citation Format
Every claim in a wiki page must cite a source:
  (source: tasks/{task_id}.yaml | sim log: sim_{test}_{seed}.log)

## Index Maintenance
index.md and all _index.md files are updated atomically with each wiki write.
```

### 6.2 Bug Knowledge Page Format

```markdown
---
id: RTL_20260510_001
type: RTL_BUG        # RTL_BUG | TB_BUG
status: open         # open | confirmed | closed | wont_fix
confidence: 0.92
first_seen: 2026-05-10
last_updated: 2026-05-11
task_ids:
  - cov_fix_001
  - regression_debug_042
error_class: uvm_error
failure_subtype: protocol_violation
ip_type: axi
spec_section: "3.4.2"
---

# RTL Bug: AXI SLVERR on 256-byte Boundary Write

## Symptom
AXI BRESP shows SLVERR on all write transactions crossing a 256-byte address
boundary, regardless of AWLEN value.

## Evidence
- BRESP = 2'b10 observed at sim time 1024ns for AWADDR=0xFF00, AWLEN=0x0F
- TB stimulus is legal per spec section 3.4.1 (INCR burst, aligned address)
- Failure reproduced across seeds: 42, 137, 891 (deterministic, not flaky)
- Identical TB with AWADDR=0xFE00 passes (no boundary crossing)

## Classification Rationale
RTL_BUG because: stimulus is legal, TB generates correct AWVALID/WVALID
sequences, and failure is seed-independent. The 256-byte boundary is a
hardware address decode issue, not a testbench problem.

## Related Patterns
- See: patterns/protocol_violation.md

## Resolution
- [ ] RTL ECO ticket filed: pending human confirmation
- [ ] Workaround: constrain AWADDR to avoid 256-byte boundaries in interim

## Citation
(source: tasks/regression_debug_042.yaml | log: sim_axi_burst_test_42.log)
```

### 6.3 Error Pattern Knowledge Page Format

```markdown
---
pattern_id: missing_timescale
error_class: compile_error
failure_subtype: missing_timescale
hit_count: 7
first_seen: 2026-04-20
last_seen: 2026-05-10
fix_success_rate: 1.0
---

# Pattern: missing_timescale

## Description
`timescale` declaration missing at the top of a newly generated SV file.
This is the most common compile error produced by CodeGeneratorAgent.

## Detection Signature
```
*E,NOTIME.*`timescale not defined
```

## Fix Template
Add to line 1 of every generated SV file:
```systemverilog
`timescale 1ns/1ps
```

## Code Generator Self-Review Checklist Update
When this pattern is matched, remind CodeGeneratorAgent:
> "Check: `timescale 1ns/1ps` must be the first line of every new .sv file."

## Resolution History
| Date | Task | Fix Applied | Result |
|------|------|-------------|--------|
| 2026-04-20 | cov_fix_001 | Added timescale | PASS |
| 2026-04-28 | tb_fix_007 | Added timescale | PASS |
| 2026-05-10 | cov_fix_042 | Added timescale | PASS |

## Citation
(sources: tasks/cov_fix_001.yaml, tasks/tb_fix_007.yaml, tasks/cov_fix_042.yaml)
```

### 6.4 log.md Format

```markdown
# DV Agentic Wiki Operation Log

Each entry format: ## [{ISO date}] {operation type} | {task ID} | {result}

## [2026-05-11] ingest | cov_fix_001 | TB_BUG resolved
- error_class: compile_error
- failure_subtype: missing_timescale
- resolution: Added `timescale 1ns/1ps to line 1 of tb/sequences/axi_burst_seq.sv
- wiki_pages_updated:
    - patterns/missing_timescale.md (hit_count: 6→7)
    - bugs/TB_20260511_003.md (new)
    - index.md (updated)
    - log.md (this entry)

## [2026-05-10] lint | — | 3 issues found
- orphan_pages: coverage/old_bin.md (no inbound links)
- stale_claims: bugs/RTL_20260401_001.md (newer log contradicts BRESP claim)
- missing_pages: patterns/width_mismatch.md (referenced but not created)
- action: human review required for stale_claims
```

### 6.5 index.md Format

```markdown
# DV Agentic Wiki Index

Last updated: 2026-05-11T14:32:00Z | Total pages: 23

## Bugs (5 pages)
| Page | Type | Status | Confidence | Last Updated |
|------|------|--------|------------|--------------|
| [RTL_20260510_001](bugs/RTL_20260510_001.md) | RTL_BUG | open | 0.92 | 2026-05-11 |
| [TB_20260511_003](bugs/TB_20260511_003.md) | TB_BUG | closed | 0.88 | 2026-05-11 |

## Patterns (10 pages)
| Page | failure_subtype | hit_count | fix_success_rate |
|------|----------------|-----------|-----------------|
| [missing_timescale](patterns/missing_timescale.md) | missing_timescale | 7 | 100% |
| [unmatched_block](patterns/unmatched_block.md) | unmatched_block | 3 | 100% |
| [scoreboard_fail](patterns/scoreboard_fail.md) | scoreboard_fail | 2 | 50% |

## Coverage (5 pages)
| Page | Feature | Bin | Status |
|------|---------|-----|--------|
| [axi_write_back_pressure](coverage/axi_write_cov_back_pressure.md) | axi_write | back_pressure | filled |

## Specs (3 pages)
| Page | Feature | Clarification Type |
|------|---------|-------------------|
| [axi_burst_len_clarification](specs/axi_burst_len_clarification.md) | AXI burst | Ambiguous spec |
```

---

## 7. Core Component Specification

### 7.1 WikiManager (New Module)

**Location**: `src/dv_agentic/wiki/manager.py`

```python
"""DV Agentic Wiki Manager — knowledge base read/write core.

Three public services:
  WikiIngestService  — archives session results to wiki
  WikiQueryService   — queries wiki pages (for PromptLoader use)
  WikiLintService    — periodically checks wiki consistency

Design principles:
  - All write operations use atomic_write() to ensure no partial writes
  - Search index stays in sync with Markdown content (write-through)
  - All operations are logged to log.md (append-only)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class WikiConfig:
    """Wiki integration settings (parsed from project.yaml).

    Attributes:
        enabled: Whether to enable wiki integration.
        wiki_dir: Path to the wiki root directory.
        max_context_tokens: Maximum token count injected into PromptLoader.
        auto_ingest: Whether to automatically trigger ingest after Reporter completes.
        search_backend: Search backend ("bm25" | "none").
    """
    enabled: bool = False
    wiki_dir: Path = Path(".agent/wiki")
    max_context_tokens: int = 2000
    auto_ingest: bool = True
    search_backend: str = "bm25"  # Phase A: bm25 only
```

### 7.2 WikiIngestService (New)

**Location**: `src/dv_agentic/wiki/ingest.py`

**Interface Specification**:

```python
class WikiIngestService:
    """Archives session results to wiki.

    When to call:
      - After ReporterAgent.run() completes (triggered by CLI or Orchestrator)
      - Can be called independently (CLI: python -m dv_agentic.cli.wiki_ingest)

    Side effects:
      - Updates wiki/{category}/*.md
      - Appends to wiki/log.md
      - Updates wiki/index.md and all _index.md files
      - Updates bm25 search index

    Never:
      - Modifies Raw Source (task records, simulation logs)
      - Deletes existing wiki pages (only updates or creates)
    """

    def __init__(self, wiki_config: WikiConfig, llm: BaseLLMClient) -> None: ...

    async def ingest_session(
        self,
        session_report: str,            # ReporterAgent output
        failure_summary: str | None,    # LogAnalyzerAgent output
        classification: str | None,     # BugClassifierAgent output
        coverage_summary: str | None,   # CoverageAnalystAgent output
        task_id: str,
    ) -> WikiIngestResult: ...

    async def ingest_pattern(
        self,
        failure_subtype: str,
        error_class: str,
        context_lines: list[str],
        fix_applied: str | None,
        success: bool,
        task_id: str,
    ) -> None:
        """Updates hit_count and fix history in patterns/{failure_subtype}.md."""
        ...

    async def ingest_bug(
        self,
        classification_result: ClassificationResult,
        evidence: list[str],
        task_id: str,
        log_path: str,
    ) -> str:
        """Creates or updates bugs/{type}_{date}_{id}.md, returns page path."""
        ...

    async def ingest_coverage_hole(
        self,
        covergroup: str,
        bin_name: str,
        action_class: str,   # "actionable" | "protocol_blocked" | "design_excluded"
        scenario: str,
        filled: bool,
        task_id: str,
    ) -> None:
        """Creates or updates coverage/{covergroup}_{bin}.md."""
        ...
```

**WikiIngestResult Data Structure**:

```python
@dataclass
class WikiIngestResult:
    task_id: str
    pages_created: list[str]    # Newly created page paths
    pages_updated: list[str]    # Updated page paths
    log_entry: str              # Text to be appended to log.md
    index_updated: bool
    search_index_updated: bool
```

### 7.3 WikiQueryService (New)

**Location**: `src/dv_agentic/wiki/query.py`

```python
class WikiQueryService:
    """Queries wiki knowledge for PromptLoader use.

    Query results are truncated to max_context_tokens,
    ensuring LLM context window limits are not exceeded.
    """

    def __init__(self, wiki_config: WikiConfig) -> None: ...

    def get_known_error_patterns(
        self,
        error_class: str | None = None,
        failure_subtype: str | None = None,
        top_k: int = 5,
    ) -> str:
        """Returns summary text of known error patterns, ready to inject into {{KNOWN_ERROR_PATTERNS}}."""
        ...

    def get_known_rtl_bugs(
        self,
        ip_type: str | None = None,
        status: str = "open",
        top_k: int = 5,
    ) -> str:
        """Returns summary of known RTL bugs, ready to inject into {{KNOWN_RTL_BUGS}}."""
        ...

    def get_coverage_history(
        self,
        covergroup: str | None = None,
        top_k: int = 5,
    ) -> str:
        """Returns coverage hole analysis history, ready to inject into {{COVERAGE_HOLE_HISTORY}}."""
        ...

    def search(
        self,
        query: str,
        category: str | None = None,  # "bugs" | "patterns" | "coverage" | None
        top_k: int = 5,
    ) -> list[WikiSearchResult]:
        """BM25 full-text search, returns list of relevant pages."""
        ...

    def get_pattern_page(self, failure_subtype: str) -> str | None:
        """Directly reads the pattern page for a specific subtype, for fast lookups."""
        ...
```

### 7.4 WikiLintService (New)

**Location**: `src/dv_agentic/wiki/lint.py`

```python
class WikiLintService:
    """Periodically checks wiki consistency.

    When triggered:
      - Every time an Orchestrator session starts (lightweight scan)
      - Manual CLI execution: python -m dv_agentic.cli.wiki_lint
      - Auto-triggered after more than N ingests have accumulated

    Check items:
      1. Orphan pages: pages that exist but are not recorded in index.md
      2. Broken links: Markdown links in pages pointing to non-existent pages
      3. Stale claims: bugs/ pages with first_seen > 90 days and still open
      4. Missing pages: pages mentioned in index.md but do not actually exist
      5. Uncited claims: pages with assertions but no (source: ...) citation
    """

    @dataclass
    class LintReport:
        orphan_pages: list[str]
        broken_links: list[tuple[str, str]]
        stale_open_bugs: list[str]
        missing_pages: list[str]
        uncited_claims: list[tuple[str, int]]  # (page, line_number)
        suggestions: list[str]   # Suggested new pages to create
        human_review_required: bool

    async def run(self, depth: str = "quick") -> LintReport:
        """depth: "quick" (scan wiki index only) | "full" (scan all page content)"""
        ...
```

### 7.5 WikiSearchIndex (New)

**Location**: `src/dv_agentic/wiki/search.py`

```python
"""BM25 search index wrapper layer.

Dependencies:
  Internal (air-gapped): bm25s[core] — pip install "bm25s[core]"
  External (with internet): qmd — pip install "qmd[mcp]" (optional upgrade path)

Designed to be replaceable (Strategy Pattern):
  WikiSearchIndex.create(backend="bm25")  → BM25SearchIndex
  WikiSearchIndex.create(backend="qmd")   → QMDSearchIndex (future)
"""

import abc
from pathlib import Path


class WikiSearchIndex(abc.ABC):
    """Abstract search index interface."""

    @abc.abstractmethod
    def build(self, wiki_dir: Path) -> None:
        """Rebuild index from wiki_dir."""

    @abc.abstractmethod
    def update(self, page_path: Path, content: str) -> None:
        """Incrementally update index for a single page."""

    @abc.abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """BM25 keyword search."""

    @classmethod
    def create(cls, backend: str, wiki_dir: Path) -> "WikiSearchIndex":
        if backend == "bm25":
            return BM25SearchIndex(wiki_dir)
        raise ValueError(f"Unknown backend: {backend}")


@dataclass
class SearchResult:
    page_path: str
    score: float
    excerpt: str        # First 200 characters
    frontmatter: dict   # YAML frontmatter parsed


class BM25SearchIndex(WikiSearchIndex):
    """Local search index implemented using bm25s.

    Index persisted to .agent/wiki/.search_index/
    Automatically calls update() after each ingest.
    """

    INDEX_DIR = ".search_index"

    def __init__(self, wiki_dir: Path) -> None:
        self.wiki_dir = wiki_dir
        self.index_path = wiki_dir / self.INDEX_DIR
        self._retriever: Any | None = None  # bm25s.BM25 instance

    def build(self, wiki_dir: Path) -> None:
        """Scans all .md files and builds index, saved to self.index_path."""
        try:
            import bm25s
        except ImportError as e:
            raise ImportError(
                "bm25s is required for wiki search. "
                "Install with: pip install 'bm25s[core]'"
            ) from e
        ...

    def update(self, page_path: Path, content: str) -> None:
        """Incremental update: if index does not exist, call build() first."""
        ...

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """BM25 search, returns top_k results."""
        ...
```

---

## 8. Agent Integration Specification

### 8.1 ReporterAgent Extension

**Modification scope**: minimal (only adds one optional async call at the end of `run()`)

```python
# src/dv_agentic/agents/reporter.py extension

class ReporterAgent(BaseAgent):

    def __init__(
        self,
        config: AgentConfig,
        llm: BaseLLMClient,
        output_path: str | None = None,
        wiki_config: WikiConfig | None = None,  # New (optional)
        ...
    ) -> None:
        ...
        self.wiki_config = wiki_config

    async def run(self, task_input: str) -> str:
        # ... existing logic unchanged ...
        result = report.to_str()

        # New: asynchronously triggers wiki ingest (non-blocking to main flow)
        if self.wiki_config and self.wiki_config.enabled and self.wiki_config.auto_ingest:
            asyncio.create_task(self._ingest_to_wiki(task_input, result))

        return result

    async def _ingest_to_wiki(self, session_input: str, session_report: str) -> None:
        """Archives this session's results to wiki in the background. Failures do not affect the main flow."""
        try:
            from ..wiki.manager import WikiIngestService
            ingest = WikiIngestService(self.wiki_config, self.llm)
            await ingest.ingest_session(
                session_report=session_report,
                failure_summary=None,   # Pass LogAnalyzer output if available in session
                classification=None,
                coverage_summary=None,
                task_id=self._extract_task_id(session_input),
            )
            logger.info("Wiki ingest completed for task '%s'", ...)
        except Exception:
            logger.exception("Wiki ingest failed (non-fatal)")
```

### 8.2 BugClassifierAgent Extension

**Modification scope**: minimal (queries wiki before classification to improve confidence)

```python
# src/dv_agentic/agents/bug_classifier.py extension

async def run(self, task_input: str) -> str:
    # New: queries wiki for similar bugs before classification
    wiki_context = self._load_wiki_context(task_input)
    if wiki_context:
        task_input = f"{task_input}\n\n---\n## Known Similar Bug Records\n{wiki_context}"

    # ... existing logic unchanged ...

def _load_wiki_context(self, failure_summary: str) -> str:
    """Tries to load relevant knowledge from wiki. Returns empty string silently on failure."""
    if not self.wiki_config or not self.wiki_config.enabled:
        return ""
    try:
        from ..wiki.query import WikiQueryService
        query_svc = WikiQueryService(self.wiki_config)
        return query_svc.search(failure_summary[:200], category="bugs", top_k=3)
    except Exception:
        return ""
```

### 8.3 OrchestratorAgent Extension

**Modification scope**: minimal (triggers lightweight lint at session start)

```python
# src/dv_agentic/agents/orchestrator.py extension

async def run(self, task_input: str) -> str:
    # New: runs quick wiki health check at session start (non-blocking)
    if self.wiki_config and self.wiki_config.enabled:
        asyncio.create_task(self._run_wiki_lint_quick())

    # ... existing logic unchanged ...

async def _run_wiki_lint_quick(self) -> None:
    """Quickly scans wiki index, logs but does not block main flow."""
    try:
        from ..wiki.lint import WikiLintService
        lint = WikiLintService(self.wiki_config)
        report = await lint.run(depth="quick")
        if report.human_review_required:
            logger.warning("Wiki lint: human review required — %d issues", ...)
    except Exception:
        pass
```

---

## 9. PromptLoader Extension Specification

### 9.1 New Placeholders

Three wiki-sourced placeholders added on top of the existing ones:

| Placeholder | Source | Injected Into |
|-------------|--------|---------------|
| `{{KNOWN_ERROR_PATTERNS}}` | Existing (static profile) → **changed to wiki-first** | log_analyzer, bug_classifier |
| `{{KNOWN_RTL_BUGS}}` | Existing (static profile) → **changed to wiki-first** | log_analyzer, bug_classifier |
| `{{COVERAGE_HOLE_HISTORY}}` | **New** (from wiki/coverage/) | coverage_analyst |
| `{{WIKI_PATTERN_SUMMARY}}` | **New** (from wiki/patterns/ statistics) | code_generator |

### 9.2 PromptLoader._gather_context() Extension

```python
# src/dv_agentic/prompts/prompt_loader.py extension

def _gather_context(self) -> dict[str, str]:
    """Existing logic unchanged; adds wiki context overlay at the end."""
    context = {}  # existing logic

    # New: Wiki context (takes priority over static profile)
    if self.wiki_config and self.wiki_config.enabled:
        wiki_ctx = self._load_wiki_context()
        # wiki knowledge overrides static profile knowledge (if wiki has content)
        for key, value in wiki_ctx.items():
            if value:  # Override only if wiki has content
                context[key] = value

    return context

def _load_wiki_context(self) -> dict[str, str]:
    """Loads all injectable knowledge from wiki. Returns empty dict silently on failure."""
    try:
        from ..wiki.query import WikiQueryService
        query = WikiQueryService(self.wiki_config)
        return {
            "KNOWN_ERROR_PATTERNS": query.get_known_error_patterns(top_k=5),
            "KNOWN_RTL_BUGS": query.get_known_rtl_bugs(top_k=5),
            "COVERAGE_HOLE_HISTORY": query.get_coverage_history(top_k=3),
            "WIKI_PATTERN_SUMMARY": query.get_pattern_summary(),
        }
    except Exception:
        logger.debug("Wiki context loading failed (non-fatal)", exc_info=True)
        return {}
```

---

## 10. CLI Extension Specification

### 10.1 New CLI Commands

```
python -m dv_agentic.cli.wiki_ingest   # Manually triggers ingest (accepts session report)
python -m dv_agentic.cli.wiki_lint     # Manually runs wiki health check
python -m dv_agentic.cli.wiki_search   # Search wiki
python -m dv_agentic.cli.wiki_build    # Rebuilds bm25 search index from scratch
```

### 10.2 wiki_search CLI

```bash
# Search error patterns
python -m dv_agentic.cli.wiki_search "timescale" --category patterns

# Search open RTL bugs
python -m dv_agentic.cli.wiki_search "SLVERR boundary" --category bugs

# Global search
python -m dv_agentic.cli.wiki_search "back pressure AXI"
```

### 10.3 New Fields in project.yaml

```yaml
# .agent/project.yaml — new wiki block

project:
  name: "sample_verify_project"
  environment: internal

composition:
  team: sample_team
  ip_types: [axi]
  simulator: xcelium
  coverage: imc

# New: wiki integration settings
wiki:
  enabled: true                    # Whether to enable (defaults to false, backward-compatible)
  wiki_dir: ".agent/wiki"         # wiki root directory
  max_context_tokens: 2000         # Maximum token count injected into prompt
  auto_ingest: true                # Auto-archive after Reporter completes
  search_backend: "bm25"          # "bm25" | "none"
  lint_on_startup: true            # Run quick lint when Orchestrator starts
  lint_interval_sessions: 10       # Trigger full lint every 10 sessions
```

---

## 11. Wiki Page Schema

### 11.1 Required YAML Frontmatter Fields (by page type)

**bugs/ pages**:
```yaml
---
id: {RTL|TB}_{YYYYMMDD}_{3-digit}
type: RTL_BUG | TB_BUG
status: open | confirmed | closed | wont_fix
confidence: 0.00–1.00
first_seen: YYYY-MM-DD
last_updated: YYYY-MM-DD
task_ids: [...]
error_class: {LogAnalyzer error_class}
failure_subtype: {LogAnalyzer failure_subtype}
ip_type: axi | pcie | ddr | custom
spec_section: "X.X.X"  # optional
---
```

**patterns/ pages**:
```yaml
---
pattern_id: {failure_subtype}
error_class: compile_error | uvm_error | uvm_fatal | ...
failure_subtype: {exactly matches LogAnalyzerAgent._classify_subtype() return value}
hit_count: 0
first_seen: YYYY-MM-DD
last_seen: YYYY-MM-DD
fix_success_rate: 0.00–1.00
---
```

**coverage/ pages**:
```yaml
---
covergroup: {covergroup_name}
bin: {bin_name}
action_class: actionable | protocol_blocked | design_excluded | needs_investigation
feature: {vplan feature name}
priority: 1–N
filled: false | true
filled_by_task: {task_id}  # if filled=true
---
```

### 11.2 Citation Format Specification

Every knowledge claim (non-trivially obvious technical facts) must include a citation at the end of the line:

```markdown
The RTL does not handle burst transactions crossing a 256-byte boundary.
(source: tasks/regression_debug_042.yaml | log: sim_axi_burst_test_42.log)
```

Lint scans for uncited assertion lines (heuristic: lines containing assertion words such as "always", "never", "must", "is").

---

## 12. Search Layer Specification

### 12.1 bm25s Integration Details

```python
# Dependency declaration (pyproject.toml)
[project.optional-dependencies]
wiki = [
    "bm25s[core]>=0.2.0",  # Pure Python BM25, air-gapped compatible
]

# Installation command
pip install "dv-agentic-system[wiki]"
```

### 12.2 Index Build Flow

```
Initialization (first time):
  WikiSearchIndex.create("bm25", wiki_dir).build(wiki_dir)
  → Scans wiki/**/*.md (excluding WIKI.md, log.md, index.md)
  → Parses YAML frontmatter + body
  → Builds bm25s.BM25 index
  → Persists to .agent/wiki/.search_index/

Incremental update (after each ingest):
  index.update(page_path, content)
  → Re-tokenizes the page
  → Updates sparse matrix

Query (each PromptLoader call):
  index.search("AXI SLVERR boundary", top_k=5)
  → BM25 scoring
  → Returns (page_path, score, excerpt, frontmatter)
```

### 12.3 Token Budget Management

```
wiki context injected by PromptLoader is bounded by max_context_tokens:

  total_budget = wiki_config.max_context_tokens  # default 2000
  per_category_budget = total_budget // 4        # 500 tokens per category

  Allocation strategy:
    KNOWN_ERROR_PATTERNS  → max 500 tokens (patterns/ top 5)
    KNOWN_RTL_BUGS        → max 500 tokens (bugs/ open top 5)
    COVERAGE_HOLE_HISTORY → max 500 tokens (coverage/ actionable top 5)
    WIKI_PATTERN_SUMMARY  → max 500 tokens (statistical summary table)

  Per-page summary format:
    **{pattern_id}** (hit_count: N, fix_rate: X%) — {description first line}
    Fix: {fix_template first 80 chars}
```

---

## 13. Phased Implementation Plan

### Phase A: Minimum Viable Integration (2 weeks)

**Goal**: wiki directory structure + patterns/ auto-update + PromptLoader injection

| Task | File | Notes |
|------|------|-------|
| A1 | `wiki/manager.py` | WikiConfig dataclass + WikiIngestService.ingest_pattern() |
| A2 | `wiki/query.py` | WikiQueryService.get_known_error_patterns() |
| A3 | `wiki/search.py` | BM25SearchIndex (using bm25s) |
| A4 | `prompts/prompt_loader.py` | Extend _gather_context(), add _load_wiki_context() |
| A5 | `config/config_loader.py` | Parse project.yaml wiki: block, build WikiConfig |
| A6 | `cli/wiki_search.py` | Basic search CLI |
| A7 | `tests/test_wiki_*.py` | Unit tests (mock bm25s) |

**Acceptance Criteria**:
- LogAnalyzer detects `missing_timescale` → `patterns/missing_timescale.md` `hit_count` auto-increments
- Next session's `{{KNOWN_ERROR_PATTERNS}}` contains `missing_timescale` summary
- All existing tests still pass (wiki defaults to `enabled: false`, backward-compatible)

### Phase B: Bug Archiving and Querying (2 weeks)

**Goal**: bugs/ auto-creation + BugClassifier history-awareness

| Task | Notes |
|------|-------|
| B1 | WikiIngestService.ingest_bug() |
| B2 | BugClassifierAgent queries wiki before classification |
| B3 | `cli/wiki_ingest.py` (manual trigger) |
| B4 | wiki/log.md append-only writes |
| B5 | wiki/index.md auto-update |

**Acceptance Criteria**:
- BugClassifier classification confidence is ≥ 0.1 higher when historical bugs exist vs. when they don't
- bugs/_index.md correctly reflects all open bugs

### Phase C: Coverage Archiving + Reporter Integration (1 week)

**Goal**: coverage/ pages + ReporterAgent auto-ingest

| Task | Notes |
|------|-------|
| C1 | WikiIngestService.ingest_coverage_hole() |
| C2 | WikiIngestService.ingest_session() (integrates the first three methods) |
| C3 | ReporterAgent trailing async ingest |
| C4 | CoverageAnalystAgent queries wiki coverage history |

### Phase D: Lint + Full CLI (1 week)

**Goal**: wiki health check + complete operation tools

| Task | Notes |
|------|-------|
| D1 | WikiLintService.run(depth="quick"\|"full") |
| D2 | OrchestratorAgent triggers quick lint at startup |
| D3 | `cli/wiki_lint.py` |
| D4 | `cli/wiki_build.py` (rebuild index) |
| D5 | Integration tests: full workflow verification of wiki compounding effect |

---

## 14. Test Strategy

### 14.1 Unit Tests

```python
# tests/test_wiki_ingest.py

class TestWikiIngestService:
    def test_ingest_pattern_creates_page(self, tmp_path):
        """When ingesting a failure_subtype for the first time, the corresponding patterns/ page should be created."""

    def test_ingest_pattern_updates_hit_count(self, tmp_path):
        """When repeatedly ingesting the same failure_subtype, hit_count should accumulate."""

    def test_ingest_bug_creates_rtl_page(self, tmp_path):
        """RTL_BUG classification results should create bugs/RTL_{date}_{id}.md."""

    def test_log_md_is_append_only(self, tmp_path):
        """After each ingest, log.md should only have content appended, never deleted."""

    def test_ingest_failure_does_not_corrupt_wiki(self, tmp_path):
        """When LLM call fails, wiki should not leave partial files."""


# tests/test_wiki_query.py

class TestWikiQueryService:
    def test_get_known_error_patterns_returns_top_k(self, wiki_with_patterns):
        """Should return the top_k patterns with the highest hit_count."""

    def test_empty_wiki_returns_empty_string(self, empty_wiki):
        """When wiki is empty, should return empty string rather than error."""

    def test_token_budget_not_exceeded(self, wiki_with_many_patterns):
        """Returned content should not exceed max_context_tokens."""


# tests/test_wiki_search.py

class TestBM25SearchIndex:
    def test_build_indexes_all_md_files(self, tmp_path):
        """build() should index wiki/**/*.md (excluding special pages)."""

    def test_search_returns_relevant_results(self, populated_wiki):
        """Searching for 'timescale' should return missing_timescale.md as the first result."""

    def test_update_reflects_new_content(self, populated_wiki):
        """After update(), new content should appear in search results."""

    @pytest.mark.skipif(
        importlib.util.find_spec("bm25s") is None,
        reason="bm25s not installed"
    )
    def test_bm25s_available_when_installed(self):
        """Verify bm25s can be imported normally."""
```

### 14.2 Integration Tests

```python
# tests/test_wiki_integration.py

class TestWikiIntegration:
    def test_full_workflow_accumulates_knowledge(self, tmp_path, mock_llm):
        """
        Complete workflow:
        Session 1: LogAnalyzer detects missing_timescale
                   → patterns/missing_timescale.md created (hit_count=1)

        Session 2: PromptLoader reads wiki
                   → {{KNOWN_ERROR_PATTERNS}} contains missing_timescale summary
                   → BugClassifier has prior knowledge

        Session 3: Same type of error recurs
                   → patterns/missing_timescale.md updated (hit_count=2)
                   → BugClassifier confidence higher than Session 1
        """

    def test_wiki_disabled_by_default_is_backward_compatible(self, minimal_project_yaml):
        """When wiki.enabled=false (default), all existing functionality is unaffected."""

    def test_wiki_failure_does_not_crash_agent(self, tmp_path, broken_wiki_dir):
        """When wiki write fails, ReporterAgent should still return report normally."""
```

### 14.3 Lint Tests

```python
# tests/test_wiki_lint.py

class TestWikiLintService:
    def test_detects_orphan_pages(self, wiki_with_orphan):
        """Should detect pages not recorded in index.md."""

    def test_detects_stale_open_bugs(self, wiki_with_old_bug):
        """Bugs with first_seen > 90 days and status=open should be flagged for human review."""

    def test_clean_wiki_passes_lint(self, clean_wiki):
        """A clean wiki should return human_review_required=False."""
```

---

## 15. Anti-Patterns and Prohibitions

### 15.1 Absolute Prohibitions

| Prohibited Action | Reason |
|-------------------|--------|
| wiki write operations modifying Raw Source (tasks/, sim logs) | Violates the Raw Source immutability principle |
| wiki pages containing uncited assertions | Difficult to audit, may propagate incorrect knowledge |
| Any form of deletion or modification of existing content in log.md | Operation log must be append-only |
| WikiIngestService blocking on the main async path | Must be executed asynchronously with asyncio.create_task |
| Search index replacing PromptLoader's placeholder mechanism | wiki can only be injected via placeholders, not directly appended to the prompt |
| wiki knowledge directly modifying _PATTERNS and other code-level configurations | Knowledge and logic must remain separated |

### 15.2 Design Anti-Patterns

```
Anti-Pattern 1: Premature Vectorization
  Problem: introducing an embedding model before wiki scale reaches 100 pages
  Correct approach: Phase A uses pure BM25, upgrade only after confirming BM25 is insufficient

Anti-Pattern 2: Excessive Token Injection
  Problem: dumping the entire wiki into the system prompt
  Correct approach: max_context_tokens=2000, max 500 tokens per category

Anti-Pattern 3: wiki as the Sole Knowledge Source
  Problem: system crashes when wiki is empty
  Correct approach: wiki knowledge overrides profile knowledge, but profile knowledge serves as fallback

Anti-Pattern 4: Synchronous Blocking Ingest
  Problem: ReporterAgent waits for ingest to complete before returning results, increasing latency
  Correct approach: asyncio.create_task() lets ingest run in the background

Anti-Pattern 5: wiki Knowledge Not Isolated by Environment
  Problem: Internal environment's Xcelium-specific bugs leaking into External environment's prompt
  Correct approach: each project (different .agent/ directory) has an independent wiki instance
```

---

## Appendix A: Dependency Package List

```toml
# pyproject.toml additions

[project.optional-dependencies]
wiki = [
    "bm25s[core]>=0.2.0",  # Pure Python BM25, air-gapped compatible
]

# Installation methods
# Air-gapped Internal:  pip install "dv-agentic-system[wiki]"
# External (networked): pip install "dv-agentic-system[wiki]"  (same, qmd not needed in Phase A)
# Full-featured (future): pip install "dv-agentic-system[wiki,wiki-semantic]"
```

---

## Appendix B: wiki_config Complete Schema

```python
# src/dv_agentic/wiki/manager.py

@dataclass
class WikiConfig:
    enabled: bool = False
    wiki_dir: Path = Path(".agent/wiki")
    max_context_tokens: int = 2000
    auto_ingest: bool = True
    search_backend: str = "bm25"   # "bm25" | "none"
    lint_on_startup: bool = True
    lint_interval_sessions: int = 10
    # Per-category token quotas (sum must be ≤ max_context_tokens)
    pattern_context_tokens: int = 500
    bug_context_tokens: int = 500
    coverage_context_tokens: int = 500
    summary_context_tokens: int = 500
```

---

## Appendix C: Upgrade Path (Phase E, Future)

When wiki scale exceeds 500 pages and BM25 recall degrades, upgrade to semantic search is available:

```bash
# Add optional dependency
pip install "dv-agentic-system[wiki-semantic]"
# Install qmd: pip install "qmd[mcp]"

# project.yaml
wiki:
  search_backend: "qmd"   # Upgrade from "bm25" to "qmd"
```

```python
# QMDSearchIndex implements the WikiSearchIndex interface
class QMDSearchIndex(WikiSearchIndex):
    """Semantic search index using the qmd Python port.
    BM25 + vector + LLM reranking, supports MCP server.
    """
    ...
```

Because the architecture uses the Strategy Pattern, an upgrade only requires changing the backend string, with no modifications to any Agent logic.
