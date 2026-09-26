import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.manager import Manager
from core.rpc import Aria2Error
from core.models import DownloadRequest

class DummyRPC:
    def __init__(self):
        self.eklenenler = []
        self.secimler = {}
        self.kaldirmalar = []
        self.devam_edenler = []
        self.durumlar = {}
        self.paused = set()
        
    def add_torrent(self, payload, options):
        gid = f"tor_{len(self.eklenenler)}"
        self.eklenenler.append({"type": "torrent", "gid": gid, "options": options})
        self.durumlar[gid] = {"gid": gid, "infoHash": "abc", "status": "paused", "bittorrent": {"info": {"name": "test_torrent"}}}
        self.paused.add(gid)
        return gid
        
    def add_uri(self, uris, options):
        gid = f"mag_{len(self.eklenenler)}"
        self.eklenenler.append({"type": "magnet", "gid": gid, "uris": uris, "options": options})
        self.durumlar[gid] = {"gid": gid, "infoHash": "abc", "status": "paused"}
        self.paused.add(gid)
        return gid
        
    def tell_status(self, gid, keys=None):
        if gid not in self.durumlar:
            raise Aria2Error(1, "Not found")
        return self.durumlar[gid]
        
    def change_option(self, gid, options):
        if gid not in self.secimler:
            self.secimler[gid] = {}
        self.secimler[gid].update(options)
        
    def get_files(self, gid):
        if gid.startswith("mag_") and "bittorrent" not in self.durumlar[gid]:
            return []
        if gid.startswith("tor_"):
            return [
                {"index": "1", "path": "türkçe_belge.txt", "length": "100", "completedLength": "0", "selected": "true"}
            ]
        return [
            {"index": "1", "path": "dosya1.txt", "length": "100", "completedLength": "0", "selected": "true"},
            {"index": "2", "path": "dosya2.txt", "length": "200", "completedLength": "0", "selected": "true"}
        ]
        
    def tell_active(self, keys=None):
        return []
    def tell_waiting(self, offset, num, keys=None):
        return [d for gid, d in self.durumlar.items() if gid in self.paused][offset:offset + num]
    def tell_stopped(self, offset, num, keys=None):
        return []
        
    def unpause(self, gid):
        self.devam_edenler.append(gid)
        self.paused.discard(gid)
        
    def remove(self, gid, force=False):
        self.kaldirmalar.append(gid)
        
    def remove_result(self, gid):
        pass

class DummyStore:
    def __init__(self):
        self.kayitlar = {}
        self._id = 1
        self.secimler = {}
    def rules_list(self):
        return []

    def get(self, key, default=None):
        return default
        
    def by_gid(self, gid):
        for k in self.kayitlar.values():
            if k.get("gid") == gid:
                return k
        return None
        
    def by_id(self, row_id):
        return self.kayitlar.get(row_id)
    def list(self, limit=100):
        return []
        
    def add(self, **kwargs):
        row_id = self._id
        self._id += 1
        import json
        if "options" in kwargs:
            kwargs["options"] = json.dumps(kwargs["options"])
        self.kayitlar[row_id] = {"id": row_id, "gid": None, **kwargs}
        return row_id
        
    def attach_gid(self, row_id, gid):
        self.kayitlar[row_id]["gid"] = gid
        
    def torrent_dosya_secimlerini_kaydet(self, gid, indeksler):
        self.secimler[gid] = indeksler
        
    def torrent_dosya_secimi_var(self, gid):
        return gid in self.secimler
        
    def torrent_dosya_secimleri(self, gid):
        return self.secimler.get(gid, [])
        
    def log(self, level, msg, gid=""):
        pass
        
class DummyManager(Manager):
    def __init__(self):
        self.rpc = DummyRPC()
        self.store = DummyStore()
        self._cerezler = {}
        self.video_jobs = {}
        import threading
        self._lock = threading.Lock()
        self._video_seq = 0

def test_duraklatilmis_ekleme_gid_dondurur():
    mgr = DummyManager()
    gid = mgr.torrent_on_ekle("magnet:?xt=urn:btih:1234")
    assert gid.startswith("mag_")
    eklenen = mgr.rpc.eklenenler[0]
    assert eklenen["options"].get("pause") == "true"
    
