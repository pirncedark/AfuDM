"""Dosya turu / protokol iliskilendirme — .torrent ve magnet: AfuDM'e baglama.

Sorun: .torrent dosyasina cift tiklayinca ya da magnet: baglantisina
tiklayinca baska bir indirme yoneticisi (orn. qBittorrent) aciliyor.
Bu modul HKEY_CURRENT_USER altina (yonetici GEREKMEZ, HKLM'ye HIC
DOKUNULMAZ) yazarak AfuDM'i ayni listeye ekler.

GERI ALINABILIRLIK (tek cumleyle): ac() cagrisindan once .torrent'in o anki
varsayilan ProgId'ini (ve magnet icin var olan shell\\open\\command / aciklama
degerlerini) kendi anahtarlarimizin altina "AfuDM_Onceki..." adiyla YEDEKLER;
kapat() bu yedegi okuyup AYNEN geri yazar ve kendi eklediklerimizi siler, oyle
ki hicbir yedek yoksa (ac() hic cagrilmadiysa) kapat() sessiz bir no-op'tur.

WINDOWS 11 SINIRI (onemli, gercek): Windows 11'de kullanicinin "varsayilan
uygulama" secimi HKCU\\...\\FileExts\\.torrent\\UserChoice (ve protokoller icin
...\\UrlAssociations\\<protokol>\\UserChoice) altinda HASH ile korunur; bu
deger PROGRAMLA degistirilemez (Windows sahte/degistirilmis hash'i tanir ve
yok sayar). Bu modul bunu ZORLAMAYA CALISMAZ. Bunun yerine ProgId'imizi
kaydeder ki AfuDM Gezgin'in "Birlikte ac / Baska bir uygulama sec" listesinde
CIKSIN; kullanici gercek varsayilani hala kendisi secmelidir. `varsayilan_mi()`
gercek UserChoice (ve UserChoice yoksa gercek birlesik HKEY_CLASSES_ROOT
gorunumunu) SADECE OKUYARAK durumu durustce raporlar — hicbir sekilde yazmaz.

TEST EDILEBILIRLIK: `KOK` modul degiskenidir (core/cerez.py'deki KLASOR
deseninin ayni), testler gercek kayit defterini kirletmemek icin bunu
`Software\\AfuDM-test\\Classes` gibi bir test koku ile degistirir.
`varsayilan_mi()` ise KOK'tan BAGIMSIZ, hep GERCEK HKCU/HKCR'yi okur (sadece
okur, testlerde de gercek makine durumunu yansitir — bu kasitli).
"""
from __future__ import annotations

import sys
import winreg
from pathlib import Path

from core import paths

# Test bu koku degistirir (orn. r"Software\AfuDM-test\Classes"); GERCEK kokta
# HKLM'ye HIC DOKUNULMAZ, sadece HKCU altina yazilir.
KOK = r"Software\Classes"

TORRENT_UZANTI = ".torrent"
TORRENT_PROGID = "AfuDM.torrent"
MAGNET_PROTOKOL = "magnet"

_VARSAYILAN = ""  # winreg'de "anahtarin varsayilan degeri" adı bos dizedir


# --- dusuk seviye kayit defteri yardimcilari ---------------------------------
def _oku(alt_anahtar: str, deger_adi: str = _VARSAYILAN) -> str | None:
    """KOK altindaki alt_anahtar\\deger_adi degerini oku; yoksa None don."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"{KOK}\\{alt_anahtar}") as k:
            deger, _tur = winreg.QueryValueEx(k, deger_adi)
            return str(deger)
    except OSError:
        return None


def _yaz(alt_anahtar: str, deger: str, deger_adi: str = _VARSAYILAN) -> None:
    """KOK altindaki alt_anahtar\\deger_adi degerini yaz (yoksa anahtari olustur)."""
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{KOK}\\{alt_anahtar}") as k:
        winreg.SetValueEx(k, deger_adi, 0, winreg.REG_SZ, deger)


def _sil_deger(alt_anahtar: str, deger_adi: str = _VARSAYILAN) -> None:
    """Bir degeri sil; anahtar ya da deger yoksa sessizce gec."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"{KOK}\\{alt_anahtar}", 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, deger_adi)
    except OSError:
        pass


def _agac_sil(alt_anahtar: str) -> None:
    """KOK altindaki alt_anahtar'i ALT ANAHTARLARIYLA BIRLIKTE sil (winreg'de yerlesik yok)."""
    tam_yol = f"{KOK}\\{alt_anahtar}"
    _alt_agaci_sil(tam_yol)


