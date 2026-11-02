# CONTINUITY.md

## Snapshot
- 2026-11-01 [USER] Goal: upgrade Shelfmark to newest stable release and fix wrapper compatibility.
- 2026-11-01 [TOOL] Clean initial checkout; original submodule v1.3.12 (`89104ae`). GitHub releases/latest identifies v1.6.0, published 2026-10-31; checked out tag (`9bd6c51`). No Shelfmark source edits permitted.
- 2026-11-01 [CODE] Now: upgrade complete; fixed search tuple unpacking (offloaded to a thread), moved metadata import, Python 3.14 metadata/Docker, and Xlib dependency collision. Added 10 regression cases.
- 2026-11-01 [TOOL] Validation: 59 tests pass; pyrefly has zero errors; locked sync, Docker build, API startup and Xlib checks pass. Ruff has 70 pre-existing findings and no new findings. Live external downloads/challenge solving not tested.
- 2026-11-01 [CODE] Next: user review; no commit or deployment performed.
- 2026-11-01 [CODE] Open questions: none. Existing search is Anna's Archive-based; adding new provider support is out of scope.
- 2026-11-01 [USER] Follow-up: test completely fresh venvs without Xlib exclusion before retaining workaround.
- 2026-11-01 [TOOL] Follow-up complete: three fresh venvs without exclusion gave one failed and two passed Xlib probes with identical locked versions; three fresh venvs with exclusion all passed. Working venv/config untouched; keep D007.

## Invariants
- `src/shelfmark/` submodule must not be edited.
- API key is `SERVER_API_KEY` env var (read via `os.environ.get`, no config layer).
- Empty `SERVER_API_KEY` = no auth required.

## Decisions
- **D001 ACTIVE (2026-06-25):** Newznab search responses include `?apikey=` in all download URLs. [CODE]
- **D002 ACTIVE (2026-06-26):** All blocking I/O in `_execute_download` runs in `asyncio.to_thread()` to keep the event loop free for Readarr's polling. [CODE]
- **D003 ACTIVE (2026-06-26):** Completed downloads are post-processed via shelfmark's `post_process_download()` to move files from `TMP_DIR` → `INGEST_DIR`, handling archive extraction and renaming. Absolute path stored in `storage`. [CODE]
- **D004 ACTIVE (2026-06-28):** Minimal config layer. `config.py` loads 6 env vars as module globals for clarity (SERVER_*, INGEST_DIR, TMP_DIR). Shelfmark reads its own env vars natively. Deleted pydantic-settings and pydantic dependencies. [CODE]
- **D005 SUPERSEDED by D006 (2026-11-01) [CODE]:** 2026-06-29 import workaround used an editable path dependency; current checkout uses a uv workspace instead.
- 2026-11-01 [CODE] **D006 ACTIVE:** Shelfmark is a non-package uv workspace member at `src/shelfmark`; `main.py` injects its source path. Wrapper metadata and Docker now both require Python 3.14, matching Shelfmark.
- 2026-11-01 [CODE] **D007 ACTIVE:** Exclude obsolete `python3-xlib` via root uv settings; existing `python-xlib` supplies the shared Xlib namespace. Existing environments need one `uv sync --reinstall-package python-xlib` after removing the collision (done here; documented in README).

## Done (recent)
- 2026-11-01 [CODE] Upgraded Shelfmark v1.3.12 → v1.6.0 (`9bd6c51388f6efc1ce258f6b22022a94bcc7f230`), regenerated lockfile, fixed search/download imports and Python requirements; no submodule source edits.
- 2026-11-01 [TOOL] New regression tests reproduced search, download-import and browser dependency failures before fixes; final suite passes 59/59, including real parser and handler/post-processing with mocked network.
- **2026-08-03 [CODE]:**
  - Fixed `release-please-config.json`: `extra-files` was `src/borg2mqtt/__init__.py` → `src/shelfmark_news/__init__.py`.
  - `reusable_checks.yml`: checkout now `submodules: recursive` (needed for submodule); types job uses `pyrefly check` (was nonexistent `basedpyright`, and bare `pyrefly` just prints help/exit 0); added a `tests` job running `uv run pytest -v`.
  - `on_main.yml`: replaced PyPI wheel + gh release upload with GHCR Docker image publish (`ghcr.io/<repo>:<tag>` + `:latest`), added `packages: write` permission.
- **2026-08-03:** Full rename `shelfmark-wrapper`→`shelfmark-news` / `shelfmark_wrapper`→`shelfmark_news`: package dir, pyproject (name/script/packages), source imports+loggers+meta tag, tests, Dockerfile, compose (+example) service/container name, justfile, README (incl. clone URL paths), AGENTS. `uv.lock` regenerated, `.venv` reinstalled. 49/49 tests pass, ruff clean, console script `shelfmark-news` works. [TOOL]
- **2026-08-03:** Pre-release audit: no secrets in tracked files (all values placeholder/env-var). Removed `allow_credentials=True` from CORS (main.py). Re-registered `shelfmark/` gitlink at `cdd156e` (upstream HEAD) after `git submodule update` was impossible (gitdir missing) — fresh clone replaces old checkout, 49/49 tests pass. [TOOL]
- 2026-11-01 [CODE] Earlier milestones (2026-06-26–29): threaded downloads, post-processing, SABnzbd category/status/speed/ETA support and import/config simplification; durable contracts recorded in D001–D006.

