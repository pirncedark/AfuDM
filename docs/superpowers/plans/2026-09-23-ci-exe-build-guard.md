# CI EXE Build Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make every CI release build `AfuDM.exe` from the checked-out sources and reject stale or unverifiable executables.

**Architecture:** `release.yml` and `ci.yml` will invoke PyInstaller explicitly before packaging. `build_release.ps1` will require a fresh `dist/AfuDM.exe`, reject an older tracked/root executable, and copy the validated build into the package input. `verify_release.ps1` will call a small Python verifier that extracts the embedded `app` and `core.surum` modules with PyInstaller's `CArchiveReader`.

**Tech Stack:** GitHub Actions, PowerShell 5.1-compatible scripts, Python 3.11, PyInstaller `CArchiveReader`, unittest.

**Spec:** User request in the conversation: CI EXE provenance, stale-build guard, embedded-module release verification, local red/green verification, and English-first PR with Turkish section.

## Global Constraints

- Work only in `C:/Users/afuuu/Desktop/afuproject/AfuDM-ci` on branch `ci-exe-derleme`.
- Do not merge or create a tag.
- Do not modify `C:/Users/afuuu/Desktop/afuproject/AfuDM`.
- PowerShell scripts must remain ASCII-compatible for Windows PowerShell 5.1.
- PR title and first body section are English; the body then contains `## Türkçe` and ends with the requested Claude Code attribution.

## Review Focus

- A missing `dist/AfuDM.exe` must fail before packaging; test the static guard contract and local command.
- A root `AfuDM.exe` older than `app.py` or `core/surum.py` must fail instead of being silently copied; test both source timestamps.
- A valid fresh PyInstaller output must be the packaged executable; test the copy/package contract.
- A zip with an executable missing `app` or with a stale `core.surum` module must fail verification; test the verifier's archive checks.
- Both CI workflows must compile before packaging; test their ordered command contracts.

### Task 1: Add failing release-tool contracts

**Files:**
- Modify: `tests/release_tools_test.py`

- [ ] Add tests asserting the workflow order, stale/missing EXE guard strings, and verifier invocation.
- [ ] Run `python -m unittest tests.release_tools_test -v` and confirm the new assertions fail against the current scripts.

### Task 2: Add embedded EXE verifier and guards

**Files:**
- Create: `scripts/verify_exe.py`
- Modify: `scripts/build_release.ps1`
- Modify: `scripts/verify_release.ps1`

- [ ] Implement `verify_exe.py` with `CArchiveReader`, extracting `app` and `core.surum`, checking the expected version and normalized `control` module.
- [ ] Make `build_release.ps1` require fresh `dist/AfuDM.exe`, reject stale root/source timestamps, and copy the validated dist output before `paketle.py`.
- [ ] Make `verify_release.ps1` extract the zip executable and invoke the verifier with the package version.
- [ ] Run the focused tests and the verifier against the downloaded v2.7.1 executable.

### Task 3: Wire explicit PyInstaller builds into CI

**Files:**
- Modify: `.github/workflows/release.yml`
- Modify: `.github/workflows/ci.yml`

- [ ] Add explicit `python -m PyInstaller --noconfirm --clean AfuDM.spec` steps before packaging in both workflows.
- [ ] Run static contract tests and PowerShell parse checks.

### Task 4: Local red/green build verification

- [ ] Remove only generated local build outputs needed for the stale-exe test, preserving user files.
- [ ] Run `build_release.ps1` with no `dist/AfuDM.exe` and confirm a non-zero stale-build guard failure.
- [ ] Run `build_exe.ps1 -Temiz`, then `build_release.ps1`, and confirm the package contains the fresh executable.
- [ ] Run the complete project test suite and inspect the final diff/status.

### Task 5: Commit, push, PR, and CI follow-up

- [ ] Commit with Turkish message using `git commit -F` and the required Claude co-author trailer.
- [ ] Push `ci-exe-derleme`, open an English-first PR with `## Türkçe`, and do not merge or tag.
- [ ] Monitor PR checks with `gh pr checks` and report the PR URL plus any remaining CI status.
