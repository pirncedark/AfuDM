import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import io
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import pdf_canli_dene, verify_exe
from core import db


class ToolsTest(unittest.TestCase):
    def test_pdf_snapshot_reads_real_schema_and_filters_old_requests(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(db.paths, 'ensure_dirs'):
                store = db.Store(str(root / 'afudm.db'))
            try:
                started = time.time()
                store.conn.execute(
                    'INSERT INTO downloads(gid,source,added_at,status) VALUES(?,?,?,?)',
                    ('old', 'https://example.test/proof', started - 10, 'complete'))
                store.conn.execute(
                    'INSERT INTO downloads(gid,source,added_at,status) VALUES(?,?,?,?)',
                    ('new', 'https://example.test/proof', started + 1, 'complete'))
                store.conn.commit()
                store.log('info', 'Download approval accepted', gid='new')
                row, events = pdf_canli_dene.snapshot(root, 'https://example.test/proof', started)
                self.assertEqual(row['gid'], 'new')
                self.assertEqual(events[0]['gid'], 'new')
                self.assertEqual(events[0]['message'], 'Download approval accepted')
                self.assertIsNone(pdf_canli_dene.snapshot(root, 'https://example.test/other', started)[0])
            finally:
                store.conn.close()

    def test_headless_gate_rejects_missing_module_and_ui_import(self):
        app = compile('if "--headless" in args:\n import headless', 'app', 'exec')
        class Archive:
            def extract(self, name):
                return compile('def calistir():\n return 0', name, 'exec')
        verify_exe.verify_headless(Archive(), app)
        class Missing:
            def extract(self, name):
                raise KeyError(name)
        with self.assertRaisesRegex(RuntimeError, 'headless'):
            verify_exe.verify_headless(Missing(), app)
        class UI:
            def extract(self, name):
                return compile('import webview\ndef calistir():\n return 0', name, 'exec')
        with self.assertRaisesRegex(RuntimeError, 'webview'):
            verify_exe.verify_headless(UI(), app)

    def test_pdf_evidence_requires_real_pdf_and_matching_event(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'api_endpoint.json').write_text(json.dumps({'port': 6811, 'token': 'SECRET'}))
            pdf = root / 'proof.pdf'
            args = SimpleNamespace(data=root, url='https://example.test/pdf?secret=SECRET',
                filename='proof.pdf', wait=1, output=root / 'evidence.json')
            for content, gid, expected in ((b'%PDF-1.7', 'proof', 0), (b'HTML', 'proof', 1),
                                            (b'%PDF-1.7', 'wrong', 1)):
                pdf.write_bytes(content)
                row = {'gid': 'proof', 'status': 'complete', 'filename': pdf.name,
                       'dest_dir': str(root), 'error': None}
                events = [{'id': 1, 'level': 'info', 'gid': gid,
                           'message': 'Download approval accepted'},
                          {'id': 2, 'level': 'error', 'gid': '', 'message': args.url}]
                with patch.object(pdf_canli_dene.urllib.request, 'urlopen',
                    return_value=io.BytesIO(b'{"ok":true,"pending":true,"id":1}')), \
                    patch.object(pdf_canli_dene, 'snapshot', return_value=(row, events)):
                    self.assertEqual(pdf_canli_dene.run(args), expected)
                report = args.output.read_text('utf-8')
                self.assertNotIn('SECRET', report)
                self.assertEqual(json.loads(report)['ok'], expected == 0)


if __name__ == '__main__':
    unittest.main()