## Incidents
- 2026-11-01 [TOOL] Xlib collision: both old local environment and first upgraded Docker image lacked `Xlib.X.FamilyServerInterpreted`, required by browser bypass. Upstream `src/shelfmark/Dockerfile:190–204` documents the same collision. Mitigation: D007; status RESOLVED, verified in local tests and a fresh Docker image.
- 2026-11-01 [TOOL] Fresh-venv reproduction confirms install-order dependence rather than stale state: identical dependencies (`python-xlib==0.33`, `python3-xlib==0.15`) produced mixed results. Excluding the obsolete package removed the collision in all three control environments.
- 2026-11-01 [TOOL] File ownership verified using installed `Xlib/X.py` SHA-256 versus both distributions' RECORD hashes: failing venv matches `python3-xlib==0.15`; both passing venvs match `python-xlib==0.33`. Same installed-package list does not imply the same file contents when distributions overlap.

## Working set
- 2026-11-01 [CODE] `src/shelfmark` — released gitlink only
- 2026-11-01 [CODE] `pyproject.toml`, `uv.lock`, `Dockerfile`
- 2026-11-01 [CODE] `src/shelfmark_news/newznab.py`, `src/shelfmark_news/sabnzbd.py`
- 2026-11-01 [CODE] `tests/test_api.py`, new integration regression tests
- 2026-11-01 [CODE] `README.md`, `CONTINUITY.md`

## Open questions
- 2026-11-01 [CODE] None.

## Receipts
- 2026-11-01 [CODE] User-requested expanded comment in `pyproject.toml` documents the Xlib file collision, lockfile limitation, SeleniumBase failure, compatible replacement and removal condition; dependency settings unchanged.
- 2026-11-01 [TOOL] uv docs `https://docs.astral.sh/uv/concepts/preview/#detect-module-conflicts` explicitly state conflicting modules can make imports depend on install order despite different distribution names; optional preview feature warns about this. No project settings changed during this explanation.
- 2026-11-01 [TOOL] Six isolated fresh venvs tested in `/tmp/opencode/shelfmark-xlib-clean-xx2imn9d`; `results.json` records without-exclusion probes (false/true/true), `results-fixed.json` records with-exclusion probes (true/true/true). Only lock graph difference was `python3-xlib`; original workspace and working venv unchanged.
- 2026-11-01 [TOOL] GitHub `https://api.github.com/repos/calibrain/shelfmark/releases/latest`: stable v1.6.0, published 2026-10-31; fetched tag via HTTPS.
- 2026-11-01 [TOOL] `uv sync --locked`, `uv run pytest -v`: 59 passed (one pre-existing Starlette/httpx deprecation warning); `uv run pyrefly check`: zero errors.
- 2026-11-01 [TOOL] `docker build -t shelfmark-news:upgrade-check .`: succeeds; first image API smoke checks pass; final image `c77d1561f129` passes Xlib assertion and Shelfmark bypass-module imports.
- 2026-11-01 [TOOL] `ruff check`: 70 findings; compared rule/message counts to `git show HEAD:<file>` with same Ruff binary, no new findings. `git diff --check` passes.
- 2026-11-01 [TOOL] `git -C src/shelfmark status --porcelain`: empty; only submodule gitlink updated in parent. No external mirror downloads or production deployment attempted.
- `2026-08-03 [TOOL]` Moved submodule `shelfmark/` → `src/shelfmark/` (git mv + .gitmodules path). Updated pyproject (workspace members, pyrefly search-path/excludes, ruff extend-exclude), main.py sys.path injection, Dockerfile (PYTHONPATH + COPY paths), README/AGENTS paths. Regenerated uv.lock (stale member path). 49/49 tests pass, ruff clean, app imports. [CODE]
- `2026-08-03 [TOOL]` Pre-release audit: no real secrets tracked. CORS + submodule gitlink fixed. 49/49 tests pass, ruff clean, `git add -A --dry-run` sweeps nothing from shelfmark/.
- `2026-06-29 [TOOL]` 19/19 tests pass. Ruff: clean on src/. Server starts (import works, `/books` permission is config issue).
- `2026-06-28 [TOOL]` 19/19 tests pass. Ruff: clean on src/, only pre-existing shelfmark/ issues.
- `2026-06-26 [TOOL]` 21/21 tests pass. Ruff: only pre-existing shelfmark/ issues (none in src/ or tests/).
