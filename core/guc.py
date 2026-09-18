"""Guc yonetimi: isler bitince uyutma ve telefondan uyandirma (Wake-on-LAN).

Neden uyku, kapatma degil: bilgisayar KAPATILIRSA acilista Windows sifresi
istenir ve Baslangic klasorundeki AfuDM oturum acilana kadar CALISMAZ. Uykudan
uyandiginda ise oturum zaten acik (ekran kilitli olsa bile) ve indirme kaldigi
yerden surer — kullanicinin sifre girmesine gerek kalmaz.

Tarayici UDP paketi gonderemez, bu yuzden telefondaki AfuDM arayuzu makineyi
kendisi uyandiramaz; kullanici telefonuna bir Wake-on-LAN uygulamasi kurar ve
buradaki MAC adresini girer. Modul o yuzden MAC'i ve WoL'un ACIK OLUP
OLMADIGINI raporlamaya odaklanir; `wol_gonder` da agdaki baska bir makineyi
(ornegin ikinci bir PC) uyandirmak icin durur.
"""
from __future__ import annotations

import ctypes
import re
import socket
import subprocess

CREATE_NO_WINDOW = 0x08000000


def uyut() -> bool:
    """Makineyi uyut (S3). Hazirda bekletme DEGIL: uyanma saniyeler surer.

    SetSuspendState'in ilk parametresi "hibernate"; False vererek uyku istiyoruz.
    Windows'ta hazirda bekletme ACIKSA sistem yine de hazirda bekletmeyi
    secebilir; bu Windows'un karari, buradan zorlanmaz.
    """
    try:
        return bool(ctypes.windll.powrprof.SetSuspendState(False, False, False))
    except (AttributeError, OSError):
        return False


def _powershell(komut: str, saniye: float = 20.0) -> str:
    try:
        sonuc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-Command", komut],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=saniye, creationflags=CREATE_NO_WINDOW,
        )
        return (sonuc.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def aktif_kart() -> dict:
    """Su an baglantiyi tasiyan ag karti: ad + MAC (telefona girilecek olan)."""
    ham = _powershell(
        "Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | "
        "Select-Object -First 1 Name,MacAddress,InterfaceDescription | "
        "ForEach-Object { $_.Name + '|' + $_.MacAddress + '|' + $_.InterfaceDescription }")
    parcalar = ham.splitlines()[0].split("|") if ham else []
    if len(parcalar) < 2:
        return {"ad": "", "mac": "", "aciklama": ""}
    return {"ad": parcalar[0].strip(), "mac": parcalar[1].strip().upper(),
            "aciklama": (parcalar[2].strip() if len(parcalar) > 2 else "")}


def wol_acik_mi(kart_adi: str) -> bool | None:
    """Ag karti sihirli paketle uyandirmaya AYARLI mi?

    None = okunamadi (surucu bu ayari sunmuyor olabilir). Bunu "kapali" gibi
    gostermek kullaniciyi yanlis yonlendirir, o yuzden ayri deger.
    """
    if not kart_adi:
        return None
    ham = _powershell(
        f"(Get-NetAdapterPowerManagement -Name '{kart_adi}' -ErrorAction SilentlyContinue)"
        ".WakeOnMagicPacket")
    deger = ham.strip().lower()
    if deger in ("enabled", "1", "true"):
        return True
    if deger in ("disabled", "0", "false"):
        return False
    return None


def uyandirmaya_hazir() -> bool:
    """Windows'un "bu aygit bilgisayari uyandirabilir" listesinde ag karti var mi?"""
    ham = _powershell("powercfg -devicequery wake_armed")
    return bool(re.search(r"(ethernet|wi-?fi|wireless|network|realtek|intel\(r\) )",
                          ham, re.I))


def durum() -> dict:
    """Ayarlar penceresinin gosterdigi butun bilgi tek cagrida."""
    kart = aktif_kart()
    return {
        "kart": kart["ad"],
        "mac": kart["mac"],
        "aciklama": kart["aciklama"],
        "wol": wol_acik_mi(kart["ad"]),
        "hazir": uyandirmaya_hazir(),
    }


def wol_gonder(mac: str, yayin: str = "255.255.255.255", port: int = 9) -> bool:
    """Sihirli paket gonder (agdaki BASKA bir makineyi uyandirmak icin).

    Paket: 6 bayt 0xFF + MAC'in 16 kez tekrari. Yayin adresine UDP gider.
    """
    temiz = re.sub(r"[^0-9a-fA-F]", "", mac or "")
    if len(temiz) != 12:
        raise ValueError("MAC adresi 12 onaltilik basamak olmali")
    bayt = bytes.fromhex(temiz)
    paket = b"\xff" * 6 + bayt * 16
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            s.sendto(paket, (yayin, port))
        finally:
            s.close()
    except OSError as exc:
        raise ValueError(f"paket gonderilemedi: {exc}") from exc
    return True
