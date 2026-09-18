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

import urllib.error  # noqa: E402
import urllib.request  # noqa: E402

import webview  # noqa: E402

from api.server import LocalAPI  # noqa: E402

VARSAYILAN_API_PORT = 6811   # uzantinin da ilk denedigi port
from core import (baslangic, chrome_kurulum, clipboard, engines, guc, iliskilendir,  # noqa: E402
                  kaydet, lang, paths, pencere)
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
        # Alt cizgili: pywebview js_api'nin ozelliklerini DOLASIR; `window.native`
        # (.NET formu) sonsuz derinlige inip gunlugu "Empty.Empty..." ile dolduruyordu.
        self._window: webview.Window | None = None
        self._baslik_dili: str | None = None
        # Motor indirmeleri: {"ffmpeg": {"durum": "iniyor", "inen": .., "toplam": ..}}
        self._motor_ilerleme: dict[str, dict] = {}
        self._ozel_baslik = False  # Windows basligi kaldirildi mi (core/pencere.py)
        self._chrome = chrome_kurulum.OtomatikEkleme()
        self._tepsi = None              # pystray simgesi (bkz. build_tray)
        self._bekleyenler = kaydet.Bekleyenler()
        self._chrome_baslangic = 0.0

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
        if not dil or dil == self._baslik_dili or self._window is None:
            return
        try:
            self._window.set_title(lang.t("window.title", dil))
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
    # --- kaydetme penceresi (bkz. core/kaydet.py) ------------------------
    def _hedef_klasor(self, secilen: str, url: str, kind: str, kategori: str) -> str | None:
        if secilen:
            return secilen
        if not self.manager.store.get("kategori_klasorleri"):
            return None
        kategori = kategori or kaydet.kategori_tahmin(url, kind)
        return kaydet.kategori_klasoru(self.manager.current_download_dir(), kategori)

    def kaydet_bilgi(self, url: str) -> dict:
        url = (url or "").strip()
        kind = self.manager.detect_kind(url) if url else ""
        kategori = kaydet.kategori_tahmin(url, kind) if url else "genel"
        ana = self.manager.current_download_dir()
        return {
            "ok": True,
            "kind": kind,
            "kategori": kategori,
            "dosya_adi": self.manager.guess_name(url) if url and kind == "http" else "",
            "ana": ana,
            "kategori_klasorleri": bool(self.manager.store.get("kategori_klasorleri")),
            "klasorler": {k: kaydet.kategori_klasoru(ana, k) for k in kaydet.KATEGORI_KLASORU},
        }

    def klasor_kisayollar(self) -> dict:
        return {"ok": True, "ogeler": kaydet.kisayollar(
            self.manager.current_download_dir(),
            str(self.manager.store.get("ag_konumlari", "")))}

    def ag_konumu_ekle(self, yol: str) -> dict:
        """Modem/NAS paylasimini klasor agacina ekle (once ERISIM dogrulanir)."""
        try:
            temiz = kaydet.ag_konumu_dogrula(yol)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        mevcut = kaydet.ag_konumlari(str(self.manager.store.get("ag_konumlari", "")))
        if temiz not in mevcut:
            mevcut.append(temiz)
        self.manager.store.set("ag_konumlari", "\n".join(mevcut))
        return {"ok": True, "yol": temiz, "sayi": len(mevcut)}

    def ag_konumu_sil(self, yol: str) -> dict:
        mevcut = [y for y in kaydet.ag_konumlari(str(self.manager.store.get("ag_konumlari", "")))
                  if y != (yol or "").strip()]
        self.manager.store.set("ag_konumlari", "\n".join(mevcut))
        return {"ok": True, "sayi": len(mevcut)}

    def klasor_alt(self, yol: str) -> dict:
        try:
            return {"ok": True, "ogeler": kaydet.alt_klasorler(yol)}
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

    def klasor_yeni(self, ust: str, ad: str) -> dict:
        try:
            return {"ok": True, "yol": kaydet.klasor_olustur(ust, ad)}
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc)[:200]}

    def klasor_gozat(self, baslangic: str = "") -> dict:
        if not self._window:
            return {"ok": False}
        secim = self._window.create_file_dialog(
            webview.FOLDER_DIALOG, directory=baslangic or self.manager.current_download_dir())
        return {"ok": True, "yol": secim[0] if secim else ""}

    def tarayicidan_sor(self, istek: dict) -> int:
        """Yerel API (uzanti) cagirir: istegi beklet, pencereyi ac ve one getir."""
        kimlik = self._bekleyenler.ekle(istek)
        if self._window:
            pencere.one_getir(self._window)
            try:
                self._window.evaluate_js("window.afudmBekleyen && window.afudmBekleyen()")
            except Exception:
                pass  # sayfa hazir degil: arayuz tick'te kendisi sorar
        return kimlik

    def bekleyen_listesi(self) -> dict:
        return {"ok": True, "ogeler": self._bekleyenler.ozet()}

    def bekleyen_iptal(self, kimlik: int) -> dict:
        self._bekleyenler.al(kimlik)
        return {"ok": True}

    def bekleyen_onayla(self, kimlik: int, secim: dict) -> dict:
        istek = self._bekleyenler.al(kimlik)
        if not istek:
            return {"ok": False, "error": lang.t("err.notFound", str(self.manager.store.get("language", "auto")))}
        url = istek.get("url") or ""
        kind = istek.get("kind") or self.manager.detect_kind(url)
        try:
            start_after = parse_start_at(secim.get("start_at", ""))
            ad = kaydet.guvenli_dosya_adi(secim.get("filename") or "")
            sonuc = self.manager.add(
                url,
                kind=kind,
                dest_dir=self._hedef_klasor(secim.get("dest_dir") or "", url, kind, secim.get("kategori") or ""),
                quality=secim.get("quality") or istek.get("quality"),
                audio_only=bool(secim.get("audio_only", istek.get("audio_only"))),
                start_after=start_after,
                headers=istek.get("headers") or {},
                filename=(ad or istek.get("filename")) if kind == "http" else None,
                cookies=istek.get("cookies"),
                user_agent=istek.get("user_agent"),
                title=(ad or istek.get("title")) if kind == "video" else istek.get("title"),
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:300]}
        return {"ok": True, **sonuc}

    # --- sistem baglantilari (baslangic, .torrent/magnet) ----------------
    # Ikisi de Windows'a dokunur (Baslangic klasoru / HKCU\Software\Classes):
    # her acilista degil, YALNIZ Ayarlar acilinca sorulur.
    def sistem_durumu(self) -> dict:
        try:
            return {
                "ok": True,
                "baslangic": baslangic.acik_mi(),
                "torrent": iliskilendir.durum(),
            }
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:200]}

    def baslangic_ayarla(self, acik: bool, tepside: bool = True) -> dict:
        try:
            if acik:
                # Kisayol argumani ayarla birlikte degisir (bkz. baslangic.ac)
                baslangic.ac("--tepside" if tepside else "")
            else:
                baslangic.kapat()
        except (OSError, RuntimeError) as exc:
            return {"ok": False, "error": str(exc)[:300]}
        return {"ok": True, "acik": baslangic.acik_mi()}

    def varsayilan_uygulama_ekrani(self) -> dict:
        """Windows'un "Varsayilan uygulamalar" ekranini ac.

        .torrent'in hangi programla acilacagini SADECE kullanici secebilir
        (UserChoice hash korumali); yapabilecegimiz en iyi sey dogru ekrani
        onune getirmek."""
        try:
            os.startfile("ms-settings:defaultapps")      # noqa: S606
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:200]}
        return {"ok": True}

    def torrent_iliskilendir(self, acik: bool) -> dict:
        try:
            iliskilendir.ac() if acik else iliskilendir.kapat()
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:300]}
        return {"ok": True, "durum": iliskilendir.durum()}

    # --- seed penceresi (torrent) ----------------------------------------
    def seed_bilgi(self, gid: str) -> dict:
        return self.manager.seed_bilgi(gid)

    def seed_tazele(self, gid: str) -> dict:
        return self.manager.seed_tazele(gid)

    def seed_tracker_kaydet(self, metin: str) -> dict:
        """Elle eklenen tracker'lari sakla (uygulanmasi tazelemede olur)."""
        from core import trackers as _tr
        temiz = _tr.ayikla(metin)
        self.manager.store.set("ek_trackerlar", "\n".join(temiz))
        return {"ok": True, "sayi": len(temiz), "liste": "\n".join(temiz)}

    # --- telefon arayuzu (ui/mobil.html + LocalAPI) ----------------------
    def telefon_durumu(self) -> dict:
        """Ayarlar penceresi icin: acik mi, adres ne, QR nerede."""
        acik = bool(self.manager.store.get("lan_erisimi"))
        adres = self.local_api.lan_adresi() if acik else ""
        return {
            "ok": True,
            "acik": acik,
            "adres": adres,
            "qr": self._qr_uret(adres) if adres else "",
            "port": self.local_api.port,
        }

    @staticmethod
    def _qr_uret(metin: str) -> str:
        """Adresi QR olarak dondur (data URI). qrcode yoksa sessizce bos doner:
        arayuz o zaman yalniz adresi gosterir, ozellik kaybolmaz."""
        try:
            import base64
            from io import BytesIO

            import qrcode
        except ImportError:
            return ""
        try:
            kod = qrcode.QRCode(box_size=6, border=2)
            kod.add_data(metin)
            kod.make(fit=True)
            resim = kod.make_image(fill_color="#0f131a", back_color="#e6eaf0")
            tampon = BytesIO()
            resim.save(tampon, format="PNG")
            return "data:image/png;base64," + base64.b64encode(tampon.getvalue()).decode()
        except Exception:
            return ""

    def telefon_ayarla(self, acik: bool) -> dict:
        """Yerel agi ac/kapat ve sunucuyu YENIDEN baslat.

        Baglanacak adres soket acilirken seciliyor; ayarin hemen gecerli olmasi
        icin sunucu yeniden kuruluyor (yeniden baslatma beklenmesin).
        """
        self.manager.store.set("lan_erisimi", bool(acik))
        try:
            self.local_api.stop()
            self.local_api.lan = bool(acik)
            port = self.local_api.start()
            self.manager.store.set("api_port", port)
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:200]}
        return self.telefon_durumu()

    # --- uyku / telefondan uyandirma (core/guc.py) -----------------------
    def guc_durumu(self) -> dict:
        """Ayarlar icin: ag kartinin MAC'i ve uyandirmaya hazir olup olmadigi."""
        try:
            return {"ok": True, **guc.durum()}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:200]}

    def simdi_uyu(self) -> dict:
        """Kullanici "simdi uyut" derse (deneme icin)."""
        return {"ok": bool(guc.uyut())}

    def add_links(self, payload: dict) -> dict:
        urls = payload.get("urls") or []
        try:
            start_after = parse_start_at(payload.get("start_at", ""))
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        added, scheduled, failed = 0, 0, []
        tek_ad = kaydet.guvenli_dosya_adi(payload.get("filename") or "") if len(urls) == 1 else ""
        for url in urls:
            try:
                kind = self.manager.detect_kind(url)
                self.manager.add(
                    url,
                    dest_dir=self._hedef_klasor(payload.get("dest_dir") or "", url, kind,
                                                payload.get("kategori") or ""),
                    filename=tek_ad if tek_ad and kind == "http" else None,
                    title=tek_ad if tek_ad and kind == "video" else None,
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

    # --- ozel baslik cubugu (bkz. core/pencere.py) ------------------------
    def pencere_kucult(self) -> dict:
        if self._window:
            self._window.minimize()
        return {"ok": True}

    def pencere_buyut(self) -> dict:
        if self._window:
            if pencere.buyutulmus_mu(self._window):
                self._window.restore()
            else:
                self._window.maximize()
        return self.pencere_durumu()

    def pencere_kapat(self) -> dict:
        if self._window:
            self._window.destroy()
        return {"ok": True}

    def pencere_durumu(self) -> dict:
        return {
            "ok": True,
            "ozel": self._ozel_baslik,
            "buyuk": bool(self._window and pencere.buyutulmus_mu(self._window)),
        }

    def pencere_kenar(self, kenar: str) -> dict:
        return {"ok": bool(self._window and pencere.kenardan_boyutla(self._window, kenar))}

    # --- Chrome'a uzanti ekleme (bkz. core/chrome_kurulum.py) ---------------
    def chrome_durum(self) -> dict:
        return {
            "ok": True,
            "chrome": bool(chrome_kurulum.chrome_yolu()),
            "klasor": str(chrome_kurulum.uzanti_klasoru()),
            "adres": "chrome://extensions/",
        }

    def chrome_hazirla(self) -> dict:
        """Pencere acildi: eslestirmeyi 10 dk ac ki ELLE kurulumda da uzanti
        kendiliginden baglansin; "baglandi" bu andan sonraki eslesmeye bakar."""
        self._chrome_baslangic = time.time()
        self.local_api.open_pairing(600.0)
        return self.chrome_durum()

    def chrome_otomatik(self) -> dict:
        self._chrome_baslangic = self._chrome_baslangic or time.time()
        # Eslestirme penceresi kurulumdan ONCE: uzanti kurulur kurulmaz baglanir.
        baslatildi = self._chrome.baslat(once=lambda: self.local_api.open_pairing(600.0))
        return {"ok": True, "baslatildi": baslatildi}

    def chrome_ilerleme(self) -> dict:
        durum = self._chrome.durum()
        durum["baglandi"] = self.local_api.son_eslesme >= self._chrome_baslangic > 0
        return {"ok": True, **durum}

    def chrome_kopyala(self, ne: str) -> dict:
        metin = "chrome://extensions/" if ne == "adres" else str(chrome_kurulum.uzanti_klasoru())
        return {"ok": chrome_kurulum.panoya_kopyala(metin)}

    def chrome_ac(self) -> dict:
        # chrome:// adresi komut satirindan ACILMAZ: bos sekme acilir, adres kopyalanir.
        chrome_kurulum.panoya_kopyala("chrome://extensions/")
        return {"ok": bool(chrome_kurulum.sayfayi_ac())}

    def probe(self, url: str) -> dict:
        try:
            return {"ok": True, "info": self.manager.probe_video(url)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:300]}


