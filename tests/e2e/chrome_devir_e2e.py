"""Real headless Chromium/extension handoff; run: python tests/e2e/chrome_devir_e2e.py

Requires Playwright's full Chromium (not headless-shell) and engine/aria2c.exe.
Intentionally excluded from scripts/test.ps1. All application/browser data is temporary.
"""
from __future__ import annotations

import atexit
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    assert not 6810 <= port <= 6830
    return port


def small_pdf():
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>']
    data = b'%PDF-1.4\n'
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += f'{index} 0 obj\n'.encode() + obj + b'\nendobj\n'
    start = len(data)
    data += b'xref\n0 4\n0000000000 65535 f \n'
    data += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
    return data + f'trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode()


PDF = small_pdf()
ZIP = b'PK\x03\x04' + b'AfuDM-test' * 150000


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_HEAD(self):
        self.respond(False)

    def do_GET(self):
        self.respond(True)

    def respond(self, body):
        if self.path == '/':
            content, mime, disposition = b'<html><body>Download fixture</body></html>', 'text/html', ''
        elif self.path.startswith('/doc?'):
            content, mime, disposition = PDF, 'application/pdf', 'inline; filename="rapor.pdf"'
        elif self.path.startswith('/dosya.zip'):
            content, mime, disposition = ZIP, 'application/octet-stream', 'attachment; filename="dosya.zip"'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        if disposition:
            self.send_header('Content-Disposition', disposition)
        self.end_headers()
        if body:
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError):
                pass


