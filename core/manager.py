"""AfuDM yonetici: her sey buradan gecer.

Sorumluluklari:
  - Link turunu ayirt et (http / video / torrent / magnet) ve dogru motora yonlendir
  - aria2 indirmeleri + yt-dlp video isleri icin TEK birlesik durum goruntusu ver
  - duraklat / devam / iptal, hiz siniri, eszamanlilik
  - zamanlanmis baslatma, gunluk tracker guncelleme, bitince bildirim/kapatma
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from video import ytdlp

from .dosya_adi import resolve_filename

from . import cerez, eklenti, lang, models, paths, trackers, rules, settings_validation
from .automation import AutomationWorker
from . import proxy as P
from .daemon import Aria2Daemon
from .db import Store
from .windows_integration import WindowsIntegration
from .hata import BadSource, KayitYok, RenewDesteklenmez
from .rpc import Aria2Error

POLL_INTERVAL = 0.5
TRACKER_CHECK_INTERVAL = 3600.0

# Hiz profilleri (FDM'nin "Snail Mode" esinlenmesi): TBK sinirini CANLI degistirir.
#   turbo  -> sinirsiz (0)
#   normal -> kullanicinin max_speed_kb ayari gecerli
#   snail  -> snail_speed_kb (varsayilan 100 KB/s — oyun/toplantida interneti rahatlatir)
HIZ_PROFILLERI = ("snail", "normal", "turbo")


class AyarGecersiz(ValueError):
    """UI koprusune alan bazli i18n hatalarini tasir; gizli deger tasimaz."""
    def __init__(self, hatalar: list[dict]) -> None:
        super().__init__("settings_invalid")
        self.hatalar = hatalar


class TorrentDosyaListesi(list[dict]):
    """Dosya listesi; magnet ustverisi gelmediyse UI'nin ayirt edecegi durum."""

    def __init__(self, *args, hazir_degil: bool = False, neden: str = "", gid: str = "") -> None:
        super().__init__(*args)
        self.hazir_degil = hazir_degil
        self.neden = neden
        self.gid = gid



def human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num) < 1024:
            return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} B"
        num /= 1024
    return f"{num:.1f} PB"