def test_metadata_gelmeden_dosya_listesi_bos_doner():
    mgr = DummyManager()
    gid = mgr.torrent_on_ekle("magnet:?xt=urn:btih:1234")
    dosyalar = mgr.torrent_dosyalari(gid)
    assert getattr(dosyalar, "hazir_degil", False) is True
    assert len(dosyalar) == 0

def test_secim_uygulanip_devam_ettirilince_indeksler_gonderilir():
    mgr = DummyManager()
    mgr._proksi = lambda opts: None
    gid = mgr.torrent_on_ekle("magnet:?xt=urn:btih:1234")
    req = DownloadRequest.from_mapping({
        "source": "magnet:?xt=urn:btih:1234",
        "kind": "torrent",
        "adopt_gid": gid,
        "selected_files": [2]
    })
    child_gid = "mag_0_child"
    mgr.rpc.durumlar[gid]["followedBy"] = [child_gid]
    mgr.rpc.durumlar[child_gid] = {"gid": child_gid, "infoHash": "def", "bittorrent": {"info": {"name": "test"}}}
    mgr.add(req)
    assert mgr.rpc.secimler[child_gid]["select-file"] == "2"
    assert child_gid in mgr.rpc.devam_edenler

def test_iptal_edildiginde_indirme_kaldiriliyor():
    mgr = DummyManager()
    gid = mgr.torrent_on_ekle("magnet:?xt=urn:btih:1234")
    mgr.torrent_on_iptal(gid)
    assert gid in mgr.rpc.kaldirmalar

def test_tek_dosyali_ve_turkce_isimli_torrent():
    mgr = DummyManager()
    mgr._proksi = lambda opts: None
    tor_file = Path("test.torrent")
    tor_file.write_bytes(b"dummy")
    try:
        gid = mgr.torrent_on_ekle(str(tor_file))
        dosyalar = mgr.torrent_dosyalari(gid)
        assert getattr(dosyalar, "hazir_degil", False) is False
        assert len(dosyalar) == 1
        assert dosyalar[0]["ad"] == "türkçe_belge.txt"
        assert dosyalar[0]["yol"] == "türkçe_belge.txt"
    finally:
        if tor_file.exists():
            tor_file.unlink()


def _api(manager, pending):
    from app import Api
    from types import SimpleNamespace

    api = object.__new__(Api)
    api.manager = manager
    api._bekleyenler = pending
    api.servis = SimpleNamespace(hedef_klasor=lambda *args: None)
    return api


def test_bekleyen_onayla_on_eklenen_torrent_gidini_kullanir():
    from core.kaydet import Bekleyenler
    import json

    mgr = DummyManager()
    mgr._proksi = lambda opts: None
    url = "dialog-preview.torrent"
    Path(url).write_bytes(b"dummy torrent")
    try:
        preview_gid = mgr.torrent_on_ekle(url)
        pending = Bekleyenler()
        kimlik = pending.ekle({"url": url, "kind": "torrent"})
        result = _api(mgr, pending).bekleyen_onayla(
            kimlik, {"adopt_gid": preview_gid, "selected_files": [1]}
        )
    finally:
        Path(url).unlink(missing_ok=True)

    assert result["ok"] is True
    assert len(mgr.rpc.eklenenler) == 1
    assert preview_gid in mgr.rpc.devam_edenler
    assert mgr.rpc.secimler[preview_gid]["select-file"] == "1"
    row = mgr.store.by_id(result["id"])
    assert json.loads(row["options"])["adopt_gid"] == preview_gid


def test_servis_ekle_on_eklenen_torrent_gidini_kullanir():
    from core.servis import AfuDMServis
    import json

    mgr = DummyManager()
    mgr._proksi = lambda opts: None
    url = "dialog-preview-service.torrent"
    Path(url).write_bytes(b"dummy torrent")
    try:
        preview_gid = mgr.torrent_on_ekle(url)
        service = object.__new__(AfuDMServis)
        service.manager = mgr
        service.store = mgr.store
        result = service.ekle({
            "urls": [url], "adopt_gid": preview_gid, "selected_files": [1]
        })
    finally:
        Path(url).unlink(missing_ok=True)

    assert result["ok"] is True
    assert len(mgr.rpc.eklenenler) == 1
    assert preview_gid in mgr.rpc.devam_edenler
    assert mgr.rpc.secimler[preview_gid]["select-file"] == "1"
    row = mgr.store.by_id(1)
    assert json.loads(row["options"])["adopt_gid"] == preview_gid


