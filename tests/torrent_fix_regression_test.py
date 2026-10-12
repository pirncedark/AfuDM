import sys, unittest, tempfile
from pathlib import Path
from unittest.mock import patch
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from torrent_onekle_test import DummyManager
from core.db import Store
from core.rpc import Aria2Error

class TorrentFixTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.m = DummyManager()
        self.m.store = Store(':memory:')
        self.m.store.set('download_dir', self.tmp.name)
        self.m._removed_gids = set()
        self.m._removed_hashes = set()
        self.m.last_error = ''
        self.m.rpc.global_stat = lambda: {}
        self.m.rpc.alive = lambda: True
        self.m._proksi = lambda options: None
    def test_preview_dir(self):
        self.m.torrent_on_ekle('magnet:?xt=urn:btih:abc')
        self.assertEqual(self.m.rpc.eklenenler[0]['options'].get('dir'), self.tmp.name)
    def test_snapshot_with_minimal_manager_without_lock(self):
        del self.m._lock
        self.assertEqual(self.m.snapshot()['items'], [])
    def test_preview_hidden_with_child(self):
        gid = self.m.torrent_on_ekle('magnet:?xt=urn:btih:abc')
        self.assertEqual(self.m.snapshot()['items'], [])
        self.m.rpc.durumlar[gid]['followedBy'] = ['child']
        self.m.rpc.durumlar['child'] = {'gid':'child','following':gid,'infoHash':'abc','status':'paused'}
        self.m.rpc.paused.add('child')
        self.assertEqual(self.m.snapshot()['items'], [])
        result = self.m.add('magnet:?xt=urn:btih:abc', kind='torrent', adopt_gid=gid, dest_dir=self.tmp.name)
        self.assertEqual(result['gid'], 'child')
        self.assertEqual(len(self.m.store.list()), 1)
        self.m.rpc.tell_active = lambda: [self.m.rpc.durumlar['child']]
        self.assertEqual(len(self.m.snapshot()['items']), 1)
    def test_adopt_dir_failure_does_not_resume(self):
        gid = self.m.torrent_on_ekle('magnet:?xt=urn:btih:abc')
        self.m.rpc.change_option = lambda *args: (_ for _ in ()).throw(Aria2Error(1, 'dir rejected'))
        with self.assertRaisesRegex(ValueError, 'klasor'):
            self.m.add('magnet:?xt=urn:btih:abc', kind='torrent', adopt_gid=gid, dest_dir=self.tmp.name)
        self.assertEqual(self.m.rpc.devam_edenler, [])
    def test_new_jobs_and_explicit_dir(self):
        for n, kind in enumerate(('http','torrent')):
            folder = str(Path(self.tmp.name) / kind)
            self.m.store.set('download_dir', folder)
            source = f'https://example.invalid/{n}.zip' if kind == 'http' else 'magnet:?xt=urn:btih:def'
            self.m.add(source, kind=kind)
            self.assertEqual(self.m.rpc.eklenenler[-1]['options']['dir'], folder)
        chosen = str(Path(self.tmp.name) / 'chosen')
        self.m.add('https://example.invalid/chosen.zip', dest_dir=chosen)
        self.assertEqual(self.m.rpc.eklenenler[-1]['options']['dir'], chosen)
    def test_category_and_explicit_folder_priority(self):
        from core.servis import AfuDMServis
        service = object.__new__(AfuDMServis)
        service.manager, service.store = self.m, self.m.store
        self.m.store.set('kategori_klasorleri', True)
        for kind in ('http', 'torrent'):
            folder = service.hedef_klasor('', 'https://example.invalid/a.zip', kind, '')
            self.assertTrue(Path(folder).is_relative_to(Path(self.tmp.name)))
            self.assertEqual(service.hedef_klasor(self.tmp.name, '', kind, ''), self.tmp.name)
    def test_auto_adopt_releases_preview_parent(self):
        gid = self.m.torrent_on_ekle('magnet:?xt=urn:btih:abc')
        self.m.rpc.durumlar[gid]['followedBy'] = ['child']
        self.m.rpc.durumlar['child'] = {'gid':'child','following':gid,'infoHash':'abc','status':'paused'}
        self.m.rpc.paused.discard(gid)
        self.m.rpc.paused.add('child')
        self.m.snapshot()
        result = self.m.add('magnet:?xt=urn:btih:abc', kind='torrent')
        self.assertEqual(result['gid'], 'child')
        self.m.rpc.tell_active = lambda: [self.m.rpc.durumlar['child']]
        self.assertEqual(len(self.m.snapshot()['items']), 1)
    def test_cancelled_child_stays_hidden(self):
        gid = self.m.torrent_on_ekle('magnet:?xt=urn:btih:abc')
        self.m.rpc.durumlar[gid]['followedBy'] = ['child']
        self.m.rpc.durumlar['child'] = {'gid':'child','infoHash':'abc','status':'removed'}
        self.m.rpc.paused.add('child')
        self.m.torrent_on_iptal(gid)
        self.assertEqual(self.m.snapshot()['items'], [])
    def test_child_reattaches_local_or_http_torrent_row(self):
        row_id = self.m.store.add(kind='torrent', source='https://example.invalid/a.torrent', title='a', dest_dir=self.tmp.name, options={})
        self.m.store.attach_gid(row_id, 'parent')
        self.m.store.update_by_id(row_id, status='paused')
        self.m.rpc.durumlar['parent'] = {'gid':'parent','status':'complete','followedBy':['child']}
        self.m.rpc.durumlar['child'] = {'gid':'child','status':'paused','following':'parent','infoHash':'abc'}
        self.m.rpc.paused.update(('parent', 'child'))
        self.assertEqual(len(self.m.snapshot()['items']), 1)
        self.assertEqual(self.m.store.by_id(row_id)['gid'], 'child')
        self.assertEqual(len(self.m.store.list()), 1)
    def test_daemon_metadata_disabled(self):
        from core.daemon import _args
        with patch('core.daemon.netcheck.aria2_ipv6_args', return_value=[]):
            self.assertIn('--bt-save-metadata=false', _args('test', self.tmp.name))
    def test_local_torrent_preview_and_launch(self):
        torrent = Path(self.tmp.name) / 'source.torrent'
        torrent.write_bytes(b'd4:infod1:a1:bee')
        gid = self.m.torrent_on_ekle(str(torrent))
        result = self.m.add(str(torrent), kind='torrent', adopt_gid=gid, dest_dir=self.tmp.name)
        self.assertEqual(result['gid'], gid)
        self.assertEqual(len(self.m.rpc.eklenenler), 1)
        self.assertEqual(self.m.rpc.secimler[gid]['dir'], self.tmp.name)
    def test_metadata_not_saved_in_payload_dir(self):
        self.m.torrent_on_ekle('magnet:?xt=urn:btih:abc')
        self.assertEqual(self.m.rpc.eklenenler[0]['options'].get('bt-save-metadata'), 'false')

if __name__ == '__main__':
    unittest.main(verbosity=2)
