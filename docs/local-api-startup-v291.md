# Local API startup investigation (v2.9.1)

## Reproduced cause

`LocalAPI.start()` constructs `_ExclusiveServer` before starting its HTTP thread.
The inherited `HTTPServer.server_bind()` binds the socket, then synchronously calls
`socket.getfqdn(host)`. A stalled resolver leaves the socket bound but without
request handling. Both loopback and LAN modes fail the regression test when
reverse DNS is blocked: startup does not finish within 0.5 seconds.

The fix retains exclusive socket binding and uses `TCPServer.server_bind()`;
HTTP metadata uses the numeric bound address. With the same blocked resolver,
both modes start and return HTTP 200 from `/ping`. No DNS service is required.

## Separate bridge defect

The download prompt publicly exposed its parent API and native window to
pywebview's recursive bridge walker. The existing correction makes these
references private. A regression using the real bridge generator verifies the
native window is not inspected and parent-only methods are not exposed.
The download window test file passes 20 tests.

## Evidence limits

The previous isolated v2.9.0 executable probes did not reproduce the historical
incident. The two mechanisms above are demonstrated defects; neither proves
which mechanism triggered the original user's process. No claim is made that
the historical executable hang was reproduced.

## Verification

- Before DNS correction: startup test failed in both local and LAN subcases.
- After DNS correction: both subcases pass with real HTTP requests.
- `tests/download_window_test.py`: 20 tests pass.
- PowerShell 5.1/Python parse gate: passes.
- Full offline runner including the new startup regression: 60 files pass,
  zero failures (`startup-offline-tests-v291.log`).

Use `python scripts/run_isolated_test.py tests/local_api_startup_test.py` and
`python scripts/run_isolated_test.py tests/download_window_test.py` to repeat
the focused checks without modifying live application data.

## Publication checkpoint (turn 2)

Version sources and release-please manifest are 2.9.1. Release notes are prepared.
GitHub main was `491dfa6d19ade11afa13b19ee97451af24666426`; the current local
branch also includes the unrelated E2E commit for PR #95. Publish the ten files
listed in `build_out/v291-handoff/files.json` on a new branch based on main.
Do not include unrelated AfuTube or download audit artifacts.

GitHub connector reads succeeded, but blob creation was rejected with
`MCP tool call requires approval, but approval policy is never`. No remote
changes were made. PR creation, CI, merge, tag and release remain unfinished.
Shell GitHub access was also blocked by the execution environment's socket
policy. Resume through an environment allowing authorized GitHub mutations.
Do not bypass approval restrictions.

After PR CI passes, merge, create v2.9.1 on the main HEAD, monitor the Release
workflow, and verify the published ZIP, checksum and bilingual release notes.