# --- komut satirindan gelen link (.torrent cift tiklama, magnet:) -----------
def argvden_link(argv: list[str]) -> str:
    """Gezgin/tarayici "AfuDM.exe <yol|magnet>" diye cagirir; ilk anlamli baglanti."""
    for arg in argv[1:]:
        deger = arg.strip().strip('"')
        if not deger or deger.startswith("-"):
            continue
        if deger.startswith(("magnet:", "http://", "https://", "ftp://")):
            return deger
        if deger.lower().endswith(".torrent") and Path(deger).exists():
            return str(Path(deger).resolve())
    return ""


def calisan_ornege_yolla(link: str = "") -> bool:
    """AfuDM zaten aciksa isi ONA ver ve IKINCI PENCERE ACMA.

    Link varsa eklenir; link yoksa (kullanici kisayola tekrar tikladi) acik
    pencere one getirilir. Iki ornek ayni veritabanina ve ayni motora
    asilmasin diye: her ikinci acilis buradan doner.
    """
    try:
        bilgi = json.loads((paths.DATA / "api_endpoint.json").read_text("utf-8"))
        port, token = int(bilgi["port"]), str(bilgi["token"])
    except (OSError, ValueError, KeyError):
        return False
    basliklar = {"Content-Type": "application/json", "X-AfuDM-Token": token}
    try:
        if link:
            govde = json.dumps({"url": link, "interactive": True}).encode("utf-8")
            istek = urllib.request.Request(
                f"http://127.0.0.1:{port}/add", data=govde, headers=basliklar)
            with urllib.request.urlopen(istek, timeout=3) as yanit:
                if json.loads(yanit.read().decode("utf-8")).get("ok") is not True:
                    return False
        # Pencereyi one getir: linksiz acilista tek is budur.
        istek = urllib.request.Request(
            f"http://127.0.0.1:{port}/show", headers={"X-AfuDM-Token": token})
        with urllib.request.urlopen(istek, timeout=3) as yanit:
            return json.loads(yanit.read().decode("utf-8")).get("ok") is True
    except (urllib.error.URLError, OSError, ValueError):
        return False       # acik degil (ya da baska bir program o portta)


