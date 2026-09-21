# -*- coding: utf-8 -*-
"""v1.7.5 mobil torrent paneli ve REST sozlesmesi testleri."""
from __future__ import annotations

import json
import re
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.server import LocalAPI  # noqa: E402
from core.manager import TorrentDosyaListesi  # noqa: E402

total_checks = 0
passed_checks = 0
failed_checks = 0
fails: list[str] = []


def check(ad: str, kosul: bool, detay: str = "") -> None:
    global total_checks, passed_checks, failed_checks
    total_checks += 1
    durum = "GECTI" if kosul else "DUSTU"
    if kosul:
        passed_checks += 1
        print(f"  [{durum}] {ad}")
    else:
        failed_checks += 1
        print(f"  [{durum}] {ad}" + (f" -> {detay}" if detay else ""))
        fails.append(ad + (f" ({detay})" if detay else ""))


def request(port: int, path: str, token: str | None = None, body: dict | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-AfuDM-Token"] = token
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}")


class SahteManager:
    """Gercek HTTP katmanini sinamak icin aria2'den bagimsiz torrent siniri."""

    def __init__(self) -> None:
        self.alinan_secim: list[int] | None = None
        self.hata_ucu = ""

    def torrent_dosyalari(self, gid: str) -> TorrentDosyaListesi:
        if self.hata_ucu == "dosyalar":
            raise ValueError("dosya listesi okunamadi")
        return TorrentDosyaListesi(
            [{"indeks": 1, "ad": "ornek.mkv", "boyut": 42, "secili": True}],
            hazir_degil=True,
            neden="Magnet ustverisi henuz gelmedi.",
            gid=gid,
        )

    def torrent_metrikleri(self, gid: str) -> dict:
        if self.hata_ucu == "metrik":
            raise ValueError("metrik okunamadi")
        return {"gid": gid, "hazir_degil": False, "ratio": 1.0}

    def seed_bilgi(self, gid: str) -> dict:
        if self.hata_ucu == "seed":
            raise ValueError("seed okunamadi")
        return {"gid": gid, "seed": 3}

    def torrent_secimi_ayarla(self, gid: str, indeksler: list[int]) -> dict:
        self.alinan_secim = indeksler
        return {"gid": gid, "indeksler": indeksler}


def hata_sozlesmesi(port: int, token: str, manager: SahteManager, uc: str, hata_ucu: str) -> bool:
    manager.hata_ucu = hata_ucu
    status, body = request(port, uc, token=token)
    manager.hata_ucu = ""
    return status == 400 and {"code", "message", "error"}.issubset(body)


