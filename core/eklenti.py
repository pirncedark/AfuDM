"""v2.0 "Plugin Platform" — eklenti manifesti, kayit defteri ve ayri surec hostu.

Katmanlar:
  * `manifest_dogrula` / `paket_incele` — semanin TEK kaynagi. Kurulumdan ONCE
    kullaniciya hangi izinlerin ve hangi domainlerin istendigi buradan gosterilir.
  * `Store.eklenti_*` (core/db.py, sema v4) — kurulu eklenti kaydi.
  * `EklentiHost` — her eklenti icin AYRI SUREC. Cokme ve takilma ana uygulamayi
    ETKILEMEZ; host yeniden baslatilabilir.
  * `EklentiServisi` — pywebview kopru ve HTTP API'nin ORTAK servis katmani.

DURUSTLUK (degismez kural):
    Bu ilk asama GERCEK IZOLASYON/SANDBOX DEGILDIR; "guvenilen eklenti"
    modelidir. Eklenti kodu AfuDM'in tum yetkileriyle calisir. Manifestteki
    izin ve domain listeleri BEYANDIR: kullaniciya kurulum oncesi gosterilir,
    kayda gecer, ama teknik olarak ZORLANMAZ. "Sandbox var" veya "izole
    calisir" iddiasi UI'de ve burada KULLANILMAZ.
"""
import hashlib

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

from . import paths, surum

MANIFEST_ADI = "eklenti.json"
PAKET_UZANTISI = ".afup"

# Manifestte beyan edilebilecek BILINEN izinler. Bilinmeyen izin reddedilmez,
# UI'de ham anahtariyla gosterilir — kullanici yine de gormus olur.
BILINEN_IZINLER = (
    "indirme_oku",     # indirme listesini/durumunu okur
    "indirme_ekle",    # yeni indirme ekler
    "indirme_yonet",   # duraklatir/surdurur/siler
    "ayar_oku",        # AfuDM ayarlarini okur
    "ayar_yaz",        # AfuDM ayarlarini degistirir
    "ag",              # internete cikar
    "dosya_oku",       # diskten okur
    "dosya_yaz",       # diske yazar
    "bildirim",        # bildirim gosterir
)

# Ayar alaninin ne zaman etkili oldugu — UI'de rozet olarak gosterilir.
UYGULAMA_ZAMANLARI = ("hemen", "yeni_indirmeler", "sonraki_baslatma", "servis_yeniden")

AD_DESENI = re.compile(r"^[a-z0-9][a-z0-9_-]{1,39}$")
SURUM_DESENI = re.compile(r"^\d+(\.\d+){0,3}$")
GIRIS_DESENI = re.compile(r"^[A-Za-z0-9_./-]+\.py$")
DOMAIN_DESENI = re.compile(r"^(\*\.)?[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$")

AYAR_TURLERI = ("metin", "sayi", "anahtar", "secim")

# Bir isteme verilen en fazla bekleme. Takilan eklenti buradan yakalanir.
ISTEK_ZAMAN_ASIMI = 15.0
BASLATMA_ZAMAN_ASIMI = 20.0
GUNLUK_SATIR_SINIRI = 200


class EklentiHatasi(Exception):
    """Kullaniciya GOSTERILEBILIR eklenti hatasi (kod anahtari + mesaj)."""

    def __init__(self, kod: str, mesaj: str) -> None:
        super().__init__(mesaj)
        self.kod = kod
        self.mesaj = mesaj


# --- surum karsilastirma ---------------------------------------------------
def surum_dizisi(metin: str) -> tuple[int, ...]:
    parcalar = []
    for parca in str(metin or "0").split("."):
        try:
            parcalar.append(int(parca))
        except ValueError:
            parcalar.append(0)
    while len(parcalar) < 4:
        parcalar.append(0)
    return tuple(parcalar[:4])


def surum_uyumlu(min_surum: str, max_surum: str, mevcut: str | None = None) -> bool:
    mevcut_d = surum_dizisi(mevcut or surum.SURUM)
    if min_surum and mevcut_d < surum_dizisi(min_surum):
        return False
    if max_surum and mevcut_d > surum_dizisi(max_surum):
        return False
    return True


# --- manifest --------------------------------------------------------------
def _metin(veri: dict, anahtar: str, zorunlu: bool = False, sinir: int = 200) -> str:
    deger = veri.get(anahtar)
    if deger is None:
        deger = ""
    if not isinstance(deger, (str, int, float)):
        raise EklentiHatasi("MANIFEST_ALAN", f"{anahtar} metin olmali")
    metin = str(deger).strip()
    if zorunlu and not metin:
        raise EklentiHatasi("MANIFEST_EKSIK", f"{anahtar} zorunlu")
    return metin[:sinir]


def _ayar_semasi_dogrula(ham) -> list[dict]:
    if ham in (None, ""):
        return []
    if not isinstance(ham, list):
        raise EklentiHatasi("MANIFEST_ALAN", "ayar_semasi liste olmali")
    cikti: list[dict] = []
    gorulen: set[str] = set()
    for alan in ham[:40]:
        if not isinstance(alan, dict):
            raise EklentiHatasi("MANIFEST_ALAN", "ayar_semasi ogesi nesne olmali")
        anahtar = str(alan.get("anahtar") or "").strip()
        if not anahtar or len(anahtar) > 60 or anahtar in gorulen:
            raise EklentiHatasi("MANIFEST_ALAN", f"ayar anahtari gecersiz: {anahtar[:40]}")
        gorulen.add(anahtar)
        tur = str(alan.get("tur") or "metin").strip()
        if tur not in AYAR_TURLERI:
            raise EklentiHatasi("MANIFEST_ALAN", f"bilinmeyen ayar turu: {tur[:20]}")
        uygulama = str(alan.get("uygulama") or "hemen").strip()
        if uygulama not in UYGULAMA_ZAMANLARI:
            uygulama = "hemen"
        secenekler = alan.get("secenekler") or []
        if tur == "secim":
            if not isinstance(secenekler, list) or not secenekler:
                raise EklentiHatasi("MANIFEST_ALAN", f"{anahtar}: secim icin secenekler gerekli")
            secenekler = [str(s)[:80] for s in secenekler[:50]]
        else:
            secenekler = []
        cikti.append({
            "anahtar": anahtar,
            "tur": tur,
            "etiket": str(alan.get("etiket") or anahtar)[:120],
            "aciklama": str(alan.get("aciklama") or "")[:300],
            "varsayilan": alan.get("varsayilan", "" if tur == "metin" else
                                   (0 if tur == "sayi" else
                                    (False if tur == "anahtar" else secenekler[0]))),
            "secenekler": secenekler,
            "uygulama": uygulama,
        })
        if tur == "sayi":
            for sinir_ad in ("en_az", "en_cok"):
                if sinir_ad in alan:
                    try:
                        cikti[-1][sinir_ad] = float(alan[sinir_ad])
                    except (TypeError, ValueError):
                        raise EklentiHatasi(
                            "MANIFEST_ALAN",
                            f"{anahtar}: {sinir_ad} sayi olmali") from None
    return cikti