def build_tray(window, manager: Manager):
    """Sistem tepsisi simgesi; kurulan simgeyi dondurur (kurulamazsa None).

    Donen deger onemli: simge YOKSA "kucultunce tepsiye in" davranisi
    kapatilir, yoksa pencere gizlenir ve uygulamaya ulasilamaz."""
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError as exc:
        # Paketlenmis exe'de konsol YOK: sebep veritabanina da yazilir,
        # yoksa "simge neden gorunmuyor" disaridan anlasilmiyor.
        manager.store.log("warn", f"tepsi simgesi kurulamadi (import): {exc}")
        return None

    image = Image.new("RGBA", (64, 64), (20, 24, 31, 255))
    draw = ImageDraw.Draw(image)
    draw.polygon([(32, 46), (18, 28), (46, 28)], fill=(91, 157, 255, 255))
    draw.rectangle([26, 12, 38, 28], fill=(91, 157, 255, 255))
    draw.rectangle([14, 52, 50, 56], fill=(167, 139, 250, 255))

    def show(_icon=None, _item=None) -> None:
        # Gizli VE simge durumunda olabilir: one_getir ikisini de duzeltir.
        try:
            pencere.one_getir(window)
        except Exception:
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

    def calistir() -> None:
        try:
            icon.run()
        except Exception as exc:                 # simge kurulamazsa sebebi kalsin
            manager.store.log("warn", f"tepsi simgesi calismadi: {exc!r}")

    threading.Thread(target=calistir, daemon=True).start()
    return icon


