# AGENTS.md

## Commands

- **Sync deps:** `uv sync` (installs root package + `shelfmark/` submodule workspace member)
- **Test:** `uv run pytest -v`
- **Lint:** `ruff check`

## Architecture

- Python package: `src/shelfmark_wrapper/` — FastAPI app emulating Newznab and SABnzbd APIs for Readarr integration
- API routers: `src/shelfmark_wrapper/api/newznab.py` (search/indexer) and `api/sabnzbd.py` (download client)
- `shelfmark/` is a **git submodule** (uv workspace member) providing the actual book search/download engine
- Config uses environment variables directly (no config layer); see `.env.example` and `.envrc` for the expected names (largely shelfmark's native env var names like `INGEST_DIR`, `TMP_DIR`, `SERVER_API_KEY`)
- `.envrc` provides direnv defaults for local development (creates `data/downloads`, `data/tmp`, etc.)
- `tests/` is the only pytest `testpaths`; uses `TestClient` from FastAPI, `asyncio_mode = "auto"`

## Quirks

- After cloning, run `git submodule update --init --recursive` before `uv sync`
- Running the server: `uv run shelfmark-wrapper` or `uv run python -m shelfmark_wrapper.main`
- Tests set environment variables before importing the app
- `shelfmark/` is a full standalone Flask project with its own pyproject.toml; its source is `shelfmark/shelfmark/`, not the repo root. It should not be edited.
- No CI config is present in this repo

## Accuracy, recency, and sourcing (REQUIRED)


### Editing files

- Make the smallest safe change that solves the issue.
- Preserve existing style and conventions.
- Prefer patch-style edits (small, reviewable diffs) over full-file rewrites.
- After making changes, run the project’s standard checks when feasible (format/lint, unit tests, build/typecheck).
- Never remove comments unless there are no longer valid
- NEVER utilize git stash or other git commands that would remove local changes
- Do NOT suggest or make changes to any files in the submodule shelfmark/ project.

## Baseline workflow

- Start every task by determining:
  1. Goal + acceptance criteria.
  2. Constraints (time, safety, scope).
  3. What must be inspected (files, commands, tests, docs).
  4. Whether the request depends on **recency** (if yes, apply the "Accuracy, recency, and sourcing" rules).
  5. If requirements are ambiguous, ask targeted clarifying questions before making irreversible changes.


## Continuity Ledger (compaction-safe)

Maintain a single continuity file for this workspace: `CONTINUITY.md`.
`CONTINUITY.md` is the canonical briefing designed to survive compaction; do not rely on earlier chat/tool output unless it's reflected there.

### Operating rule
- At the start of each assistant turn: read `CONTINUITY.md` before acting.
- Update `CONTINUITY.md` only when there is a meaningful delta in: Goal/success criteria, Invariants/constraints, Decisions, State (Done/Now/Next), Open questions, Working set, or important tool outcomes.

### Keep it bounded (anti-bloat)
- Keep `CONTINUITY.md` short and high-signal:
  - `Snapshot`: ≤ 25 lines.
  - `Done (recent)`: ≤ 7 bullets.
  - `Working set`: ≤ 12 paths.
  - `Receipts`: keep last 10–20 entries.
- If sections exceed caps, compress older items into milestone bullets with pointers (commit/PR/log path/doc path). Do not paste raw logs.

### Anti-drift rules
- Facts only, no transcripts.
- Every entry must include:
  - a date or ISO timestamp (e.g., `2026-01-13` or `2026-01-13T09:42Z`)
  - a provenance tag: `[USER]`, `[CODE]`, `[TOOL]`, `[ASSUMPTION]`
- If unknown, write `UNCONFIRMED` (never guess). If something changes, supersede it explicitly (don't silently rewrite history).

### Decisions and incidents
- Record durable choices in `Decisions` as ADR-lite entries (e.g., `D001 ACTIVE: …`).
- For recurring weirdness, create a small, stable incident capsule (Symptoms / Evidence pointers / Mitigation / Status).

### Plan tool vs ledger
- Use `update_plan` for short-term execution scaffolding (3–7 steps).
- Use `CONTINUITY.md` for long-running continuity ("what/why/current state"), not micro task lists.
- Keep them consistent at the intent/progress level.

### In replies
- Start with a brief "Ledger Snapshot" (Goal + Now + Next + Open Questions).
- Print the full ledger only when it materially changed or the user requests it.