def manifest_dogrula(ham: dict) -> dict:
    """Ham manifesti dogrular ve NORMALLESTIRILMIS sozluk dondurur.

    Gecersiz manifest hicbir sey kurmaz — kismi kurulum yoktur."""
    if not isinstance(ham, dict):
        raise EklentiHatasi("MANIFEST_BOZUK", "manifest bir JSON nesnesi olmali")
    ad = _metin(ham, "ad", zorunlu=True, sinir=40).lower()
    if not AD_DESENI.match(ad):
        raise EklentiHatasi("MANIFEST_AD", "ad yalniz kucuk harf, rakam, - ve _ icerebilir")
    eklenti_surum = _metin(ham, "surum", zorunlu=True, sinir=20)
    if not SURUM_DESENI.match(eklenti_surum):
        raise EklentiHatasi("MANIFEST_SURUM", "surum 1.2.3 biciminde olmali")
    giris = _metin(ham, "giris", zorunlu=True, sinir=120).replace("\\", "/")
    if not GIRIS_DESENI.match(giris) or giris.startswith("/") or ".." in giris.split("/"):
        raise EklentiHatasi("MANIFEST_GIRIS", "giris paket icinde bir .py dosyasi olmali")
    afudm_min = _metin(ham, "afudm_min", sinir=20)
    afudm_max = _metin(ham, "afudm_max", sinir=20)
    for etiket, deger in (("afudm_min", afudm_min), ("afudm_max", afudm_max)):
        if deger and not SURUM_DESENI.match(deger):
            raise EklentiHatasi("MANIFEST_SURUM", f"{etiket} 1.2.3 biciminde olmali")

    izinler_ham = ham.get("izinler") or []
    if not isinstance(izinler_ham, list):
        raise EklentiHatasi("MANIFEST_ALAN", "izinler liste olmali")
    izinler = []
    for izin in izinler_ham[:30]:
        metin = str(izin).strip()[:40]
        if metin and metin not in izinler:
            izinler.append(metin)

    domainler_ham = ham.get("domainler") or []
    if not isinstance(domainler_ham, list):
        raise EklentiHatasi("MANIFEST_ALAN", "domainler liste olmali")
    domainler = []
    for domain in domainler_ham[:60]:
        metin = str(domain).strip().lower()[:120]
        if not metin:
            continue
        if metin != "*" and not DOMAIN_DESENI.match(metin):
            raise EklentiHatasi("MANIFEST_DOMAIN", f"gecersiz domain: {metin[:40]}")
        if metin not in domainler:
            domainler.append(metin)

    return {
        "ad": ad,
        "baslik": _metin(ham, "baslik", sinir=120) or ad,
        "surum": eklenti_surum,
        "aciklama": _metin(ham, "aciklama", sinir=500),
        "yazar": _metin(ham, "yazar", sinir=120),
        "giris": giris,
        "afudm_min": afudm_min,
        "afudm_max": afudm_max,
        "sha256": _metin(ham, "sha256", sinir=64).lower(),
        "izinler": izinler,
        "domainler": domainler,
        "ayar_semasi": _ayar_semasi_dogrula(ham.get("ayar_semasi")),
    }


def _zip_guvenli_uyeler(zf: zipfile.ZipFile, max_boyut: int = 200 * 1024 * 1024, max_oran: float = 100.0) -> list[zipfile.ZipInfo]:
    """Zip Slip korumasi: paket disina yazmaya calisan girdiyi REDDEDER.
    Zip Bomb korumasi: boyut ve sikistirma oranini asan paketi REDDEDER."""
    uyeler = []
    toplam_boyut = 0
    toplam_sikistirilmis = 0
    for bilgi in zf.infolist():
        ad = bilgi.filename.replace("\\", "/")
        if ad.startswith("/") or ".." in ad.split("/") or ":" in ad.split("/")[0][1:2]:
            raise EklentiHatasi("PAKET_GUVENSIZ", f"paket disina yazmaya calisiyor: {ad[:60]}")
        if bilgi.file_size > max_boyut:
            raise EklentiHatasi("PAKET_COK_BUYUK", f"dosya cok buyuk: {ad[:60]} ({bilgi.file_size} bayt)")
        toplam_boyut += bilgi.file_size
        toplam_sikistirilmis += bilgi.compress_size
        uyeler.append(bilgi)
    if toplam_boyut > max_boyut:
        raise EklentiHatasi("PAKET_COK_BUYUK", f"toplam boyut cok buyuk: {toplam_boyut} bayt")
    if toplam_sikistirilmis > 0 and (toplam_boyut / toplam_sikistirilmis) > max_oran:
        raise EklentiHatasi("PAKET_COK_BUYUK", "asiri sikistirma orani (zip bomb suphesi)")
    return uyeler


