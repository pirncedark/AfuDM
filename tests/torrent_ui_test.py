# -*- coding: utf-8 -*-
"""Torrent dosya agaci ve secimi UI testleri -- AGSIZ ve pencere ACMADAN.

Denetlenenler:
1) index.html icindeki her yeni data-i18n anahtarinin i18n.js'te tr ve en karsiliklari
2) index.html ve app.js icindeki kritik id'lerin varligi ve okunmasi
3) app.py Api sinifinda kopru metodlarinin varligi ve davranisi
4) "hepsini sec / hicbirini sec / tersine cevir / secim filtreleme / sayac" mantiginin saf fonksiyon dogrulamasi
5) Bos / magnet ustverisi gelmemis ("hazir degil") durumunda kullanici mesaji yolu
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import Api  # noqa: E402
from core.db import Store  # noqa: E402
from core.manager import Manager, TorrentDosyaListesi  # noqa: E402

fails: list[str] = []


def check(ad: str, kosul: bool, detay: str = "") -> None:
    durum = "GECTI" if kosul else "DUSTU"
    print(f"  [{durum}] {ad}" + (f" -- {detay}" if detay else ""))
    if not kosul:
        fails.append(ad + (f" ({detay})" if detay else ""))


# ---------------------------------------------------------------------------
# 1) index.html ve i18n.js denetimi
# ---------------------------------------------------------------------------
print("1) index.html ve ui/i18n.js dosya agaci anahtarlari")
html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
js_i18n = (ROOT / "ui" / "i18n.js").read_text(encoding="utf-8")


def blok_ayikla(metin: str, baslangic: str) -> str:
    i = metin.index(baslangic) + len(baslangic) - 1
    derinlik = 0
    for j in range(i, len(metin)):
        if metin[j] == "{":
            derinlik += 1
        elif metin[j] == "}":
            derinlik -= 1
            if derinlik == 0:
                return metin[i : j + 1]
    raise ValueError("kapanmayan blok: " + baslangic)


ANAHTAR_RE = re.compile(r'"([A-Za-z0-9_.\-]+)"\s*:\s*"((?:[^"\\]|\\.)*)"')


def sozluk(blok: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in ANAHTAR_RE.finditer(blok)}


tr_sozluk = sozluk(blok_ayikla(js_i18n, "tr: {"))
en_sozluk = sozluk(blok_ayikla(js_i18n, "en: {"))

# Torrent agacina ozgu tum "tor." anahtarlarinin listesi
tor_anahtarlar = [
    "tor.title",
    "tor.files",
    "tor.btnFiles",
    "tor.apply",
    "tor.applying",
    "tor.applied",
    "tor.appliedAll",
    "tor.selectAll",
    "tor.selectNone",
    "tor.invert",
    "tor.filterPh",
    "tor.showAll",
    "tor.limitNotice",
    "tor.count",
    "tor.notReady",
    "tor.empty",
    "tor.close",
    "tor.file",
    "tor.size",
    "tor.progress",
    "tor.path",
    "tor.seed",
    "tor.ratio",
    "tor.upload",
    "tor.download",
    "tor.trackers",
    "tor.peers",
    "tor.seeding",
    "tor.leeching",
    "tor.metaNotReady",
]

for k in tor_anahtarlar:
    check(f"tr'de {k} var", k in tr_sozluk and bool(tr_sozluk[k].strip()), tr_sozluk.get(k, ""))
    check(f"en'de {k} var", k in en_sozluk and bool(en_sozluk[k].strip()), en_sozluk.get(k, ""))

# index.html icindeki data-i18n / data-i18n-ph anahtarlarinin sozlukte varligi
html_tor_anahtarlar = set(re.findall(r'data-i18n(?:-ph)?="(tor\.[^"]+)"', html))
check("index.html'de tor. anahtarlari kullanilmis", len(html_tor_anahtarlar) >= 8, str(html_tor_anahtarlar))
for k in html_tor_anahtarlar:
    check(f"HTML'deki {k} tr sozlukte var", k in tr_sozluk)
    check(f"HTML'deki {k} en sozlukte var", k in en_sozluk)


# ---------------------------------------------------------------------------
# 2) HTML ve app.js DOM ID'leri ve baglantisi
# ---------------------------------------------------------------------------
print("2) HTML ve app.js id eslesmesi")
app_js = (ROOT / "ui" / "app.js").read_text(encoding="utf-8")
beklenen_idler = [
    "torGid",
    "torBaslik",
    "torSayac",
    "torAra",
    "torSecHepsi",
    "torSecHicbiri",
    "torSecTers",
    "torErr",
    "torBilgi",
    "torAgac",
    "torLimitBar",
    "torLimitNot",
    "torLimitHepsi",
    "torUygula",
    "dTorFiles",
    "torMetrikBar",
    "torSeedVal",
    "torPeersVal",
    "torRatioVal",
    "torDownVal",
    "torUpVal",
    "torTrackersVal",
    "dPanelOverview",
    "dPanelFiles",
    "dPanelTrackers",
    "dPanelRules",
    "dPanelAutomation",
    "dPanelLogs",
]

sekme_idler = [
    "detailTabs",
    "dTabOverview",
    "dTabFiles",
    "dTabTrackers",
    "dTabRules",
    "dTabAutomation",
    "dTabLogs",
]
check("index.html'de id='torrentVeil' var", 'id="torrentVeil"' in html)
check("app.js'te openVeil('torrentVeil') cagrisi var", 'openVeil("torrentVeil")' in app_js)
check("app.js'te closeVeil('torrentVeil') cagrisi var", 'closeVeil("torrentVeil")' in app_js)
check("index.html'de data-close='torrentVeil' var", 'data-close="torrentVeil"' in html)
for id_ad in beklenen_idler:
    check(f"index.html'de id='{id_ad}' var", f'id="{id_ad}"' in html)
    check(f"app.js'te $('{id_ad}') cagrisi var", f'$("{id_ad}")' in app_js)

for id_ad in sekme_idler:
    check(f"index.html'de id='{id_ad}' var", f'id="{id_ad}"' in html)

check("index.html'de 6 adet dtab butonu var", html.count('class="dtab') >= 6)
check("app.js'te switchDetailTab tanimli", "function switchDetailTab" in app_js)
check("app.js'te renderDetailTabContent tanimli", "function renderDetailTabContent" in app_js)
for tab in ("overview", "files", "trackers", "rules", "automation", "logs"):
    check(f"dtab.{tab} tr sozlukte var", f"dtab.{tab}" in tr_sozluk)
    check(f"dtab.{tab} en sozlukte var", f"dtab.{tab}" in en_sozluk)


# ---------------------------------------------------------------------------
# 3) app.py Api kopru metodlari
# ---------------------------------------------------------------------------
print("3) app.py Api kopru metodlari")


class SahteRPC:
    def __init__(self, durumlar: dict[str, dict] | dict, dosyalar: list[dict], peers: list[dict] | None = None) -> None:
        self.durumlar = durumlar if isinstance(durumlar, dict) and any(isinstance(v, dict) for v in durumlar.values()) else {"": durumlar}
        self.dosyalar = dosyalar
        self.peers_listesi = peers or []
        self.degisenler: list[tuple[str, dict]] = []

    def tell_status(self, gid: str, keys=None) -> dict:
        d = self.durumlar.get(gid) or self.durumlar.get("") or {}
        return dict(d, gid=gid)

    def get_files(self, gid: str) -> list[dict]:
        return list(self.dosyalar)

    def get_peers(self, gid: str) -> list[dict]:
        return list(self.peers_listesi)

    def get_global_option(self) -> dict:
        return {"bt-tracker": "udp://tracker.test:1337/announce"}

    def change_option(self, gid: str, secenekler: dict) -> str:
        self.degisenler.append((gid, dict(secenekler)))
        return "OK"


class SahteLocalAPI:
    port = 9099
    token = "test-token"


with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as gecici:
    tmp = Path(gecici)
    manager = Manager.__new__(Manager)
    manager.store = Store(str(tmp / "test_api.db"))
    dosyalar_ham = [
        {"index": "1", "path": "Film/bolum1.mkv", "length": "1000", "completedLength": "500", "selected": "true"},
        {"index": "2", "path": "Film/bolum2.mkv", "length": "2000", "completedLength": "0", "selected": "false"},
        {"index": "3", "path": "Film/altyazi.srt", "length": "50", "completedLength": "50", "selected": "true"},
    ]
    rpc = SahteRPC(
        {
            "tor-gid-1": {"status": "active", "infoHash": "hash123", "bittorrent": {"info": {"name": "Film"}}},
            "http-gid": {"status": "active", "bittorrent": {}, "infoHash": ""},
        },
        dosyalar_ham,
    )
    manager.rpc = rpc
    manager.video_jobs = {}
    manager._known_complete = set()
    manager._cerezler = {}
    manager.last_error = ""

    manager.store.add("torrent", "magnet:?xt=urn:btih:hash123", gid="tor-gid-1")

    api = Api(manager, SahteLocalAPI())  # type: ignore

    # torrent_dosyalari basarili cagrisi
    yanit = api.torrent_dosyalari("tor-gid-1")
    check("api.torrent_dosyalari ok=True", yanit.get("ok") is True, str(yanit))
    check("api.torrent_dosyalari hazir_degil=False", yanit.get("hazir_degil") is False)
    check("api.torrent_dosyalari 3 dosya dondurdu", len(yanit.get("dosyalar", [])) == 3)
    check("dosya alanlari eksiksiz", all("indeks" in d and "ad" in d and "boyut" in d for d in yanit["dosyalar"]))

    # torrent_secimi_ayarla basarili cagrisi
    secim_yanit = api.torrent_secimi_ayarla("tor-gid-1", [1, 3])
    check("api.torrent_secimi_ayarla ok=True", secim_yanit.get("ok") is True, str(secim_yanit))
    check("indeksler normalize edildi", secim_yanit.get("indeksler") == [1, 3])
    check("aria2 change_option select-file aldi", rpc.degisenler[-1] == ("tor-gid-1", {"select-file": "1,3"}))

    # bos secim (tumunu secme)
    secim_tum = api.torrent_secimi_ayarla("tor-gid-1", [])
    check("bos secim aria2 select-file='' gonderdi", rpc.degisenler[-1] == ("tor-gid-1", {"select-file": ""}))

    # gecersiz GID veya torrent olmayan kayit icin guvenli hata donusu
    manager.store.add("http", "https://ornek.com/dosya.zip", gid="http-gid")
    hata_yanit = api.torrent_dosyalari("http-gid")
    check("torrent olmayan gid icin ok=False doner", hata_yanit.get("ok") is False)
    check("error alani dolu", bool(hata_yanit.get("error")))

    hata_secim = api.torrent_secimi_ayarla("http-gid", [1])
    check("torrent olmayan secim icin ok=False", hata_secim.get("ok") is False)

    # Magnet hazir degil durumu
    manager.rpc = SahteRPC({"status": "active", "bittorrent": {}}, [])
    hazir_degil_yanit = api.torrent_dosyalari("tor-gid-1")
    check("magnet ustveri yokken hazir_degil=True", hazir_degil_yanit.get("hazir_degil") is True)
    check("hazir degil aciklamasi var", "Magnet" in hazir_degil_yanit.get("neden", ""))
    check("dosyalar bos liste", hazir_degil_yanit.get("dosyalar") == [])

    # Dilim 4: torrent_metrikleri testleri
    print("3b) Dilim 4 torrent_metrikleri ve hazir_degil akisi")
    manager.rpc = SahteRPC(
        {
            "tor-gid-1": {
                "status": "active",
                "infoHash": "hash123",
                "numSeeders": "5",
                "connections": "12",
                "completedLength": "1000000",
                "totalLength": "2000000",
                "uploadLength": "1500000",
                "downloadSpeed": "512000",
                "uploadSpeed": "128000",
                "seeder": "false",
                "bittorrent": {
                    "announceList": [["udp://tracker1/announce"], ["http://tracker2/announce"]],
                },
            },
        },
        dosyalar_ham,
        peers=[
            {"ip": "1.2.3.4", "port": 5000, "seeder": "true", "downloadSpeed": 2000, "uploadSpeed": 1000, "peerId": "c1"},
            {"ip": "1.2.3.5", "port": 5001, "seeder": "false", "downloadSpeed": 4000, "uploadSpeed": 0, "peerId": "c2"},
        ],
    )
    metrik_yanit = api.torrent_metrikleri("tor-gid-1")
    check("api.torrent_metrikleri ok=True", metrik_yanit.get("ok") is True, str(metrik_yanit))
    check("metrik hazir_degil=False", metrik_yanit.get("hazir_degil") is False)
    m = metrik_yanit.get("metrikler", {})
    check("seed sayisi 5", m.get("num_seeders") == 5, str(m.get("num_seeders")))
    check("baglanti sayisi 12", m.get("connections") == 12, str(m.get("connections")))
    check("ratio 1.5", m.get("ratio") == 1.5, str(m.get("ratio")))
    check("download_speed 512000", m.get("download_speed") == 512000)
    check("upload_speed 128000", m.get("upload_speed") == 128000)
    check("tracker_sayisi 2", m.get("tracker_sayisi") == 2)
    check("peers_seeders 1", m.get("peers_seeders") == 1)
    check("peers_leechers 1", m.get("peers_leechers") == 1)

    # Torrent olmayan GID icin torrent_metrikleri hazir_degil / hata yolu
    metrik_hata = api.torrent_metrikleri("http-gid")
    check("http icin metrikler ok=False", metrik_hata.get("ok") is False)
    check("http icin hazir_degil=True", metrik_hata.get("hazir_degil") is True)

    # Magnet ustveri henuz yokken torrent_metrikleri hazir_degil=True
    manager.rpc = SahteRPC({"tor-gid-1": {"status": "active", "bittorrent": {}, "infoHash": ""}}, [])
    metrik_magnet = api.torrent_metrikleri("tor-gid-1")
    check("magnet ustveri yokken metrik hazir_degil=True", metrik_magnet.get("hazir_degil") is True)
    check("magnet ustveri yokken metrikler bos sozluk", metrik_magnet.get("metrikler") == {})

    manager.store.conn.close()


# ---------------------------------------------------------------------------
# 4) Secim mantigi saf fonksiyon testleri (app.js ile ayni kural seti)
# ---------------------------------------------------------------------------
print("4) Secim mantigi: hepsi / hicbiri / tersi / sayaclar / filtreleme")


def saf_hepsini_sec(dosyalar: list[dict]) -> set[int]:
    return {d["indeks"] for d in dosyalar}


def saf_hicbirini_sec() -> set[int]:
    return set()


def saf_tersine_cevir(dosyalar: list[dict], secimler: set[int]) -> set[int]:
    return {d["indeks"] for d in dosyalar if d["indeks"] not in secimler}


def saf_filtrele(dosyalar: list[dict], arama: str) -> list[dict]:
    if not arama:
        return dosyalar
    q = arama.strip().lower()
    return [d for d in dosyalar if q in d.get("ad", "").lower() or q in d.get("yol", "").lower()]


def saf_sayaclar(dosyalar: list[dict], secimler: set[int]) -> dict:
    toplam_boyut = sum(d.get("boyut", 0) for d in dosyalar)
    secili_boyut = sum(d.get("boyut", 0) for d in dosyalar if d["indeks"] in secimler)
    return {
        "toplam": len(dosyalar),
        "secili": len(secimler),
        "toplam_boyut": toplam_boyut,
        "secili_boyut": secili_boyut,
    }


ornek_dosyalar = [
    {"indeks": 1, "ad": "video1.mkv", "yol": "Dizi/video1.mkv", "boyut": 1000},
    {"indeks": 2, "ad": "video2.mkv", "yol": "Dizi/video2.mkv", "boyut": 2000},
    {"indeks": 3, "ad": "altyazi.srt", "yol": "Dizi/altyazi.srt", "boyut": 50},
    {"indeks": 4, "ad": "cover.jpg", "yol": "Dizi/cover.jpg", "boyut": 100},
]

hepsi = saf_hepsini_sec(ornek_dosyalar)
check("hepsini sec tum indeksleri icerir", hepsi == {1, 2, 3, 4})

hicbiri = saf_hicbirini_sec()
check("hicbirini sec bos kume dondurur", hicbiri == set())

ters1 = saf_tersine_cevir(ornek_dosyalar, {1, 3})
check("tersine cevir {1,3} -> {2,4}", ters1 == {2, 4})

ters2 = saf_tersine_cevir(ornek_dosyalar, hepsi)
check("tumunun tersi bostur", ters2 == set())

ters3 = saf_tersine_cevir(ornek_dosyalar, set())
check("bosun tersi tumudur", ters3 == {1, 2, 3, 4})

# Sayaclar
sayac = saf_sayaclar(ornek_dosyalar, {1, 2})
check("sayac secili sayisi", sayac["secili"] == 2)
check("sayac toplam sayisi", sayac["toplam"] == 4)
check("sayac secili boyut (1000 + 2000 = 3000)", sayac["secili_boyut"] == 3000)
check("sayac toplam boyut", sayac["toplam_boyut"] == 3150)

# Filtreleme
filtrelenmis_srt = saf_filtrele(ornek_dosyalar, "srt")
check("srt aramasinda 1 sonuc", len(filtrelenmis_srt) == 1 and filtrelenmis_srt[0]["indeks"] == 3)

filtrelenmis_video = saf_filtrele(ornek_dosyalar, "video")
check("video aramasinda 2 sonuc", len(filtrelenmis_video) == 2)

filtrelenmis_bos = saf_filtrele(ornek_dosyalar, "bulunamaz_uzanti")
check("bulunamayan aramada bos liste", len(filtrelenmis_bos) == 0)


# ---------------------------------------------------------------------------
# 5) Klasor/agac kurma ve alt dosyalari kapsama mantigi
# ---------------------------------------------------------------------------
print("5) Klasor hiyerarsisi ve klasor kutusu alt dosya secimi")


def klasorun_alt_dosyalari(dosyalar: list[dict], klasor_yol: str) -> list[dict]:
    return [
        d for d in dosyalar
        if d.get("parent_yol") == klasor_yol or (d.get("parent_yol") and d.get("parent_yol", "").startswith(klasor_yol + "/"))
    ]


hiyerarsi_dosyalar = [
    {"indeks": 1, "ad": "s01e01.mp4", "parent_yol": "Dizi/Sezon 1"},
    {"indeks": 2, "ad": "s01e02.mp4", "parent_yol": "Dizi/Sezon 1"},
    {"indeks": 3, "ad": "s02e01.mp4", "parent_yol": "Dizi/Sezon 2"},
    {"indeks": 4, "ad": "info.nfo", "parent_yol": "Dizi"},
]

sezon1_alt = klasorun_alt_dosyalari(hiyerarsi_dosyalar, "Dizi/Sezon 1")
check("Sezon 1 altindaki dosyalar (2 adet)", {d["indeks"] for d in sezon1_alt} == {1, 2})

dizi_kok_alt = klasorun_alt_dosyalari(hiyerarsi_dosyalar, "Dizi")
check("Dizi kok klasoru altindaki tum dosyalar (4 adet)", {d["indeks"] for d in dizi_kok_alt} == {1, 2, 3, 4})


# ---------------------------------------------------------------------------
# 6) Buyuk torrent performans siniri ve gosterim mantigi
# ---------------------------------------------------------------------------
print("6) Buyuk torrent performans siniri ve hazir_degil mantigi")


def saf_buyuk_liste_gosterim(dosyalar: list[dict], limit: int, hepsini_goster: bool = False) -> tuple[list[dict], bool]:
    sinir = 100000 if hepsini_goster else limit
    gosterilen = dosyalar[:sinir]
    limit_uyarisi = (not hepsini_goster) and len(dosyalar) > limit
    return gosterilen, limit_uyarisi


buyuk_liste = [{"indeks": i, "ad": f"file_{i}.dat", "boyut": 1024} for i in range(500)]
gosterilen_varsayilan, uyari_varsayilan = saf_buyuk_liste_gosterim(buyuk_liste, limit=250, hepsini_goster=False)
check("varsayilan limitle 250 dosya gosterilir", len(gosterilen_varsayilan) == 250)
check("250 ustu dosyada limit uyarisi aktif", uyari_varsayilan is True)

gosterilen_hepsi, uyari_hepsi = saf_buyuk_liste_gosterim(buyuk_liste, limit=250, hepsini_goster=True)
check("hepsini goster acikken 500 dosya gosterilir", len(gosterilen_hepsi) == 500)
check("hepsini goster acikken limit uyarisi gizlenir", uyari_hepsi is False)

kucuk_liste = [{"indeks": i, "ad": f"file_{i}.dat", "boyut": 1024} for i in range(50)]
_, uyari_kucuk = saf_buyuk_liste_gosterim(kucuk_liste, limit=250, hepsini_goster=False)
check("limit alti torrentte uyari bar gizlenir", uyari_kucuk is False)

print()
if fails:
    print(f"BASARISIZ ({len(fails)} test dustu):", ", ".join(fails))
    sys.exit(1)
print("Hepsi gecti")
