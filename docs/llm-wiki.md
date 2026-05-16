# LLM Wiki

## Inspiration

This module is directly inspired by **Andrej Karpathy**'s *LLM Wiki* concept,
published in April 2026:

> "Instead of just retrieving from raw documents at query time, the LLM
> incrementally builds and maintains a persistent wiki — a structured,
> interlinked collection of markdown files that sits between you and the raw
> sources. When you add a new source, the LLM doesn't just index it for later
> retrieval. It reads it, extracts the key information, and integrates it into
> the existing wiki — updating entity pages, revising topic summaries, noting
> where new data contradicts old claims, strengthening or challenging the
> evolving synthesis. The knowledge is compiled once and then kept current, not
> re-derived on every query."
>
> — Andrej Karpathy, ["LLM Wiki"](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f), April 2026

The key distinction from traditional RAG is that LLM Wiki produces a
**"persistent, compounding artifact"** — cross-references are already resolved,
contradictions already flagged — rather than re-deriving knowledge on every
query. Karpathy explains why LLMs are uniquely suited for this role:

> "The tedious part of maintaining a knowledge base is not the reading or the
> thinking — it's the bookkeeping... Humans abandon wikis because the
> maintenance burden grows faster than the value. LLMs don't get bored, don't
> forget to update a cross-reference, and can touch 15 files in one pass."

This project applies Karpathy's three-layer architecture (Raw Sources → Wiki →
Schema) and three core operations (**Ingest**, **Query**, **Lint**) to the DV
(Design Verification) domain.

---

## Overview

LLM Wiki is a Git-versioned Markdown knowledge base that persists verification
insights across agent sessions. Every DV session produces signal — error
patterns, bug classifications, coverage gap analyses — that would otherwise
vanish when the chat window closes. The wiki captures this signal at write time
(after each `ReporterAgent` run) and replays it at read time (before the next
`PromptLoader` builds a system prompt), so knowledge compounds session-over-session
without manual curation.

> **Design principle**:
> Knowledge should be compiled at write time, not re-derived at query time.

---

## Architecture

The wiki layer is implemented in `src/dv_agentic/wiki/` as five focused modules:

```
src/dv_agentic/wiki/
├── manager.py   — WikiConfig dataclass, YAML frontmatter I/O, atomic_write
├── ingest.py    — WikiIngestService: writes analysis results into wiki pages
├── query.py     — WikiQueryService:  reads wiki pages for prompt injection
├── search.py    — BM25 / keyword search index (Strategy Pattern)
└── lint.py      — WikiLintService:  detects orphan pages, broken links, stale claims
```

### Module Responsibilities

| Module | Responsibility | Consumers |
|--------|---------------|-----------|
| `manager` | Configuration parsing, page I/O primitives, atomic writes | all other modules |
| `ingest` | Creates/updates `patterns/`, `bugs/`, `coverage/` pages after each session | `ReporterAgent`, CLI |
| `query` | Reads wiki knowledge and formats it for token-budget-aware injection | `PromptLoader` |
| `search` | Builds and queries a BM25 or keyword index over all wiki pages | `ingest` (post-write refresh), CLI `wiki-search` |
| `lint` | Validates wiki integrity: orphan pages, stale dates, missing referenced pages | CLI `wiki-lint`, `OrchestratorAgent` startup |

### Three-Layer Model

```
┌─────────────────────────────────────────────────────┐
│ SCHEMA LAYER  — rules & configuration               │
│   .agent/wiki/WIKI.md   (bootstrap schema)          │
│   .agent/project.yaml   (wiki: block)               │
│   PromptLoader          (placeholder injection)     │
├─────────────────────────────────────────────────────┤
│ WIKI LAYER  — LLM-maintained knowledge              │
│   .agent/wiki/index.md  bugs/  patterns/            │
│                         coverage/  specs/  log.md   │
├─────────────────────────────────────────────────────┤
│ RAW SOURCE LAYER  — immutable artefacts             │
│   Simulation logs   Coverage reports   Spec PDFs    │
│   .agent/tasks/{task_id}.yaml                       │
└─────────────────────────────────────────────────────┘
```

---

## Directory Structure

All wiki files live under `.agent/wiki/` inside the project root.

```
.agent/wiki/
├── WIKI.md                       # Schema declaration (bootstrap file)
├── index.md                      # Auto-maintained directory of all pages
├── log.md                        # Append-only operation log
│
├── bugs/                         # Confirmed RTL and TB bug pages
│   ├── _index.md                 # Sub-directory index
│   ├── RTL_20260510_001.md       # RTL_{YYYYMMDD}_{seq:03d}.md
│   └── TB_20260511_003.md        # TB_{YYYYMMDD}_{seq:03d}.md
│
├── patterns/                     # Known failure patterns
│   ├── _index.md
│   ├── missing_timescale.md      # compile_error subtype
│   ├── unmatched_block.md
│   ├── scoreboard_fail.md        # sim_error subtype
│   └── protocol_violation.md
│
├── coverage/                     # Coverage hole analyses
│   ├── _index.md
│   └── {covergroup}_{bin}.md
│
├── specs/                        # Spec clarification notes
│   ├── _index.md
│   └── {feature}_clarification.md
│
└── .search_index/                # Persistent BM25 index (auto-generated, gitignored)
```