def _json_oku(ham: bytes) -> dict:
    try:
        return json.loads(ham.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise EklentiHatasi("MANIFEST_BOZUK", f"{MANIFEST_ADI} gecerli JSON degil") from exc


def paket_incele(yol: str, max_boyut_mb: int = 200, max_oran: float = 100.0) -> dict:
    """KURMADAN manifesti okur — izin/domain ekrani bunu kullanir.

    `.afup` (zip) veya acik klasor kabul eder."""
    kaynak = Path(str(yol or "").strip().strip('"'))
    if not kaynak.exists():
        raise EklentiHatasi("PAKET_YOK", "paket bulunamadi")
    if kaynak.is_dir():
        manifest_yolu = kaynak / MANIFEST_ADI
        if not manifest_yolu.is_file():
            raise EklentiHatasi("MANIFEST_YOK", f"{MANIFEST_ADI} bulunamadi")
        ham = _json_oku(manifest_yolu.read_bytes())
        dosya_sayisi = sum(1 for _ in kaynak.rglob("*"))
        boyut = sum(p.stat().st_size for p in kaynak.rglob("*") if p.is_file())
    else:
        if kaynak.suffix.lower() != PAKET_UZANTISI:
            raise EklentiHatasi("PAKET_TUR", f"yalniz {PAKET_UZANTISI} paketi veya klasor")
        try:
            with zipfile.ZipFile(kaynak) as zf:
                uyeler = _zip_guvenli_uyeler(zf, max_boyut=max_boyut_mb * 1024 * 1024, max_oran=max_oran)
                adlar = [u.filename.replace("\\", "/") for u in uyeler]
                if MANIFEST_ADI not in adlar:
                    raise EklentiHatasi("MANIFEST_YOK", f"pakette {MANIFEST_ADI} yok (kokte olmali)")
                ham = _json_oku(zf.read(MANIFEST_ADI))
                dosya_sayisi = len([u for u in uyeler if not u.is_dir()])
                boyut = sum(u.file_size for u in uyeler)
        except zipfile.BadZipFile as exc:
            raise EklentiHatasi("PAKET_BOZUK", "paket okunamadi (zip bozuk)") from exc

    manifest = manifest_dogrula(ham)
    manifest["uyumlu"] = surum_uyumlu(manifest["afudm_min"], manifest["afudm_max"])
    manifest["afudm_surum"] = surum.SURUM
    manifest["kaynak"] = str(kaynak)
    manifest["dosya_sayisi"] = dosya_sayisi
    manifest["boyut"] = boyut
    # UI bunu kurulum onayinda AYNEN gosterir: teknik kisitlama YOKTUR.
    manifest["guven_modeli"] = "guvenilen_eklenti"
    return manifest


def _paketi_ac(kaynak: Path, hedef: Path, max_boyut_mb: int = 200, max_oran: float = 100.0) -> None:
    hedef.mkdir(parents=True, exist_ok=True)
    if kaynak.is_dir():
        shutil.copytree(kaynak, hedef, dirs_exist_ok=True)
        return
    with zipfile.ZipFile(kaynak) as zf:
        _zip_guvenli_uyeler(zf, max_boyut=max_boyut_mb * 1024 * 1024, max_oran=max_oran)
        zf.extractall(hedef)



def _sil(klasor: Path) -> None:
    shutil.rmtree(klasor, ignore_errors=True)


# --- ayri surec host -------------------------------------------------------
class EklentiHost:
    """Tek bir eklentinin AYRI SURECI. Cokme/takilma burada kalir.

    Durumlar: `kapali`, `baslatiliyor`, `calisiyor`, `hata`, `zaman_asimi`,
    `cokmus`. Her durum UI'de gorunur ve "Yeniden baslat" ile toparlanir.
    """

    def __init__(self, kayit: dict, klasor: Path) -> None:
        self.ad = str(kayit["ad"])
        self.kayit = kayit
        self.klasor = klasor
        self.durum = "kapali"
        self.son_hata = ""
        self.baslama_at = 0.0
        self.pid = 0
        self.gunluk: list[str] = []
        self._proc: subprocess.Popen | None = None
        self._kilit = threading.Lock()
        self._sayac = 0
        self._bekleyenler: dict[int, dict] = {}
        self._olaylar: dict[int, threading.Event] = {}

    # -- surec -------------------------------------------------------------
    def _komut(self) -> tuple[list[str], dict]:
        ortam = dict(os.environ)
        ortam["PYTHONIOENCODING"] = "utf-8"
        if getattr(sys, "frozen", False):
            # Paketlenmis kopyada ayri python yok: kendimizi host kipinde acariz.
            ortam["AFUDM_EKLENTI_HOST"] = "1"
            return [sys.executable], ortam
        return [sys.executable, "-u", "-m", "core.eklenti_host"], ortam

    def baslat(self, zaman_asimi: float = BASLATMA_ZAMAN_ASIMI) -> dict:
        with self._kilit:
            if self._proc and self._proc.poll() is None:
                return {"ok": True, "zaten": True, "durum": self.durum}
            self.durum = "baslatiliyor"
            self.son_hata = ""
            self.gunluk = []
            komut, ortam = self._komut()
            try:
                self._proc = subprocess.Popen(
                    komut, cwd=str(paths.BASE), env=ortam,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding="utf-8", errors="replace", bufsize=1,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except OSError as exc:
                self.durum = "hata"
                self.son_hata = f"host baslatilamadi: {exc}"[:400]
                return {"ok": False, "error": self.son_hata, "durum": self.durum}
            self.pid = self._proc.pid
            self.baslama_at = time.time()
            threading.Thread(target=self._oku, daemon=True).start()
            threading.Thread(target=self._gunluk_oku, daemon=True).start()
            yapilandirma = {
                "ad": self.ad,
                "surum": self.kayit.get("surum", ""),
                "afudm_surum": surum.SURUM,
                "klasor": str(self.klasor),
                "giris": self.kayit.get("giris", ""),
                "ayarlar": self.kayit.get("ayarlar") or {},
                "izinler": self.kayit.get("izinler") or [],
                "domainler": self.kayit.get("domainler") or [],
            }
            try:
                self._proc.stdin.write(json.dumps(yapilandirma, ensure_ascii=False) + "\n")
                self._proc.stdin.flush()
            except OSError as exc:
                self.durum = "hata"
                self.son_hata = f"host ile konusulamadi: {exc}"[:400]
                return {"ok": False, "error": self.son_hata, "durum": self.durum}

        sonuc = self.istek("baslat", {}, zaman_asimi=zaman_asimi)
        if sonuc.get("ok"):
            self.durum = "calisiyor"
        return sonuc

    def durdur(self, kibar_sure: float = 5.0) -> dict:
        proc = self._proc
        if not proc or proc.poll() is not None:
            self.durum = "kapali"
            self._proc = None
            return {"ok": True, "durum": "kapali"}
        try:
            self.istek("durdur", {}, zaman_asimi=kibar_sure)
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        self._proc = None
        self.pid = 0
        self.durum = "kapali"
        return {"ok": True, "durum": "kapali"}

    def yeniden_baslat(self) -> dict:
        self.durdur()
        return self.baslat()

    def calisiyor(self) -> bool:
        return bool(self._proc and self._proc.poll() is None)

    # -- protokol ----------------------------------------------------------
    def istek(self, eylem: str, veri: dict | None = None,
              zaman_asimi: float = ISTEK_ZAMAN_ASIMI) -> dict:
        """Host'a tek istek. TAKILIRSA sureci oldurur ve hatayi kaydeder."""
        proc = self._proc
        if not proc or proc.poll() is not None:
            self.durum = "kapali" if self.durum != "cokmus" else "cokmus"
            return {"ok": False, "error": "eklenti calismiyor", "durum": self.durum}
        with self._kilit:
            self._sayac += 1
            kimlik = self._sayac
            olay = threading.Event()
            self._olaylar[kimlik] = olay
            try:
                proc.stdin.write(json.dumps(
                    {"id": kimlik, "eylem": eylem, "veri": veri or {}},
                    ensure_ascii=False) + "\n")
                proc.stdin.flush()
            except OSError as exc:
                self._olaylar.pop(kimlik, None)
                self.durum = "cokmus"
                self.son_hata = f"host yaziya kapali: {exc}"[:400]
                return {"ok": False, "error": self.son_hata, "durum": self.durum}

        if not olay.wait(zaman_asimi):
            self._olaylar.pop(kimlik, None)
            self.durum = "zaman_asimi"
            self.son_hata = (f"eklenti {zaman_asimi:.0f} saniyede cevap vermedi "
                             f"({eylem}); surec durduruldu")
            try:
                proc.kill()
            except Exception:
                pass
            self._proc = None
            self.pid = 0
            return {"ok": False, "error": self.son_hata, "durum": self.durum}

        yanit = self._bekleyenler.pop(kimlik, {}) or {}
        self._olaylar.pop(kimlik, None)
        if yanit.get("ok"):
            return {"ok": True, "sonuc": yanit.get("sonuc")}
        self.durum = "hata"
        self.son_hata = str(yanit.get("hata") or "bilinmeyen eklenti hatasi")[:400]
        return {"ok": False, "error": self.son_hata, "durum": self.durum}

    def _oku(self) -> None:
        proc = self._proc
        if not proc or not proc.stdout:
            return
        try:
            for satir in proc.stdout:
                satir = satir.strip()
                if not satir:
                    continue
                try:
                    govde = json.loads(satir)
                except ValueError:
                    self._gunluge_yaz(satir)
                    continue
                kimlik = int(govde.get("id") or 0)
                if kimlik in self._olaylar:
                    self._bekleyenler[kimlik] = govde
                    self._olaylar[kimlik].set()
        except (OSError, ValueError):
            pass
        finally:
            kod = proc.poll()
            if proc is self._proc and kod is not None:
                if self.durum not in ("kapali", "zaman_asimi"):
                    self.durum = "cokmus"
                    self.son_hata = (self.son_hata
                                     or f"eklenti sureci beklenmedik sekilde kapandi (kod {kod})")
                self.pid = 0
                # Bekleyen istekler sonsuza kadar asili kalmasin
                for kimlik, olay in list(self._olaylar.items()):
                    self._bekleyenler[kimlik] = {
                        "id": kimlik, "ok": False, "hata": self.son_hata}
                    olay.set()

    def _gunluk_oku(self) -> None:
        proc = self._proc
        if not proc or not proc.stderr:
            return
        try:
            for satir in proc.stderr:
                self._gunluge_yaz(satir.rstrip())
        except (OSError, ValueError):
            pass

    def _gunluge_yaz(self, satir: str) -> None:
        if not satir:
            return
        self.gunluk.append(f"{time.strftime('%H:%M:%S')} {satir[:400]}")
        if len(self.gunluk) > GUNLUK_SATIR_SINIRI:
            del self.gunluk[: len(self.gunluk) - GUNLUK_SATIR_SINIRI]

    def ozet(self) -> dict:
        if self._proc and self._proc.poll() is not None and self.durum == "calisiyor":
            self.durum = "cokmus"
        return {
            "durum": self.durum,
            "calisiyor": self.calisiyor(),
            "pid": self.pid,
            "baslama_at": self.baslama_at,
            "son_hata": self.son_hata,
            "gunluk": list(self.gunluk[-40:]),
        }


# --- islem izleyici (uzun isler UI thread'inde calismaz) -------------------
class Islem:
    """Kurulum/guncelleme gibi uzun isin CANLI durumu. UI bunu yoklar."""

    def __init__(self, tur: str, ad: str) -> None:
        self.tur = tur
        self.ad = ad
        self.durum = "calisiyor"     # calisiyor | bitti | hata | iptal
        self.adim = "hazirlaniyor"
        self.mesaj = ""
        self.hata_kodu = ""
        self.baslangic = time.time()
        self.bitis = 0.0
        self.iptal_istendi = threading.Event()

    def ozet(self) -> dict:
        return {
            "tur": self.tur, "ad": self.ad, "durum": self.durum, "adim": self.adim,
            "mesaj": self.mesaj, "hata_kodu": self.hata_kodu,
            "baslangic": self.baslangic, "bitis": self.bitis,
            "iptal_edilebilir": self.durum == "calisiyor",
        }


class EklentiServisi:
    """pywebview kopru ve HTTP API'nin ORTAK eklenti servisi.

    Uzun isler (kur/guncelle) AYRI THREAD'de calisir; UI `islem()` ile canli
    durumu okur, `islem_iptal()` ile vazgecer."""

    def __init__(self, store) -> None:
        self.store = store
        self.kok = paths.PLUGINS
        self.kok.mkdir(parents=True, exist_ok=True)
        self._hostlar: dict[str, EklentiHost] = {}
        self._kilit = threading.RLock()
        self._islem: Islem | None = None
        self._izleyici: threading.Thread | None = None
        self._dur = threading.Event()

    # -- yasam dongusu -----------------------------------------------------
    def basla(self) -> None:
        """Etkin eklentileri baslatir ve saglik izleyicisini kurar.

        Idempotent: ikinci cagri zaten calisan hicbir seyi bozmaz."""
        for kayit in self.store.eklenti_listesi():
            if kayit.get("etkin"):
                try:
                    self._host(kayit).baslat()
                except Exception as exc:       # tek eklenti ACILISI DUSURMEZ
                    self.store.eklenti_alan_yaz(kayit["ad"], son_hata=str(exc)[:400])
        if not self._izleyici:
            self._izleyici = threading.Thread(target=self._izle, daemon=True)
            self._izleyici.start()

    def kapat(self) -> None:
        self._dur.set()
        for host in list(self._hostlar.values()):
            try:
                host.durdur(kibar_sure=2.0)
            except Exception:
                pass

    def _izle(self) -> None:
        """Saglik nabzi — GUI/API thread'inde DEGIL, kendi thread'inde."""
        while not self._dur.wait(6.0):
            for ad, host in list(self._hostlar.items()):
                if not host.calisiyor():
                    if host.durum == "calisiyor":
                        host.durum = "cokmus"
                        host.son_hata = host.son_hata or "eklenti sureci kapandi"
                        self.store.eklenti_alan_yaz(ad, son_hata=host.son_hata)
                    continue
                yanit = host.istek("ping", {}, zaman_asimi=5.0)
                if not yanit.get("ok"):
                    self.store.eklenti_alan_yaz(ad, son_hata=host.son_hata)

    def _host(self, kayit: dict) -> EklentiHost:
        with self._kilit:
            host = self._hostlar.get(kayit["ad"])
            if host is None:
                host = EklentiHost(kayit, self.kok / kayit["ad"])
                self._hostlar[kayit["ad"]] = host
            else:
                host.kayit = kayit
            return host

    # -- okuma -------------------------------------------------------------
    def liste(self) -> dict:
        kayitlar = []
        for kayit in self.store.eklenti_listesi():
            host = self._hostlar.get(kayit["ad"])
            ozet = host.ozet() if host else {
                "durum": "kapali", "calisiyor": False, "pid": 0,
                "baslama_at": 0.0, "son_hata": kayit.get("son_hata", ""), "gunluk": []}
            manifest = kayit.get("manifest") or {}
            kayitlar.append({
                "ad": kayit["ad"],
                "baslik": kayit.get("baslik") or kayit["ad"],
                "surum": kayit.get("surum", ""),
                "onceki_surum": kayit.get("onceki_surum", ""),
                "kaynak": kayit.get("kaynak", ""),
                "aciklama": manifest.get("aciklama", ""),
                "yazar": manifest.get("yazar", ""),
                "izinler": kayit.get("izinler") or [],
                "domainler": kayit.get("domainler") or [],
                "ayar_semasi": manifest.get("ayar_semasi") or [],
                "ayarlar": kayit.get("ayarlar") or {},
                "etkin": bool(kayit.get("etkin")),
                "uyumlu": surum_uyumlu(manifest.get("afudm_min", ""),
                                       manifest.get("afudm_max", "")),
                "afudm_min": manifest.get("afudm_min", ""),
                "afudm_max": manifest.get("afudm_max", ""),
                "kurulum_at": kayit.get("kurulum_at", 0),
                "guncelleme_at": kayit.get("guncelleme_at", 0),
                "son_hata": ozet.get("son_hata") or kayit.get("son_hata", ""),
                "durum": ozet["durum"],
                "calisiyor": ozet["calisiyor"],
                "pid": ozet["pid"],
                "baslama_at": ozet["baslama_at"],
            })
        return {
            "ok": True,
            "eklentiler": kayitlar,
            "klasor": str(self.kok),
            "afudm_surum": surum.SURUM,
            "bilinen_izinler": list(BILINEN_IZINLER),
            # UI bu bayragi gorunce guven uyarisini GOSTERIR. Sandbox YOK.
            "guven_modeli": "guvenilen_eklenti",
            "islem": self._islem.ozet() if self._islem else None,
        }

    def gunluk(self, ad: str) -> dict:
        host = self._hostlar.get(ad)
        kayit = self.store.eklenti(ad)
        if kayit is None:
            return {"ok": False, "error": "eklenti kurulu degil", "satirlar": []}
        ozet = host.ozet() if host else {"gunluk": [], "durum": "kapali",
                                         "son_hata": kayit.get("son_hata", "")}
        return {"ok": True, "ad": ad, "satirlar": ozet.get("gunluk") or [],
                "durum": ozet.get("durum"), "son_hata": ozet.get("son_hata", "")}

    def incele(self, yol: str) -> dict:
        """Kurulumdan ONCE: hangi izinler, hangi domainler, uyumlu mu."""
        try:
            max_boyut = int(self.store.get("eklenti_max_boyut_mb", 200))
            max_oran = float(self.store.get("eklenti_max_oran", 100.0))
            manifest = paket_incele(yol, max_boyut_mb=max_boyut, max_oran=max_oran)
        except EklentiHatasi as exc:
            return {"ok": False, "code": exc.kod, "error": exc.mesaj}
        except OSError as exc:
            return {"ok": False, "code": "PAKET_OKUNAMADI", "error": str(exc)[:200]}
        mevcut = self.store.eklenti(manifest["ad"])
        manifest["kurulu"] = bool(mevcut)
        manifest["kurulu_surum"] = (mevcut or {}).get("surum", "")
        manifest["guncelleme_mi"] = bool(mevcut)
        return {"ok": True, "manifest": manifest}

    # -- islem izleme ------------------------------------------------------
    def islem(self) -> dict:
        return {"ok": True, "islem": self._islem.ozet() if self._islem else None}

    def islem_iptal(self) -> dict:
        islem = self._islem
        if not islem or islem.durum != "calisiyor":
            return {"ok": False, "error": "iptal edilecek islem yok"}
        islem.iptal_istendi.set()
        return {"ok": True}

    def _islem_basla(self, tur: str, ad: str) -> Islem:
        with self._kilit:
            if self._islem and self._islem.durum == "calisiyor":
                raise EklentiHatasi("ISLEM_MESGUL", "baska bir eklenti islemi suruyor")
            self._islem = Islem(tur, ad)
            return self._islem

    def _arka_planda(self, islem: Islem, is_parcasi) -> dict:
        def kosucu() -> None:
            try:
                mesaj = is_parcasi(islem)
                # Is zaten "bitti" adimina geldiyse gec gelen iptal YOK SAYILIR:
                # tamamlanmis isi "iptal edildi" diye gostermek yalan olur.
                if (islem.iptal_istendi.is_set() and islem.durum == "calisiyor"
                        and islem.adim != "bitti"):
                    islem.durum = "iptal"
                    islem.mesaj = "islem iptal edildi"
                elif islem.durum == "calisiyor":
                    islem.durum = "bitti"
                    islem.mesaj = mesaj or ""
            except EklentiHatasi as exc:
                islem.durum, islem.hata_kodu, islem.mesaj = "hata", exc.kod, exc.mesaj
            except Exception as exc:
                islem.durum = "hata"
                islem.hata_kodu = type(exc).__name__
                islem.mesaj = str(exc)[:400]
            finally:
                islem.bitis = time.time()

        threading.Thread(target=kosucu, daemon=True).start()
        return {"ok": True, "islem": islem.ozet()}

    # -- kurulum / guncelleme ---------------------------------------------
    def kur(self, yol: str, onaylanan_izinler: list | None = None) -> dict:
        """Yerel `.afup` paketinden kurar. Imza YOKTUR: guvenilen kaynak sarttir."""
        try:
            max_boyut = int(self.store.get("eklenti_max_boyut_mb", 200))
            max_oran = float(self.store.get("eklenti_max_oran", 100.0))
            manifest = paket_incele(yol, max_boyut_mb=max_boyut, max_oran=max_oran)
        except EklentiHatasi as exc:
            return {"ok": False, "code": exc.kod, "error": exc.mesaj}
        if self.store.eklenti(manifest["ad"]):
            return {"ok": False, "code": "ZATEN_KURULU",
                    "error": f"{manifest['ad']} zaten kurulu — 'Guncelle' kullan"}
        if not manifest["uyumlu"]:
            return {"ok": False, "code": "UYUMSUZ",
                    "error": f"eklenti AfuDM {surum.SURUM} ile uyumlu degil"}
        beklenen = set(manifest["izinler"])
        if onaylanan_izinler is not None and set(map(str, onaylanan_izinler)) != beklenen:
            return {"ok": False, "code": "IZIN_ONAYI",
                    "error": "izin listesi degismis — kurulum ekranini yeniden ac"}
        try:
            islem = self._islem_basla("kur", manifest["ad"])
        except EklentiHatasi as exc:
            return {"ok": False, "code": exc.kod, "error": exc.mesaj}
        return self._arka_planda(islem, lambda i: self._kur_isle(i, manifest, Path(yol)))

    def _kur_isle(self, islem: Islem, manifest: dict, kaynak: Path) -> str:
        hedef = self.kok / manifest["ad"]
        islem.adim = "dosyalar_aciliyor"
        if islem.iptal_istendi.is_set():
            return ""
        gercek_sha = ""
        if kaynak.is_file():
            h = hashlib.sha256()
            with zipfile.ZipFile(kaynak) as zf:
                # Guvenlik icin infolist() siralamasi yerine isme gore siraliyoruz
                dosyalar = sorted([u.filename for u in zf.infolist() if not u.is_dir() and u.filename != MANIFEST_ADI])
                for dosya in dosyalar:
                    with zf.open(dosya) as f:
                        for buf in iter(lambda: f.read(65536), b""):
                            h.update(buf)
            gercek_sha = h.hexdigest().lower()
            beklenen = manifest.get("sha256", "").lower()
            izin_ver = self.store.get("eklenti_imzasiz_izin", True)
            if not beklenen:
                if not izin_ver:
                    raise EklentiHatasi("IMZASIZ_REDDEDILDI", "imzasiz (sha256 yok) eklentiye izin verilmiyor")
            elif beklenen != gercek_sha:
                raise EklentiHatasi("OZET_UYUSMUYOR", f"sha256 uyusmuyor! beklenen: {beklenen}, gercek: {gercek_sha}")
        _sil(hedef)
        try:
            max_boyut = int(self.store.get("eklenti_max_boyut_mb", 200))
            max_oran = float(self.store.get("eklenti_max_oran", 100.0))
            _paketi_ac(kaynak, hedef, max_boyut_mb=max_boyut, max_oran=max_oran)
        except (OSError, zipfile.BadZipFile) as exc:
            _sil(hedef)
            raise EklentiHatasi("PAKET_ACILMADI", f"paket acilamadi: {exc}"[:300]) from exc
        if islem.iptal_istendi.is_set():
            _sil(hedef)
            return ""
        if not (hedef / manifest["giris"]).is_file():
            _sil(hedef)
            raise EklentiHatasi("GIRIS_YOK", f"giris dosyasi pakette yok: {manifest['giris']}")
        islem.adim = "kaydediliyor"
        simdi = time.time()
        self.store.eklenti_yaz({
            "ad": manifest["ad"], "baslik": manifest["baslik"], "surum": manifest["surum"],
            "kaynak": str(kaynak), "giris": manifest["giris"], "manifest": manifest,
            "izinler": manifest["izinler"], "domainler": manifest["domainler"],
            "ayarlar": _varsayilan_ayarlar(manifest), "etkin": False, "son_hata": "",
            "onceki_surum": "", "kurulum_at": simdi, "guncelleme_at": simdi,
            "sha256": gercek_sha,
        })
        islem.adim = "bitti"
        return f"{manifest['baslik']} {manifest['surum']} kuruldu (devre disi)"

    def guncelle(self, ad: str, yol: str) -> dict:
        """Guncelleme BASARISIZSA onceki surume GERI DONER (rollback)."""
        kayit = self.store.eklenti(ad)
        if kayit is None:
            return {"ok": False, "code": "KURULU_DEGIL", "error": "eklenti kurulu degil"}
        try:
            max_boyut = int(self.store.get("eklenti_max_boyut_mb", 200))
            max_oran = float(self.store.get("eklenti_max_oran", 100.0))
            manifest = paket_incele(yol, max_boyut_mb=max_boyut, max_oran=max_oran)
        except EklentiHatasi as exc:
            return {"ok": False, "code": exc.kod, "error": exc.mesaj}
        if manifest["ad"] != ad:
            return {"ok": False, "code": "YANLIS_PAKET",
                    "error": f"paket '{manifest['ad']}' icin — '{ad}' bekleniyordu"}
        if not manifest["uyumlu"]:
            return {"ok": False, "code": "UYUMSUZ",
                    "error": f"yeni surum AfuDM {surum.SURUM} ile uyumlu degil"}
        try:
            islem = self._islem_basla("guncelle", ad)
        except EklentiHatasi as exc:
            return {"ok": False, "code": exc.kod, "error": exc.mesaj}
        return self._arka_planda(
            islem, lambda i: self._guncelle_isle(i, kayit, manifest, Path(yol)))

    def _guncelle_isle(self, islem: Islem, eski: dict, manifest: dict, kaynak: Path) -> str:
        ad = eski["ad"]
        hedef = self.kok / ad
        yedek = paths.PLUGIN_YEDEK / ad
        islem.adim = "durduruluyor"
        host = self._hostlar.get(ad)
        calisiyordu = bool(host and host.calisiyor())
        if host:
            host.durdur()

        islem.adim = "yedekleniyor"
        paths.PLUGIN_YEDEK.mkdir(parents=True, exist_ok=True)
        _sil(yedek)
        try:
            if hedef.exists():
                shutil.copytree(hedef, yedek)
        except OSError as exc:
            raise EklentiHatasi("YEDEK_ALINAMADI",
                                f"yedek alinamadi, guncelleme yapilmadi: {exc}"[:300]) from exc

        try:
            if islem.iptal_istendi.is_set():
                raise EklentiHatasi("IPTAL", "islem iptal edildi")

            gercek_sha = ""
            if kaynak.is_file():
                h = hashlib.sha256()
                with zipfile.ZipFile(kaynak) as zf:
                    dosyalar = sorted([u.filename for u in zf.infolist() if not u.is_dir() and u.filename != MANIFEST_ADI])
                    for dosya in dosyalar:
                        with zf.open(dosya) as f:
                            for buf in iter(lambda: f.read(65536), b""):
                                h.update(buf)
                gercek_sha = h.hexdigest().lower()
                beklenen = manifest.get("sha256", "").lower()
                izin_ver = self.store.get("eklenti_imzasiz_izin", True)
                if not beklenen:
                    if not izin_ver:
                        raise EklentiHatasi("IMZASIZ_REDDEDILDI", "imzasiz (sha256 yok) eklentiye izin verilmiyor")
                elif beklenen != gercek_sha:
                    raise EklentiHatasi("OZET_UYUSMUYOR", f"sha256 uyusmuyor! beklenen: {beklenen}, gercek: {gercek_sha}")
            islem.adim = "dosyalar_aciliyor"
            _sil(hedef)
            max_boyut = int(self.store.get("eklenti_max_boyut_mb", 200))
            max_oran = float(self.store.get("eklenti_max_oran", 100.0))
            _paketi_ac(kaynak, hedef, max_boyut_mb=max_boyut, max_oran=max_oran)
            if not (hedef / manifest["giris"]).is_file():
                raise EklentiHatasi("GIRIS_YOK",
                                    f"giris dosyasi pakette yok: {manifest['giris']}")
            islem.adim = "kaydediliyor"
            ayarlar = _ayarlari_tasi(eski.get("ayarlar") or {}, manifest)
            self.store.eklenti_yaz({
                "ad": ad, "baslik": manifest["baslik"], "surum": manifest["surum"],
                "kaynak": str(kaynak), "giris": manifest["giris"], "manifest": manifest,
                "izinler": manifest["izinler"], "domainler": manifest["domainler"],
                "ayarlar": ayarlar, "etkin": bool(eski.get("etkin")), "son_hata": "",
                "onceki_surum": eski.get("surum", ""),
                "kurulum_at": eski.get("kurulum_at", time.time()),
                "guncelleme_at": time.time(),
                "sha256": gercek_sha,
            })
            if calisiyordu or eski.get("etkin"):
                islem.adim = "baslatiliyor"
                yeni_host = self._host(self.store.eklenti(ad) or eski)
                sonuc = yeni_host.baslat()
                if not sonuc.get("ok"):
                    raise EklentiHatasi(
                        "YENI_SURUM_BASLAMADI",
                        f"yeni surum baslamadi: {sonuc.get('error', '')}"[:300])
        except Exception as exc:
            islem.adim = "geri_aliniyor"
            self._geri_al(ad, eski, yedek, hedef, calisiyordu)
            kod = getattr(exc, "kod", type(exc).__name__)
            mesaj = getattr(exc, "mesaj", str(exc))
            raise EklentiHatasi(
                kod, f"{mesaj} — onceki surum ({eski.get('surum', '?')}) geri yuklendi"[:400]
            ) from exc
        islem.adim = "bitti"
        return (f"{manifest['baslik']} {eski.get('surum', '?')} -> {manifest['surum']} "
                f"guncellendi")
    def elle_geri_al(self, ad: str) -> dict:
        """Kullanici istegiyle onceki surume rollback."""
        kayit = self.store.eklenti(ad)
        if not kayit:
            return {"ok": False, "code": "KURULU_DEGIL", "error": "eklenti kurulu degil"}
        if not kayit.get("onceki_surum"):
            return {"ok": False, "code": "YEDEK_YOK", "error": "onceki surum kaydi yok"}
            
        yedek = paths.PLUGIN_YEDEK / ad
        if not yedek.exists():
            return {"ok": False, "code": "YEDEK_SILINMIS", "error": "yedek dosyalari bulunamadi"}
            
        islem = self._islem_basla("geri_al", ad)
        
        def kosucu(i: Islem):
            try:
                i.adim = "geri_aliniyor"
                hedef = self.kok / ad
                host = self._hostlar.get(ad)
                calisiyordu = bool(host and host.calisiyor()) or kayit.get("etkin")
                if host:
                    host.durdur()
                
                _sil(hedef)
                import shutil
                shutil.copytree(yedek, hedef)
                
                eski = dict(kayit)
                eski["surum"] = kayit["onceki_surum"]
                eski["onceki_surum"] = kayit["surum"]
                eski["son_hata"] = ""
                self.store.eklenti_yaz(eski)
                
                if calisiyordu:
                    yeni_host = self._host(self.store.eklenti(ad) or eski)
                    yeni_host.baslat()
                    
                i.mesaj = f"{kayit['surum']} -> {eski['surum']} geri alindi"
                i.adim = "bitti"
            except Exception as exc:
                i.adim = "hata"
                i.mesaj = str(exc)[:400]
            finally:
                i.bitis = time.time()
                
        import threading
        threading.Thread(target=kosucu, daemon=True).start()
        return {"ok": True, "islem": islem.ozet()}


    def _geri_al(self, ad: str, eski: dict, yedek: Path, hedef: Path, calisiyordu: bool) -> None:
        """Rollback: dosyalar + kayit + (gerekiyorsa) surec eski haline doner."""
        try:
            host = self._hostlar.get(ad)
            if host:
                host.durdur()
            _sil(hedef)
            if yedek.exists():
                shutil.copytree(yedek, hedef)
            self.store.eklenti_yaz({**eski, "guncelleme_at": time.time(),
                                    "son_hata": "guncelleme basarisiz — geri alindi"})
            if calisiyordu:
                self._host(self.store.eklenti(ad) or eski).baslat()
        except Exception:
            # Geri alma da basarisizsa kullanici en azindan hatayi gorur.
            self.store.eklenti_alan_yaz(
                ad, son_hata="guncelleme basarisiz ve geri alma tamamlanamadi")

    def kaldir(self, ad: str) -> dict:
        kayit = self.store.eklenti(ad)
        if kayit is None:
            return {"ok": False, "code": "KURULU_DEGIL", "error": "eklenti kurulu degil"}
        try:
            islem = self._islem_basla("kaldir", ad)
        except EklentiHatasi as exc:
            return {"ok": False, "code": exc.kod, "error": exc.mesaj}
        return self._arka_planda(islem, lambda i: self._kaldir_isle(i, ad))

    def _kaldir_isle(self, islem: Islem, ad: str) -> str:
        islem.adim = "durduruluyor"
        host = self._hostlar.pop(ad, None)
        if host:
            host.durdur()
        islem.adim = "dosyalar_siliniyor"
        _sil(self.kok / ad)
        self.store.eklenti_sil(ad)
        islem.adim = "bitti"
        return f"{ad} kaldirildi"

    # -- etkinlik / ayar ---------------------------------------------------
    def etkinlestir(self, ad: str, acik: bool) -> dict:
        kayit = self.store.eklenti(ad)
        if kayit is None:
            return {"ok": False, "code": "KURULU_DEGIL", "error": "eklenti kurulu degil"}
        if acik:
            manifest = kayit.get("manifest") or {}
            if not surum_uyumlu(manifest.get("afudm_min", ""), manifest.get("afudm_max", "")):
                return {"ok": False, "code": "UYUMSUZ",
                        "error": f"eklenti AfuDM {surum.SURUM} ile uyumlu degil"}
            host = self._host(kayit)
            sonuc = host.baslat()
            self.store.eklenti_alan_yaz(
                ad, etkin=bool(sonuc.get("ok")), son_hata=host.son_hata)
            if not sonuc.get("ok"):
                return {"ok": False, "code": "BASLAMADI",
                        "error": sonuc.get("error") or "eklenti baslatilamadi"}
            return {"ok": True, "durum": host.durum}
        host = self._hostlar.get(ad)
        if host:
            host.durdur()
        self.store.eklenti_alan_yaz(ad, etkin=False)
        return {"ok": True, "durum": "kapali"}

    def yeniden_baslat(self, ad: str) -> dict:
        kayit = self.store.eklenti(ad)
        if kayit is None:
            return {"ok": False, "code": "KURULU_DEGIL", "error": "eklenti kurulu degil"}
        if not kayit.get("etkin"):
            return {"ok": False, "code": "PASIF",
                    "error": "eklenti devre disi — once etkinlestir"}
        host = self._host(kayit)
        sonuc = host.yeniden_baslat()
        self.store.eklenti_alan_yaz(ad, son_hata=host.son_hata)
        if not sonuc.get("ok"):
            return {"ok": False, "code": "BASLAMADI",
                    "error": sonuc.get("error") or "eklenti baslatilamadi"}
        return {"ok": True, "durum": host.durum}

    def ayar_kaydet(self, ad: str, ayarlar: dict) -> dict:
        """Eklentinin KENDI ayar semasina gore dogrular ve kalici yazar."""
        kayit = self.store.eklenti(ad)
        if kayit is None:
            return {"ok": False, "code": "KURULU_DEGIL", "error": "eklenti kurulu degil"}
        sema = (kayit.get("manifest") or {}).get("ayar_semasi") or []
        try:
            temiz = _ayarlari_dogrula(sema, ayarlar or {}, kayit.get("ayarlar") or {})
        except EklentiHatasi as exc:
            return {"ok": False, "code": exc.kod, "error": exc.mesaj}
        self.store.eklenti_alan_yaz(ad, ayarlar=temiz)
        host = self._hostlar.get(ad)
        uygulandi = False
        if host and host.calisiyor():
            host.kayit = self.store.eklenti(ad) or kayit
            sonuc = host.istek("ayar", {"ayarlar": temiz})
            uygulandi = bool(sonuc.get("ok"))
            if not uygulandi:
                self.store.eklenti_alan_yaz(ad, son_hata=host.son_hata)
        return {"ok": True, "ayarlar": temiz, "canli_uygulandi": uygulandi}


def _varsayilan_ayarlar(manifest: dict) -> dict:
    return {alan["anahtar"]: alan.get("varsayilan")
            for alan in (manifest.get("ayar_semasi") or [])}


def _ayarlari_tasi(eski: dict, manifest: dict) -> dict:
    """Guncellemede KULLANICI AYARLARI KORUNUR; yeni alanlar varsayilanla gelir."""
    yeni = _varsayilan_ayarlar(manifest)
    for anahtar, deger in (eski or {}).items():
        if anahtar in yeni:
            yeni[anahtar] = deger
    return yeni


def _ayarlari_dogrula(sema: list, gelen: dict, mevcut: dict) -> dict:
    """Gecersiz tek alan HICBIR alani yazmaz (atomik ayar kurali)."""
    cikti = dict(mevcut)
    for alan in sema:
        anahtar = alan["anahtar"]
        if anahtar not in gelen:
            cikti.setdefault(anahtar, alan.get("varsayilan"))
            continue
        deger = gelen[anahtar]
        tur = alan.get("tur", "metin")
        if tur == "anahtar":
            if isinstance(deger, str):
                deger = deger.strip().lower() in ("1", "true", "evet")
            cikti[anahtar] = bool(deger)
        elif tur == "sayi":
            try:
                sayi = float(deger)
            except (TypeError, ValueError):
                raise EklentiHatasi("AYAR_TUR", f"{alan.get('etiket', anahtar)}: sayi bekleniyor")
            if "en_az" in alan and sayi < float(alan["en_az"]):
                raise EklentiHatasi("AYAR_ARALIK",
                                    f"{alan.get('etiket', anahtar)}: en az {alan['en_az']}")
            if "en_cok" in alan and sayi > float(alan["en_cok"]):
                raise EklentiHatasi("AYAR_ARALIK",
                                    f"{alan.get('etiket', anahtar)}: en cok {alan['en_cok']}")
            cikti[anahtar] = int(sayi) if float(sayi).is_integer() else sayi
        elif tur == "secim":
            metin = str(deger)
            if metin not in (alan.get("secenekler") or []):
                raise EklentiHatasi("AYAR_SECIM",
                                    f"{alan.get('etiket', anahtar)}: gecersiz secenek")
            cikti[anahtar] = metin
        else:
            metin = str(deger)
            if len(metin) > 2000:
                raise EklentiHatasi("AYAR_UZUN",
                                    f"{alan.get('etiket', anahtar)}: en cok 2000 karakter")
            cikti[anahtar] = metin
    return cikti