def _alt_agaci_sil(yol: str) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, yol, 0, winreg.KEY_ALL_ACCESS) as k:
            while True:
                try:
                    alt_ad = winreg.EnumKey(k, 0)
                except OSError:
                    break
                _alt_agaci_sil(f"{yol}\\{alt_ad}")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, yol)
    except FileNotFoundError:
        pass


# --- hedef calistirilabilir --------------------------------------------------
def hedef() -> tuple[str, str]:
    """(calistirilabilir_yol, tam_komut_satiri) dondurur.

    Once paths.BASE altindaki AfuDM.exe'yi dener; yoksa pythonw.exe + app.py
    ile duser (kaynaktan calisirken de iliskilendirme test edilebilsin diye).
    """
    exe = paths.BASE / "AfuDM.exe"
    if exe.exists():
        return str(exe), f'"{exe}" "%1"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.exists():
        pythonw = Path(sys.executable)
    app_py = paths.BASE / "app.py"
    return str(pythonw), f'"{pythonw}" "{app_py}" "%1"'


# --- torrent ------------------------------------------------------------------
def _torrent_ac(komut: str) -> None:
    # 1) kendi ProgId'imiz
    _yaz(TORRENT_PROGID, "AfuDM Torrent Dosyasi")
    _yaz(f"{TORRENT_PROGID}\\shell\\open\\command", komut)

    # 2) eski durumu YALNIZ ILK KEZ yedekle (ikinci ac() kendi degerimizi
    #    yedek sanip UZERINE YAZMASIN)
    if _oku(TORRENT_PROGID, "AfuDM_OncekiVarMi") is None:
        eski_progid = _oku(TORRENT_UZANTI)
        if eski_progid is not None and eski_progid != TORRENT_PROGID:
            _yaz(TORRENT_PROGID, "1", "AfuDM_OncekiVarMi")
            _yaz(TORRENT_PROGID, eski_progid, "AfuDM_OncekiProgId")
        else:
            _yaz(TORRENT_PROGID, "0", "AfuDM_OncekiVarMi")

    # 3) .torrent'i bize baglama + "Birlikte ac" listesine ekleme
    _yaz(TORRENT_UZANTI, TORRENT_PROGID)
    _yaz(f"{TORRENT_UZANTI}\\OpenWithProgids", "", TORRENT_PROGID)


def _torrent_kapat() -> None:
    onceki_var = _oku(TORRENT_PROGID, "AfuDM_OncekiVarMi")
    if onceki_var is None:
        return  # ac() hic cagrilmamis, dokunacak bir sey yok
    if onceki_var == "1":
        eski_progid = _oku(TORRENT_PROGID, "AfuDM_OncekiProgId") or ""
        _yaz(TORRENT_UZANTI, eski_progid)
    else:
        _sil_deger(TORRENT_UZANTI)
    _sil_deger(f"{TORRENT_UZANTI}\\OpenWithProgids", TORRENT_PROGID)
    _agac_sil(TORRENT_PROGID)


# --- magnet ---------------------------------------------------------------------
def _magnet_ac(komut: str) -> None:
    if _oku(MAGNET_PROTOKOL, "AfuDM_OncekiVarMi") is None:
        eski_komut = _oku(f"{MAGNET_PROTOKOL}\\shell\\open\\command")
        eski_aciklama = _oku(MAGNET_PROTOKOL)
        if eski_komut is not None or eski_aciklama is not None:
            _yaz(MAGNET_PROTOKOL, "1", "AfuDM_OncekiVarMi")
            if eski_komut is not None:
                _yaz(MAGNET_PROTOKOL, eski_komut, "AfuDM_OncekiKomut")
            if eski_aciklama is not None:
                _yaz(MAGNET_PROTOKOL, eski_aciklama, "AfuDM_OncekiAciklama")
        else:
            _yaz(MAGNET_PROTOKOL, "0", "AfuDM_OncekiVarMi")

    _yaz(MAGNET_PROTOKOL, "URL:Magnet Baglantisi")
    _yaz(MAGNET_PROTOKOL, "", "URL Protocol")
    _yaz(f"{MAGNET_PROTOKOL}\\shell\\open\\command", komut)


