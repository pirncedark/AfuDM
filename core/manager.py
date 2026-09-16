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

from . import lang, paths, trackers
from .daemon import Aria2Daemon
from .db import Store
from .rpc import Aria2Error

POLL_INTERVAL = 0.5
TRACKER_CHECK_INTERVAL = 3600.0


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
        self.last_error: str = ""

    # --- yasam dongusu ----------------------------------------------------
    def start(self) -> None:
        self.rpc = self.daemon.start()
        self.apply_settings()
        if self.store.get("auto_update_trackers"):
            threading.Thread(target=self._refresh_trackers, daemon=True).start()
        self._poller = threading.Thread(target=self._poll_loop, daemon=True)
        self._poller.start()
        self.store.log("info", "AfuDM basladi")

    def stop(self) -> None:
        self._stop.set()
        for job in list(self.video_jobs.values()):
            if job.status == "active":
                job.stop()
        self.daemon.stop()
        self.store.log("info", "AfuDM kapandi")

    def _refresh_trackers(self, force: bool = False) -> None:
        try:
            count = trackers.apply_to_aria2(self.rpc, force=force)
            if count:
                self.store.log("info", f"{count} guncel tracker uygulandi")
        except Exception as exc:  # aglar kopabilir, uygulamayi dusurmesin
            self.store.log("warn", f"tracker guncellenemedi: {exc}")

    # --- ayarlar ----------------------------------------------------------
    def apply_settings(self) -> None:
        settings = self.store.all_settings()
        limit = int(settings.get("max_speed_kb") or 0)
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

    def update_settings(self, changes: dict) -> dict:
        for key, value in changes.items():
            self.store.set(key, value)
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

    def find_duplicate(self, source: str) -> dict | None:
        """Ayni is kuyrukta duruyor mu? Magnet icin info hash, digerleri icin
        adres karsilastirilir."""
        infohash = self.magnet_infohash(source)
        if infohash:
            for item in self.snapshot()["items"]:
                if (item.get("infoHash") or "").lower() == infohash:
                    return item
        for row in self.store.list(limit=300):
            if row["status"] not in self.ACTIVE_STATES:
                continue
            if row["source"] == source:
                return row
            if infohash and self.magnet_infohash(row["source"]) == infohash:
                return row
        return None

    @staticmethod
    def guess_name(source: str) -> str:
        if source.lower().startswith("magnet:"):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(source).query)
            name = query.get("dn", [""])[0]
            return name or "magnet baglantisi"
        path = urllib.parse.urlparse(source).path
        return urllib.parse.unquote(Path(path).name) or source[:60]

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
    def add(
        self,
        source: str,
        kind: str | None = None,
        dest_dir: str | None = None,
        quality: str | None = None,
        audio_only: bool = False,
        playlist: bool = False,
        start_after: float | None = None,
        headers: dict | None = None,
        filename: str | None = None,
    ) -> dict:
        source = source.strip()
        if not source:
            raise ValueError("bos link")
        kind = kind or self.detect_kind(source)
        duplicate = self.find_duplicate(source)
        if duplicate:
            label = "bu torrent" if kind == "torrent" else "bu baglanti"
            raise ValueError(f"{label} zaten kuyrukta: {duplicate.get('title') or source[:60]}")
        dest_dir = dest_dir or self.current_download_dir()
        Path(dest_dir).mkdir(parents=True, exist_ok=True)
        options = {
            "quality": quality or self.store.get("video_quality", "best"),
            "audio_only": audio_only,
            "playlist": playlist,
            "headers": headers or {},
            "filename": filename or "",
        }
        row_id = self.store.add(
            kind=kind,
            source=source,
            title=self.guess_name(source),
            dest_dir=dest_dir,
            options=options,
            start_after=start_after,
        )
        if start_after:
            when = time.strftime("%H:%M", time.localtime(start_after))
            self.store.log("info", f"zamanlandi ({when}): {source[:80]}")
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
            self.store.log("error", f"baslatilamadi: {exc}")
            raise
        self.store.attach_gid(row["id"], gid)
        self.store.log("info", f"basladi [{kind}]: {row['title']}")
        return {"id": row["id"], "gid": gid, "kind": kind}

    def _launch_http(self, row: dict, options: dict, dest_dir: str) -> str:
        aria_options: dict[str, object] = {"dir": dest_dir}
        if options.get("filename"):
            aria_options["out"] = options["filename"]
        headers = options.get("headers") or {}
        if headers:
            aria_options["header"] = [f"{k}: {v}" for k, v in headers.items()]
        return self.rpc.add_uri([row["source"]], aria_options)

    def _launch_torrent(self, row: dict, dest_dir: str) -> str:
        source = row["source"]
        aria_options = {"dir": dest_dir}
        local = Path(source)
        try:
            if local.exists() and local.suffix.lower() == ".torrent":
                payload = base64.b64encode(local.read_bytes()).decode("ascii")
                return self.rpc.add_torrent(payload, aria_options)
            # magnet veya .torrent URL'si: aria2 --follow-torrent ile devralir
            return self.rpc.add_uri([source], aria_options)
        except Aria2Error as exc:
            # aria2 ayni info hash'i ikinci kez kabul etmez; kullaniciya
            # ham motor mesaji yerine anlasilir bir sey soyle.
            if "already registered" in str(exc).lower():
                raise ValueError("bu torrent zaten kuyrukta") from exc
            raise

    def _launch_video(self, row: dict, options: dict, dest_dir: str) -> str:
        with self._lock:
            self._video_seq += 1
            job_id = f"yt:{self._video_seq}"
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
            fields["finished_at"] = job.finished_at or time.time()
            if job.error:
                fields["error"] = job.error[:500]
        self.store.update_by_gid(job.job_id, **fields)
        if job.status == "complete" and job.job_id not in self._known_complete:
            self._known_complete.add(job.job_id)
            self._on_complete(job.display_title(), job.total)

    # --- video yardimcilari ----------------------------------------------
    def probe_video(self, url: str) -> dict:
        return ytdlp.probe(url)

    # --- kontrol ----------------------------------------------------------
    def pause(self, gid: str) -> bool:
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
        if gid.startswith("yt:"):
            row = self.store.by_gid(gid)
            if not row:
                return False
            self.store.update_by_id(row["id"], status="queued", gid=None)
            self._launch(self.store.by_id(row["id"]))  # type: ignore[arg-type]
            return True
        self.rpc.unpause(gid)
        self.store.update_by_gid(gid, status="active")
        return True

    def remove(self, gid: str, delete_files: bool = False) -> bool:
        row = self.store.by_gid(gid)
        targets: list[Path] = []
        if gid.startswith("yt:"):
            job = self.video_jobs.pop(gid, None)
            if job:
                job.stop()
                if job.filename:
                    targets.append(Path(job.dest_dir) / job.filename)
        else:
            # Silmeden ONCE dosya listesini al: aria2 kaydi silinince kaybolur.
            if delete_files:
                try:
                    for entry in self.rpc.tell_status(gid).get("files") or []:
                        if entry.get("path"):
                            targets.append(Path(entry["path"]))
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
        if row and row.get("filename") and row.get("dest_dir"):
            targets.append(Path(row["dest_dir"]) / row["filename"])
        if delete_files:
            self._delete_targets(targets, row)
        if row:
            self.store.update_by_id(row["id"], status="removed", finished_at=time.time())
        return True

    @staticmethod
    def _delete_targets(targets: list[Path], row: dict | None) -> None:
        """Dosyalari ve aria2'nin .aria2 kontrol dosyalarini birlikte temizle;
        yarim kalmis indirmeler klasorde iz birakmasin."""
        for target in targets:
            for candidate in (target, Path(str(target) + ".aria2")):
                try:
                    candidate.unlink(missing_ok=True)
                except OSError:
                    pass
            # Cok dosyali torrent: kontrol dosyasi klasorun YANINDA durur
            # (downloads/Sintel/... icin downloads/Sintel.aria2), klasor
            # bosaldiysa klasorun kendisi de gitmeli.
            try:
                parent = target.parent
                base = Path(row["dest_dir"]).resolve() if row and row.get("dest_dir") else None
                if base and parent.resolve() != base:
                    Path(str(parent) + ".aria2").unlink(missing_ok=True)
                    if parent.is_dir() and not any(parent.iterdir()):
                        parent.rmdir()
            except OSError:
                pass

    def pause_all(self) -> None:
        try:
            self.rpc.pause_all()
        except Aria2Error:
            pass
        for gid in list(self.video_jobs):
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
        for status in live:
            gid = status.get("gid", "")
            gids_seen.add(gid)
            if self.is_metadata_only(status):
                continue
            items.append(self._shape_aria2(status))
        for job in self.video_jobs.values():
            gids_seen.add(job.job_id)
            row = self.store.by_gid(job.job_id)
            shaped = job.to_dict()
            shaped["id"] = row["id"] if row else None
            shaped["progress"] = (
                round(job.downloaded / job.total * 100, 1) if job.total else 0.0
            )
            items.append(shaped)
        # aria2 oturumu unutmus olabilir: DB'deki bitmis/zamanlanmis kayitlar
        for row in self.store.list(limit=200):
            if row["gid"] and row["gid"] in gids_seen:
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
                self._maybe_trackers()
            except Exception as exc:
                self.last_error = str(exc)

    def _sync_aria2(self) -> None:
        try:
            statuses = self.rpc.tell_active() + self.rpc.tell_stopped(0, 100)
        except Aria2Error:
            return
        for status in statuses:
            gid = status.get("gid", "")
            row = self.store.by_gid(gid)
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
                self.store.update_by_gid(gid, **fields)
            # magnet -> gercek torrent: aria2 yeni GID uretir, kaydi tasiyoruz
            followed = status.get("followedBy") or []
            if followed and row:
                child = followed[0]
                if not self.store.by_gid(child):
                    self.store.update_by_id(row["id"], gid=child, status="active")
            if state == "complete" and gid not in self._known_complete and not followed:
                self._known_complete.add(gid)
                title = name or (row["title"] if row else gid)
                self._on_complete(title, total)

    def _start_due(self) -> None:
        for row in self.store.due_scheduled():
            try:
                self.store.update_by_id(row["id"], status="queued")
                self._launch(self.store.by_id(row["id"]))  # type: ignore[arg-type]
            except Exception as exc:
                self.store.log("error", f"zamanlanmis is basarisiz: {exc}")

    def _maybe_trackers(self) -> None:
        if not self.store.get("auto_update_trackers"):
            return
        now = time.time()
        if now - self._last_tracker_check < TRACKER_CHECK_INTERVAL:
            return
        self._last_tracker_check = now
        if not trackers.is_fresh():
            threading.Thread(target=self._refresh_trackers, daemon=True).start()

    # --- bitis islemleri --------------------------------------------------
    def _on_complete(self, title: str, size: int) -> None:
        self.store.log("info", f"tamamlandi: {title} ({human_size(size)})")
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