def main():
    from core import paths

    # Audit hook remains active until process exit and protects the live instance.
    def guard(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            target = Path(os.fsdecode(args[0])).resolve()
            mode, flags = args[1:3]
            writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or bool(
                (flags or 0) & (os.O_WRONLY | os.O_RDWR))
            if writing and target.is_relative_to(ROOT / 'data'):
                raise PermissionError('E2E blocked live data write')
    sys.addaudithook(guard)

    with tempfile.TemporaryDirectory(prefix='afudm-chrome-e2e-') as folder, ExitStack() as stack:
        base = Path(folder)
        for name in ('DATA', 'DOWNLOADS', 'PLUGINS', 'PLUGIN_YEDEK', 'DB_PATH',
                     'SESSION_FILE', 'ARIA2_LOG', 'SECRET_FILE', 'API_TOKEN_FILE', 'TRACKERS_CACHE'):
            stack.enter_context(patch.object(paths, name, base / getattr(paths, name).relative_to(ROOT)))
        from core import daemon
        rpc_port = free_port()
        stack.enter_context(patch.object(daemon, 'RPC_PORT', rpc_port))
        stack.enter_context(patch.object(daemon, 'RPC_PORT_SON', rpc_port))
        # Keep aria2's torrent side files/ports isolated, while retaining its real HTTP engine.
        real_args = daemon._args
        def isolated_args(*args):
            return real_args(*args) + ['--enable-dht=false', '--enable-dht6=false',
                                       '--bt-enable-lpd=false', f'--listen-port={free_port()}']
        stack.enter_context(patch.object(daemon, '_args', isolated_args))
        from core.manager import Manager
        from api import server
        stack.enter_context(patch.object(server, '_dosya_iznini_kisitla', lambda _path: None))
        # Avoid OS integration and optional engine installation in this isolated test.
        stack.enter_context(patch('core.manager.WindowsIntegration', return_value=None))
        manager = Manager()
        stack.callback(manager.store.conn.close)
        manager.store.set('auto_update_trackers', False)
        manager.store.set('kaydetme_penceresi', True)
        manager.store.set('download_dir', str(paths.DOWNLOADS))
        stack.callback(manager.stop)
        manager.start()
        # ExitStack owns shutdown before path patches are restored; a second
        # atexit shutdown would otherwise use the live application's paths.
        atexit.unregister(manager.daemon.stop)
        assert manager.daemon.proc is not None and manager.rpc.alive(), manager.last_error
        assert manager.daemon.port == rpc_port
        def join_poller():
            manager._stop.set()
            if manager._poller:
                manager._poller.join(timeout=5)
        stack.callback(join_poller)

        import app
        stack.enter_context(patch.object(app.engines, 'eksikler', return_value=[]))
        local_api = server.LocalAPI(manager, port=free_port())
        stack.callback(local_api.stop)
        api = app.Api(manager, local_api)
        main_window = Mock(name='main_window')
        api._window = main_window
        approvals, errors = [], []
        class Prompt:
            def goster(self):
                try:
                    for item in api.bekleyen_listesi()['ogeler']:
                        result = api.bekleyen_onayla(item['id'], {})
                        assert result.get('ok'), result
                        approvals.append(result)
                except Exception as exc:
                    errors.append(exc)
                    raise
        api._indirme_penceresi = Prompt()
        stack.enter_context(patch.object(server._Handler, 'on_ask', api.tarayicidan_sor))
        foreground = stack.enter_context(patch.object(app.pencere, 'one_getir'))
        local_api.start()
        assert not 6810 <= local_api.port <= 6830

        httpd = ThreadingHTTPServer(('127.0.0.1', 0), FixtureHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        stack.callback(thread.join, 5)
        stack.callback(httpd.server_close)
        stack.callback(httpd.shutdown)
        origin = f'http://127.0.0.1:{httpd.server_port}'

        from playwright.sync_api import sync_playwright
        playwright = stack.enter_context(sync_playwright())
        chrome_dir = base / 'chrome-downloads'
        chrome_dir.mkdir()
        context = playwright.chromium.launch_persistent_context(
            str(base / 'profile'), channel='chromium', headless=True,
            accept_downloads=True, downloads_path=str(chrome_dir),
            args=[f'--disable-extensions-except={ROOT / "extension"}',
                  f'--load-extension={ROOT / "extension"}'])
        stack.callback(context.close)
        worker = context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
        worker.evaluate('cfg => chrome.storage.local.set(cfg)', {
            'port': local_api.port, 'token': local_api.token, 'enabled': True,
            'uzantiAcik': True, 'minSizeMB': 0, 'videoCatch': False})
        # Explicit CDP path prevents writes to the user's Downloads directory.
        cdp = context.new_cdp_session(context.pages[0])
        cdp.send('Browser.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': str(chrome_dir)})
        page = context.pages[0]
        page.goto(origin)
        worker.evaluate('''() => {
            globalThis.e2eCreated = [];
            chrome.downloads.onCreated.addListener(item => e2eCreated.push({id:item.id, url:item.url}));
        }''')

        def rows(url):
            return [row for row in manager.store.list() if row['source'] == url]
        def downloads(url):
            return worker.evaluate('url => chrome.downloads.search({url})', url)
        def wait(predicate, label, timeout=30):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if errors:
                    raise AssertionError(f'Prompt failed: {errors}')
                result = predicate()
                if result:
                    return result
                page.wait_for_timeout(100)
            raise AssertionError(f'Timed out: {label}; rows={manager.store.list()}')
        def trigger(url):
            page.evaluate('''url => {
                const a = document.createElement('a'); a.href = url; a.download = '';
                document.body.appendChild(a); a.click(); a.remove();
            }''', url)
        def created(url, count):
            return worker.evaluate('url => e2eCreated.filter(x => x.url === url).length', url) >= count
        def cancelled(url):
            return all(row['state'] == 'interrupted' for row in downloads(url))

        pdf_url = origin + '/doc?id=1'
        trigger(pdf_url)
        wait(lambda: len(rows(pdf_url)) == 1 and rows(pdf_url)[0]['status'] == 'complete', 'PDF completion')
        pdf_files = list(paths.DOWNLOADS.rglob('rapor.pdf'))
        assert len(pdf_files) == 1 and pdf_files[0].read_bytes() == PDF
        assert len(rows(pdf_url)) == 1 and len(approvals) == 1
        assert not created(pdf_url, 1), 'Preflight must prevent Chrome download creation'
        wait(lambda: cancelled(pdf_url), 'Chrome PDF cancellation/erasure')
        wait(lambda: not any(p.is_file() for p in chrome_dir.rglob('*')), 'no Chrome PDF artifact')
        print('PASS 1: PDF handoff, rapor.pdf, real aria2 content, Chrome cleanup')

        zip_url = origin + '/dosya.zip?duplicate=1'
        trigger(zip_url)
        trigger(zip_url)
        wait(lambda: len(rows(zip_url)) == 1 and rows(zip_url)[0]['status'] == 'complete', 'duplicate handoff')
        wait(lambda: cancelled(zip_url), 'both Chrome downloads cancelled/erased')
        page.wait_for_timeout(1500)
        assert len(rows(zip_url)) == 1
        assert not created(zip_url, 1), 'Double click must not create Chrome downloads'
        zip_files = list(paths.DOWNLOADS.rglob('dosya.zip'))
        assert len(zip_files) == 1 and zip_files[0].read_bytes() == ZIP
        print('PASS 3: two clicks, zero Chrome download events, one AfuDM download')

        local_api.stop()
        offline_url = origin + '/dosya.zip?offline=1'
        count_before = len(manager.store.list())
        trigger(offline_url)
        page.wait_for_timeout(4000)
        assert not created(offline_url, 1), 'Failed preflight must not silently download in Chrome'
        assert not rows(offline_url) and len(manager.store.list()) == count_before
        print('PASS 2: API stopped, no parallel Chrome download or AfuDM record')

        assert not any(call.args and call.args[0] is main_window for call in foreground.call_args_list)
        main_window.evaluate_js.assert_not_called()
        print('PASS 4: browser prompt never brings main panel forward')
    print('PASS: all four scenarios; isolated resources cleaned up')


if __name__ == '__main__':
    main()
