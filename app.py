"""AfuDM — portable indirme yoneticisi.

Calistirma:  python app.py        (veya AfuDM.bat)
Her sey uygulama klasorunde kalir; sisteme kurulum yapmaz.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import webview  # noqa: E402

from api.server import LocalAPI  # noqa: E402
from core import clipboard, engines, lang, paths  # noqa: E402
from core.manager import Manager  # noqa: E402

# Pencere basligi dile gore secilir (bkz. core/lang.py); ayar okunana kadar bu durur.
WINDOW_TITLE = "AfuDM"


def parse_start_at(text: str) -> float | None:
    """'23:30' veya '2026-09-17 23:30' -> epoch. Bos ise None."""
    text = (text or "").strip()
    if not text:
        return None
    now = time.localtime()
    for fmt, needs_date in (("%Y-%m-%d %H:%M", False), ("%d.%m.%Y %H:%M", False), ("%H:%M", True)):
        try:
            parsed = time.strptime(text, fmt)
        except ValueError:
            continue
        if needs_date:
            stamp = time.mktime(
                (now.tm_year, now.tm_mon, now.tm_mday, parsed.tm_hour, parsed.tm_min,
                 0, 0, 0, -1)
            )
            if stamp <= time.time():
                stamp += 86400  # gecmisse yarina al
            return stamp
        return time.mktime(parsed)
    raise ValueError(lang.t("err.timeFormat"))


def open_in_explorer(target: str) -> None:
    path = Path(target)
    if not path.exists():
        return
    if path.is_dir():
        os.startfile(str(path))  # noqa: S606 — Windows dosya gezgini
    else:
        subprocess.Popen(["explorer", "/select,", str(path)])


class Api:
    """Arayuzun cagirdigi kopru. Her metot JSON'a cevrilebilir sozluk doner."""

    def __init__(self, manager: Manager, local_api: LocalAPI) -> None:
        self.manager = manager
        self.local_api = local_api
        self.window: webview.Window | None = None
        self._baslik_dili: str | None = None
        # Motor indirmeleri: {"ffmpeg": {"durum": "iniyor", "inen": .., "toplam": ..}}
        self._motor_ilerleme: dict[str, dict] = {}

    # --- durum ------------------------------------------------------------
    def snapshot(self) -> dict:
        snap = self.manager.snapshot()
        self._basligi_esitle(snap.get("lang"))
        return snap

    def _basligi_esitle(self, dil: str | None) -> None:
        """Pencere basligini gecerli dile esitler.

        Arayuzdeki metinleri app.js ceviriyor ama pencere basligi Windows'un
        elinde — dil nereden degisirse degissin (Ayarlar penceresi, yerel API
        veya Windows dili) her turda burada esitlenir."""
        if not dil or dil == self._baslik_dili or self.window is None:
            return
        try:
            self.window.set_title(lang.t("window.title", dil))
            self._baslik_dili = dil
        except Exception:
            pass

    def motor_durumu(self) -> dict:
        """Hangi motor kurulu, hangisi iniyor — Ayarlar penceresi bunu gosterir."""
        return {
            "ok": True,
            "motorlar": engines.durum(),
            "ilerleme": dict(self._motor_ilerleme),
        }

    def motor_indir(self, ad: str) -> dict:
        """Istege bagli motoru arka planda indirir; ilerleme motor_durumu()'ndan okunur."""
        if self._motor_ilerleme.get(ad, {}).get("durum") == "iniyor":
            return {"ok": True, "zaten": True}

        def is_parcasi() -> None:
            self._motor_ilerleme[ad] = {"durum": "iniyor", "inen": 0, "toplam": 0}

            def ilerleme(inen: int, toplam: int) -> None:
                self._motor_ilerleme[ad] = {
                    "durum": "iniyor", "inen": inen, "toplam": toplam,
                }

            try:
                sonuc = engines.indir(ad, ilerleme=ilerleme)
                self._motor_ilerleme[ad] = {"durum": "bitti", "boyut_mb": sonuc["boyut_mb"]}
            except Exception as exc:
                self._motor_ilerleme[ad] = {"durum": "hata", "hata": str(exc)[:200]}

        threading.Thread(target=is_parcasi, daemon=True).start()
        return {"ok": True}

    def api_info(self) -> dict:
        return {"ok": True, "port": self.local_api.port, "token": self.local_api.token}

    def peers(self, gid: str) -> dict:
        return {"ok": True, "peers": self.manager.peers(gid)}

    def start_pairing(self, seconds: int = 120) -> dict:
        """Uzanti anahtari elle yapistirmadan alabilsin; pencere kisa surelidir."""
        self.local_api.open_pairing(float(seconds))
        return {"ok": True, "seconds": int(seconds), "port": self.local_api.port}

    # --- ekleme -----------------------------------------------------------
    def add_links(self, payload: dict) -> dict:
        urls = payload.get("urls") or []
        try:
            start_after = parse_start_at(payload.get("start_at", ""))
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        added, scheduled, failed = 0, 0, []
        for url in urls:
            try:
                self.manager.add(
                    url,
                    dest_dir=payload.get("dest_dir") or None,
                    quality=payload.get("quality") or None,
                    audio_only=bool(payload.get("audio_only")),
                    playlist=bool(payload.get("playlist")),
                    start_after=start_after,
                )
                if start_after:
                    scheduled += 1
                else:
                    added += 1
            except Exception as exc:
                failed.append(f"{url[:48]}: {exc}"[:180])
        if not added and not scheduled and failed:
            return {"ok": False, "error": failed[0]}
        return {"ok": True, "added": added, "scheduled": scheduled, "failed": failed}

    # --- kontrol ----------------------------------------------------------
    def control(self, action: str, gid: str, delete_files: bool = False) -> dict:
        try:
            if action == "pause":
                self.manager.pause(gid)
            elif action == "resume":
                self.manager.resume(gid)
            elif action == "remove":
                self.manager.remove(gid, delete_files)
            elif action == "pause_all":
                self.manager.pause_all()
            elif action == "resume_all":
                self.manager.resume_all()
            else:
                return {"ok": False, "error": lang.t("err.unknownAction", str(self.manager.store.get("language", "auto")))}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:300]}
        return {"ok": True}

    def retry(self, row_id: int) -> dict:
        try:
            return {"ok": True, **self.manager.retry(int(row_id))}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:300]}

    def clear_finished(self) -> dict:
        return {"ok": True, "removed": self.manager.store.clear_finished()}

    # --- ayarlar ----------------------------------------------------------
    def settings_save(self, payload: dict) -> dict:
        try:
            ayarlar = self.manager.update_settings(payload)
            return {"ok": True, "settings": ayarlar}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:300]}

    # --- klasor -----------------------------------------------------------
    def open_download_dir(self) -> dict:
        open_in_explorer(self.manager.current_download_dir())
        return {"ok": True}

    def open_item_folder(self, gid: str) -> dict:
        for item in self.manager.snapshot()["items"]:
            if item["gid"] == gid:
                folder = item.get("dir") or self.manager.current_download_dir()
                name = item.get("filename") or ""
                open_in_explorer(str(Path(folder) / name) if name else folder)
                return {"ok": True}
        return {"ok": False, "error": lang.t("err.notFound", str(self.manager.store.get("language", "auto")))}

    def probe(self, url: str) -> dict:
        try:
            return {"ok": True, "info": self.manager.probe_video(url)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:300]}