def rest_sozlesmesi() -> None:
    print("A) REST sozlesmesi (gercek HTTP, sahte manager)")
    # LocalAPI.start() api_endpoint.json'u EZER; AfuDM aciksa uzanti yanlis
    # porta gider. Yedekle, sonda geri yaz.
    endpoint = ROOT / "data" / "api_endpoint.json"
    try:
        endpoint_backup = endpoint.read_text("utf-8") if endpoint.exists() else None
        endpoint_izinli = True
    except PermissionError:
        # Bazı izole CI ortamları, canlı anahtar dosyasını kasıtlı olarak
        # okumaya kapatır. Aynı yazma yan etkisini geçici veri dizininde tut.
        endpoint_backup = None
        endpoint_izinli = False
    eski_data = None
    eski_token_dosyasi = None
    eski_izin_kisitla = None
    gecici_data = None
    if not endpoint_izinli:
        from api import server as api_server

        gecici_data = tempfile.TemporaryDirectory()
        eski_data = api_server.paths.DATA
        eski_token_dosyasi = api_server.paths.API_TOKEN_FILE
        eski_izin_kisitla = api_server._dosya_iznini_kisitla
        api_server.paths.DATA = Path(gecici_data.name)
        api_server.paths.API_TOKEN_FILE = api_server.paths.DATA / "api_token.txt"
        # Canli dosya degil, test gecici dizini: Windows ACL yan etkisi test
        # sonunda dizinin silinmesini engellemesin.
        api_server._dosya_iznini_kisitla = lambda _yol: None
    manager = SahteManager()
    api = LocalAPI(manager, port=16811)
    port = api.start()
    try:
        status, body = request(port, "/torrent/dosyalar?gid=X", token=api.token)
        expected = {"ok", "gid", "hazir_degil", "neden", "dosyalar"}
        check("A1 torrent/dosyalar duz bes anahtari tasir", expected.issubset(body) and isinstance(body.get("dosyalar"), list), str(body))
        check("A2 hazir olmayan magnet nedeni korunur", status == 200 and body.get("hazir_degil") is True and bool(body.get("neden", "").strip()), str(body))

        status, body = request(port, "/torrent/dosyalar?gid=", token=api.token)
        check("A3 bos gid GID_GEREKLI ile reddedilir", status == 400 and body.get("code") == "GID_GEREKLI", str(body))

        status, body = request(port, "/torrent/dosyalar?gid=X")
        # Sunucunun genel korumali yolu GECERSIZ_TOKEN doner; ANAHTAR_GEREKLI
        # yalniz /klasorler ucuna ozeldir (api/server.py:175 vs 228/313).
        # Bu tutarsizlik bilinerek KILITLENIYOR: degistirmek mobil/CLI
        # istemcilerini etkiler, v2.3 Reliability & Security isi.
        check("A4 tokensiz istek 401 GECERSIZ_TOKEN ile reddedilir", status == 401 and body.get("code") == "GECERSIZ_TOKEN", str(body))

        status, body = request(port, "/torrent/secim", token=api.token, body={"gid": "X", "indeksler": "1,2"})
        check("A5 liste olmayan indeksler reddedilir", status == 400 and body.get("code") == "GECERSIZ_SECIM", str(body))

        status, body = request(port, "/torrent/secim", token=api.token, body={"gid": "X", "indeksler": [1, 2, -3, 0]})
        check("A6 negatif ve sifir indeksler ayiklanir", status == 200 and manager.alinan_secim == [1, 2], str(body))

        status, body = request(port, "/torrent/secim", token=api.token, body={"gid": "X", "indeksler": [True]})
        check("A7 boolean indeks reddedilir", status == 400 and body.get("code") == "GECERSIZ_SECIM", str(body))

        status_metrik, body_metrik = request(port, "/torrent/metrik?gid=X", token=api.token)
        status_seed, body_seed = request(port, "/seed?gid=X", token=api.token)
        check("A8 metrik ve seed uclari basarili yanit verir", status_metrik == 200 and body_metrik.get("ok") is True and status_seed == 200 and body_seed.get("ok") is True)

        check("A9 dosyalar ValueError hata sozlesmesini korur", hata_sozlesmesi(port, api.token, manager, "/torrent/dosyalar?gid=X", "dosyalar"))
        check("A9 metrik ValueError hata sozlesmesini korur", hata_sozlesmesi(port, api.token, manager, "/torrent/metrik?gid=X", "metrik"))
        check("A9 seed ValueError hata sozlesmesini korur", hata_sozlesmesi(port, api.token, manager, "/seed?gid=X", "seed"))

        status, body = request(port, "/capabilities", token=api.token)
        capabilities = set(body.get("ozellikler", []))
        check("A10 torrent mobil yetenekleri duyurulur", status == 200 and {"torrent_dosya_secimi", "seed_durumu", "tracker_tarama"}.issubset(capabilities), str(body))
    finally:
        api.stop()
        if endpoint_backup is not None:
            endpoint.write_text(endpoint_backup, encoding="utf-8")
        if eski_data is not None:
            from api import server as api_server

            api_server.paths.DATA = eski_data
            api_server.paths.API_TOKEN_FILE = eski_token_dosyasi
            api_server._dosya_iznini_kisitla = eski_izin_kisitla
        if gecici_data is not None:
            gecici_data.cleanup()


