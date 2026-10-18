import os
import pytest
import tempfile
from core.butunluk import tara

def test_gercek_rar_saglam():
    # Gerçek RAR 4 başlığı: Rar!\x1A\x07\x00
    with tempfile.NamedTemporaryFile(suffix=".rar", delete=False) as f:
        f.write(b"Rar!\x1A\x07\x00" + b"some_other_data")
        dosya_yolu = f.name
    try:
        sonuc = tara(dosya_yolu, uzanti=".rar")
        assert sonuc["durum"] == "saglam"
    finally:
        os.remove(dosya_yolu)

def test_html_iceren_sahte_rar_bozuk():
    # HTML sayfası inmiş
    with tempfile.NamedTemporaryFile(suffix=".rar", delete=False) as f:
        f.write(b"<!DOCTYPE html>\n<html><body>Error</body></html>")
        dosya_yolu = f.name
    try:
        sonuc = tara(dosya_yolu, uzanti=".rar")
        assert sonuc["durum"] == "bozuk"
        assert "HTML" in sonuc["neden"]
    finally:
        os.remove(dosya_yolu)

def test_html_uzantili_dosya_saglam():
    # Gerçek HTML sayfası (beklenen .html uzantısı)
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        f.write(b"<!DOCTYPE html>\n<html><body>Hello</body></html>")
        dosya_yolu = f.name
    try:
        sonuc = tara(dosya_yolu, uzanti=".html")
        assert sonuc["durum"] == "saglam"
    finally:
        os.remove(dosya_yolu)

def test_aria2_varsa_eksik():
    # İndirme devam ediyor veya yarım kalmış
    with tempfile.NamedTemporaryFile(suffix=".rar", delete=False) as f:
        f.write(b"Rar!\x1A\x07\x00")
        dosya_yolu = f.name

    aria2_yolu = dosya_yolu + ".aria2"
    with open(aria2_yolu, 'wb') as f:
        f.write(b"fake aria2 data")

    try:
        sonuc = tara(dosya_yolu, uzanti=".rar")
        assert sonuc["durum"] == "eksik"
        assert ".aria2" in sonuc["neden"]
    finally:
        os.remove(dosya_yolu)
        os.remove(aria2_yolu)

def test_yanlis_imza_bozuk():
    # ZIP uzantılı ama başlığı PK değil
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        f.write(b"Not a zip file at all")
        dosya_yolu = f.name
    try:
        sonuc = tara(dosya_yolu, uzanti=".zip")
        assert sonuc["durum"] == "bozuk"
        assert "imza yok" in sonuc["neden"].lower()
    finally:
        os.remove(dosya_yolu)

def test_boyut_uyusmuyor():
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"1234567890") # 10 bayt
        dosya_yolu = f.name
    try:
        sonuc = tara(dosya_yolu, beklenen_boyut=15, uzanti=".txt")
        assert sonuc["durum"] == "eksik"
        assert "Boyut uyuşmuyor" in sonuc["neden"]
    finally:
        os.remove(dosya_yolu)

def test_boyut_sifir():
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        pass # Boş
        dosya_yolu = f.name
    try:
        sonuc = tara(dosya_yolu, uzanti=".txt")
        assert sonuc["durum"] == "eksik"
        assert "0 bayt" in sonuc["neden"]
    finally:
        os.remove(dosya_yolu)


def test_aria2_ve_html_blok_bozuk_bloklari_verir():
    from core.butunluk import BLOCK_SIZE
    with tempfile.NamedTemporaryFile(suffix=".rar", delete=False) as f:
        f.write(b"<!DOCTYPE html><html>x</html>".ljust(BLOCK_SIZE, b" "))
        f.write(b"\x00" * BLOCK_SIZE)
        f.write(b"Rar!\x1A\x07\x00" + os.urandom(1000))
        yol = f.name
    open(yol + ".aria2", "wb").write(b"x")
    try:
        s = tara(yol, uzanti=".rar")
        assert s["durum"] == "bozuk"
        assert [b["index"] for b in s["bozuk_bloklar"]] == [0, 1]
    finally:
        os.remove(yol)
        os.remove(yol + ".aria2")


