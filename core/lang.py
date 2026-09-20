"""Dil secimi ve Python tarafindaki metinler (tepsi menusu, bildirim, pencere).

Ayar `language`: "auto" | "tr" | "en".
  auto -> Windows arayuz dili Turkce ise tr, degilse en.

Arayuzun kendi sozlugu `ui/i18n.js` icinde; buradaki sozluk YALNIZCA Python'un
bastigi metinler icindir (pencere basligi, tepsi menusu, Telegram bildirimi).
Iki taraf da ayni ayardan beslenir: karar burada verilir, arayuze `snapshot`
icindeki `lang` alaniyla gider.
"""
from __future__ import annotations

import ctypes
import locale

DESTEKLENEN = ("tr", "en")

_TEXTS = {
    "tr": {
        "window.title": "AfuDM — indirme yöneticisi",
        "tray.show": "Pencereyi göster",
        "tray.hidden": (
            "AfuDM tepside çalışmaya devam ediyor. Simge görev çubuğundaki "
            "^ okunun altında; oradan sürükleyip görev çubuğuna sabitleyebilirsin."
        ),
        "tray.hide": "Pencereyi gizle",
        "tray.pauseAll": "Tümünü duraklat",
        "tray.resumeAll": "Tümünü sürdür",
        "tray.quit": "Çıkış",
        "notify.done": "✅ AfuDM indirme tamamlandı",
        "err.timeFormat": "saat formatı anlaşılmadı (örnek: 23:30)",
        "err.unknownAction": "bilinmeyen eylem",
        "err.notFound": "kayıt bulunamadı",
        "err.needFfmpeg": (
            "Bu video sesi ve görüntüyü ayrı gönderiyor; birleştirmek için ffmpeg "
            "gerekiyor. Ayarlar'dan gelişmiş video desteğini indir."
        ),
        "err.needFfmpegAudio": (
            "mp3'e çevirmek için ffmpeg gerekiyor. Ayarlar'dan gelişmiş video "
            "desteğini indir; o zamana kadar ses kaynaktaki biçimiyle iner."
        ),
        "note.ffmpegEmbedSkipped": (
            "ffmpeg bulunamadigi icin istenen video gomme islemleri uygulanamadi."
        ),
        # --- v2.1 Headless Server: tek ornek / cakisma ---
        "ornek.zatenAcik": (
            "AfuDM bu klasorde zaten acik — acik pencere one getirildi."
        ),
        "ornek.headlessCalisiyor": (
            "Bu klasorde AfuDM sunucu kipinde calisiyor. Masaustu penceresi "
            "acilmadi; panel icin: afuadm server status"
        ),
        "ornek.masaustuAcik": (
            "Masaustu AfuDM acik. Sunucu ayri bir surec olarak acilamaz; "
            "sunucuyu AfuDM penceresindeki Sunucu sekmesinden ac."
        ),
        "ornek.sunucuZatenAcik": (
            "AfuDM sunucusu bu klasorde zaten calisiyor. Durum icin: "
            "afuadm server status"
        ),
        "srv.started": "Sunucu acildi",
        "srv.stopped": "Sunucu kapatildi",
        "srv.notRunning": "Sunucu calismiyor",
    },
    "en": {
        "window.title": "AfuDM — download manager",
        "tray.show": "Show window",
        "tray.hidden": (
            "AfuDM keeps running in the tray. The icon sits under the ^ arrow on "
            "the taskbar; drag it onto the taskbar to keep it visible."
        ),
        "tray.hide": "Hide window",
        "tray.pauseAll": "Pause all",
        "tray.resumeAll": "Resume all",
        "tray.quit": "Quit",
        "notify.done": "✅ AfuDM download finished",
        "err.timeFormat": "could not read the time (example: 23:30)",
        "err.unknownAction": "unknown action",
        "err.notFound": "entry not found",
        "err.needFfmpeg": (
            "This video sends audio and video separately; ffmpeg is needed to join "
            "them. Download the advanced video support from Settings."
        ),
        "err.needFfmpegAudio": (
            "ffmpeg is needed to convert to mp3. Download the advanced video support "
            "from Settings; until then the audio is saved in its original format."
        ),
        "note.ffmpegEmbedSkipped": (
            "ffmpeg was not found, so the requested video embedding operations were skipped."
        ),
        # --- v2.1 Headless Server: single instance / conflict ---
        "ornek.zatenAcik": (
            "AfuDM is already open in this folder — the existing window was "
            "brought to front."
        ),
        "ornek.headlessCalisiyor": (
            "AfuDM is running in server mode in this folder. The desktop window "
            "was not opened; for the panel: afuadm server status"
        ),
        "ornek.masaustuAcik": (
            "Desktop AfuDM is open. The server cannot start as a separate "
            "process; start it from the Server tab inside AfuDM."
        ),
        "ornek.sunucuZatenAcik": (
            "The AfuDM server is already running in this folder. For status: "
            "afuadm server status"
        ),
        "srv.started": "Server started",
        "srv.stopped": "Server stopped",
        "srv.notRunning": "Server is not running",
    },
}


def system_language() -> str:
    """Windows arayuz dili Turkce mi? Okunamazsa Ingilizce'ye duser."""
    try:
        lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        # 0x1F = Turkce (birincil dil kimligi, alt dilden bagimsiz)
        if (lcid & 0x3FF) == 0x1F:
            return "tr"
        return "en"
    except Exception:
        try:
            code = (locale.getdefaultlocale()[0] or "").lower()
        except Exception:
            code = ""
        return "tr" if code.startswith("tr") else "en"


def resolve(setting: str | None) -> str:
    """Ayardaki degeri gercek dil koduna cevirir."""
    value = (setting or "auto").strip().lower()
    if value in DESTEKLENEN:
        return value
    return system_language()


def t(key: str, setting: str | None = None) -> str:
    """Ayara gore metni verir. Anahtar yoksa anahtarin kendisi doner."""
    table = _TEXTS.get(resolve(setting), _TEXTS["en"])
    return table.get(key, _TEXTS["tr"].get(key, key))