def mobil_ui_sozlesmesi() -> None:
    print("B) Telefon arayuzu sozlesmesi (ui/mobil.html metin kontrolu)")
    html = (ROOT / "ui" / "mobil.html").read_text(encoding="utf-8")
    for element_id in ("torrentKatman", "torrentDosyalar", "seedOzet", "torrentKaydet", "torrentVazgec", "trackerTara"):
        check(f"B1 id='{element_id}' var", bool(re.search(rf'id=["\']{element_id}["\']', html)))

    for element_id in ("baglantiUyari", "baglantiAdres", "baglanBtn"):
        check(f"B1b yeni baglanti paneli id='{element_id}' var", bool(re.search(rf'id=["\']{element_id}["\']', html)))

    api_fn = re.search(r'async function\s+api\s*\([^)]*\)\s*\{([\s\S]*?)\n\}', html)
    api_kodu = api_fn.group(1) if api_fn else ""
    check("B1c api() hata nesnesine kod ekler", "hata.kod = veri.code" in api_kodu, api_kodu[:120])
    check("B1d api() yetki hatasini atar", 'veri.code || ""' in api_kodu, api_kodu[:120])

    yetki = re.search(r'function\s+yetkiSorunu\s*\([^)]*\)\s*\{([\s\S]*?)\n\}', html)
    yetki_kodu = yetki.group(1) if yetki else ""
    check("B1e yetkiSorunu ANAHTAR_GEREKLI/GECERSIZ_TOKEN tanir",
          "ANAHTAR_GEREKLI" in yetki_kodu and "GECERSIZ_TOKEN" in yetki_kodu, yetki_kodu[:160])

    baglan = re.search(r'\$\s*\(\s*["\']baglanBtn["\']\s*\)\.addEventListener\([^)]*,\s*\(\)\s*=>\s*\{([\s\S]*?)\n\}\);', html)
    baglan_kodu = baglan.group(1) if baglan else ""
    check("B1f baglanBtn anahtari ayiklar ve kaydeder",
          "searchParams.get(\"k\")" in baglan_kodu and "anahtarKaydet" in baglan_kodu, baglan_kodu[:160])

    tracker = re.search(r'\$\s*\(\s*["\']trackerTara["\']\s*\)\.addEventListener\([^)]*\)\s*=>\s*\{[\s\S]*?\n\}\);?', html)
    check("B1g trackerTara dinleyicisi '});' ile kapanir (script parse edilir)",
          bool(tracker) and tracker.group(0).rstrip().endswith("});"),
          (tracker.group(0)[-40:] if tracker else "dinleyici bulunamadi"))

    liste_dinleyici = re.search(r'\$\(["\']liste["\']\)\.addEventListener\("click",[\s\S]*?\n}\);', html)
    liste_kodu = liste_dinleyici.group(0) if liste_dinleyici else ""
    dosyalar_dali = re.search(r'if\s*\([^)]*eylem\s*===\s*["\']dosyalar["\'][^)]*\)\s*\{([\s\S]*?)\}', liste_kodu)
    dal_kodu = dosyalar_dali.group(1) if dosyalar_dali else ""
    check("B2 dosyalar eylemi katmani acar, control POST'a gitmez", "torrentKatmanAc" in dal_kodu and bool(re.search(r'\breturn\s*;', dal_kodu)), dal_kodu[:160])

    kapat = re.search(r'function\s+torrentKatmanKapat\s*\([^)]*\)\s*\{([\s\S]*?)\n\}', html)
    check("B3 torrentKatmanKapat clearInterval icerir", bool(kapat and "clearInterval" in kapat.group(1)))

    for endpoint in ("/torrent/secim", "/tracker/tara", "/torrent/metrik", "/seed"):
        check(f"B4 {endpoint} mobil arayuzde cagrilir", endpoint in html)
    check("B5 Escape tusu katmani kapatir", bool(re.search(r'addEventListener\([^)]*["\']Escape["\']|["\']Escape["\']', html)))


if __name__ == "__main__":
    rest_sozlesmesi()
    mobil_ui_sozlesmesi()
    print(f"\n{'=' * 52}\nSONUC: {passed_checks}/{total_checks} test gecti")
    if fails:
        print("Gecmeyenler: " + ", ".join(fails))
        raise SystemExit(1)