def _magnet_kapat() -> None:
    onceki_var = _oku(MAGNET_PROTOKOL, "AfuDM_OncekiVarMi")
    if onceki_var is None:
        return
    if onceki_var == "1":
        eski_komut = _oku(MAGNET_PROTOKOL, "AfuDM_OncekiKomut")
        eski_aciklama = _oku(MAGNET_PROTOKOL, "AfuDM_OncekiAciklama")
        if eski_aciklama is not None:
            _yaz(MAGNET_PROTOKOL, eski_aciklama)
        else:
            _sil_deger(MAGNET_PROTOKOL)
        if eski_komut is not None:
            _yaz(f"{MAGNET_PROTOKOL}\\shell\\open\\command", eski_komut)
        else:
            _agac_sil(f"{MAGNET_PROTOKOL}\\shell\\open\\command")
        _sil_deger(MAGNET_PROTOKOL, "AfuDM_OncekiKomut")
        _sil_deger(MAGNET_PROTOKOL, "AfuDM_OncekiAciklama")
        _sil_deger(MAGNET_PROTOKOL, "AfuDM_OncekiVarMi")
    else:
        # ac() oncesinde magnet HIC kayitli degildi -> tamamen bizim urunumuz
        _agac_sil(MAGNET_PROTOKOL)


# --- disa acik API --------------------------------------------------------------
def ac() -> None:
    """.torrent ve magnet: AfuDM'e bagla. Iki kez cagrilmak GUVENLIDIR (yedek
    yalniz ilk cagrida alinir)."""
    _, komut = hedef()
    _torrent_ac(komut)
    _magnet_ac(komut)


def kapat() -> None:
    """ac() ile yapilan her seyi geri al: yedeklenen eski durum aynen doner,
    hicbir yedek yoksa (ac() cagrilmadiysa) sessizce hicbir sey yapmaz."""
    _torrent_kapat()
    _magnet_kapat()


def acik_mi() -> bool:
    """Su an .torrent VE magnet ikisi de bizim hedefimize kayitli mi (kayitli
    olmak GERCEK Windows varsayilani olmak ANLAMINA GELMEZ, bkz. durum())."""
    d = durum()
    return d["torrent"]["kayitli"] and d["magnet"]["kayitli"]


def varsayilan_mi(tur: str) -> bool:
    """Windows'un GERCEK varsayilan uygulama secimini (UserChoice, yoksa
    birlesik HKEY_CLASSES_ROOT) SADECE OKUYARAK durustce raporlar; KOK'tan
    bagimsizdir ve hicbir sekilde YAZMAZ (UserChoice hash korumali, zorlanamaz)."""
    _, komut = hedef()
    if tur == "torrent":
        uc_yol = r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.torrent\UserChoice"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, uc_yol) as k:
                progid, _t = winreg.QueryValueEx(k, "ProgId")
            return progid == TORRENT_PROGID
        except OSError:
            pass
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, TORRENT_UZANTI) as k:
                progid, _t = winreg.QueryValueEx(k, _VARSAYILAN)
            return progid == TORRENT_PROGID
        except OSError:
            return False
    if tur == "magnet":
        uc_yol = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\magnet\UserChoice"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, uc_yol) as k:
                progid, _t = winreg.QueryValueEx(k, "ProgId")
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"{progid}\\shell\\open\\command") as ck:
                gercek_komut, _t2 = winreg.QueryValueEx(ck, _VARSAYILAN)
            return gercek_komut == komut
        except OSError:
            pass
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"{MAGNET_PROTOKOL}\shell\open\command") as k:
                gercek_komut, _t = winreg.QueryValueEx(k, _VARSAYILAN)
            return gercek_komut == komut
        except OSError:
            return False
    raise ValueError(f"bilinmeyen tur: {tur!r} (torrent | magnet olmali)")


def durum() -> dict:
    """torrent ve magnet icin ayri ayri {'kayitli': .., 'varsayilan': ..} dondurur.
    kayitli   -> AfuDM su an bizim ac()'imizin yazdigi hedefe bagli mi
    varsayilan -> Windows'un GERCEK secimi bu mu (bkz. varsayilan_mi belgeleri)"""
    _, komut = hedef()
    torrent_kayitli = (
        _oku(TORRENT_UZANTI) == TORRENT_PROGID
        or _oku(f"{TORRENT_UZANTI}\\OpenWithProgids", TORRENT_PROGID) is not None
    )
    magnet_kayitli = _oku(f"{MAGNET_PROTOKOL}\\shell\\open\\command") == komut
    return {
        "torrent": {"kayitli": bool(torrent_kayitli), "varsayilan": varsayilan_mi("torrent")},
        "magnet": {"kayitli": bool(magnet_kayitli), "varsayilan": varsayilan_mi("magnet")},
    }
