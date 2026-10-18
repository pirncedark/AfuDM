# v2.9.0 startup investigation

## Confirmed defect and fix

The new download prompt bridge (`IndirmePenceresiApi`) stored its parent
bridge as public `api` and native window as public `window`. pywebview's
`inject_pywebview.get_functions` recursively walks public attributes using
`dir` and `getattr`. This exposed the native Window/.NET graph and the whole
parent API during bridge initialization. The existing main `Api` class
already documents the same native graph problem and stores its Window as
`_window` for that reason.

The shipped backup `_yedek/AfuDM.exe.v2.9.0-askida` was inspected read-only
with PyInstaller's `CArchiveReader`. Its embedded `IndirmePenceresiApi`
constructor has `api` and `window` in `co_names`; its embedded pywebview
serializer uses the same recursive `dir`/`getattr` walker. This establishes
that the defect is present in the reported binary, rather than only in
the working source.

The minimal fix makes the prompt references private (`_api`, `_window`),
including the assignment in `main`. Public callable bridge methods and
download behavior retain their names.

The final combined patch also includes independent API startup hardening:
`_ExclusiveServer.server_bind` calls `socketserver.TCPServer.server_bind`
directly and stores the numeric host/actual port instead of performing
`HTTPServer`'s synchronous reverse DNS. Windows exclusive binding remains
enabled. This closes a separately demonstrated startup dependency; it is
not evidence that DNS caused the historical incident.

## Regression evidence

The new test in `tests/download_window_test.py` invokes the **real installed
pywebview serializer**, not a duplicate walker or source-text check. It
supplies a native-window sentinel, records any access to `native`, checks
that parent API methods are not exported, and verifies that the intended
`bekleyen_onayla` method remains exported.

Before production changes:

```text
python scripts/run_isolated_test.py tests/download_window_test.py
[pywebview] Error while processing window.native: Native .NET object must never be traversed
AssertionError: ['native'] != [] : pywebview traversed the prompt native window
Ran 20 tests in 1.052s
FAILED (failures=1)
```

After the private-reference fix:

```text
python scripts/run_isolated_test.py tests/download_window_test.py
Ran 20 tests in 1.044s
OK

python scripts/run_isolated_test.py tests/pending_persistence_test.py
Ran 5 tests in 0.051s
OK

python -m py_compile app.py tests/download_window_test.py
exit 0
```

The real serializer test requires pywebview and skips explicitly when it
is absent; the other prompt tests retain their existing CI stub support.

## Native source smoke result

`python tests/native_startup_smoke.py` exercises the actual `app.main`
with real pywebview/WebView2 in a bounded child process, temporary data,
separate local API port, and only probe-owned windows. It disables
clipboard/tray/system integrations and optional downloads. It checks both
native bridge readiness events, exact prompt methods, a bridge call, and
HTTP `/ping` after readiness. It is opt-in, outside the offline runner,
and requires pywebview, WebView2 and psutil.

This environment did **not** pass the native smoke. Forcing both windows
hidden first produced WebView2 controller initialization error
`0x80070578` (invalid window handle) and a readiness timeout. Retrying with
the normal visible main window also timed out. The final diagnostic attempt
identified `native bridge 0 readiness timeout`: the main window never
reached `_pywebviewready`, before the prompt test could run. Shutdown also
logged a WebView2 user-data cleanup warning (`BrowserProcessId` unavailable)
and a connection reset in pywebview's internal HTTP server. The bounded
attempts closed only their own windows and application processes.

This is a failed native validation, not a passing GUI smoke or proof of
the original hang. No packaged GUI bridge validation is claimed. The
real serializer regression remains the passing evidence for the prompt
reference fix; the native initialization failure requires follow-up in
a working desktop/WebView2 execution environment.

## What was and was not reproduced

Two isolated launches of the original backup executable were performed
using a temporary portable folder, a copied aria2 binary, and separate API
port 34999. The first used a fresh database. The second used a read-only
SQLite backup of the live database into the temporary folder. Both answered
`/ping` with HTTP 200 after 12.08 seconds. The clone disabled plugins,
automation, trackers, updates, sharing/server access, and used a temporary
download directory. No aria2 session or plugin code was copied.
`pending_downloads.json` was absent. Only the process trees created by
these probes were terminated; the user's existing application was untouched.

These probes establish that early API readiness is possible in the old
binary. They do **not** establish native UI or download bridge readiness:
`main` starts the local HTTP API before creating the windows. The original
incident's blocked-thread stack was not captured. Therefore the native
bridge defect is proven, while attribution of every symptom of the original
reported "local API hanging" incident remains unconfirmed. A packaged
native UI smoke test is still needed before claiming that historical
incident is fully reproduced and resolved.

## Ruled-out attribution

`HTTPServer.server_bind` performs synchronous reverse DNS before the serving
thread starts. A controlled delayed-resolver test demonstrated that this can
delay startup (both loopback and LAN cases failed before the fix; see
`startup-regression-before.log`). The actual loopback lookup took 16 ms and
wildcard lookup was immediate in this session. No DNS stall was reproduced
in either binary probe. The final patch includes the independent numeric-bind
hardening and `tests/local_api_startup_test.py`; those controlled failures
must not be conflated with a captured stack from the historical incident.

The currently running root `AfuDM.exe` had an older September 23 timestamp;
it answered `/ping` immediately and is distinct from the September 30 backup.
Its behavior cannot prove the backup binary's historical startup failure.
The live endpoint file could not be read because its ACL denied access;
no tokens were printed and those permissions were not changed.