def _sunucu(icerik, range_destek=True, html=False):
    import http.server, threading

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if html:
                b = b"<!DOCTYPE html><html>expired</html>"
                self.send_response(206 if range_destek else 200)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
                return
            r = self.headers.get("Range")
            if r and range_destek:
                a, b = r.split("=")[1].split("-")
                a, b = int(a), int(b)
                d = icerik[a:b + 1]
                self.send_response(206)
            else:
                d = icerik
                self.send_response(200)
            self.send_header("Content-Length", str(len(d)))
            self.end_headers()
            self.wfile.write(d)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_blok_indir_onarim_ozdes_cikar():
    import hashlib
    from core.butunluk import BLOCK_SIZE, blok_indir
    kaynak = b"Rar!\x1A\x07\x00" + os.urandom(BLOCK_SIZE * 3)
    bozuk = bytearray(kaynak)
    for i in (0, 2):
        bozuk[i * BLOCK_SIZE:(i + 1) * BLOCK_SIZE] = b"\x00" * BLOCK_SIZE
    srv = _sunucu(kaynak)
    try:
        url = "http://127.0.0.1:%d/x.rar" % srv.server_port
        for i in (0, 2):
            boyut = min(BLOCK_SIZE, len(kaynak) - i * BLOCK_SIZE)
            bozuk[i * BLOCK_SIZE:i * BLOCK_SIZE + boyut] = blok_indir(url, {}, i * BLOCK_SIZE, boyut)
        assert hashlib.sha256(bozuk).digest() == hashlib.sha256(kaynak).digest()
    finally:
        srv.shutdown()


def test_blok_indir_html_ve_range_yok_reddedilir():
    from core.butunluk import blok_indir
    for kw in ({"html": True}, {"range_destek": False}):
        srv = _sunucu(b"A" * 5000, **kw)
        try:
            with pytest.raises(ValueError):
                blok_indir("http://127.0.0.1:%d/x" % srv.server_port, {}, 0, 100)
        finally:
            srv.shutdown()


def _aria2_kontrol(parca, toplam, dolu_parca):
    import struct
    sayi = -(-toplam // parca)
    bit = bytearray((sayi + 7) // 8)
    for i in range(dolu_parca):
        bit[i // 8] |= 0x80 >> (i % 8)
    return (struct.pack(">HI", 1, 0) + struct.pack(">I", 20) + b"\x00" * 20
            + struct.pack(">IQQ", parca, toplam, 0) + struct.pack(">I", len(bit)) + bytes(bit))


def test_rastgele_veri_json_gibi_baslasa_bozuk_sayilmaz():
    # Sikistirilmis arsivde bir blok tesaduf '{' ile baslayabilir; JSON hata sayfasi degildir.
    import random
    rng = random.Random(7)
    govde = bytes([0x7B]) + bytes(rng.randrange(256) for _ in range(5000))
    with tempfile.NamedTemporaryFile(suffix=".rar", delete=False) as f:
        f.write(b"Rar!\x1A\x07\x01\x00" + govde)
        dosya_yolu = f.name
    try:
        assert tara(dosya_yolu, uzanti=".rar")["durum"] == "saglam"
    finally:
        os.remove(dosya_yolu)


def test_gercek_json_hata_sayfasi_hala_bozuk():
    with tempfile.NamedTemporaryFile(suffix=".rar", delete=False) as f:
        f.write(b'{"error": "link expired", "code": 403}')
        dosya_yolu = f.name
    try:
        assert tara(dosya_yolu, uzanti=".zip")["durum"] == "bozuk"
    finally:
        os.remove(dosya_yolu)


def test_tam_aria2_kontrol_dosyasi_eksik_sayilmaz_ve_silinir():
    with tempfile.NamedTemporaryFile(suffix=".rar", delete=False) as f:
        f.write(b"Rar!\x1A\x07\x01\x00" + b"abc" * 100)
        dosya_yolu = f.name
    aria2_yolu = dosya_yolu + ".aria2"
    with open(aria2_yolu, "wb") as f:
        f.write(_aria2_kontrol(1024, 1000, 1))
    try:
        assert tara(dosya_yolu, uzanti=".rar")["durum"] == "saglam"
        from core.butunluk import artik_kontrol_dosyasini_sil
        assert artik_kontrol_dosyasini_sil(dosya_yolu) is True
        assert not os.path.exists(aria2_yolu)
    finally:
        for yol in (dosya_yolu, aria2_yolu):
            if os.path.exists(yol):
                os.remove(yol)


def test_yarim_aria2_kontrol_dosyasi_eksik_ve_silinmez():
    with tempfile.NamedTemporaryFile(suffix=".rar", delete=False) as f:
        f.write(b"Rar!\x1A\x07\x01\x00" + b"abc" * 100)
        dosya_yolu = f.name
    aria2_yolu = dosya_yolu + ".aria2"
    with open(aria2_yolu, "wb") as f:
        f.write(_aria2_kontrol(100, 1000, 4))
    try:
        assert tara(dosya_yolu, uzanti=".rar")["durum"] == "eksik"
        from core.butunluk import artik_kontrol_dosyasini_sil
        assert artik_kontrol_dosyasini_sil(dosya_yolu) is False
        assert os.path.exists(aria2_yolu)
    finally:
        for yol in (dosya_yolu, aria2_yolu):
            if os.path.exists(yol):
                os.remove(yol)