class Manager:
    def __init__(self) -> None:
        paths.ensure_dirs()
        self.store = Store()
        self._recover_orphan_video_jobs()
        try:
            self.windows = WindowsIntegration(self.store)
        except Exception:
            self.windows = None
        download_dir = self.store.get("download_dir") or str(paths.default_download_dir())
        Path(download_dir).mkdir(parents=True, exist_ok=True)
        self.daemon = Aria2Daemon(download_dir=download_dir)
        self.rpc = self.daemon.rpc
        self.video_jobs: dict[str, ytdlp.VideoJob] = {}
        self._video_seq = self.store.max_video_seq()
        self._lock = threading.RLock()
        self._poller: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_tracker_check = 0.0
        self._known_complete: set[str] = set()
        self._removed_gids: set[str] = set()
        self._removed_hashes: set[str] = set()
        self.last_error: str = ""
        # Oturum cerezleri: kayit kimligi -> cerezler. BILEREK veritabaninda degil
        # (bkz. core/cerez.py); is bitince/silinince birakilir.
        self._cerezler: dict[int, list[dict]] = {}
        self.automation = AutomationWorker(self.store, self.notify_telegram)
        # v2.0 Plugin Platform: eklenti servisi TEK kaynak — pywebview koprusu
        # ve HTTP API ayni nesneyi kullanir (ayri durum tutulmaz).
        self.eklentiler = eklenti.EklentiServisi(self.store)
        self.windows_notify = None

    def _recover_orphan_video_jobs(self) -> None:
        """Onceki oturumdan kalmis, artik calisan isi olmayan video kayitlarini duzelt."""
        rows = self.store.list(limit=100_000)
        tamamlananlar = {
            (row.get("source"), row.get("dest_dir"))
            for row in rows
            if row.get("kind") == "video" and row.get("status") == "complete"
        }
        tamamlanan_basliklar = {
            (json.loads(row.get("options") or "{}").get("title"), row.get("dest_dir"))
            for row in rows
            if row.get("kind") == "video"
            and row.get("status") == "complete"
            and json.loads(row.get("options") or "{}").get("title")
        }
        for row in rows:
            if row.get("kind") != "video" or row.get("status") not in ("active", "waiting"):
                continue
            # Tamamlanmis kardesi varsa eski/tekrarlanan is gizlenir; dosyalara dokunulmaz.
            title = json.loads(row.get("options") or "{}").get("title")
            kardes_tamamlandi = (
                (row.get("source"), row.get("dest_dir")) in tamamlananlar
                or (title and (title, row.get("dest_dir")) in tamamlanan_basliklar)
            )
            durum = "removed" if kardes_tamamlandi else "paused"
            self.store.update_by_id(row["id"], status=durum)


    # --- yasam dongusu ----------------------------------------------------
    def start(self) -> None:
        cerez.artiklari_temizle()
        try:
            self.rpc = self.daemon.start()
        except Exception as exc:
            self.last_error = f"aria2c baslatilamadi: {exc}"
            self.store.log("warn", self.last_error)
            self.rpc = self.daemon.rpc
        self.apply_settings()
        self.automation.start()
        if self.store.get("auto_update_trackers"):
            threading.Thread(target=self._refresh_trackers, daemon=True).start()
        self._poller = threading.Thread(target=self._poll_loop, daemon=True)
        self._poller.start()
        # Etkin eklentiler AYRI SUREClerde acilir; biri patlasa da buraya
        # dusmez — servis her eklentinin hatasini kendi kaydina yazar.
        threading.Thread(target=self.eklentiler.basla, daemon=True).start()
        self.store.log("info", "AfuDM basladi")

    def stop(self) -> None:
        self._stop.set()
        self.automation.stop()
        for job in list(self.video_jobs.values()):
            if job.status == "active":
                job.stop()
        try:
            self.eklentiler.kapat()
        except Exception:
            pass
        self.daemon.stop()
        self.store.log("info", "AfuDM kapandi")

    def _refresh_trackers(self, force: bool = False) -> None:
        try:
            count = trackers.apply_to_aria2(
                self.rpc, force=force, ek=str(self.store.get("ek_trackerlar", "")),
                canli=str(self.store.get("canli_trackerlar", "")))
            if count:
                self.store.log("info", f"{count} guncel tracker uygulandi")
        except Exception as exc:  # aglar kopabilir, uygulamayi dusurmesin
            self.store.log("warn", f"tracker guncellenemedi: {exc}")

    # --- ayarlar ----------------------------------------------------------
    def hiz_limiti_kb(self, settings: dict | None = None) -> int:
        """Gecerli profil icin toplam indirme hiz siniri (KB/s; 0 = sinirsiz)."""
        settings = settings or self.store.all_settings()
        profil = str(settings.get("hiz_profili") or "normal").strip().lower()
        if profil == "turbo":
            return 0
        if profil == "snail":
            return max(int(settings.get("snail_speed_kb") or 100), 0)
        return max(int(settings.get("max_speed_kb") or 0), 0)

    def apply_settings(self) -> None:
        settings = self.store.all_settings()
        limit = self.hiz_limiti_kb(settings)
        options = {
            "max-concurrent-downloads": str(int(settings.get("max_concurrent", 5))),
            "split": str(int(settings.get("split", 64))),
            "max-connection-per-server": str(int(settings.get("max_conn_per_server", 16))),
            "max-overall-download-limit": f"{limit}K" if limit > 0 else "0",
            "seed-ratio": str(float(settings.get("seed_ratio", 1.0))),
        }
        try:
            self.rpc.change_global_option(options)
        except Aria2Error as exc:
            self.last_error = str(exc)

    def set_mode(self, ad: str) -> dict:
        """Hiz profilini CANLI degistir: `afuadm mode snail|normal|turbo`.

        aria2 changeGlobalOption max-overall-download-limit'i calisan
        indirmeleri KESMEDEN uygular (FDM Snail Mode'un aynisi).

        Sozlesme/Kararlilik: PROFIL AKTIF sinir kaynagidir — `normal` her
        zaman Ayarlar'daki `max_speed_kb`'yi okur (profiller arasi beklenmedik
        kalinti deger yoktur). Yani `turbo` → `normal` donusu kullanicinin
        en son kayitli normal sinirina DONER; turbo'nun "sinirsiz" olgusu
        normal profile tasmaz."""
        ad = (ad or "").strip().lower()
        if ad not in HIZ_PROFILLERI:
            raise ValueError(
                "gecersiz hiz profili: %s (snail|normal|turbo olmali)" % ad
            )
        self.store.set("hiz_profili", ad)
        self.apply_settings()
        return {
            "ok": True,
            "profil": ad,
            "limit_kb": self.hiz_limiti_kb(),
            "durum": "degisti",
        }

    def baglanti_ayarla(
        self,
        gid: str,
        baglanti: int | None = None,
        hiz_kb: int | None = None,
    ) -> dict:
        """Network Core — CALISAN indirmenin ayarlarini KESMEDEN degisir.

        aria2 `changeOption` calisan ise aninda uygulanir. Degerler DB'ye de
        islenir; yeniden baslatmada `_launch_http` ayni sinirlarla baslar
        (bkz. `_baglanti_secenekleri`). Video (yt-dlp) islerinde canli ayar
        desteklenmez (ayrik alt surectir, secenekleri sonradan erismez)."""
        row = self.store.by_gid(gid)
        if not row:
            raise KayitYok("kayit bulunamadi: %s" % gid)
        if gid.startswith("yt:"):
            raise ValueError("video islerinde canli ayar desteklenmez")
        sec: dict[str, object] = {}
        if baglanti is not None:
            baglanti = int(baglanti)
            if not 1 <= baglanti <= 64:
                raise ValueError("baglanti sayisi 1-64 araliginda olmali")
            sec["max-connection-per-server"] = str(baglanti)
        if hiz_kb is not None:
            hiz_kb = int(hiz_kb)
            if hiz_kb < 0:
                raise ValueError("hiz negatif KB/s olamaz")
            sec["max-download-limit"] = "0" if hiz_kb == 0 else "%dK" % hiz_kb
        if sec:
            try:
                self.rpc.change_option(gid, sec)
            except Aria2Error as exc:
                raise ValueError("canli degistirilemedi: %s" % str(exc)[:160]) from exc
            opts = json.loads(row["options"] or "{}")
            if baglanti is not None:
                opts["baglanti"] = baglanti
            if hiz_kb is not None:
                opts["hiz_kb"] = hiz_kb
            self.store.update_by_id(row["id"], options=json.dumps(opts))
            self.store.log("info", "is ayarlari canli degistirildi: %s" % row["title"], gid=gid)
        return {"ok": True, "gid": gid, "baglanti": baglanti, "hiz_kb": hiz_kb}

    def update_settings(self, changes: dict) -> dict:
        """Ayarlari DOGRULA ve HEPSI-YA-HICBIRI kaydet.

        Bir alan bile gecersizse hicbiri yazilmaz (kismi kayit yok) ve
        `AyarGecersiz` ile alan+i18n anahtari listesi yukari tasinir.
        """
        hatalar, temiz = settings_validation.ayarlari_dogrula(changes or {})
        if hatalar:
            raise AyarGecersiz(hatalar)
        changes = temiz
        onceki_snail = int(self.store.get("snail_speed_kb") or 100)
        for key, value in changes.items():
            self.store.set(key, value)
        # Salyangoz hizi degistiyse ve profil SU AN salyangozsa yeni sinir
        # aria2'ye CANLI uygulanir (indirmeler kesilmez). apply_settings()
        # asagida zaten cagriliyor; burada yalnizca gorunurluk/kayit var.
        if "snail_speed_kb" in changes:
            yeni_snail = int(changes["snail_speed_kb"])
            aktif = str(self.store.get("hiz_profili") or "normal").strip().lower()
            if aktif == "snail" and yeni_snail != onceki_snail:
                self.store.log(
                    "info", "salyangoz hizi canli uygulandi: %d KB/s" % yeni_snail
                )
        if "download_dir" in changes:
            new_dir = changes["download_dir"] or str(paths.default_download_dir())
            Path(new_dir).mkdir(parents=True, exist_ok=True)
            try:
                self.rpc.change_global_option({"dir": new_dir})
            except Aria2Error:
                pass
        self.apply_settings()
        return self.store.all_settings()

    def current_download_dir(self) -> str:
        return self.store.get("download_dir") or str(paths.default_download_dir())

    # --- link turu --------------------------------------------------------
    @staticmethod
    def detect_kind(source: str) -> str:
        lowered = source.lower()
        if lowered.startswith("magnet:"):
            return "torrent"
        if lowered.split("?")[0].endswith(".torrent"):
            return "torrent"
        if ytdlp.is_video_site(source):
            return "video"
        return "http"

    @staticmethod
    def is_supported_source(source: str) -> bool:
        """Motorlarin GERCEKTEN acabilecegi bir kaynak mi?"""
        lowered = source.lower()
        if lowered.startswith(("http://", "https://", "ftp://", "sftp://", "magnet:")):
            return True
        try:
            yerel = Path(source)
            return yerel.suffix.lower() == ".torrent" and yerel.exists()
        except OSError:
            return False

    @staticmethod
    def magnet_infohash(source: str) -> str:
        """magnet linkinden info hash'i (hex, kucuk harf) cikar; yoksa bos string.

        aria2 mukerrer torrenti ancak ustveri cozulurken (asenkron) reddeder,
        ekleme aninda kabul eder. Bu yuzden kopya kontrolunu burada yapiyoruz.
        """
        if not source.lower().startswith("magnet:"):
            return ""
        query = urllib.parse.parse_qs(urllib.parse.urlparse(source).query)
        for value in query.get("xt", []):
            if not value.lower().startswith("urn:btih:"):
                continue
            raw = value.split(":")[-1].strip()
            if len(raw) == 40:
                return raw.lower()
            if len(raw) == 32:  # base32 gosterim
                try:
                    return base64.b32decode(raw.upper()).hex()
                except (ValueError, TypeError):
                    return raw.lower()
            return raw.lower()
        return ""

    ACTIVE_STATES = ("queued", "active", "waiting", "paused", "scheduled")

    def gecmis_sources(self, limit: int = 3000) -> list[str]:
        """DB'de kayitli tum kaynak adresleri (gecmis + kuyruk). LinkGrabber
        "daha once eklendi" uyari cizgisi icin kullanilir; engellemez."""
        return [r["source"] for r in self.store.list(limit=limit)]

    def _live_statuses(self) -> list[dict] | None:
        """Motorun su an tuttugu isler; motor cevap vermiyorsa None (BILINMIYOR).
        Bos liste ile None'i ayirmak sart: bos liste "motorda is yok" demek."""
        try:
            return (
                self.rpc.tell_active()
                + self.rpc.tell_waiting(0, 200)
                + self.rpc.tell_stopped(0, 200)
            )
        except Aria2Error as exc:
            self.last_error = str(exc)
            return None

    def find_duplicate(self, source: str) -> dict | None:
        """Ayni is kuyrukta duruyor mu? Magnet icin info hash, digerleri icin
        adres karsilastirilir.

        Veritabaninda "active" gorunup motorda KARSILIGI OLMAYAN kayit kuyrukta
        DEGILDIR. (Uygulama beklenmedik kapandiginda ya da aria2 oturumu
        silindiginde kayit oylece kalirdi; sonra ayni magnet "bu torrent zaten
        kuyrukta" diye reddedilir, listede de gorunmedigi icin kullanici
        torrentin hic calismadigini sanirdi.) Boyle kayitlar burada olu olarak
        isaretlenir ve yol acilir.
        """
        infohash = self.magnet_infohash(source)
        live = self._live_statuses()
        if infohash and live:
            for status in live:
                if (status.get("infoHash") or "").lower() == infohash:
                    return self._shape_aria2(status)
        # Motor cevap vermiyorsa (canli None) hicbir kayit olu SAYILMAZ: gecici
        # bir RPC hatasi yuzunden calisan indirmenin kaydini bozmayalim.
        canli = None
        if live is not None:
            canli = {status.get("gid", "") for status in live} | set(self.video_jobs)
        for row in self.store.list(limit=300):
            if row["status"] not in self.ACTIVE_STATES:
                continue
            ayni = row["source"] == source or (
                infohash and self.magnet_infohash(row["source"]) == infohash
            )
            if not ayni:
                continue
            # Zamanlanmis is henuz motorda olmaz; o gercekten kuyruktadir.
            if row["status"] == "scheduled" or canli is None or row["gid"] in canli:
                return row
            self.store.update_by_id(
                row["id"], status="error", finished_at=time.time(),
                error="motorda karsiligi kalmadi (uygulama kapanmis olabilir)",
            )
            self.store.log("warn", f"olu kayit temizlendi: {row['title']}", gid=row.get("gid", "") or "")
        return None

    @staticmethod
    def guess_name(source: str) -> str:
        return resolve_filename(source)

    @staticmethod
    def clean_title(title: str) -> str:
        """aria2 ustveri indirmelerine "[METADATA]" eki koyar; kullanici gormesin."""
        return title[len("[METADATA]"):] if title.startswith("[METADATA]") else title

    @staticmethod
    def is_metadata_only(status: dict) -> bool:
        """Magnet ustverisi kaydi GERCEK torrenti dogurduysa (followedBy) artik
        listede yeri yok — yoksa kullanici ayni indirmeyi iki satir gorur.
        Ustveri henuz cozulmediyse gizlemeyiz: tek geri bildirim o satir."""
        return bool(status.get("followedBy"))

    # --- ekleme -----------------------------------------------------------
    def add(self, source: str | models.DownloadRequest, **kw) -> dict:
        """Is ekler. Girdi ya `models.DownloadRequest` ya da flat-kwargs'tir;
        ikisi de TEK kuralla (`models.DownloadRequest.from_mapping`) gecerli
        kisa forma indirgenir (v1.4 Foundation: tum cagiricilar bu noktada
        birlesir). Tarihsel imza korundu: `add(url, kind=..., dest_dir=...)`.
        """
        req = (source if isinstance(source, models.DownloadRequest)
               else models.DownloadRequest.from_mapping({"source": source, **kw}))
        if not self.is_supported_source(req.source):
            # Panodan/elle gelen duz metin (ornegin bir dosya adi) aria2'ye
            # gidince "Unrecognized URI or unsupported protocol" diye kaybolurdu.
            raise ValueError(
                "gecersiz baglanti: http(s), ftp, magnet ya da .torrent dosyasi olmali"
            )
        kind = req.kind or self.detect_kind(req.source)
        duplicate = self.find_duplicate(req.source)
        if duplicate:
            label = "bu torrent" if kind == "torrent" else "bu baglanti"
            raise ValueError(f"{label} zaten kuyrukta: {duplicate.get('title') or req.source[:60]}")
        category = "video" if kind == "video" else ("torrent" if kind == "torrent" else "")
        resolved = rules.evaluate(self.store.rules_list(), {"dest_dir": self.current_download_dir(), "proxy": self.store.get("proxy", ""), "max_speed_kb": self.store.get("max_speed_kb", 0), "split": self.store.get("max_conn_per_server", 16)}, rules.context(req.source, req.filename or req.title or "", 0, kind, category), {"dest_dir": req.dest_dir, "proxy": req.proxy})
        effective = resolved["effective_options"]
        dest_dir = effective.get("dest_dir") or self.current_download_dir()
        rule_start_after = models.parse_time_spec(effective.get("start_after", ""))
        start_after = req.start_after or rule_start_after
        Path(dest_dir).mkdir(parents=True, exist_ok=True)
        options = {
            "quality": req.quality or self.store.get("video_quality", "best"),
            "audio_only": req.audio_only,
            "playlist": req.playlist,
            "headers": req.headers or {},
            "filename": req.filename or "",
            "user_agent": req.user_agent or "",
            "title": req.title or "",
            "proxy": effective.get("proxy", ""),
            "hiz_kb": effective.get("max_speed_kb", 0),
            "baglanti": effective.get("split", 0),
            "rules_trace": resolved["trace"],
            "checksum": req.checksum or "",
            "adopt_gid": getattr(req, "adopt_gid", None),
            "selected_files": getattr(req, "selected_files", None),
            # v1.6 Video Pro: istege bagli, varsayilanlar DB ayarlarindan
            # (video_quality uslubu); request verilen onde gelir.
            "altyazi_diller": req.altyazi_diller or self.store.get("video_altyazi_diller", ""),
            "oto_altyazi": req.oto_altyazi or self.store.get("video_oto_altyazi", False),
            "altyazi_goem": req.altyazi_goem or self.store.get("video_altyazi_goem", False),
            "kucuk_resim": req.kucuk_resim or self.store.get("video_kucuk_resim", ""),
            "ustveri_goem": req.ustveri_goem or self.store.get("video_ustveri_goem", False),
            "bolumler": req.bolumler or self.store.get("video_bolumler", ""),
            "sponsorblock": req.sponsorblock or self.store.get("video_sponsorblock", ""),
            "bolum_araligi": req.bolum_araligi or self.store.get("video_bolum_araligi", ""),
            "kapsayici": req.kapsayici or self.store.get("video_kapsayici", ""),
            "ses_formati": req.ses_formati or self.store.get("video_ses_formati", ""),
            "dosya_sablonu": req.dosya_sablonu or self.store.get("video_dosya_sablonu", ""),
            "tarayici_cerezi": req.tarayici_cerezi or self.store.get("video_tarayici_cerezi", ""),
        }
        row_id = self.store.add(
            kind=kind,
            source=req.source,
            title=options["title"] or self.guess_name(req.source),
            dest_dir=dest_dir,
            options=options,
            start_after=start_after,
        )
        temiz = cerez.temizle(req.cookies)
        if temiz:
            self._cerezler[row_id] = temiz
        if start_after:
            when = time.strftime("%H:%M", time.localtime(start_after))
            self.store.log("info", f"zamanlandi ({when}): {req.source[:80]}")
            return {"id": row_id, "kind": kind, "scheduled_for": start_after}
        return self._launch(self.store.by_id(row_id))  # type: ignore[arg-type]

    def _launch(self, row: dict) -> dict:
        kind = row["kind"]
        options = json.loads(row["options"] or "{}")
        dest_dir = row["dest_dir"] or self.current_download_dir()
        try:
            if kind == "video":
                gid = self._launch_video(row, options, dest_dir)
            elif kind == "torrent":
                gid = self._launch_torrent(row, dest_dir)
            else:
                gid = self._launch_http(row, options, dest_dir)
        except Exception as exc:
            self.store.update_by_id(
                row["id"], status="error", error=str(exc)[:500], finished_at=time.time()
            )
            self.store.log("error", f"baslatilamadi: {exc}", gid=row.get("gid", "") or "")
            raise
        self.store.attach_gid(row["id"], gid)
        self.store.log("info", f"basladi [{kind}]: {row['title']}", gid=gid)
        return {"id": row["id"], "gid": gid, "kind": kind}

    def _proksi(self, options: dict) -> dict | None:
        """Bir is icin gecerli proxy: is-acik → sistem → genel (sirasiyla).

        Her katman 'proxy' katmanina ait; normalize (host:port + tip) curls
        `core/proxy.parcala` yapar. Sistem proxy GitHub gibi her acilista
        yeniden okunur — kullanici Windows'ta proxy acmis olabilir."""
        adres = str(options.get("proxy") or "").strip()
        if adres:
            return P.parcala(adres)
        if self.store.get("system_proxy"):
            sistem = P.sistem_proxysi()
            if sistem:
                return P.parcala(sistem)
        genel = str(self.store.get("proxy") or "").strip()
        if genel:
            return P.parcala(genel)
        return None

    def _baglanti_secenekleri(self, options: dict) -> dict:
        """Is uzerinde hatirlanan CANLI ayar degerleri (max-connection-par-server
        ve max-download-limit). Yeniden baslatmada da korunur (bkz. baglanti_ayarla)."""
        sec: dict = {}
        try:
            baglanti = int(options.get("baglanti") or 0)
        except (TypeError, ValueError):
            baglanti = 0
        if 1 <= baglanti <= 64:
            sec["max-connection-per-server"] = str(baglanti)
        try:
            hiz = int(options.get("hiz_kb") or 0)
        except (TypeError, ValueError):
            hiz = 0
        if hiz > 0:
            sec["max-download-limit"] = "%dK" % hiz
        return sec

    def _launch_http(self, row: dict, options: dict, dest_dir: str) -> str:
        aria_options: dict[str, object] = {"dir": dest_dir}
        if options.get("filename"):
            aria_options["out"] = options["filename"]
        headers = [f"{k}: {v}" for k, v in (options.get("headers") or {}).items()]
        cerezler = self._cerezler.get(row["id"])
        if cerezler:
            headers.append("Cookie: " + cerez.baslik(cerezler))
        if headers:
            aria_options["header"] = headers
        if options.get("user_agent"):
            aria_options["user-agent"] = options["user_agent"]
        proksi = self._proksi(options)
        if proksi:
            aria_options.update(P.aria2_secenekleri(proksi))
        if options.get("checksum"):
            aria_options["checksum"] = options["checksum"]
        aria_options.update(self._baglanti_secenekleri(options))
        return self.rpc.add_uri([row["source"]], aria_options)

    def _launch_torrent(self, row: dict, dest_dir: str) -> str:
        options = json.loads(row["options"] or "{}")
        adopt_gid = options.get("adopt_gid")
        
        if adopt_gid:
            gid = adopt_gid
            try:
                durum = self.rpc.tell_status(gid, ["followedBy"])
                if durum.get("followedBy"):
                    gid = durum["followedBy"][0]
            except Aria2Error:
                pass
            
            try:
                self.rpc.change_option(gid, {"dir": dest_dir})
            except Aria2Error as exc:
                self.store.log("error", f"kayit dizini degistirilemedi: {exc}", gid=gid)
                
            selected = options.get("selected_files")
            if selected:
                try:
                    self.rpc.change_option(gid, {"select-file": self._select_file_degeri(selected)})
                    # DB guncellemesi (daha gid attach edilmedi ama sorun degil)
                    self.store.torrent_dosya_secimlerini_kaydet(gid, selected)
                except Aria2Error as exc:
                    self.store.log("error", f"dosya secimi uygulanamadi: {exc}", gid=gid)
            
            try:
                self.rpc.unpause(gid)
            except Aria2Error:
                pass
            return gid

        source = row["source"]
        aria_options = {"dir": dest_dir}
        proksi = self._proksi(options)
        if proksi:
            aria_options.update(P.aria2_secenekleri(proksi))
        local = Path(source)
        try:
            if local.exists() and local.suffix.lower() == ".torrent":
                payload = base64.b64encode(local.read_bytes()).decode("ascii")
                return self.rpc.add_torrent(payload, aria_options)
            return self.rpc.add_uri([source], aria_options)
        except Aria2Error as exc:
            if "already registered" in str(exc).lower():
                raise ValueError("bu torrent zaten kuyrukta") from exc
            raise

    def _launch_video(self, row: dict, options: dict, dest_dir: str) -> str:
        with self._lock:
            self._video_seq += 1
            job_id = f"yt:{self._video_seq}"
        cerezler = self._cerezler.get(row["id"])
        cerez_dosyasi = str(cerez.dosya_yaz(job_id, cerezler)) if cerezler else ""
        proksi = self._proksi(options)
        proxy_url = P.url(proksi) if proksi else ""
        job = ytdlp.VideoJob(
            job_id=job_id,
            url=row["source"],
            dest_dir=dest_dir,
            quality=options.get("quality", "best"),
            audio_only=bool(options.get("audio_only")),
            playlist=bool(options.get("playlist")),
            title=row["title"] or row["source"],
            # Hata metinleri kullanicinin dilinde yazilsin
            dil=str(self.store.get("language", "auto")),
            cookie_file=cerez_dosyasi,
            user_agent=options.get("user_agent", ""),
            headers=options.get("headers") or {},
            dosya_adi=options.get("title", ""),
            proxy=proxy_url,
            # v1.6 Video Pro: alanlar add()'de options'a islendi; VideoJob'a
            # tasinir. Varsayilanlar zaten add()'de cozuldugu icin burada
            # quick get yeterli.
            altyazi_diller=options.get("altyazi_diller", ""),
            oto_altyazi=bool(options.get("oto_altyazi")),
            altyazi_goem=bool(options.get("altyazi_goem")),
            kucuk_resim=options.get("kucuk_resim", ""),
            ustveri_goem=bool(options.get("ustveri_goem")),
            bolumler=options.get("bolumler", ""),
            sponsorblock=options.get("sponsorblock", ""),
            bolum_araligi=options.get("bolum_araligi", ""),
            kapsayici=options.get("kapsayici", ""),
            ses_formati=options.get("ses_formati", ""),
            dosya_sablonu=options.get("dosya_sablonu", ""),
            tarayici_cerezi=options.get("tarayici_cerezi", ""),
        )
        self.video_jobs[job_id] = job
        job.start(aria2c=str(paths.ARIA2C), on_update=self._on_video_update)
        return job_id

    def _on_video_update(self, job: ytdlp.VideoJob) -> None:
        fields = {
            "total_bytes": job.total,
            "done_bytes": job.downloaded,
            "status": job.status,
            "filename": job.filename,
            # URL'den tahmin edilen ad ("watch") yerine yt-dlp'nin gercek basligi
            "title": job.display_title(),
        }
        if job.status in ("complete", "error", "removed"):
            # Surdurmede _launch dosyayi bellekten yeniden yazar.
            cerez.sil(job.job_id)
            fields["finished_at"] = job.finished_at or time.time()
            if job.error:
                fields["error"] = job.error[:500]
        self.store.update_by_gid(job.job_id, **fields)
        if job.status == "complete" and job.job_id not in self._known_complete:
            self._known_complete.add(job.job_id)
            self._cerez_birak(self.store.by_gid(job.job_id))
            self._on_complete(job.display_title(), job.total, job.job_id)

    # --- video yardimcilari ----------------------------------------------
    def probe_video(self, url: str) -> dict:
        return ytdlp.probe(url)

    # --- kontrol ----------------------------------------------------------
    def pause(self, gid: str) -> bool:
        if not self.store.by_gid(gid):
            raise KayitYok("kayit bulunamadi: %s" % gid)
        if gid.startswith("yt:"):
            # yt-dlp duraklatmayi desteklemez; durdurup kaldigi yerden
            # devam edilecek sekilde isaretliyoruz (--continue ile surdurur).
            job = self.video_jobs.get(gid)
            if job:
                job.stop()
                job.status = "paused"
                self.store.update_by_gid(gid, status="paused")
                return True
            return False
        self.rpc.pause(gid)
        self.store.update_by_gid(gid, status="paused")
        return True

    def resume(self, gid: str) -> bool:
        if not self.store.by_gid(gid):
            raise KayitYok("kayit bulunamadi: %s" % gid)
        if gid.startswith("yt:"):
            row = self.store.by_gid(gid)
            self.store.update_by_id(row["id"], status="queued", gid=None)
            self._launch(self.store.by_id(row["id"]))  # type: ignore[arg-type]
            return True
        self.rpc.unpause(gid)
        self.store.update_by_gid(gid, status="active")
        return True

    def remove(self, gid: str, delete_files: bool = False) -> bool:
        if not hasattr(self, "_removed_gids"):
            self._removed_gids = set()
        if not hasattr(self, "_removed_hashes"):
            self._removed_hashes = set()

        if gid:
            self._removed_gids.add(gid)

        row = None
        if gid.startswith("row:"):
            try:
                row_id = int(gid.split(":", 1)[1])
                row = self.store.by_id(row_id)
            except (ValueError, IndexError):
                row = None
        else:
            row = self.store.by_gid(gid)

        if not row:
            # If it's a completely unknown GID, raise KayitYok to satisfy tests/API contracts
            raise KayitYok("kayit bulunamadi: %s" % gid)

        actual_gid = (row.get("gid") if row and row.get("gid") else gid) or gid
        if actual_gid:
            self._removed_gids.add(actual_gid)

        if row and row.get("source"):
            infohash = self.magnet_infohash(row["source"])
            if infohash:
                self._removed_hashes.add(infohash.lower())

        gids_to_remove: set[str] = set()
        if actual_gid:
            gids_to_remove.add(actual_gid)

        targets: list[Path] = []

        if actual_gid.startswith("yt:"):
            job = self.video_jobs.pop(actual_gid, None)
            if job:
                job.stop()
                if job.filename and job.dest_dir:
                    targets.append(Path(job.dest_dir) / job.filename)
        else:
            # aria2 parent/child GID baglantilari (followedBy / following)
            try:
                status = self.rpc.tell_status(actual_gid, ["followedBy", "following", "files", "infoHash"])
                if status.get("infoHash"):
                    self._removed_hashes.add(status["infoHash"].lower())
                followed = status.get("followedBy") or []
                for child_gid in followed:
                    if child_gid:
                        gids_to_remove.add(child_gid)
                        self._removed_gids.add(child_gid)
                parent_gid = status.get("following")
                if parent_gid:
                    gids_to_remove.add(parent_gid)
                    self._removed_gids.add(parent_gid)

                if delete_files:
                    for g in list(gids_to_remove):
                        try:
                            g_status = self.rpc.tell_status(g, ["files"])
                            for entry in g_status.get("files") or []:
                                if entry.get("path"):
                                    targets.append(Path(entry["path"]))
                        except Exception:
                            pass
            except Exception:
                pass

            for g in gids_to_remove:
                try:
                    self.rpc.remove(g, force=True)
                except Exception:
                    pass
                try:
                    self.rpc.remove_result(g)
                except Exception:
                    pass

            try:
                self.rpc.save_session()
            except Exception:
                pass
        if row:
            if row.get("filename") and row.get("dest_dir"):
                targets.append(Path(row["dest_dir"]) / row["filename"])
            elif row.get("target_path"):
                targets.append(Path(row["target_path"]))
            if row.get("dest_dir"):
                dest_dir = Path(row["dest_dir"])
                if row.get("filename"):
                    targets.append(dest_dir / row["filename"])
                if row.get("title"):
                    targets.append(dest_dir / row["title"])
                try:
                    options = json.loads(row.get("options") or "{}")
                    if options.get("filename"):
                        targets.append(dest_dir / options["filename"])
                    if options.get("title"):
                        targets.append(dest_dir / options["title"])
                except (json.JSONDecodeError, TypeError):
                    pass
            if row.get("source") and row["source"].lower().endswith(".torrent"):
                local_torrent = Path(row["source"])
                if local_torrent.exists() and local_torrent.is_file():
                    targets.append(local_torrent)

        if delete_files and targets:
            self._delete_targets(targets, row)

        if actual_gid.startswith("yt:"):
            cerez.sil(actual_gid)
        self._cerez_birak(row)
        if row:
            try:
                self.store.update_by_id(row["id"], status="removed", finished_at=time.time())
            except Exception:
                pass
        if actual_gid:
            try:
                self.store.update_by_gid(actual_gid, status="removed", finished_at=time.time())
            except Exception:
                pass
        return True

    def resolve_item_path(self, gid: str) -> Path | None:
        """Tekil ve coklu indirmeler, DB kayitlari, video job'lari ve aria2
        kaynaklari icin diskteki gercek dosya yolunu dondurur. Klasor ise veya
        birden fazla dosya iceriyorsa en buyuk/ana dosyayi bulur."""
        import glob
        from pathlib import Path

        candidates: list[Path] = []

        # 1. Canli aria2 durumu
        try:
            st = self.rpc.tell_status(gid)
            if st:
                for entry in st.get("files") or []:
                    if entry.get("path"):
                        candidates.append(Path(entry["path"]))
        except Exception:
            pass

        # 2. DB kaydi
        row = self.store.by_gid(gid)
        if not row and gid.startswith("row:"):
            try:
                row = self.store.by_id(int(gid.split(":")[1]))
            except (ValueError, IndexError):
                pass
        if row:
            if row.get("target_path"):
                candidates.append(Path(row["target_path"]))
            dest_dir = row.get("dest_dir") or row.get("dir") or ""
            filename = row.get("filename") or ""
            if dest_dir and filename:
                merged = ytdlp.birlesik_dosya_bul(dest_dir, filename)
                if merged and merged.name != filename:
                    try:
                        self.store.update_by_id(
                            row["id"],
                            filename=merged.name,
                            total_bytes=merged.stat().st_size,
                        )
                    except (OSError, KeyError):
                        pass
                    candidates.append(merged)
                else:
                    candidates.append(Path(dest_dir) / filename)
                    escaped = glob.escape(filename)
                    matches = glob.glob(str(Path(dest_dir) / f"{escaped}*"))
                    for m in matches:
                        candidates.append(Path(m))

        # 3. Video jobs (yt-dlp)
        if gid in self.video_jobs:
            vjob = self.video_jobs[gid]
            if getattr(vjob, "output_path", None):
                candidates.append(Path(vjob.output_path))
            if getattr(vjob, "target_path", None):
                candidates.append(Path(vjob.target_path))
            if getattr(vjob, "dir", None) and getattr(vjob, "filename", None):
                candidates.append(Path(vjob.dir) / vjob.filename)

        # 4. Snapshot items
        try:
            snap = self.snapshot()
            for item in snap.get("items", []):
                if item.get("gid") == gid or (row and item.get("id") == row.get("id")):
                    dest_dir = item.get("dir") or item.get("dest_dir") or self.current_download_dir()
                    filename = item.get("filename") or ""
                    if item.get("target_path"):
                        candidates.append(Path(item["target_path"]))
                    if dest_dir and filename:
                        merged = ytdlp.birlesik_dosya_bul(dest_dir, filename)
                        if merged and merged.name != filename:
                            candidates.append(merged)
                        else:
                            candidates.append(Path(dest_dir) / filename)
                            escaped = glob.escape(filename)
                            matches = glob.glob(str(Path(dest_dir) / f"{escaped}*"))
                            for m in matches:
                                candidates.append(Path(m))
        except Exception:
            pass

        # Aday yollari dogrula
        for cand in candidates:
            if not cand:
                continue
            try:
                if cand.is_file():
                    return cand
                elif cand.is_dir():
                    files = [p for p in cand.rglob("*") if p.is_file()]
                    if files:
                        files.sort(key=lambda p: p.stat().st_size, reverse=True)
                        return files[0]
            except Exception:
                pass

        return None


    def _cerez_birak(self, row: dict | None) -> None:
        if row:
            self._cerezler.pop(row["id"], None)

    @staticmethod
    def _delete_targets(targets: list[Path], row: dict | None) -> None:
        """Dosyalari, klasorleri, temp/part ve .aria2 kontrol dosyalarini temizle;
        yarim kalmis indirmeler klasorde iz birakmasin. Windows dosya kilitlerine
        karsi kisa yenileme/tekrar deneme uygular."""
        import shutil
        import os
        import stat

        def _force_remove_file(p: Path) -> None:
            if not p:
                return
            try:
                if not p.exists() and not p.is_symlink():
                    return
            except OSError:
                pass
            try:
                os.chmod(p, stat.S_IWRITE)
            except OSError:
                pass
            for _attempt in range(5):
                try:
                    p.unlink(missing_ok=True)
                    return
                except OSError:
                    time.sleep(0.1)

        def _remove_readonly(func, path, _exc_info):
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except OSError:
                pass

        def _silmeye_calis(p: Path) -> None:
            """Klasor ise rmtree ile sil, dosya/symlink ise unlink et."""
            for _attempt in range(5):
                try:
                    if p.is_dir():
                        shutil.rmtree(p, onerror=_remove_readonly)
                    elif p.is_file() or p.is_symlink():
                        _force_remove_file(p)
                    return
                except OSError:
                    time.sleep(0.1)

        seen: set[Path] = set()
        for target in targets:
            if not target:
                continue
            try:
                t_path = target.resolve() if isinstance(target, Path) else Path(str(target)).resolve()
            except OSError:
                t_path = target if isinstance(target, Path) else Path(str(target))

            if t_path in seen:
                continue
            seen.add(t_path)

            # 1. candidate.aria2 kontrol dosyasi
            _force_remove_file(Path(str(t_path) + ".aria2"))

            # 2. Klasor ise rmtree ile sil, dosya/symlink ise unlink et
            _silmeye_calis(t_path)
            _force_remove_file(Path(str(t_path) + ".aria2"))

            # 3. Klasor icindeki ytdlp / aria2 parca/gecici dosyalarini temizle
            try:
                parent = t_path.parent
                stem = t_path.stem
                if parent.exists() and parent.is_dir() and stem:
                    for child in parent.iterdir():
                        try:
                            if child.is_file() and child.name.startswith(stem):
                                if (child.name.endswith((".part", ".ytdl", ".temp", ".aria2"))
                                        or ".f" in child.name):
                                    _force_remove_file(child)
                        except OSError:
                            pass
            except OSError:
                pass

            # 4. Cok dosyali torrent / klasor: ust klasor bosaldiysa ve dest_dir altinda ise sil
            try:
                parent = t_path.parent
                base = Path(row["dest_dir"]).resolve() if row and row.get("dest_dir") else None
                if base and parent.exists() and parent.is_dir() and parent.resolve() != base:
                    _force_remove_file(Path(str(parent) + ".aria2"))
                    if not any(parent.iterdir()):
                        for _attempt in range(3):
                            try:
                                parent.rmdir()
                                break
                            except OSError:
                                time.sleep(0.1)
            except OSError:
                pass

    def pause_all(self) -> None:
        # aria2.pauseAll yalnizca waiting/paused/active islere uygulanir;
        # stopped (bitti/error) işlere engine tarafinda zaten dokunulmaz.
        # Video (yt-dlp) islerinde ayni semantigi biz koruruz: tamamlanan/
        # hatali/removed işleri tekrar durdurup durumunu bozmayiz.
        try:
            self.rpc.pause_all()
        except Aria2Error:
            pass
        bitmis = ("complete", "error", "removed")
        for gid, job in list(self.video_jobs.items()):
            if getattr(job, "status", "") not in bitmis:
                self.pause(gid)

    def resume_all(self) -> None:
        try:
            self.rpc.unpause_all()
        except Aria2Error:
            pass
        for row in self.store.list():
            if row["status"] == "paused" and (row["gid"] or "").startswith("yt:"):
                self.resume(row["gid"])

    def retry(self, row_id: int) -> dict:
        row = self.store.by_id(row_id)
        if not row:
            raise ValueError("kayit bulunamadi")
        self.store.update_by_id(row_id, status="queued", gid=None, error=None)
        return self._launch(self.store.by_id(row_id))  # type: ignore[arg-type]

    # --- olen linki yenileme (NDM'nin "Renew expired link" mantigi) ----------
    # Sozlesme: yalnizca http(s)/ftp isleri; torrent/magnet/video renew
    # istemez (changeUri'siz coclar). Hatalar makine-okur kod tasir:
    #   RENEW_UNSUPPORTED — yanlis is turu  |  KAYIT_YOK — gid yok
    def renew(
        self,
        gid: str,
        yeni_url: str,
        headers: dict | None = None,
        cookies: list[dict] | None = None,
        user_agent: str | None = None,
    ) -> dict:
        """Suresi dolan linki SIFIRLAMADAN yeni adresle devam ettirir.

        Google Drive, upload siteleri veya imzali linkler saatler sonra olur.
        `aria2.changeUri` eski URI'yi listeden cikarip yeniyi ekler; `.aria2`
        kontrol dosyasi sayesinde INEN BAYTLAR KORUNUR. changeUri yalnizca
        waiting/paused/error durumlarinda calisir — aktif is ise once duraklatir,
        degisimle birlikte devam ettiririz.

        `headers`, `cookies` ve `user_agent` verilirse ayni atomik adimda
        o indirmenin aria2 seceneklerine yazilir (mevcut basliklar korunur,
        yeniler kazanir) ve DB'ye islenir. Sozlesme, gelecekteki istemcilerin
        (ornek. CLI `renew <gid> <url>`) imzayi genisletmeden ilerlemesine
        izin verecek sekilde esnek birakilir."""
        yeni_url = (yeni_url or "").strip()
        if not yeni_url.lower().startswith(("http://", "https://", "ftp://")):
            raise BadSource("yeni adres http(s) veya ftp olmali")
        row = self.store.by_gid(gid)
        if not row:
            raise KayitYok("kayit bulunamadi: %s" % gid)
        if row["kind"] not in ("http", "ftp"):
            raise RenewDesteklenmez(
                "%s isleri yenilenemez — yalnizca http(s)/ftp indirmeleri"
                % row["kind"]
            )
        try:
            status = self.rpc.tell_status(gid, ["status", "files"])
        except Aria2Error as exc:
            raise ValueError("motor o isi bilmiyor: %s" % str(exc)[:120]) from exc
        dosyalar = status.get("files") or []
        if not dosyalar:
            raise ValueError("dosya bilgisi yok")
        uriler = dosyalar[0].get("uris") or []
        eski = ""
        for u in uriler:
            if u.get("status") == "used":
                eski = u.get("uri", "")
                break
        if not eski:
            eski = uriler[0].get("uri", "") if uriler else ""
        if not eski:
            eski = row.get("source") or ""

        durum = status.get("status", "")
        aktif = durum == "active"
        hatali = durum == "error"

        # Yeni secenekler (verildiyse) mevcutlarin UZERINE bindirilir.
        options = json.loads(row["options"] or "{}")
        sec = dict(options.get("headers") or {})
        if headers:
            sec.update({k: v for k, v in headers.items() if k and v})
        cerez_temiz = cerez.temizle(cookies) if cookies else None
        if user_agent:
            options["user_agent"] = user_agent
        options["headers"] = sec
        basliklar = [f"{k}: {v}" for k, v in sec.items()]
        if cerez_temiz:
            basliklar.append("Cookie: " + cerez.baslik(cerez_temiz))
            self._cerezler[row["id"]] = cerez_temiz

        if aktif:
            try:
                self.rpc.pause(gid)
            except Aria2Error:
                pass
        try:
            degisen = int(self.rpc.change_uri(gid, 1, [eski], [yeni_url]) or 0)
            aria_opt: dict[str, object] = {}
            if basliklar:
                aria_opt["header"] = basliklar
            if options.get("user_agent"):
                aria_opt["user-agent"] = options["user_agent"]
            if aria_opt:
                self.rpc.change_option(gid, aria_opt)
        except Aria2Error as exc:
            if aktif:
                try:
                    self.rpc.unpause(gid)
                except Aria2Error:
                    pass
            raise ValueError("adres degistirilemedi: %s" % str(exc)[:180]) from exc
        self.store.update_by_id(
            row["id"],
            source=yeni_url,
            options=json.dumps(options, ensure_ascii=False),
            error=None,
            status="active" if (aktif or hatali) else durum,
        )
        if aktif or hatali:
            try:
                self.rpc.unpause(gid)
            except Aria2Error:
                pass
        self.store.log("info", "adres yenilendi: %s" % row["title"], gid=gid)
        return {
            "ok": True,
            "gid": gid,
            "eski": eski,
            "yeni": yeni_url,
            "degisen": degisen,
        }

    # --- seed / tracker tazeleme --------------------------------------------
    def seed_bilgi(self, gid: str) -> dict:
        """Seed penceresi icin: kac seed/baglanti, kac tracker, liste ne kadar taze."""
        try:
            status = self.rpc.tell_status(
                gid, ["gid", "status", "infoHash", "numSeeders", "connections",
                      "bittorrent", "dir", "completedLength", "totalLength"])
        except Aria2Error as exc:
            return {"ok": False, "error": str(exc)[:200]}
        bittorrent = status.get("bittorrent") or {}
        duyuru = bittorrent.get("announceList") or []
        try:
            global_ayar = self.rpc.get_global_option()
        except Aria2Error:
            global_ayar = {}
        havuz = [t for t in (global_ayar.get("bt-tracker") or "").split(",") if t]
        yas = trackers.cache_yasi()
        return {
            "ok": True,
            "baslik": (self.store.by_gid(gid) or {}).get("title") or gid,
            "seed": int(status.get("numSeeders", 0) or 0),
            "baglanti": int(status.get("connections", 0) or 0),
            "tracker": sum(len(grup) for grup in duyuru),
            "havuz": len(havuz),
            "liste_yasi_saat": None if yas is None else round(yas / 3600, 1),
            "dht": (global_ayar.get("enable-dht") or "") == "true",
            "ek_trackerlar": str(self.store.get("ek_trackerlar", "")),
            "ek_sayisi": len(trackers.ayikla(str(self.store.get("ek_trackerlar", "")))),
            "canli_sayisi": len(trackers.ayikla(str(self.store.get("canli_trackerlar", "")))),
            "tarama": self.store.get("tracker_tarama_ozeti", {}) or {},
            "durum": status.get("status", ""),
            "ilerleme": round(
                int(status.get("completedLength", 0)) * 100
                / max(int(status.get("totalLength", 1)), 1), 1),
        }

    def tracker_tara(self, gid: str = "") -> dict:
        """Klasordeki tracker'lari olc, canlilari hemen aria2'ye uygula.

        GID verilirse o torrentin info hash'iyle scrape yapilir; torrenti
        taniyan tracker'lar listenin basina gelir.
        """
        infohash = ""
        if gid:
            try:
                status = self.rpc.tell_status(gid, ["infoHash"])
            except Aria2Error as exc:
                return {"ok": False, "error": str(exc)[:200]}
            infohash = (status.get("infoHash") or "").lower()
        try:
            from . import tracker_saglik
            sonuc = tracker_saglik.tazele(self.store, infohash)
            uygulanan = trackers.apply_to_aria2(
                self.rpc, force=False,
                ek=str(self.store.get("ek_trackerlar", "")),
                canli=str(self.store.get("canli_trackerlar", "")))
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:200]}
        return {"ok": True, **sonuc["sayilar"], "uygulanan": uygulanan}

    # --- seed listeleri (Ayarlar > Seed listeleri) ---------------------------
    def seed_dosyalari(self) -> dict:
        """Ayarlar bolumu icin: hangi liste dosyalari var, son tarama ne durumda."""
        from . import tracker_saglik
        try:
            dosyalar = tracker_saglik.dosyalar()
            toplam = len(tracker_saglik.klasorden_oku())
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:200]}
        try:
            yas = time.time() - float(self.store.get("tracker_tarama_zamani", 0) or 0)
        except (TypeError, ValueError):
            yas = 0.0
        return {
            "ok": True,
            "dosyalar": dosyalar,
            "klasor": str(tracker_saglik.KLASOR),
            "adres": toplam,
            "canli": len(trackers.ayikla(str(self.store.get("canli_trackerlar", "")))),
            "tarama": self.store.get("tracker_tarama_ozeti", {}) or {},
            "tarama_yasi_saat": None if not yas or yas > 10 ** 9 else round(yas / 3600, 1),
            "taze": tracker_saglik.taze_mi(self.store),
            "otomatik": bool(self.store.get("tracker_otomatik_tara")),
        }

    def seed_dosya_ekle(self, yol: str) -> dict:
        """Secilen .txt'yi trackers/ klasorune kopyala ve YENIDEN taramayi tetikle."""
        from . import tracker_saglik
        try:
            sonuc = tracker_saglik.dosya_ekle(yol)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)[:200]}
        if not sonuc.get("zaten"):
            self._seed_taramasini_bayatlat()
        return {"ok": True, **sonuc}

    def seed_dosya_sil(self, ad: str) -> dict:
        from . import tracker_saglik
        try:
            sonuc = tracker_saglik.dosya_sil(ad)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)[:200]}
        self._seed_taramasini_bayatlat()
        return {"ok": True, **sonuc}

    def _seed_taramasini_bayatlat(self) -> None:
        """Liste degisti: eldeki olcum artik gecersiz, arka planda yeniden tara.

        Tarama agdan olcum yaptigi icin ARKA PLANDA kosar; bitince canli liste
        aria2'ye uygulanir (bkz. tracker_tara).
        """
        self.store.set("tracker_tarama_zamani", 0)
        threading.Thread(target=self._tracker_saglik_tara, daemon=True).start()

    def seed_tazele(self, gid: str) -> dict:
        """Guncel tracker listesini cekip torrenti YENIDEN DUYURUR.

        OLCULDU (2026-09-18): aria2 CALISAN torrente tracker EKLEMEZ —
        `changeOption(bt-tracker)` "OK" der ama duyuru listesi degismez. Tek
        uygulanabilir yol kaldirip AYNI dizine yeniden eklemektir; `.aria2`
        kontrol dosyasi sayesinde ILERLEME KORUNUR (olculdu: 15.5 MB'lik is
        yeniden eklendikten sonra 26 MB'dan devam etti, tracker 2 -> 3).

        Dosyalara DOKUNULMAZ: silme yok, yalniz motordan cikarilip geri konur.
        """
        row = self.store.by_gid(gid)
        try:
            status = self.rpc.tell_status(gid, ["infoHash", "dir", "bittorrent", "status"])
        except Aria2Error as exc:
            return {"ok": False, "error": str(exc)[:200]}
        infohash = (status.get("infoHash") or "").lower()
        if not infohash:
            return {"ok": False, "error": "bu is bir torrent degil"}
        hedef = status.get("dir") or (row or {}).get("dest_dir") or self.current_download_dir()

        # NOT: tarama BURADA yapilmaz — ag islemi tazelemeyi 15+ sn geciktirir
        # ve kullanici dugmeye basinca beklemis olur. Tarama arka planda,
        # gunluk dongude calisir (bkz. _maybe_trackers).
        sayi = trackers.apply_to_aria2(
            self.rpc, force=True, ek=str(self.store.get("ek_trackerlar", "")),
            canli=str(self.store.get("canli_trackerlar", "")))

        # Kaynak: once kaydin kendi kaynagi (.torrent dosyasi hala duruyorsa),
        # yoksa info hash'ten magnet — tracker'lar zaten global listeden gelir.
        kaynak = (row or {}).get("source") or ""
        if kaynak.lower().endswith(".torrent") and not Path(kaynak).exists():
            kaynak = ""
        if not kaynak.startswith("magnet:") and not kaynak.startswith("http"):
            if not kaynak:
                kaynak = f"magnet:?xt=urn:btih:{infohash}"
        secenekler = {"dir": hedef}
        # ``select-file`` belirtilmezse aria2 tum dosyalari secer. Kullanici
        # tercihi varsa (bos tercih dahil) yeniden eklenen torrente acikca
        # yeniden ver; aksi halde seed tazeleme tum torrent'i indirir.
        if self.store.torrent_dosya_secimi_var(gid):
            secenekler["select-file"] = self._select_file_degeri(
                self.store.torrent_dosya_secimleri(gid)
            )
        try:
            self.rpc.pause(gid)
        except Aria2Error:
            pass
        try:
            self.rpc.remove(gid, force=True)
        except Aria2Error:
            pass
        try:
            self.rpc.remove_result(gid)
        except Aria2Error:
            pass
        try:
            if kaynak.lower().endswith(".torrent") and Path(kaynak).exists():
                yeni_gid = self.rpc.add_torrent(
                    base64.b64encode(Path(kaynak).read_bytes()).decode(), secenekler)
            else:
                yeni_gid = self.rpc.add_uri([kaynak], secenekler)
        except Aria2Error as exc:
            self.store.log("warn", f"seed tazeleme basarisiz: {exc}", gid=gid)
            return {"ok": False, "error": str(exc)[:200]}
        if row:
            self.store.update_by_id(row["id"], gid=yeni_gid, status="active", error=None)
            self.store.torrent_dosya_secimlerini_tasi(gid, yeni_gid)
        self.store.log("info", f"seed tazelendi: {sayi} tracker ile yeniden duyuruldu", gid=yeni_gid)
        return {"ok": True, "tracker": sayi, "gid": yeni_gid}

    # --- durum goruntusu --------------------------------------------------
    def snapshot(self) -> dict:
        items: list[dict] = []
        gids_seen: set[str] = set()
        try:
            live = (
                self.rpc.tell_active()
                + self.rpc.tell_waiting(0, 200)
                + self.rpc.tell_stopped(0, 200)
            )
        except Aria2Error as exc:
            self.last_error = str(exc)
            live = []
        ids_seen: set[int] = set()   # DB id bazli duplicate engeli
        for status in live:
            gid = status.get("gid", "")
            if not gid or gid in self._removed_gids:
                continue
            infohash = (status.get("infoHash") or "").lower()
            if infohash and infohash in self._removed_hashes:
                continue
            if self.is_metadata_only(status):
                continue
            row = self.store.by_gid(gid)
            if row and row.get("status") == "removed":
                self._removed_gids.add(gid)
                continue
            if row is None and status.get("infoHash"):
                row = self._reattach_torrent(status)
                if row and row.get("status") == "removed":
                    self._removed_gids.add(gid)
                    continue
            gids_seen.add(gid)
            if row:
                ids_seen.add(row["id"])
            items.append(self._shape_aria2(status))
        for job in list(self.video_jobs.values()):
            if job.job_id in self._removed_gids or job.status == "removed":
                continue
            row = self.store.by_gid(job.job_id)
            if row and row.get("status") == "removed":
                self._removed_gids.add(job.job_id)
                continue
            gids_seen.add(job.job_id)
            shaped = job.to_dict()
            shaped["id"] = row["id"] if row else None
            if row:
                ids_seen.add(row["id"])
            shaped["progress"] = (
                round(job.downloaded / job.total * 100, 1) if job.total else 0.0
            )
            items.append(shaped)
        # aria2 oturumu unutmus olabilir: DB'deki bitmis/zamanlanmis kayitlar
        for row in self.store.list(limit=200):
            if row["id"] in ids_seen or row.get("status") == "removed":
                continue
            if row["gid"] and (row["gid"] in gids_seen or row["gid"] in self._removed_gids):
                continue
            if row.get("source"):
                h = self.magnet_infohash(row["source"])
                if h and h in self._removed_hashes:
                    continue
            if row["status"] in ("complete", "error", "scheduled", "paused"):
                items.append(self._shape_row(row))
        try:
            stat = self.rpc.global_stat()
        except Aria2Error:
            stat = {}
        return {
            "items": items,
            "stat": {
                "downloadSpeed": int(stat.get("downloadSpeed", 0))
                + sum(j.speed for j in self.video_jobs.values() if j.status == "active"),
                "uploadSpeed": int(stat.get("uploadSpeed", 0)),
                "numActive": int(stat.get("numActive", 0))
                + sum(1 for j in self.video_jobs.values() if j.status == "active"),
                "numWaiting": int(stat.get("numWaiting", 0)),
                "numStopped": int(stat.get("numStopped", 0)),
            },
            "settings": self.store.all_settings(),
            "engine_ok": self.rpc.alive(),
            "download_dir": self.current_download_dir(),
            # Arayuz hangi dilde yazacagini buradan ogrenir ("auto" cozulmus halde)
            "lang": lang.resolve(str(self.store.get("language", "auto"))),
            "last_error": self.last_error,
            "automation": self.store.automation_jobs(limit=200),
        }

    def _shape_aria2(self, status: dict) -> dict:
        gid = status.get("gid", "")
        row = self.store.by_gid(gid)
        total = int(status.get("totalLength", 0) or 0)
        done = int(status.get("completedLength", 0) or 0)
        files = status.get("files") or []
        name = ""
        if files:
            name = Path(files[0].get("path", "")).name
        bittorrent = status.get("bittorrent") or {}
        bt_name = (bittorrent.get("info") or {}).get("name")
        is_torrent = bool(bittorrent) or bool(status.get("infoHash"))
        speed = int(status.get("downloadSpeed", 0) or 0)
        eta = int((total - done) / speed) if speed > 0 and total > done else 0
        return {
            "id": row["id"] if row else None,
            "gid": gid,
            "kind": "torrent" if is_torrent else (row["kind"] if row else "http"),
            "status": status.get("status", "unknown"),
            "title": self.clean_title(bt_name or name or (row["title"] if row else gid)),
            "filename": name,
            "totalLength": total,
            "completedLength": done,
            "progress": round(done / total * 100, 1) if total else 0.0,
            "downloadSpeed": speed,
            "uploadSpeed": int(status.get("uploadSpeed", 0) or 0),
            "connections": int(status.get("connections", 0) or 0),
            "numSeeders": int(status.get("numSeeders", 0) or 0),
            "seeder": status.get("seeder") == "true",
            "eta": eta,
            "dir": status.get("dir", ""),
            "errorMessage": status.get("errorMessage", ""),
            "infoHash": status.get("infoHash", ""),
            "numPieces": int(status.get("numPieces", 0) or 0),
            "source": row["source"] if row else "",
            "uploadLength": int(status.get("uploadLength", 0) or 0),
            "ratio": (
                round(int(status.get("uploadLength", 0) or 0) / done, 3) if done else 0.0
            ),
        }

    def _shape_row(self, row: dict) -> dict:
        total = int(row.get("total_bytes") or 0)
        done = int(row.get("done_bytes") or 0)
        return {
            "id": row["id"],
            "gid": row["gid"] or f"row:{row['id']}",
            "kind": row["kind"],
            "status": row["status"],
            "title": row["title"] or row["source"],
            "filename": row["filename"] or "",
            "totalLength": total,
            "completedLength": done,
            "progress": round(done / total * 100, 1) if total else 0.0,
            "downloadSpeed": 0,
            "uploadSpeed": 0,
            "connections": 0,
            "numSeeders": 0,
            "eta": 0,
            "dir": row["dest_dir"] or "",
            "errorMessage": row["error"] or "",
            "source": row["source"],
            "start_after": row["start_after"],
        }

    def peers(self, gid: str) -> list[dict]:
        """Torrent icin canli peer/seed listesi."""
        if gid.startswith(("yt:", "row:")):
            return []
        try:
            raw = self.rpc.get_peers(gid)
        except Aria2Error:
            return []
        return [
            {
                "ip": p.get("ip"),
                "port": p.get("port"),
                "seeder": p.get("seeder") == "true",
                "downloadSpeed": int(p.get("downloadSpeed", 0) or 0),
                "uploadSpeed": int(p.get("uploadSpeed", 0) or 0),
                "client": p.get("peerId", "")[:24],
            }
            for p in raw
        ]

    def torrent_on_ekle(self, source: str) -> str:
        """Kullanici dosya secimi yapabilsin diye torrenti duraklatilmis olarak aria2'ye ekler.
        DB'ye kaydedilmez; secim/iptal adiminda nihai islem yapilir."""
        aria_options = {
            "pause": "true",
            "pause-metadata": "false",
        }
        proksi = self._proksi({})
        if proksi:
            aria_options.update(P.aria2_secenekleri(proksi))
        
        local = Path(source)
        try:
            if local.exists() and local.suffix.lower() == ".torrent":
                payload = base64.b64encode(local.read_bytes()).decode("ascii")
                return self.rpc.add_torrent(payload, aria_options)
            return self.rpc.add_uri([source], aria_options)
        except Aria2Error as exc:
            if "already registered" in str(exc).lower():
                raise ValueError("bu torrent zaten kuyrukta") from exc
            raise

    def torrent_on_iptal(self, gid: str) -> None:
        """On-eklenmis ancak iptal edilmis torrenti aria2'den siler."""
        try:
            durum = self.rpc.tell_status(gid, ["followedBy"])
            child = (durum.get("followedBy") or [None])[0]
            self.rpc.remove(gid, force=True)
            self.rpc.remove_result(gid)
            if child:
                self.rpc.remove(child, force=True)
                self.rpc.remove_result(child)
        except Aria2Error:
            pass

    # --- torrent dosyalari ------------------------------------------------
    @staticmethod
    def _torrent_dosya_turu(uzanti: str) -> str:
        turler = {
            "video": {".mp4", ".mkv", ".avi", ".webm", ".ts"},
            "ses": {".mp3", ".m4a", ".aac", ".ogg", ".flac", ".wav"},
            "arsiv": {".zip", ".rar", ".7z", ".tar", ".gz", ".iso"},
            "belge": {".pdf", ".txt", ".epub", ".mobi", ".doc", ".docx"},
            "resim": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"},
        }
        for ad, uzantilar in turler.items():
            if uzanti in uzantilar:
                return ad
        return "diger"

    @staticmethod
    def _torrent_yol_parcalari(yol: str, torrent_adi: str) -> list[str]:
        parcalar = [parca for parca in yol.replace("\\", "/").split("/") if parca]
        if parcalar and parcalar[0].endswith(":"):
            parcalar = parcalar[1:]
        if torrent_adi:
            for sira, parca in enumerate(parcalar):
                if parca.casefold() == torrent_adi.casefold():
                    return parcalar[sira:]
        return parcalar

    def torrent_dosyalari(self, gid: str) -> list[dict]:
        """Bir torrentin aria2 dosyalarini UI'den bagimsiz, agac-hazir hale getir."""
        row = self.store.by_gid(gid)
        try:
            durum = self.rpc.tell_status(gid, ["gid", "infoHash", "bittorrent", "followedBy"])
            if durum.get("followedBy"):
                gid = durum["followedBy"][0]
                durum = self.rpc.tell_status(gid, ["gid", "infoHash", "bittorrent", "followedBy"])
        except Aria2Error as exc:
            raise ValueError("torrent durumu okunamadi: %s" % str(exc)[:160]) from exc
        bittorrent = durum.get("bittorrent") or {}
        torrent_mu = (row or {}).get("kind") == "torrent" or bool(bittorrent) or bool(durum.get("infoHash"))
        if not torrent_mu:
            raise ValueError("dosya listesi yalnizca torrent GID icin kullanilir")
        if not bittorrent and not durum.get("infoHash"):
            return TorrentDosyaListesi(
                hazir_degil=True,
                neden="Magnet ustverisi henuz gelmedi; dosya listesi hazir degil.",
                gid=gid,
            )
        try:
            ham_dosyalar = self.rpc.get_files(gid)
        except Aria2Error as exc:
            raise ValueError("torrent dosya listesi okunamadi: %s" % str(exc)[:160]) from exc
        if not ham_dosyalar and torrent_mu and not bittorrent:
            return TorrentDosyaListesi(
                hazir_degil=True,
                neden="Magnet ustverisi henuz gelmedi; dosya listesi hazir degil.",
                gid=gid,
            )
        torrent_adi = str((bittorrent.get("info") or {}).get("name") or "")
        tercih_var = self.store.torrent_dosya_secimi_var(gid)
        secilenler = set(self.store.torrent_dosya_secimleri(gid)) if tercih_var else set()
        sonuc = TorrentDosyaListesi(gid=gid)
        for ham in ham_dosyalar:
            indeks = int(ham.get("index", 0) or 0)
            yol = str(ham.get("path") or "")
            parcalar = self._torrent_yol_parcalari(yol, torrent_adi)
            ad = parcalar[-1] if parcalar else yol.replace("\\", "/").rsplit("/", 1)[-1]
            uzanti = Path(ad).suffix.lower()
            boyut = int(ham.get("length", 0) or 0)
            tamamlanan = int(ham.get("completedLength", 0) or 0)
            sonuc.append({
                "indeks": indeks,
                "ad": ad,
                "yol": yol,
                "boyut": boyut,
                "boyut_insan": human_size(boyut),
                "tamamlanan": tamamlanan,
                "yuzde": round(tamamlanan * 100 / boyut, 1) if boyut else 0.0,
                "secili": indeks in secilenler if tercih_var else ham.get("selected") == "true",
                "uzanti": uzanti,
                "tur": self._torrent_dosya_turu(uzanti),
                "yol_parcalari": parcalar,
                "parent_yol": "/".join(parcalar[:-1]),
                "uris": ham.get("uris") or [],
            })
        return sonuc

    def torrent_dosya_secimini_kaydet(self, gid: str, indeksler: list[int]) -> list[int]:
        """UI secimini sonraki baslatmaya kadar DB'de sakla."""
        if not ((self.store.by_gid(gid) or {}).get("kind") == "torrent"):
            raise ValueError("dosya secimi yalnizca torrent GID icin kaydedilir")
        temiz = sorted({int(indeks) for indeks in indeksler if int(indeks) > 0})
        self.store.torrent_dosya_secimlerini_kaydet(gid, temiz)
        return temiz

    @staticmethod
    def _select_file_degeri(indeksler: list[int]) -> str:
        """aria2 ``select-file`` degeri: 1-tabanli indeksler, virgullu liste.

        Bos dize aria2'de secenegin verilmemesiyle ayni anlama gelir: tum
        torrent dosyalari secilir. Bu nedenle bos kullanici tercihini de
        acikca ``{"select-file": ""}`` olarak yazariz.
        """
        return ",".join(str(indeks) for indeks in indeksler)

    def torrent_secimi_ayarla(self, gid: str, indeksler: list[int]) -> dict:
        """Torrent dosya secimini aria2'ye hemen uygula ve kalici sakla.

        aria2 ``changeOption`` ``select-file`` secenegini calisan torrentte
        dinamik uygular; bu yuzden duraklatma/yeniden baslatma yapilmaz.
        """
        row = self.store.by_gid(gid)
        if not row or row.get("kind") != "torrent":
            raise ValueError("dosya secimi yalnizca torrent GID icin ayarlanir")
        if not isinstance(indeksler, list):
            raise ValueError("dosya indeksleri liste olmali")
        try:
            temiz = sorted(set(indeksler))
        except TypeError as exc:
            raise ValueError("gecersiz dosya indeksi") from exc
        if any(isinstance(indeks, bool) or not isinstance(indeks, int) or indeks < 1
               for indeks in temiz):
            raise ValueError("gecersiz dosya indeksi: 1-tabanli pozitif tam sayi olmali")
        try:
            dosyalar = self.rpc.get_files(gid)
        except Aria2Error as exc:
            raise ValueError("torrent dosya listesi okunamadi: %s" % str(exc)[:160]) from exc
        gecerli = {int(dosya.get("index", 0) or 0) for dosya in dosyalar}
        if not gecerli:
            raise ValueError("torrent dosya listesi henuz hazir degil")
        gecersiz = [indeks for indeks in temiz if indeks not in gecerli]
        if gecersiz:
            raise ValueError("gecersiz dosya indeksi: %s" % ",".join(map(str, gecersiz)))
        try:
            self.rpc.change_option(gid, {"select-file": self._select_file_degeri(temiz)})
        except Aria2Error as exc:
            raise ValueError("dosya secimi canli degistirilemedi: %s" % str(exc)[:160]) from exc
        self.store.torrent_dosya_secimlerini_kaydet(gid, temiz)
        self.store.log("info", f"dosya secimi guncellendi ({len(temiz)} dosya)", gid=gid)
        return {"ok": True, "gid": gid, "indeksler": temiz}

    def torrent_dosya_secimleri(self, gid: str) -> list[int]:
        """Kaydedilmis dosya indekslerini dondur."""
        return self.store.torrent_dosya_secimleri(gid)
    def torrent_metrikleri(self, gid: str) -> dict:
        """Torrent bazli seed, ratio, hiz, upload/download ve tracker ozeti.

        Dosya agaci ve torrent pro UI panelleri icin canli metrik cikarir.
        Magnet ustverisi henuz cozulmediyse hazir_degil=True dondurur.
        """
        row = self.store.by_gid(gid)
        try:
            status = self.rpc.tell_status(
                gid,
                [
                    "gid", "status", "infoHash", "numSeeders", "connections",
                    "bittorrent", "dir", "completedLength", "totalLength",
                    "uploadLength", "downloadSpeed", "uploadSpeed", "seeder",
                ],
            )
        except Aria2Error as exc:
            raise ValueError("torrent durumu okunamadi: %s" % str(exc)[:160]) from exc

        bittorrent = status.get("bittorrent") or {}
        torrent_mu = (row or {}).get("kind") == "torrent" or bool(bittorrent) or bool(status.get("infoHash"))
        if not torrent_mu:
            raise ValueError("torrent metrikleri yalnizca torrent GID icin kullanilir")

        if not bittorrent and not status.get("infoHash"):
            return {
                "hazir_degil": True,
                "neden": "Magnet ustverisi henuz gelmedi; metrikler hazir degil.",
            }

        duyuru = bittorrent.get("announceList") or []
        tracker_sayisi = sum(len(grup) for grup in duyuru)
        try:
            global_ayar = self.rpc.get_global_option()
        except Aria2Error:
            global_ayar = {}
        havuz = [t for t in (global_ayar.get("bt-tracker") or "").split(",") if t]

        done = int(status.get("completedLength", 0) or 0)
        total = int(status.get("totalLength", 0) or 0)
        uploaded = int(status.get("uploadLength", 0) or 0)
        down_speed = int(status.get("downloadSpeed", 0) or 0)
        up_speed = int(status.get("uploadSpeed", 0) or 0)
        connections = int(status.get("connections", 0) or 0)
        num_seeders = int(status.get("numSeeders", 0) or 0)
        is_seeder = status.get("seeder") == "true"
        ratio = round(uploaded / done, 3) if done > 0 else 0.0

        # Canli peer listesi ozeti (guvenli sinirla)
        canli_peers = self.peers(gid)
        seeder_peers = sum(1 for p in canli_peers if p.get("seeder"))
        leech_peers = len(canli_peers) - seeder_peers

        return {
            "hazir_degil": False,
            "gid": gid,
            "durum": status.get("status", ""),
            "seeder": is_seeder,
            "num_seeders": num_seeders,
            "connections": connections,
            "download_speed": down_speed,
            "upload_speed": up_speed,
            "completed_length": done,
            "total_length": total,
            "upload_length": uploaded,
            "ratio": ratio,
            "progress": round(done / total * 100, 1) if total else 0.0,
            "tracker_sayisi": tracker_sayisi,
            "havuz_sayisi": len(havuz),
            "canli_tracker": len(trackers.ayikla(str(self.store.get("canli_trackerlar", "")))),
            "peers_toplam": len(canli_peers),
            "peers_seeders": seeder_peers,
            "peers_leechers": leech_peers,
        }

    def servers(self, gid: str) -> list[dict]:
        """HTTP indirmesinde aktif baglanti/parca bilgisi."""
        if gid.startswith(("yt:", "row:")):
            return []
        try:
            return self.rpc.get_servers(gid)
        except Aria2Error:
            return []

    # --- arka plan dongusu ------------------------------------------------
    def _poll_loop(self) -> None:
        while not self._stop.wait(POLL_INTERVAL):
            try:
                self._sync_aria2()
                self._start_due()
                self._smart_queue()
                self._maybe_trackers()
            except Exception as exc:
                self.last_error = str(exc)

    def _smart_queue(self) -> None:
        """Indirme hizi dusukse ve bekleyen is varsa eslik sınırını artır."""
        try:
            stat = self.rpc.global_stat()
            num_active = int(stat.get("numActive", 0))
            num_waiting = int(stat.get("numWaiting", 0))
            base_limit = int(self.store.get("max_concurrent", 5))
            if num_waiting > 0 and num_active > 0:
                speed = int(stat.get("downloadSpeed", 0))
                speed += sum(
                    j.speed for j in self.video_jobs.values()
                    if j.status == "active"
                )
                if speed < 1024 * 1024:  # 1 MB/s altinda
                    new_limit = min(20, num_active + 1)
                    current_opt = self.rpc.get_global_option()
                    if int(current_opt.get("max-concurrent-downloads", base_limit)) < new_limit:
                        self.rpc.change_global_option({"max-concurrent-downloads": str(new_limit)})
                    return
            current_opt = self.rpc.get_global_option()
            cur = int(current_opt.get("max-concurrent-downloads", base_limit))
            if cur > base_limit:
                speed = int(stat.get("downloadSpeed", 0))
                speed += sum(
                    j.speed for j in self.video_jobs.values()
                    if j.status == "active"
                )
                if num_waiting == 0 or speed >= 1024 * 1024:
                    self.rpc.change_global_option({"max-concurrent-downloads": str(base_limit)})
        except Exception:
            pass

    def _sync_aria2(self) -> None:
        try:
            statuses = self.rpc.tell_active() + self.rpc.tell_stopped(0, 100)
        except Aria2Error:
            return
        for status in statuses:
            gid = status.get("gid", "")
            row = self.store.by_gid(gid)
            if row is None:
                row = self._reattach_torrent(status)
            total = int(status.get("totalLength", 0) or 0)
            done = int(status.get("completedLength", 0) or 0)
            state = status.get("status", "")
            files = status.get("files") or []
            name = Path(files[0].get("path", "")).name if files else ""
            if row:
                fields: dict = {
                    "total_bytes": total,
                    "done_bytes": done,
                    "status": state,
                }
                if name:
                    fields["filename"] = name
                if state == "error":
                    fields["error"] = status.get("errorMessage", "")[:500]
                    fields["finished_at"] = time.time()
                if state == "complete":
                    fields["finished_at"] = time.time()
                    self._cerez_birak(row)
                self.store.update_by_gid(gid, **fields)
            # magnet -> gercek torrent: aria2 yeni GID uretir, kaydi tasiyoruz
            followed = status.get("followedBy") or []
            if followed and row:
                child = followed[0]
                if not self.store.by_gid(child):
                    tercih_var = self.store.torrent_dosya_secimi_var(gid)
                    secilenler = self.store.torrent_dosya_secimleri(gid)
                    self.store.update_by_id(row["id"], gid=child, status="active")
                    self.store.torrent_dosya_secimlerini_tasi(gid, child)
                    if tercih_var:
                        try:
                            self.rpc.change_option(child, {
                                "select-file": self._select_file_degeri(secilenler)
                            })
                        except Aria2Error as exc:
                            self.store.log("warn", f"magnet dosya secimi uygulanamadi: {exc}", gid=child)
            if state == "complete" and gid not in self._known_complete and not followed:
                self._known_complete.add(gid)
                title = name or (row["title"] if row else gid)
                self._on_complete(title, total, gid)

    def _reattach_torrent(self, status: dict) -> dict | None:
        """Yeniden baslatmada magnet'in GID'i DEGISIR ve kayit sahipsiz kalir.

        aria2 oturumdan magneti yeniden okur: once YENI bir ustveri GID'i, sonra
        YENI bir torrent GID'i uretir. Veritabanindaki gid ikisine de uymaz, bu
        yuzden indirme calissa bile kayit guncellenmez (listede kimliksiz gorunur,
        bitince "tamamlandi" yazilmaz, ayni magnet "zaten kuyrukta" der).
        Cozum: info hash DEGISMEZ — kaydi onunla bul ve yeni GID'e bagla.
        """
        infohash = (status.get("infoHash") or "").lower()
        if not infohash:
            return None
        for row in self.store.list(limit=300):
            if row["kind"] != "torrent" or row["status"] not in self.ACTIVE_STATES:
                continue
            if self.magnet_infohash(row["source"]) != infohash:
                continue
            yeni_gid = status.get("gid", "")
            self.store.update_by_id(row["id"], gid=yeni_gid)
            self.store.log("info", f"torrent kaydi yeniden baglandi: {row['title']}", gid=yeni_gid)
            return self.store.by_id(row["id"])
        return None

    def _start_due(self) -> None:
        for row in self.store.due_scheduled():
            try:
                self.store.update_by_id(row["id"], status="queued")
                self._launch(self.store.by_id(row["id"]))  # type: ignore[arg-type]
            except Exception as exc:
                self.store.log("error", f"zamanlanmis is basarisiz: {exc}", gid=row.get("gid", "") or "")

    def _maybe_trackers(self) -> None:
        if not self.store.get("auto_update_trackers"):
            return
        now = time.time()
        if now - self._last_tracker_check < TRACKER_CHECK_INTERVAL:
            return
        self._last_tracker_check = now
        if not trackers.is_fresh():
            threading.Thread(target=self._refresh_trackers, daemon=True).start()
        # Olu tracker ayiklama da gunde bir: 192 adresin 151'i oluydu (olculdu)
        if self.store.get("tracker_otomatik_tara"):
            from . import tracker_saglik
            if not tracker_saglik.taze_mi(self.store):
                threading.Thread(target=self._tracker_saglik_tara, daemon=True).start()

    def _tracker_saglik_tara(self) -> None:
        # Aktif torrent varsa onun hash'iyle tara; boylece onu taniyanlar one
        # gelir. Sonuc tracker_tara icinde aria2'ye hemen uygulanir.
        gid = ""
        try:
            aktif = self.rpc.tell_active()
            if aktif:
                gid = aktif[0].get("gid", "")
        except Aria2Error:
            pass
        sonuc = self.tracker_tara(gid)
        if not sonuc.get("ok"):
            self.store.log("warn", f"tracker taramasi basarisiz: {sonuc.get('error', '')}"[:150], gid=gid or "")

    # --- bitis islemleri --------------------------------------------------
    def _on_complete(self, title: str, size: int, gid: str = "") -> None:
        self.store.log("info", f"tamamlandi: {title} ({human_size(size)})", gid=gid or "")
        self.automation.enqueue_download(gid, self.store.by_gid(gid))
        if self.store.get("windows_notifications") and callable(self.windows_notify):
            try: self.windows_notify("AfuDM", f"Indirme tamamlandi: {title}")
            except Exception: pass

        if self.store.get("notify_telegram"):
            threading.Thread(
                target=self.notify_telegram,
                args=(
                    lang.t("notify.done", str(self.store.get("language", "auto")))
                    + "\n" + title + "\n" + human_size(size),
                ),
                daemon=True,
            ).start()
        if self.store.get("shutdown_when_done") and self._all_idle():
            self.store.log("warn", "tum isler bitti — bilgisayar kapatiliyor (60 sn)")
            subprocess.Popen(
                ["shutdown", "/s", "/t", "60", "/c", "AfuDM: indirmeler bitti"],
                creationflags=0x08000000,
            )
        elif self.store.get("sleep_when_done") and self._all_idle():
            # Kapatma DEGIL uyku: uyanista Windows sifresi istenmez ve AfuDM
            # zaten calisiyor olur (bkz. core/guc.py). Once 20 sn bekleriz ki
            # kullanici "vazgectim" derse duraklatabilsin.
            self.store.log("warn", "tum isler bitti — bilgisayar 20 sn sonra uyutuluyor")
            threading.Timer(20.0, self._uyut_gerekirse).start()

    def _uyut_gerekirse(self) -> None:
        """Bekleme bitince HALA bos mu? Yeni is geldiyse uyutma."""
        if not self.store.get("sleep_when_done") or not self._all_idle():
            self.store.log("info", "uyutma iptal: yeni is var")
            return
        from . import guc
        if not guc.uyut():
            self.store.log("warn", "uyutma basarisiz (guc ayarlari engelliyor olabilir)")

    def _all_idle(self) -> bool:
        try:
            if self.rpc.tell_active() or self.rpc.tell_waiting(0, 5):
                return False
        except Aria2Error:
            pass
        return not any(j.status == "active" for j in self.video_jobs.values())

    def notify_telegram(self, text: str) -> bool:
        token = self.store.get("telegram_bot_token") or os.environ.get(
            "TELEGRAM_BOT_TOKEN", ""
        )
        chat_id = self.store.get("telegram_chat_id")
        if not token or not chat_id:
            return False
        payload = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        ).encode()
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            with urllib.request.urlopen(url, data=payload, timeout=15) as resp:
                return resp.status == 200
        except Exception:
            return False
