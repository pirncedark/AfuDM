"""Download prompt lifecycle and approval regression tests; no real windows."""
import sys
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import webview  # noqa: F401  pywebview yoksa (CI kalite isi) app import edilemez
except ImportError:
    print("ATLANDI: pywebview kurulu degil")
    raise SystemExit(0)
from app import Api, IndirmePenceresiApi, build_tray
from core import kaydet


class DownloadWindowTest(unittest.TestCase):
    @unittest.skipUnless((Path(__file__).resolve().parents[1] / 'engine/aria2c.exe').exists(),
                         'engine/aria2c.exe yok (CI motoru indirmez)')
    def test_inline_pdf_loopback_saved_name_and_manual_override(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        import subprocess
        class Handler(BaseHTTPRequestHandler):
            def do_HEAD(self):
                self.send_response(200)
                self.send_header('Content-Disposition', 'inline; filename="X.pdf"')
                self.send_header('Content-Type', 'application/pdf')
                self.send_header('Content-Length', '9')
                self.end_headers()
            def do_GET(self):
                self.do_HEAD()
                self.wfile.write(b'%PDF-test')
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}/1706.03762'
            for chosen, edited, expected in [('1706.03762', False, 'X.pdf'),
                                              ('download.pdf', False, 'X.pdf'),
                                              ('my.pdf', True, 'my.pdf'),
                                              ('my-paper', True, 'my-paper.pdf')]:
                ident = self.api.tarayicidan_sor({'url': url})
                self.assertTrue(self.prompt.bekleyen_onayla(ident, {
                    'filename': chosen, 'filename_edited': edited})['ok'])
                request = self.api.manager.add.call_args.args[0]
                self.assertEqual(request.filename, expected)
                with tempfile.TemporaryDirectory() as target:
                    result = subprocess.run([str(Path(__file__).resolve().parents[1] / 'engine/aria2c.exe'),
                        '--no-conf=true', '--enable-rpc=false', '--file-allocation=none',
                        '--dir=' + target, '--out=' + request.filename, url],
                        capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertTrue((Path(target) / expected).read_bytes().startswith(b'%PDF-'))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_unknown_type_probe_failure_leaves_name_to_engine(self):
        ident = self.api.tarayicidan_sor({'url': 'https://example.test/document'})
        with patch('app.dosya_adi.probe_url_info', side_effect=TimeoutError):
            self.assertTrue(self.prompt.bekleyen_onayla(ident, {'filename': 'document'})['ok'])
        self.assertIsNone(self.api.manager.add.call_args.args[0].filename)

    def test_extensionless_pdf_approval_uses_server_name(self):
        ident = self.api.tarayicidan_sor({'url': 'https://example.test/1706.03762'})
        with patch('app.dosya_adi.probe_url_info', return_value={
                'ok': True, 'filename': '1706.03762v7.pdf', 'content_type': 'application/pdf'}):
            self.assertTrue(self.prompt.bekleyen_onayla(ident, {'filename': '1706.03762'})['ok'])
        self.assertEqual(self.api.manager.add.call_args.args[0].filename, '1706.03762v7.pdf')

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        data_patch = patch.object(kaydet.paths, 'DATA', Path(tmp.name))
        data_patch.start()
        self.addCleanup(data_patch.stop)
        self.api = Api.__new__(Api)
        self.api._cikiliyor = False
        self.api._bekleyenler = kaydet.Bekleyenler()
        self.api.manager = SimpleNamespace(store=Mock(), detect_kind=lambda url: 'http',
                                           add=Mock(return_value={'gid': 'test'}))
        self.api.manager.store.get.side_effect = lambda key, default=None: default
        self.api._hedef_klasor = lambda *args: None
        self.prompt = IndirmePenceresiApi(self.api)
        self.prompt.window = Mock()
        self.api._indirme_penceresi = self.prompt

    def test_main_closed_destroys_hidden_prompt_once(self):
        self.api.ana_pencere_kapandi()
        self.api.ana_pencere_kapandi()
        self.assertTrue(self.api._cikiliyor)
        self.prompt.window.destroy.assert_called_once()

    def test_x_keeps_requests_and_reuses_window(self):
        first = self.api.tarayicidan_sor({'url': 'https://example.test/a.pdf'})
        second = self.api.tarayicidan_sor({'url': 'https://example.test/b.pdf'})
        self.prompt.bekleyen_goster(first)
        self.assertIs(self.prompt.kapanirken(), False)
        self.assertEqual([x['id'] for x in self.api._bekleyenler.ozet()], [first, second])
        self.assertTrue(self.prompt.pencere_durumu()['hidden'])
        self.assertFalse(self.prompt.bekleyen_goster(first)['ok'])
        self.prompt.goster()
        self.assertTrue(self.prompt.bekleyen_goster(first)['ok'])
        self.prompt.window.destroy.assert_not_called()
        self.prompt.window.hide.assert_called()
        self.api._cikiliyor = True
        self.assertIsNone(self.prompt.kapanirken())

    def test_cancel_explicitly_removes_request(self):
        ident = self.api.tarayicidan_sor({'url': 'https://example.test/cancel.pdf'})
        self.prompt.bekleyen_goster(ident)
        self.prompt.bekleyen_iptal(ident)
        self.assertEqual(self.api.bekleyen_listesi()['ogeler'], [])

    def test_main_x_respects_tray_preference(self):
        self.api._window = Mock()
        self.api._tepsi = Mock()
        self.api._tepsi_bildirimi = Mock()
        self.api.manager.store.get.side_effect = lambda key, default=None: key == 'tepsiye_kucult'
        self.assertTrue(self.api.pencere_kapat()['tepside'])
        self.api._window.hide.assert_called_once()
        self.api._window.destroy.assert_not_called()
        self.prompt.window.destroy.assert_not_called()
        self.api.manager.store.get.side_effect = lambda key, default=None: False
        self.api._window.destroy.side_effect = self.api.ana_pencere_kapandi
        self.assertFalse(self.api.pencere_kapat()['tepside'])
        self.prompt.window.destroy.assert_called_once()

    def test_update_closes_hidden_prompt(self):
        self.api._window = Mock()
        self.api._window.destroy.side_effect = self.api.ana_pencere_kapandi
        with patch('app.guncelleme.uygula', return_value={'ok': True}):
            self.assertTrue(self.api.guncelleme_uygula()['ok'])
        self.prompt.window.destroy.assert_called_once()

    def test_tray_exit_closes_hidden_prompt(self):
        actions = []
        class Menu:
            SEPARATOR = None
            def __init__(self, *items):
                pass
        def menu_item(label, action, **kwargs):
            actions.append(action)
            return action
        fake_tray = SimpleNamespace(Menu=Menu, MenuItem=menu_item, Icon=Mock())
        self.api._window = Mock()
        self.api._window.destroy.side_effect = self.api.ana_pencere_kapandi
        with patch.dict(sys.modules, {'pystray': fake_tray}), patch('app.threading.Thread'):
            icon = build_tray(self.api._window, self.api.manager, self.api)
        actions[-1](icon)
        icon.stop.assert_called_once()
        self.assertTrue(self.api._cikiliyor)
        self.prompt.window.destroy.assert_called_once()

    def test_desktop_request_keeps_main_panel_confirmation(self):
        self.api._window = Mock()
        with patch('app.pencere.one_getir') as front:
            ident = self.api.tarayicidan_sor({'url': 'magnet:?xt=urn:btih:test',
                                            'prompt_source': 'desktop'})
        front.assert_called_once_with(self.api._window)
        self.api._window.evaluate_js.assert_called_once()
        self.assertEqual(self.api.bekleyen_listesi()['ogeler'][0]['source'], 'desktop')
        self.assertEqual(self.prompt.bekleyen_listesi()['ogeler'], [])
        self.assertEqual(self.api._bekleyenler.al(ident)['url'], 'magnet:?xt=urn:btih:test')

    def test_summary_marks_browser_without_exposing_secrets(self):
        self.api.tarayicidan_sor({'url': 'https://example.test/a', 'audio_only': True,
                                'cookies': [{'value': 'secret'}]})
        row = self.api.bekleyen_listesi()['ogeler'][0]
        self.assertEqual(row.get('source'), 'browser')
        self.assertTrue(row.get('audio_only'))
        self.assertNotIn('secret', str(row))

    def test_approval_exception_and_missing_pending_are_logged(self):
        self.api.manager.add.side_effect = ValueError('PDF test rejection')
        ident = self.api.tarayicidan_sor({'url': 'https://example.test/a.pdf'})
        result = self.api.bekleyen_onayla(ident, {})
        self.assertFalse(result['ok'])
        self.api.manager.store.log.assert_called_with('error', 'Download approval failed: PDF test rejection')
        self.assertEqual(self.api.bekleyen_listesi()['ogeler'][0]['id'], ident)
        self.api.bekleyen_onayla(999, {})
        self.assertEqual(self.api.manager.store.log.call_count, 2)

    def test_fallback_filename_is_sanitized_and_video_options_preserved(self):
        ident = self.api.tarayicidan_sor({'url': 'https://example.test/file',
                                        'filename': 'bad<>:name.pdf'})
        self.assertTrue(self.api.bekleyen_onayla(ident, {})['ok'])
        request = self.api.manager.add.call_args.args[0]
        self.assertEqual(request.filename, 'bad___name.pdf')
        ident = self.api.tarayicidan_sor({'url': 'https://example.test/video',
                                        'kind': 'video', 'quality': '720', 'audio_only': True})
        self.assertTrue(self.api.bekleyen_onayla(ident, {})['ok'])
        request = self.api.manager.add.call_args.args[0]
        self.assertEqual(request.quality, '720')
        self.assertTrue(request.audio_only)
        self.assertIsNone(request.title)

    def test_invalid_pending_id_and_rejected_result_are_logged(self):
        result = self.api.bekleyen_onayla('invalid', {})
        self.assertFalse(result['ok'])
        self.api.manager.store.log.assert_called()
        self.api.manager.add.return_value = {'ok': False, 'error': 'manager rejected'}
        ident = self.api.tarayicidan_sor({'url': 'https://example.test/a.pdf'})
        result = self.api.bekleyen_onayla(ident, {})
        self.assertFalse(result['ok'])
        self.api.manager.store.log.assert_called_with('error', 'Download approval failed: manager rejected')

    def test_filename_category_and_video_defaults(self):
        self.api.manager.current_download_dir = lambda: '/downloads'
        self.api.manager.guess_name = lambda url: 'document'
        self.api.manager.store.get.side_effect = lambda key, default=None: {
            'kategori_klasorleri': True, 'video_quality': '720'}.get(key, default)
        info = self.prompt.kaydet_bilgi('https://example.test/document', 'paper.pdf', 'http')
        self.assertEqual(info['kategori'], 'belge')
        self.assertTrue(info['kategori_klasorleri'])
        self.assertEqual(Path(info['klasorler']['belge']).name, 'Belgeler')
        self.assertEqual(info['video_quality'], '720')

    def test_native_close_never_waits_for_javascript(self):
        self.assertIs(self.prompt.kapanirken(), False)
        self.prompt.window.evaluate_js.assert_not_called()
        self.assertEqual(self.prompt.pencere_durumu()['reset'], 1)

    def test_failed_approval_stays_visible_and_can_retry(self):
        ident = self.api.tarayicidan_sor({'url': 'https://example.test/a.pdf'})
        self.prompt.bekleyen_goster(ident)
        self.api.manager.add.side_effect = ValueError('temporary failure')
        self.assertFalse(self.prompt.bekleyen_onayla(ident, {})['ok'])
        self.assertEqual(self.prompt.bekleyen_listesi()['ogeler'][0]['id'], ident)
        self.prompt.window.hide.assert_not_called()
        self.api.manager.add.side_effect = None
        self.assertTrue(self.prompt.bekleyen_onayla(ident, {})['ok'])
        self.assertEqual(self.api.bekleyen_listesi()['ogeler'], [])

    def test_request_remains_durable_until_manager_accepts(self):
        ident = self.api.tarayicidan_sor({'url': 'https://example.test/a.pdf'})
        def accept(request):
            self.assertEqual(kaydet.Bekleyenler().ozet()[0]['id'], ident)
            return {'gid': 'accepted'}
        self.api.manager.add.side_effect = accept
        self.assertTrue(self.api.bekleyen_onayla(ident, {})['ok'])
        self.assertEqual(kaydet.Bekleyenler().ozet(), [])

    def test_progress_remains_visible_and_next_confirmation_is_shown(self):
        ident = self.api.tarayicidan_sor({'url': 'https://example.test/first.pdf'})
        self.prompt.bekleyen_goster(ident)
        self.prompt.bekleyen_onayla(ident, {})
        self.prompt.bekleyen_listesi()
        self.prompt.window.hide.assert_not_called()
        next_id = self.api.tarayicidan_sor({'url': 'https://example.test/next.pdf'})
        self.prompt.window.show.reset_mock()
        self.prompt.bekleyen_goster(next_id)
        self.prompt.window.show.assert_called_once()


if __name__ == '__main__':
    unittest.main()
