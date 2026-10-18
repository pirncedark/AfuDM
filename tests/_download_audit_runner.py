"""Isolated audit runner; never writes live application data."""
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import shutil
from contextlib import contextmanager


@contextmanager
def audit_tempdir():
    folder = tempfile.mkdtemp(prefix='afudm_audit_')
    try:
        yield folder
    finally:
        shutil.rmtree(folder, ignore_errors=True)

ROOT = Path(__file__).resolve().parents[1]
if __name__ == '__main__' and len(sys.argv) > 1:
    sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
    from core import paths
    with audit_tempdir() as folder:
        base = Path(folder)
        for name in ('DATA', 'DOWNLOADS', 'PLUGINS', 'PLUGIN_YEDEK', 'DB_PATH', 'SESSION_FILE',
                     'ARIA2_LOG', 'SECRET_FILE', 'API_TOKEN_FILE', 'TRACKERS_CACHE'):
            old = getattr(paths, name)
            setattr(paths, name, base / old.relative_to(ROOT))
        # Temporary test tokens do not need Windows account ACL restrictions.
        from api import server
        server._dosya_iznini_kisitla = lambda path: None
        if os.environ.get('AFUDM_AUDIT_OFFLINE_FONTS') == '1':
            from playwright.sync_api import Page
            original_goto = Page.goto

            def offline_goto(page, *args, **kwargs):
                page.route('https://fonts.googleapis.com/**',
                           lambda route: route.fulfill(status=200, content_type='text/css', body=''))
                return original_goto(page, *args, **kwargs)

            Page.goto = offline_goto
        def guard(event, args):
            if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
                target = Path(os.fsdecode(args[0])).absolute()
                mode, flags = args[1:3]
                writing = (isinstance(mode, str) and any(x in mode for x in 'wax+')) or bool(flags & (os.O_WRONLY | os.O_RDWR))
                if writing and target.is_relative_to(ROOT / 'data'):
                    raise PermissionError('Audit blocked live data write: ' + str(target))
        sys.addaudithook(guard)
        target = ROOT / sys.argv[1]
        sys.argv = [str(target)]
        runpy.run_path(str(target), run_name='__main__')
elif __name__ == '__main__':
    skipped = {
        'baslik_test.py': 'requires visible live AfuDM window',
        'extension_test.py': 'requires live AfuDM and modifies downloads',
        'video_panel_test.py': 'requires live AfuDM and real download',
        'chrome_ekle_test.py': 'opens browser window',
        'port_test.py': 'opens browser window/live port discovery',
        'daemon_test.py': 'requires live AfuDM closed; fixed motor port',
        'senaryolar_test.py': 'E2E manager.start uses the live motor port; cannot safely run alongside AfuDM',
    }
    results = []
    tests = sorted((ROOT / 'tests').rglob('*_test.py')) + sorted((ROOT / 'tests').glob('*_test.mjs'))
    for target in tests:
        if target.name in skipped:
            row = dict(test=target.name, status='skipped', reason=skipped[target.name])
        else:
            command = [sys.executable, str(Path(__file__)), str(target.relative_to(ROOT))] if target.suffix == '.py' else ['node', str(target)]
            try:
                out = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                     encoding='utf-8', errors='replace', timeout=120,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                                     env={**os.environ, 'PYTHONUTF8': '1'})
                row = dict(test=target.name, status='passed' if out.returncode == 0 else 'failed',
                           code=out.returncode, output=(out.stdout + out.stderr)[-12000:])
            except subprocess.TimeoutExpired as exc:
                row = dict(test=target.name, status='timeout', reason=str(exc))
        results.append(row)
        print(row['status'].upper(), row['test'], flush=True)
        (ROOT / ('download_audit_results_' + str(os.getpid()) + '.json')).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print({key: sum(r['status'] == key for r in results) for key in ('passed', 'failed', 'skipped', 'timeout')})
    sys.exit(int(any(r['status'] in ('failed', 'timeout') for r in results)))