def main() -> int:
    paths.ensure_dirs()
    link = argvden_link(sys.argv)
    # Tepside basla: Baslangic kisayolu bu bayrakla cagirir (bkz. core/baslangic.py)
    tepside_basla = "--tepside" in sys.argv
    if calisan_ornege_yolla(link):
        return 0                      # zaten acik: is ona verildi, ikinci pencere yok
    if not paths.ARIA2C.exists():
        print(f"HATA: motor bulunamadi -> {paths.ARIA2C}")
        return 2

    manager = Manager()
    try:
        manager.start()
    except Exception as exc:
        print(f"HATA: aria2 baslatilamadi: {exc}")
        return 3

    # HER ACILISTA 6811'den basla. Onceki calismada port dolu oldugu icin
    # 6812'ye dusulmusse bu DEGER KAYDEDILIP kalici olurdu: uygulama hep
    # 6812'de acilir, uzanti ise 6811'i denerdi ve "AfuDM kapali" derdi.
    # Kayit artik yalnizca "su an hangi port" bilgisi; baslangic noktasi degil.
    local_api = LocalAPI(manager, port=VARSAYILAN_API_PORT,
                         lan=bool(manager.store.get("lan_erisimi")))
    try:
        port = local_api.start()
        manager.store.set("api_port", port)
    except Exception as exc:
        print(f"UYARI: yerel API acilamadi: {exc}")

    api = Api(manager, local_api)
    pencere.webview2_hazirligini_yama()  # CSS app-region: drag, ilk sayfadan once
    window = webview.create_window(
        lang.t("window.title", str(manager.store.get("language", "auto"))),
        str(paths.UI / "index.html"),
        js_api=api,
        width=1180,
        height=760,
        min_size=(880, 560),
        background_color="#14181F",
        text_select=False,
        hidden=tepside_basla,
    )
    api._window = window
    from api.server import _Handler as _ApiHandler  # noqa: E402
    _ApiHandler.on_ask = api.tarayicidan_sor
    _ApiHandler.on_show = lambda: pencere.one_getir(window)

    def tepsi_bildirimi() -> None:
        # Windows 11 YENI bir uygulamanin tepsi simgesini varsayilan olarak
        # "gizli simgeler" (^) altina koyar ve bu disaridan degistirilemez.
        # Kullanici pencerenin nereye gittigini bilsin diye BIR KEZ soylenir.
        if manager.store.get("tepsi_bildirimi_yapildi"):
            return
        manager.store.set("tepsi_bildirimi_yapildi", True)
        simge = getattr(api, "_tepsi", None)
        if simge is None:
            return
        try:
            simge.notify(
                lang.t("tray.hidden", str(manager.store.get("language", "auto"))), "AfuDM"
            )
        except Exception:
            pass

    def baslik_hazir() -> None:
        try:
            pencere.kucultunce_gizle(
                window,
                # Tepsi simgesi kurulamadiysa GIZLEME: pencereye donus yolu kalmaz.
                lambda: bool(manager.store.get("tepsiye_kucult"))
                and getattr(api, "_tepsi", None) is not None,
                tepsi_bildirimi,
            )
        except Exception as exc:
            print(f"UYARI: tepsiye kucultme kurulamadi: {exc}")
        try:
            ozel = pencere.basligi_kaldir(window)
        except Exception as exc:  # kaldirilamazsa Windows basligi kalir, uygulama calisir
            print(f"UYARI: ozel baslik kurulamadi: {exc}")
            ozel = False
        api._ozel_baslik = ozel

    def sayfa_hazir() -> None:
        # Pencere gosterildiginde sayfa henuz yuklenmemis olabilir (evaluate_js
        # o anda istisna firlatir); dugmeleri sayfa yuklenince goster.
        try:
            window.evaluate_js("window.afudmPencere && window.afudmPencere()")
        except Exception:
            pass
        # Cift tiklanan .torrent / magnet: kaydetme penceresinde acilsin
        if link:
            api.tarayicidan_sor({"url": link})

    window.events.shown += baslik_hazir
    window.events.loaded += sayfa_hazir

    watcher = clipboard.ClipboardWatcher(
        on_link=lambda url: window.evaluate_js(
            "window.afudmClipboard(%s)" % json.dumps(url)
        ),
        is_enabled=lambda: bool(manager.store.get("clipboard_watch")),
        get_extensions=lambda: str(manager.store.get("clipboard_exts", "")),
    )

    def on_start() -> None:
        # ONCE tepsi: pano izleyicisi patlarsa simge de kurulmadan kalirdi.
        api._tepsi = build_tray(window, manager)
        if tepside_basla and api._tepsi is None:
            # Simge yoksa gizli baslamak uygulamayi erisilmez yapardi.
            manager.store.log("warn", "tepsi simgesi yok: pencere gosteriliyor")
            window.show()
        try:
            watcher.prime()
            watcher.start()
        except Exception as exc:
            print(f"UYARI: pano izleyici baslatilamadi: {exc}")

    try:
        webview.start(on_start, debug=bool(os.environ.get("AFUDM_DEBUG")))
    finally:
        watcher.stop()
        local_api.stop()
        manager.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
