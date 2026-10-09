import os
import json
import hashlib
import threading

BLOCK_SIZE = 4 * 1024 * 1024
SIFIR_DOGAL = {".iso", ".img", ".vhd", ".vhdx", ".vmdk", ".bin", ".dat", ".raw"}

def tara(dosya_yolu, beklenen_boyut=None, checksum=None, checksum_tipi=None, uzanti=None):
    if not os.path.exists(dosya_yolu):
        return {"durum": "bulunamadi", "neden": "Dosya diskte bulunamadı."}

    aria2_yolu = dosya_yolu + ".aria2"
    aria2_var = os.path.exists(aria2_yolu)

    gercek_boyut = os.path.getsize(dosya_yolu)
    if beklenen_boyut is not None:
        try:
            beklenen_boyut = int(beklenen_boyut)
            if beklenen_boyut > 0 and gercek_boyut != beklenen_boyut:
                return {"durum": "eksik", "neden": f"Boyut uyuşmuyor (Beklenen: {beklenen_boyut}, Gerçek: {gercek_boyut})."}
        except ValueError:
            pass

    if uzanti is None:
        _, ext = os.path.splitext(dosya_yolu)
        uzanti = ext.lower()
    else:
        uzanti = uzanti.lower()
        if not uzanti.startswith('.'):
            uzanti = '.' + uzanti

    if gercek_boyut == 0:
        return {"durum": "eksik", "neden": "Dosya boyutu 0 bayt."}

    toplam_blok = (gercek_boyut + BLOCK_SIZE - 1) // BLOCK_SIZE
    bozuk_bloklar = []

    izin_verilen_html_uzantilar = ['.html', '.htm', '.xml', '.json']
    sihirli_baytlar = {
        '.rar': b'Rar!',
        '.zip': b'PK',
        '.7z': b'7z\xBC\xAF\x27\x1C',
        '.pdf': b'%PDF',
        '.exe': b'MZ',
    }

    try:
        with open(dosya_yolu, 'rb') as f:
            for i in range(toplam_blok):
                offset = i * BLOCK_SIZE
                f.seek(offset)
                block = f.read(BLOCK_SIZE)

                if not block:
                    break

                is_bad = False
                sebep = ""

                # 1. Tamamı sıfır mı?
                if not block.strip(b'\x00'):
                    is_bad = True
                    sebep = "sıfır"
                else:
                    # 2. İlk blok için sihirli bayt kontrolü
                    if i == 0 and uzanti in sihirli_baytlar:
                        beklenen_bayt = sihirli_baytlar[uzanti]
                        if not block.startswith(beklenen_bayt):
                            is_bad = True
                            sebep = "imza yok"

                    # 3. HTML/Hata sayfası kontrolü (sadece izin verilmeyen uzantılar için)
                    if uzanti not in izin_verilen_html_uzantilar:
                        baslik_str = block[:4096].decode('utf-8', errors='ignore').strip()
                        if baslik_str.lower().startswith('<!doctype') or baslik_str.lower().startswith('<html') or baslik_str.startswith('<?xml'):
                            is_bad = True
                            sebep = "HTML"
                        elif baslik_str.startswith('{') and baslik_str.endswith('}') and len(baslik_str) < 4096:
                            try:
                                json.loads(baslik_str)
                                is_bad = True
                                sebep = "JSON"
                            except:
                                pass
                        elif baslik_str.startswith('{') and '"' in baslik_str and ':' in baslik_str:
                            is_bad = True
                            sebep = "JSON"

                if is_bad:
                    bozuk_bloklar.append({"offset": offset, "boyut": len(block), "index": i, "sebep": sebep})

    except Exception as e:
        return {"durum": "eksik", "neden": f"Dosya okunamadı: {str(e)}"}

    if bozuk_bloklar:
        is_html = False
        is_imza = False
        for b in bozuk_bloklar:
            if b.get("sebep") == "HTML": is_html = True
            if b.get("sebep") == "imza yok": is_imza = True

        ek_neden = ""
        if is_html: ek_neden = " (HTML içeriyor)"
        elif is_imza: ek_neden = " (imza yok)"

        return {
            "durum": "bozuk",
            "neden": f"{len(bozuk_bloklar)} blok bozuk bulundu.{ek_neden}",
            "bozuk_bloklar": bozuk_bloklar,
            "toplam_blok": toplam_blok,
            "bozuk_sayisi": len(bozuk_bloklar)
        }

    if aria2_var:
        return {"durum": "eksik", "neden": "İndirme tamamlanmamış (.aria2 dosyası duruyor)."}
    return {"durum": "saglam", "neden": "Dosya sağlam görünüyor."}

def checksum_tara_arkaplan(dosya_yolu, checksum, checksum_tipi, callback):
    def run():
        try:
            if checksum_tipi and checksum_tipi.lower() in hashlib.algorithms_available:
                hasher = hashlib.new(checksum_tipi.lower())
            else:
                hasher = hashlib.sha256()

            with open(dosya_yolu, 'rb') as f:
                for chunk in iter(lambda: f.read(4096 * 1024), b""):
                    hasher.update(chunk)

            hesaplanan = hasher.hexdigest()
            if hesaplanan.lower() == checksum.lower():
                 callback({"durum": "saglam", "neden": "Checksum doğrulandı."})
            else:
                 callback({"durum": "bozuk", "neden": f"Checksum uyuşmuyor (Beklenen: {checksum}, Hesaplanan: {hesaplanan})."})
        except Exception as e:
            callback({"durum": "bozuk", "neden": f"Checksum hesaplanırken hata: {str(e)}"})

    t = threading.Thread(target=run, daemon=True)
    t.start()


def icerik_html_mi(data: bytes) -> bool:
    bas = data[:4096].decode("utf-8", errors="ignore").lstrip().lower()
    return bas.startswith(("<!doctype", "<html", "<?xml"))


def blok_indir(url, basliklar, offset, boyut, timeout=30):
    """Yeni linkten YALNIZ [offset, offset+boyut) araligini indirir.

    Sunucu Range'i yok sayip 200 (tum dosya) donerse okumaz; HTML/hata sayfasi
    ya da eksik bayt gelirse ValueError firlatir (dosyaya hicbir sey yazilmaz).
    """
    import urllib.request
    req = urllib.request.Request(url)
    for k, v in (basliklar or {}).items():
        req.add_header(k, v)
    if not req.has_header("User-agent"):
        req.add_header("User-Agent", "AfuDM")
    req.add_header("Range", "bytes=%d-%d" % (offset, offset + boyut - 1))
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 206:
            raise ValueError("Link kaldığı yerden indirmeyi desteklemiyor.")
        data = resp.read(boyut + 1)
    if icerik_html_mi(data):
        raise ValueError("Link geçersiz (hata sayfası döndü), yeni link ver.")
    if len(data) != boyut:
        raise ValueError("Sunucu eksik veri verdi, tekrar denenecek.")
    return data
