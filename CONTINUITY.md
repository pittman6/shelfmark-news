# CONTINUITY.md

## Snapshot
- **Goal:** Pre-release secrets audit + hardening. [2026-08-03]
- **Now:** Audit complete — no real secrets in tracked files. CORS hardened (dropped `allow_credentials=True`). `shelfmark/` gitlink re-registered at upstream HEAD `cdd156e` (old gitdir was lost, checkout was an untracked plain tree at risk of being swept in by `git add -A`). 49/49 tests pass, ruff clean.
- **Next:** Nothing pending.

## Invariants
- `shelfmark/` submodule must not be edited.
- API key is `SERVER_API_KEY` env var (read via `os.environ.get`, no config layer).
- Empty `SERVER_API_KEY` = no auth required.

## Decisions
- **D001 ACTIVE (2026-06-25):** Newznab search responses include `?apikey=` in all download URLs. [CODE]
- **D002 ACTIVE (2026-06-26):** All blocking I/O in `_execute_download` runs in `asyncio.to_thread()` to keep the event loop free for Readarr's polling. [CODE]
- **D003 ACTIVE (2026-06-26):** Completed downloads are post-processed via shelfmark's `post_process_download()` to move files from `TMP_DIR` → `INGEST_DIR`, handling archive extraction and renaming. Absolute path stored in `storage`. [CODE]
- **D004 ACTIVE (2026-06-28):** Minimal config layer. `config.py` loads 6 env vars as module globals for clarity (SERVER_*, INGEST_DIR, TMP_DIR). Shelfmark reads its own env vars natively. Deleted pydantic-settings and pydantic dependencies. [CODE]
- **D005 ACTIVE (2026-06-29):** Shelfmark dep uses editable path (`{ path = "shelfmark/", editable = true }`) instead of workspace member. `shelfmark/shelfmark/` injected onto `sys.path` at top of `main.py` because the submodule lacks `[build-system]` so editable install produces an empty package. Root `requires-python` bumped to `>=3.14` to match shelfmark's requirement. [CODE]

## Done (recent)
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
- `2026-08-03 [TOOL]` Pre-release audit: no real secrets tracked. CORS + submodule gitlink fixed. 49/49 tests pass, ruff clean, `git add -A --dry-run` sweeps nothing from shelfmark/.
- `2026-06-29 [TOOL]` 19/19 tests pass. Ruff: clean on src/. Server starts (import works, `/books` permission is config issue).
- `2026-06-28 [TOOL]` 19/19 tests pass. Ruff: clean on src/, only pre-existing shelfmark/ issues.
- `2026-06-26 [TOOL]` 21/21 tests pass. Ruff: only pre-existing shelfmark/ issues (none in src/ or tests/).
