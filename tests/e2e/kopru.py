"""Gercek Python backend ile headless Chromium arasinda JSON pywebview koprusu."""
from __future__ import annotations
import io, json, os, socket, subprocess, sys, tempfile, types
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]

class GercekKopru:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="afudm-e2e-")
        self.root = Path(self.tmp.name)
        import core.paths as paths
        self._paths = paths
        keys = ("BASE", "DATA", "DOWNLOADS", "PLUGINS", "PLUGIN_YEDEK", "DB_PATH", "SESSION_FILE", "ARIA2_LOG", "SECRET_FILE", "API_TOKEN_FILE", "TRACKERS_CACHE")
        self._old = {k: getattr(paths, k) for k in keys}
        paths.BASE = self.root; paths.DATA = self.root / "data"; paths.DOWNLOADS = self.root / "downloads"
        paths.PLUGINS = self.root / "plugins"; paths.PLUGIN_YEDEK = paths.DATA / "eklenti_yedek"
        paths.DB_PATH = paths.DATA / "afudm.db"; paths.SESSION_FILE = paths.DATA / "aria2.session"
        paths.ARIA2_LOG = paths.DATA / "aria2.log"; paths.SECRET_FILE = paths.DATA / "rpc_secret.txt"
        paths.API_TOKEN_FILE = paths.DATA / "api_token.txt"; paths.TRACKERS_CACHE = paths.DATA / "trackers.txt"
        paths.ensure_dirs()
        self.os_calls = []; self.api_calls = []; self.fake_video = None; self._popen_original = subprocess.Popen
        self._run_original = subprocess.run; self._patches = []
        webview = types.ModuleType("webview"); webview.FOLDER_DIALOG = 1; webview.OPEN_DIALOG = 2
        self._start_patch(patch.dict(sys.modules, {"webview": webview}))
        import core.engines as engines
        self._start_patch(patch.object(engines, "eksikler", return_value=[]))
        import core.netcheck as netcheck
        self._start_patch(patch.object(netcheck, "ipv6_usable", return_value=False))
        import core.windows_integration as windows_integration
        self._start_patch(patch.object(windows_integration.WindowsIntegration, "apply", lambda obj, ident: (self.os_calls.append(("registry_apply", str(ident))) or {"ok": True})))
        self._start_patch(patch.object(windows_integration.WindowsIntegration, "remove", lambda obj, ident: (self.os_calls.append(("registry_remove", str(ident))) or {"ok": True})))
        import core.guc as guc
        self._start_patch(patch.object(guc, "uyut", lambda: (self.os_calls.append(("sleep", "")) or False)))
        import app
        from core.manager import Manager
        from api.server import LocalAPI
        self.app = app; self.manager = Manager()
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
        self.local = LocalAPI(self.manager, port=port, lan=True); self.local.start()
        self.api = app.Api(self.manager, self.local); self.api.windows = None; self.api._window = None
        self._start_patch(patch.object(app.os, "startfile", lambda p: self.os_calls.append(("startfile", str(p))), create=True))
        self._start_patch(patch.object(app.Api, "pencere_kapat", lambda api: (self.os_calls.append(("window_close", "")) or {"ok": True})))
        self._start_patch(patch.object(app.subprocess, "Popen", self._popen))
        self._start_patch(patch.object(app.subprocess, "run", self._run))
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(channel=os.environ.get("AFUDM_TEST_BROWSER", "msedge"), headless=True)
        self.page = None; self.pageerrors = []; self.console_errors = []
        self._function_names = [n for n in dir(self.api) if not n.startswith("_") and callable(getattr(self.api, n))]

    def _start_patch(self, p):
        p.start(); self._patches.append(p)

    def _popen(self, args, *a, **kw):
        argv = args if isinstance(args, (list, tuple)) else [args]
        if argv and str(argv[0]).lower().endswith("yt-dlp.exe") and self.fake_video:
            spec = self.fake_video
            class FakeProc:
                returncode = 0
                def __init__(self):
                    a = str(spec["output"].with_suffix(".f137.m4a"))
                    b = str(spec["output"].with_suffix(".f248.webm"))
                    self.stdout = io.StringIO(f'[download] Destination: {a}\n[download] Destination: {b}\n[Merger] Merging formats into "{spec["output"]}"\n')
                def wait(self, *args, **kwargs):
                    spec["output"].write_bytes(spec["content"]); return 0
                def poll(self): return 0
                def terminate(self): pass
                def kill(self): pass
            return FakeProc()
        if argv and str(argv[0]).lower().endswith("explorer"):
            self.os_calls.append(("explorer", str(argv[-1])))
            return types.SimpleNamespace(returncode=0, poll=lambda: 0, wait=lambda: 0)
        return self._popen_original(args, *a, **kw)

    def _run(self, args, *a, **kw):
        argv = args if isinstance(args, (list, tuple)) else [args]
        if argv and str(argv[0]).lower() == "net" and len(argv) > 1 and str(argv[1]).lower() == "share":
            self.os_calls.append(("net share", " ".join(map(str, argv[2:]))))
            return subprocess.CompletedProcess(args, 1, "", "test fake: net share disabled")
        return self._run_original(args, *a, **kw)

    def new_page(self, viewport=None):
        self.page = self.browser.new_page(viewport=viewport or {"width": 1366, "height": 768})
        self.pageerrors = []; self.console_errors = []
        self.page.on("pageerror", lambda err: self.pageerrors.append(str(err)))
        self.page.on("console", lambda msg: self.console_errors.append(msg.text) if msg.type == "error" else None)
        for name in self._function_names:
            def invoke(payload, _name=name):
                wire_args = json.loads(json.dumps(payload, ensure_ascii=False))
                self.api_calls.append((_name, wire_args))
                result = getattr(self.api, _name)(*wire_args)
                return json.loads(json.dumps(result, ensure_ascii=False, default=str))
            self.page.expose_function("__afudm_" + name, invoke)
        proxy = "{" + ",".join(json.dumps(n) + ":(...a)=>{window.__bridgeLog.push([" + json.dumps(n) + ",a]);return window.__afudm_" + n + "(a)}" for n in self._function_names) + "}"
        self.page.add_init_script("window.__bridgeLog=[];window.pywebview={api:" + proxy + "};")
        self.page.goto((ROOT / "ui" / "index.html").as_uri())
        self.page.evaluate("window.dispatchEvent(new Event('pywebviewready'))")
        assert self.page.evaluate("state.ready") is True
        return self.page

    def assert_clean(self, test): test.assertEqual([], self.pageerrors, "uncaught pageerror")

    def close(self):
        try:
            if self.page: self.page.close()
            self.browser.close(); self.pw.stop(); self.api.paylasim_stop(); self.local.stop(); self.manager.stop()
            self.manager.store.conn.close()
        finally:
            for p in reversed(self._patches): p.stop()
            for k, v in self._old.items(): setattr(self._paths, k, v)
            self.tmp.cleanup()
