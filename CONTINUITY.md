# CONTINUITY.md

## Snapshot
- **Goal:** Project rename shelfmark-wrapper → shelfmark-news. [2026-08-03]
- **Now:** Full rename done. Package `shelfmark_wrapper` → `shelfmark_news` (dir `src/shelfmark_wrapper/` → `src/shelfmark_news/`), pyproject name/script/hatch packages, Dockerfile/compose service+container name, justfile, README/AGENTS, `uv.lock` regenerated, `.venv` reinstalled. 49/49 tests pass, ruff clean, `uv run shelfmark-news` works. Note: `src/shelfmark_news/api/` is EMPTY (AGENTS references api/newznab.py + sabnzbd.py here but real code lives at package root).
- **Next:** CI workflows under `.github/` now adapted to this repo (docker publishing to GHCR).
  - Note: repo git remote = `pittman6/shelfmark-news` on ghanon host (not github.com). PRs/releases require `RELEASE_PLEASE_GITHUB_TOKEN` secret.
  - Note: ruff-action default run has 28 pre-existing violations in tests/ (UP038, N802) — pre-existing, not CI-blocking by design but will show in checks.

## Invariants
- `src/shelfmark/` submodule must not be edited.
- API key is `SERVER_API_KEY` env var (read via `os.environ.get`, no config layer).
- Empty `SERVER_API_KEY` = no auth required.

## Decisions
- **D001 ACTIVE (2026-06-25):** Newznab search responses include `?apikey=` in all download URLs. [CODE]
- **D002 ACTIVE (2026-06-26):** All blocking I/O in `_execute_download` runs in `asyncio.to_thread()` to keep the event loop free for Readarr's polling. [CODE]
- **D003 ACTIVE (2026-06-26):** Completed downloads are post-processed via shelfmark's `post_process_download()` to move files from `TMP_DIR` → `INGEST_DIR`, handling archive extraction and renaming. Absolute path stored in `storage`. [CODE]
- **D004 ACTIVE (2026-06-28):** Minimal config layer. `config.py` loads 6 env vars as module globals for clarity (SERVER_*, INGEST_DIR, TMP_DIR). Shelfmark reads its own env vars natively. Deleted pydantic-settings and pydantic dependencies. [CODE]
- **D005 ACTIVE (2026-06-29):** Shelfmark dep uses editable path (`{ path = "shelfmark/", editable = true }`) instead of workspace member. `shelfmark/shelfmark/` injected onto `sys.path` at top of `main.py` because the submodule lacks `[build-system]` so editable install produces an empty package. Root `requires-python` bumped to `>=3.14` to match shelfmark's requirement. [CODE]

## Done (recent)
- **2026-08-03 [CODE]:**
  - Fixed `release-please-config.json`: `extra-files` was `src/borg2mqtt/__init__.py` → `src/shelfmark_news/__init__.py`.
  - `reusable_checks.yml`: checkout now `submodules: recursive` (needed for submodule); types job uses `pyrefly check` (was nonexistent `basedpyright`, and bare `pyrefly` just prints help/exit 0); added a `tests` job running `uv run pytest -v`.
  - `on_main.yml`: replaced PyPI wheel + gh release upload with GHCR Docker image publish (`ghcr.io/<repo>:<tag>` + `:latest`), added `packages: write` permission.
- **2026-08-03:** Full rename `shelfmark-wrapper`→`shelfmark-news` / `shelfmark_wrapper`→`shelfmark_news`: package dir, pyproject (name/script/packages), source imports+loggers+meta tag, tests, Dockerfile, compose (+example) service/container name, justfile, README (incl. clone URL paths), AGENTS. `uv.lock` regenerated, `.venv` reinstalled. 49/49 tests pass, ruff clean, console script `shelfmark-news` works. [TOOL]
- **2026-08-03:** Pre-release audit: no secrets in tracked files (all values placeholder/env-var). Removed `allow_credentials=True` from CORS (main.py). Re-registered `shelfmark/` gitlink at `cdd156e` (upstream HEAD) after `git submodule update` was impossible (gitdir missing) — fresh clone replaces old checkout, 49/49 tests pass. [TOOL]
- **2026-06-29:** Fixed shelfmark import — editable path dep + sys.path injection + requires-python bump. 19/19 tests pass, ruff clean. [CODE]
- **2026-06-28:** Removed config.py and pydantic-settings. Wrapper reads env vars directly (`os.environ.get`). Shelfmark reads its own env vars natively. [CODE]
- **2026-06-26:** Event loop blocking fix — `get_book_info()` and `handler.download()` wrapped in `asyncio.to_thread()`. [CODE]
- **2026-06-26:** Readarr queue visibility — `_handle_addurl` now accepts `nzbname`, `cat` is stored and echoed back. [CODE]
- **2026-06-26:** ETA format fixed to always be `H:MM:SS` matching SABnzbd's expected format. [CODE]
- **2026-06-26:** Speed/ETA tracking in `progress_callback` — computed from delta progress/time, debounced at 0.5s. [CODE]
- **2026-06-26:** Status lifecycle — `status_callback` drives QUEUED→DOWNLOADING→FAILED transitions. [CODE]

## Working set
- `pyproject.toml` — editable path dep + requires-python bump
- `src/shelfmark_wrapper/main.py` — sys.path injection
- `src/shelfmark_wrapper/api/sabnzbd.py`
- `src/shelfmark_wrapper/api/newznab.py`
- `tests/test_api.py`

## Open questions
- None.

## Receipts
- `2026-08-03 [TOOL]` Moved submodule `shelfmark/` → `src/shelfmark/` (git mv + .gitmodules path). Updated pyproject (workspace members, pyrefly search-path/excludes, ruff extend-exclude), main.py sys.path injection, Dockerfile (PYTHONPATH + COPY paths), README/AGENTS paths. Regenerated uv.lock (stale member path). 49/49 tests pass, ruff clean, app imports. [CODE]
- `2026-08-03 [TOOL]` Pre-release audit: no real secrets tracked. CORS + submodule gitlink fixed. 49/49 tests pass, ruff clean, `git add -A --dry-run` sweeps nothing from shelfmark/.
- `2026-06-29 [TOOL]` 19/19 tests pass. Ruff: clean on src/. Server starts (import works, `/books` permission is config issue).
- `2026-06-28 [TOOL]` 19/19 tests pass. Ruff: clean on src/, only pre-existing shelfmark/ issues.
- `2026-06-26 [TOOL]` 21/21 tests pass. Ruff: only pre-existing shelfmark/ issues (none in src/ or tests/).