def test_adopt_gid_olmadan_db_satiri_olmayan_paused_torrent_benimsenir():
    mgr = DummyManager()
    mgr._proksi = lambda opts: None
    preview_gid = mgr.torrent_on_ekle("magnet:?xt=urn:btih:abc")
    mgr.rpc.eklenenler.clear()

    result = mgr.add("magnet:?xt=urn:btih:abc", kind="torrent")

    assert len(mgr.rpc.eklenenler) == 0
    assert result["gid"] == preview_gid
    assert preview_gid in mgr.rpc.devam_edenler


def test_torrent_dosyasi_infohashi_bulunup_paused_gid_benimsenir():
    mgr = DummyManager()
    mgr._proksi = lambda opts: None
    # d4:info d1:a1:be e -> info dict d1:a1:b
    info = b"d1:a1:be"
    torrent = b"d4:info" + info + b"e"
    import hashlib
    infohash = hashlib.sha1(info).hexdigest()
    preview_gid = "paused-file"
    mgr.rpc.durumlar[preview_gid] = {
        "gid": preview_gid, "infoHash": infohash, "status": "paused"
    }
    mgr.rpc.paused.add(preview_gid)
    row = mgr.store.add(kind="torrent", source="preview", title="preview",
                        dest_dir="", options={})
    mgr.store.attach_gid(row, preview_gid)
    # The preview has no DB row: remove it to model the save dialog's temporary GID.
    mgr.store.kayitlar.clear()
    path = Path("infohash-test.torrent")
    path.write_bytes(torrent)
    try:
        result = mgr.add(str(path), kind="torrent")
    finally:
        path.unlink(missing_ok=True)

    assert len(mgr.rpc.eklenenler) == 0
    assert result["gid"] == preview_gid
    assert preview_gid in mgr.rpc.devam_edenler


def test_cok_dosyali_bencode_infohashi_tekli_yol_ve_tekli_tracker_listelerinde_bulunur():
    import hashlib

    def bstr(value):
        return str(len(value)).encode() + b":" + value

    def bdict(items):
        return b"d" + b"".join(bstr(key) + value for key, value in sorted(items)) + b"e"

    def blist(values):
        return b"l" + b"".join(values) + b"e"

    first_file = bdict([
        (b"length", b"i3e"), (b"path", blist([bstr(b"file.rar")]))
    ])
    second_file = bdict([
        (b"length", b"i-3e"), (b"path", blist([bstr(b"odd")]))
    ])
    info = bdict([
        (b"files", blist([first_file, second_file])),
        (b"name", bstr(b"DarkSoul")),
        (b"piece length", b"i16384e"),
        (b"pieces", bstr(b"01234567890123456789")),
    ])
    torrent = (
        bdict([
            (b"announce", bstr(b"http://tracker")),
            (b"announce-list", blist([
                blist([bstr(b"http://tracker")]),
                blist([bstr(b"http://tracker2")]),
            ])),
            (b"info", info),
        ])
    )
    path = Path("multi-file-odd-lists.torrent")
    path.write_bytes(torrent)
    try:
        assert Manager._torrent_dosya_infohash(str(path)) == hashlib.sha1(info).hexdigest()
    finally:
        path.unlink(missing_ok=True)


def test_bozuk_torrent_bencode_infohashi_bos_doner():
    path = Path("malformed-infohash.torrent")
    path.write_bytes(b"d4:infod4:pathl5:abc")
    try:
        assert Manager._torrent_dosya_infohash(str(path)) == ""
    finally:
        path.unlink(missing_ok=True)

if __name__ == "__main__":
    test_duraklatilmis_ekleme_gid_dondurur()
    test_metadata_gelmeden_dosya_listesi_bos_doner()
    test_secim_uygulanip_devam_ettirilince_indeksler_gonderilir()
    test_iptal_edildiginde_indirme_kaldiriliyor()
    test_tek_dosyali_ve_turkce_isimli_torrent()
    test_bekleyen_onayla_on_eklenen_torrent_gidini_kullanir()
    test_servis_ekle_on_eklenen_torrent_gidini_kullanir()
    test_adopt_gid_olmadan_db_satiri_olmayan_paused_torrent_benimsenir()
    test_torrent_dosyasi_infohashi_bulunup_paused_gid_benimsenir()
    test_cok_dosyali_bencode_infohashi_tekli_yol_ve_tekli_tracker_listelerinde_bulunur()
    test_bozuk_torrent_bencode_infohashi_bos_doner()
