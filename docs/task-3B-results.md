# Task 3B

The referenced `afudm_gorev_3B.md` was not present in the checkout or the
Desktop search. Implementation follows the three requirements in the request.

## Pending downloads

`core/kaydet.py` writes `DATA/pending_downloads.json` with a versioned format,
temporary file, flush/fsync, and atomic replacement. Loading restores IDs and
starts the next ID above restored requests. A malformed file is preserved as
`pending_downloads.json.corrupt-<timestamp>`.

Requests stay on disk during approval and are removed only after the manager
accepts them, or the user explicitly cancels. Failed writes keep the previous
file and queue. Pending downloads no longer expire after 30 minutes; temporary
browser credentials still expire. Cookies, headers, and user agent remain only
in memory, so authenticated downloads may require a fresh browser request after
restart. The UI summary continues to exclude those fields.

All tests that instantiate `Bekleyenler` now use temporary DATA directories.

## PDF evidence

`python scripts/pdf_canli_dene.py --url <PDF URL>` sends an interactive request
to the running local API. Approve the regular download dialog. The script waits
up to 120 seconds, reads SQLite in read-only mode, checks completion, checks the
actual `%PDF-` file header, and requires an approval event matching the download
GID. Exit 0 indicates valid evidence. Evidence is saved to `pdf_canli_kanit.json`;
`--data`, `--output`, `--filename`, and `--wait` are supported. Tokens and source
URLs are excluded from evidence; raw event messages remain in the local DB.

HTTP regression tests verify approval events and rejection/error events,
including unexpected exceptions. Evidence tests reject non-PDF files and
unrelated approval events. No external live PDF download was performed.

## Packaging

`powershell -NoProfile -File scripts/build_exe.ps1 -Test` builds to `dist_test/`
without copying over the root EXE. `-DistPath <project subdirectory>` also
supports isolated output; default builds retain the existing release behavior.

`python scripts/verify_exe.py --exe dist_test/AfuDM.exe --version 2.8.0 --headless`
checks assets, embedded version, existing control normalization, and packaged
headless entry/dispatch. This is archive inspection, not a headless service
launch; it opens no windows and writes no application data.

The isolated PyInstaller build and embedded verification passed. Targeted
pending/PDF/window/tool tests and existing save/torrent/package tests passed.

## Continuation verification (turn 2)

Reviewed git status and diff before continuing; existing implementations were
retained. Added `scripts/run_isolated_test.py` to the normal and pre-push test
runners: application data/download paths use a temporary directory, writes to
the live DATA directory are blocked, and UI tests receive an offline font
response. Legacy tests may retain SQLite handles until process exit, so the
outer temporary-directory cleanup tolerates locked files on Windows.

The PWA test now always uses temporary token/endpoint files and an ephemeral
loopback port. A real-schema PDF snapshot regression revealed that SQLite's
connection context manager did not close the connection; the evidence tool now
explicitly closes each read-only connection.

Fresh validation:

- `scripts/test.ps1`: 59 test files passed, 0 failed (exit 0).
- `scripts/pre_push_test.ps1`: passed (exit 0).
- `scripts/test.ps1 -ParseOnly`: passed (exit 0).
- Python compilation of the new tools/tests and `git diff --check`: passed.
- `scripts/build_exe.ps1 -Test`: built `dist_test/AfuDM.exe`, embedded 2.8.0
  headless/assets gate passed, root EXE was not copied over.

No external live browser/PDF download was performed; the PDF tool was verified
with real local HTTP requests, the actual database schema, and file/event
validation tests.