### Page Naming Conventions

| Category | Pattern | Example |
|----------|---------|---------|
| RTL bug | `RTL_{YYYYMMDD}_{seq:03d}.md` | `RTL_20260510_001.md` |
| TB bug | `TB_{YYYYMMDD}_{seq:03d}.md` | `TB_20260511_003.md` |
| Error pattern | `{failure_subtype}.md` (snake_case) | `missing_timescale.md` |
| Coverage hole | `{covergroup}_{bin}.md` | `axi_write_cov_back_pressure.md` |
| Spec clarification | `{feature}_clarification.md` | `axi_burst_len_clarification.md` |

Every page includes YAML frontmatter (between `---` delimiters) followed by a
Markdown body. The frontmatter is the machine-readable record; the body is the
human-readable narrative.

---

## Configuration

Add a `wiki:` block to `.agent/project.yaml`. The wiki is **disabled by default**
for full backward compatibility with existing projects.

```yaml
wiki:
  enabled: true
  wiki_dir: ".agent/wiki"        # root directory for all wiki files
  max_context_tokens: 2000       # total token budget injected per session
  auto_ingest: true              # ReporterAgent triggers ingest automatically
  search_backend: "bm25"        # "bm25" (requires bm25s) or "none"
  lint_on_startup: true          # quick lint check at OrchestratorAgent startup
  lint_interval_sessions: 10     # full lint every N sessions

  # Per-placeholder token budgets (must sum to <= max_context_tokens)
  pattern_context_tokens: 500    # {{KNOWN_ERROR_PATTERNS}}
  bug_context_tokens: 500        # {{KNOWN_RTL_BUGS}}
  coverage_context_tokens: 500   # {{COVERAGE_HOLE_HISTORY}}
  summary_context_tokens: 500    # {{WIKI_PATTERN_SUMMARY}}
```

### Installing the Search Dependency

```bash
# Standard install
pip install "dv-agentic-system[wiki]"

# Air-gapped RHEL 8.4 (pre-download bm25s wheel)
pip install "bm25s[core]" --no-index --find-links dv_wheels/
```

If `bm25s` is not installed, the system falls back to a pure-Python keyword
search automatically — no configuration change required.

---

## CLI Commands

All wiki CLI tools are invoked as Python modules. They read `.agent/project.yaml`
from the current working directory.

### `wiki-search` — Query the wiki

```bash
# Search across all categories
python -m dv_agentic.cli.wiki_search "timescale"

# Narrow to a specific category
python -m dv_agentic.cli.wiki_search "timescale" --category patterns
python -m dv_agentic.cli.wiki_search "SLVERR boundary" --category bugs
python -m dv_agentic.cli.wiki_search "back pressure" --category coverage

# Increase number of results (default: 5)
python -m dv_agentic.cli.wiki_search "protocol violation" --top-k 10
```

Results show the page title, relative path, and a relevance score.

### `wiki-lint` — Health check

```bash
# Quick lint: structural checks only (orphan pages, missing index entries)
python -m dv_agentic.cli.wiki_lint --depth quick

# Full lint: includes stale-claim detection and cross-reference validation
python -m dv_agentic.cli.wiki_lint --depth full

# Output as JSON (useful for CI integration)
python -m dv_agentic.cli.wiki_lint --depth full --format json
```

Lint detects:
- **Orphan pages** — files with no inbound links from `index.md`
- **Stale bugs** — open bug pages not updated in over 30 days
- **Missing pages** — pages referenced in `index.md` that do not exist on disk
- **Broken links** — inter-page links pointing to non-existent targets

### `wiki-build` — Rebuild the search index

```bash
# Rebuild the BM25 index from scratch (run after manual page edits)
python -m dv_agentic.cli.wiki_build

# Rebuild and also regenerate index.md
python -m dv_agentic.cli.wiki_build --reindex
```

Run `wiki-build` after manually editing wiki pages outside of agent sessions,
or after cloning a project repository where `.search_index/` was not committed.

---

## How Agents Use the Wiki

Agents interact with the wiki through two integration seams — **write** (ingest)
and **read** (query) — with no changes to agent core logic.

### Write path — `WikiIngestService`

After `ReporterAgent.run()` completes, it calls `WikiIngestService` on a
background thread (`asyncio.to_thread`). The ingest service selects the right
writer based on the session data type:

| Session output | Writer method | Target directory |
|---------------|--------------|-----------------|
| `LogAnalyzerAgent` failure match | `ingest_pattern()` | `patterns/` |
| `BugClassifierAgent` result | `ingest_bug()` | `bugs/` |
| `CoverageAnalyst` hole report | `ingest_coverage_hole()` | `coverage/` |
| Full session report | `ingest_session()` | dispatches to the above |

After every write the ingest service atomically updates `log.md` and refreshes
the relevant section of `index.md`.

### Read path — `WikiQueryService` + `PromptLoader`

When `PromptLoader._gather_context()` builds a system prompt, it calls
`WikiQueryService` to populate four placeholder variables:

| Placeholder | Source | Token Budget |
|-------------|--------|-------------|
| `{{KNOWN_ERROR_PATTERNS}}` | `patterns/*.md` sorted by `hit_count` | `pattern_context_tokens` |
| `{{KNOWN_RTL_BUGS}}` | `bugs/RTL_*.md` with status `open` | `bug_context_tokens` |
| `{{COVERAGE_HOLE_HISTORY}}` | `coverage/*.md` with `filled: false` | `coverage_context_tokens` |
| `{{WIKI_PATTERN_SUMMARY}}` | condensed summary of all pattern pages | `summary_context_tokens` |

Each method truncates its output to stay within the configured token budget,
so the wiki never silently inflates the system prompt past the LLM context limit.

### Graceful degradation

If the wiki directory is missing or the `wiki.enabled` flag is `false`, every
`WikiQueryService` method returns an empty string. The placeholders resolve to
empty strings and the prompt is identical to a non-wiki session. No agent raises
an exception.

---

## Data Flow

End-to-end flow from raw simulation output to knowledge reuse in the next session:

```
Session N
─────────────────────────────────────────────────────────────────
SimController.run_simulation()
        │
        ▼
LogAnalyzerAgent.analyze()          ← classifies error_class + failure_subtype
        │
        ▼
BugClassifierAgent.classify()       ← determines RTL_BUG vs TB_BUG + confidence
        │
        ▼
CoverageAnalyst.analyze()           ← identifies unfilled coverage holes
        │
        ▼
ReporterAgent.run()                 ← generates Markdown session report
        │
        ├─── (existing) ──► report delivered to engineer
        │
        └─── (new, non-blocking) ──► WikiIngestService
                │
                ├── ingest_pattern()  → patterns/{subtype}.md  (create / update)
                ├── ingest_bug()      → bugs/{TYPE}_{date}_{seq}.md  (create)
                ├── ingest_coverage_hole() → coverage/{cg}_{bin}.md  (create / update)
                └── _append_log()    → log.md  (append-only)
                    ↓
                index.md regenerated atomically
                .search_index/ refreshed

Session N+1
─────────────────────────────────────────────────────────────────
OrchestratorAgent starts
        │
        ├── (optional) WikiLintService.quick_lint()  ← lint_on_startup=true
        │
        ▼
PromptLoader._gather_context()
        │
        └── WikiQueryService
                ├── get_known_error_patterns()  → {{KNOWN_ERROR_PATTERNS}}
                ├── get_known_rtl_bugs()        → {{KNOWN_RTL_BUGS}}
                ├── get_coverage_history()      → {{COVERAGE_HOLE_HISTORY}}
                └── get_pattern_summary()       → {{WIKI_PATTERN_SUMMARY}}
                    ↓
        System prompt injected with accumulated knowledge
        │
        ▼
LogAnalyzerAgent / BugClassifierAgent start with prior context
→ faster convergence, fewer repeated token expenditures
```

### Key design properties

- **Additive only** — wiki pages accumulate; nothing is deleted automatically.
  `log.md` is strictly append-only.
- **Atomic writes** — every page update uses a temp-file + `os.replace` sequence
  so readers never see a partial write.
- **Non-fatal ingest** — a wiki write error is logged at `DEBUG` level and never
  propagates to the agent caller. Broken wikis do not break sessions.
- **Git-friendly** — all wiki content is plain Markdown. Engineers can review,
  edit, and revert wiki pages with standard Git tooling.

---

## Related Documents

- [`docs/llm-wiki-dv-agentic-spec.md`](llm-wiki-dv-agentic-spec.md) — Full
  integration design specification: data models, decision matrix, phased
  implementation plan, anti-patterns.
- [`docs/prompt-system.md`](prompt-system.md) — How `PromptLoader` loads and
  assembles agent system prompts, including placeholder resolution.
- [`docs/agentic-system.md`](agentic-system.md) — High-level multi-agent
  topology and orchestrator workflow.
- [Andrej Karpathy, "LLM Wiki" (GitHub Gist, April 2026)](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) —
  Original concept and motivation for this module's design.