def build_tray(window, manager: Manager) -> None:
    """Sistem tepsisi simgesi. pystray yoksa sessizce atlanir."""
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        return

    image = Image.new("RGBA", (64, 64), (20, 24, 31, 255))
    draw = ImageDraw.Draw(image)
    draw.polygon([(32, 46), (18, 28), (46, 28)], fill=(91, 157, 255, 255))
    draw.rectangle([26, 12, 38, 28], fill=(91, 157, 255, 255))
    draw.rectangle([14, 52, 50, 56], fill=(167, 139, 250, 255))

    def show(_icon=None, _item=None) -> None:
        try:
            window.show()
        except Exception:
            pass

    def hide(_icon=None, _item=None) -> None:
        try:
            window.hide()
        except Exception:
            pass

    def quit_app(icon=None, _item=None) -> None:
        if icon:
            icon.stop()
        try:
            window.destroy()
        except Exception:
            os._exit(0)

    def yazi(anahtar):
        # pystray metin olarak fonksiyon kabul eder: menu her acildiginda
        # yeniden okunur, boylece dil ayari degisince tepsi de guncellenir.
        return lambda _item: lang.t(anahtar, str(manager.store.get("language", "auto")))

    menu = pystray.Menu(
        pystray.MenuItem(yazi("tray.show"), show, default=True),
        pystray.MenuItem(yazi("tray.hide"), hide),
        pystray.MenuItem(yazi("tray.pauseAll"), lambda i, t: manager.pause_all()),
        pystray.MenuItem(yazi("tray.resumeAll"), lambda i, t: manager.resume_all()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(yazi("tray.quit"), quit_app),
    )
    icon = pystray.Icon("AfuDM", image, "AfuDM", menu)
    threading.Thread(target=icon.run, daemon=True).start()


def main() -> int:
    paths.ensure_dirs()
    if not paths.ARIA2C.exists():
        print(f"HATA: motor bulunamadi -> {paths.ARIA2C}")
        return 2

    manager = Manager()
    try:
        manager.start()
    except Exception as exc:
        print(f"HATA: aria2 baslatilamadi: {exc}")
        return 3

    local_api = LocalAPI(manager, port=int(manager.store.get("api_port", 6811)))
    try:
        port = local_api.start()
        manager.store.set("api_port", port)
    except Exception as exc:
        print(f"UYARI: yerel API acilamadi: {exc}")

    api = Api(manager, local_api)
    window = webview.create_window(
        lang.t("window.title", str(manager.store.get("language", "auto"))),
        str(paths.UI / "index.html"),
        js_api=api,
        width=1180,
        height=760,
        min_size=(880, 560),
        background_color="#14181F",
        text_select=False,
    )
    api.window = window

    watcher = clipboard.ClipboardWatcher(
        on_link=lambda url: window.evaluate_js(
            "window.afudmClipboard(%s)" % json.dumps(url)
        ),
        is_enabled=lambda: bool(manager.store.get("clipboard_watch")),
        get_extensions=lambda: str(manager.store.get("clipboard_exts", "")),
    )

    def on_start() -> None:
        watcher.prime()
        watcher.start()
        build_tray(window, manager)

    try:
        webview.start(on_start, debug=bool(os.environ.get("AFUDM_DEBUG")))
    finally:
        watcher.stop()
        local_api.stop()
        manager.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
