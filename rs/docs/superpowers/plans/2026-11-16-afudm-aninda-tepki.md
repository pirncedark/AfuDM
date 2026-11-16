# AfuDM Immediate Queue Controls Implementation Plan

> **For agentic workers:** Execute this plan inline with `superpowers:executing-plans`; apply TDD to each behavior.

**Goal:** Make pause, resume, remove, delete-files, recovery, and bulk controls acknowledge immediately while durable intent is applied to aria2 in background.

**Architecture:** Persist intent before dispatching an independent background operation. Recovery treats `removing` and `removed` as tombstones and retries pending work after the engine is reachable. The UI updates its local queue immediately and rolls back only when the backend rejects the intent.

**Tech Stack:** Rust workspace, SQLite Store, aria2 RPC, Tauri web UI.

**Spec:** `C:/Users/afuuu/Desktop/afuproject/_gorev/2026-11-16/GOREV_AFUDM_ANINDA_TEPKI.md`

## Global Constraints

- Work only in `AfuDM_wt_aninda/rs`, branch `fix/afudm-aninda-tepki`.
- Do not use destructive git commands, merge, or touch the installed app or other worktrees.
- Keep downloads intact; async deletion operates only on user-requested delete-files targets within the configured download root.
- Required checks: `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test` with the specified `AFUDM_ARIA2_TEST_EXE`.
- Commit, push this branch, create an English-title PR; do not merge or release.

## Review Focus

- A blocked RPC must not delay the user command; test a 30-second fake RPC and a sub-100ms response.
- A pending removal must stay hidden and must not be recovered after restart; test durable removal intent.
- Delete-files must retry until aria2 releases its files and must remain confined to the download root; test retries and safe paths.
- Pause/resume ordering and bulk operations must not leave UI/backend state inconsistent; test UI optimism and backend intent.
- Snapshot/recovery synchronization must not overwrite a pending intent; test status preservation during sync.

### Task 1: Persisted, nonblocking backend controls

**Files:** `crates/afudm-core/src/queue.rs`, `crates/afudm-core/src/queue/files.rs`, `crates/afudm-core/src/queue/tests.rs`

- [ ] Add failing fake-RPC tests for immediate pause/resume/remove, retry after RPC recovery, and restart recovery of `removing` records.
- [ ] Implement immediate intent persistence, background retries, pending-remove recovery, and sync/recovery guards.
- [ ] Run focused tests and the crate suite.
- [ ] Commit backend change.

### Task 2: Immediate UI and bulk behavior

**Files:** `app/ui/app.js`

- [ ] Add/adjust UI tests for optimistic remove, pause/resume, bulk removal, and rollback on command rejection.
- [ ] Apply local state updates before awaiting the command; preserve rollback behavior.
- [ ] Run focused UI checks and the project's UI test suite.
- [ ] Commit UI change.

### Task 3: Full verification and delivery

**Files:** `SONUC_AFUDM_ANINDA_TEPKI.md` outside the worktree; no other worktree writes.

- [ ] Run `cargo fmt --check`, required clippy, and full cargo tests; record literal outputs.
- [ ] Review diff and commit history; create final commit if needed.
- [ ] Push branch and create PR without merging.
- [ ] Write the requested SONUC file with evidence, changed files, test output, PR link, and scope exclusions.
