"""Run one offline test with temporary application data and downloads."""
from pathlib import Path
import os
import runpy
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = (ROOT / sys.argv[1]).resolve()
    if not target.is_relative_to(ROOT / "tests") or not target.is_file():
        raise ValueError("Expected a test file inside tests/")
    sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
    from core import paths

    # Some legacy tests retain SQLite connections until process exit on Windows.
    with tempfile.TemporaryDirectory(prefix="afudm-test-", ignore_cleanup_errors=True) as folder:
        base = Path(folder)
        for name in ("DATA", "DOWNLOADS", "PLUGINS", "PLUGIN_YEDEK", "DB_PATH",
                     "SESSION_FILE", "ARIA2_LOG", "SECRET_FILE", "API_TOKEN_FILE",
                     "TRACKERS_CACHE"):
            setattr(paths, name, base / getattr(paths, name).relative_to(ROOT))

        def guard(event, args):
            if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
                path = Path(os.fsdecode(args[0])).absolute()
                mode, flags = args[1:3]
                writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or bool(
                    (flags or 0) & (os.O_WRONLY | os.O_RDWR))
                if writing and path.is_relative_to(ROOT / "data"):
                    raise PermissionError("Test attempted to write live application data")

        sys.addaudithook(guard)
        # Offline UI tests must not depend on Google's font service.
        if target.name in ("ui_ux_gate_test.py", "ui_startup_test.py",
                            "download_window_layout_test.py"):
            from playwright.sync_api import Page
            original_goto = Page.goto

            def offline_goto(page, *args, **kwargs):
                page.route("https://fonts.googleapis.com/**", lambda route: route.fulfill(
                    status=200, content_type="text/css", body=""))
                return original_goto(page, *args, **kwargs)

            Page.goto = offline_goto
        sys.argv = [str(target)]
        runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
