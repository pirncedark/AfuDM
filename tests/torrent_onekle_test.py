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
        
    def add_torrent(self, payload, options):
        gid = f"tor_{len(self.eklenenler)}"
        self.eklenenler.append({"type": "torrent", "gid": gid, "options": options})
        self.durumlar[gid] = {"gid": gid, "infoHash": "abc", "bittorrent": {"info": {"name": "test_torrent"}}}
        return gid
        
    def add_uri(self, uris, options):
        gid = f"mag_{len(self.eklenenler)}"
        self.eklenenler.append({"type": "magnet", "gid": gid, "uris": uris, "options": options})
        self.durumlar[gid] = {"gid": gid, "infoHash": "def"}
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
        return []
    def tell_stopped(self, offset, num, keys=None):
        return []
        
    def unpause(self, gid):
        self.devam_edenler.append(gid)
        
    def remove(self, gid, force=False):
        self.kaldirmalar.append(gid)
        
    def remove_result(self, gid):
        pass

class DummyStore:
    def __init__(self):
        self.kayitlar = {}
        self._id = 1
        self.secimler = {}
        
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
        
    def log(self, level, msg):
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

if __name__ == "__main__":
    test_duraklatilmis_ekleme_gid_dondurur()
    test_metadata_gelmeden_dosya_listesi_bos_doner()
    test_secim_uygulanip_devam_ettirilince_indeksler_gonderilir()
    test_iptal_edildiginde_indirme_kaldiriliyor()
    test_tek_dosyali_ve_turkce_isimli_torrent()
