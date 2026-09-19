"""Kalici, idempotent indirme-sonrasi otomasyon worker'i."""
from __future__ import annotations
import hashlib, os, shlex, shutil, subprocess, threading, time
from pathlib import Path
from . import guc

ACTION_LABELS = {"checksum":"checksum", "extract":"extract", "move":"move", "rename":"rename", "script":"script", "notify":"notify", "power":"power"}

class AutomationWorker:
    def __init__(self, store, notify):
        self.store, self.notify = store, notify
        self.stop_event, self.wake = threading.Event(), threading.Event()
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self._loop, name="AfuDMAutomation", daemon=True); self.thread.start()

    def stop(self): self.stop_event.set(); self.wake.set()

    def enqueue_download(self, gid: str, row: dict | None):
        if not self.store.get("automation_enabled") or not row: return
        options = __import__("json").loads(row.get("options") or "{}")
        for action in self.store.get("automation_steps", []):
            if action == "checksum" and not (self.store.get("automation_checksum") and options.get("checksum")): continue
            if action == "extract" and not self.store.get("automation_extract"): continue
            if action == "move" and not self.store.get("automation_move_to"): continue
            if action == "rename" and not self.store.get("automation_rename_to"): continue
            if action == "script" and not self.store.get("automation_script"): continue
            if action == "notify" and not self.store.get("automation_notify"): continue
            if action == "power" and self.store.get("automation_power") not in ("sleep", "shutdown"): continue
            self.store.automation_enqueue(gid, action, {"path": str(Path(row.get("dest_dir") or "") / (row.get("filename") or "")), "checksum": options.get("checksum", "")})
        self.wake.set()

    def retry(self, job_id): self.store.automation_retry(int(job_id)); self.wake.set(); return self.store.automation_jobs_by_id(int(job_id))
    def cancel(self, job_id):
        job=self.store.automation_jobs_by_id(int(job_id)); self.store.automation_cancel(int(job_id))
        if job and job["action"] == "power": subprocess.run(["shutdown", "/a"], capture_output=True, creationflags=0x08000000)
        return self.store.automation_jobs_by_id(int(job_id))

    def _loop(self):
        while not self.stop_event.is_set():
            job=self.store.automation_claim()
            if not job: self.wake.wait(1); self.wake.clear(); continue
            try: self._run(job)
            except Exception as exc: self.store.automation_update(job["id"], status="error", error=str(exc)[:300], finished_at=time.time())

    def _run(self, job):
        if job.get("status") == "cancelled": return
        action, p = job["action"], job["payload"]; path=Path(p.get("path") or "")
        self.store.automation_update(job["id"], progress=10)
        if action == "checksum":
            spec=str(p.get("checksum") or ""); algo, _, expected=spec.partition(":")
            if not expected: raise ValueError("checksum beklenen değer içermiyor")
            digest=hashlib.new(algo.replace("-", ""));
            with path.open("rb") as f:
                for block in iter(lambda:f.read(1024*1024), b""): digest.update(block)
            if digest.hexdigest().lower()!=expected.lower(): raise ValueError("checksum doğrulaması başarısız")
        elif action == "extract":
            if not path.exists(): raise ValueError("arşiv dosyası bulunamadı")
            shutil.unpack_archive(str(path), str(path.with_suffix("")))
        elif action == "move":
            target=Path(str(self.store.get("automation_move_to"))).expanduser(); target.mkdir(parents=True, exist_ok=True); new=target/path.name
            if path.resolve()!=new.resolve(): shutil.move(str(path), str(new)); p["path"]=str(new)
        elif action == "rename":
            template=str(self.store.get("automation_rename_to")).strip(); new=path.with_name(template.replace("{name}", path.stem).replace("{ext}", path.suffix))
            if new.name and path.exists() and path!=new: path.rename(new); p["path"]=str(new)
        elif action == "script":
            command=str(self.store.get("automation_script")).strip()
            if not command: raise ValueError("script komutu ayarlanmamış")
            # shell yok: komut yalnızca kullanıcının açıkça yazdığı metinden ayrıştırılır.
            subprocess.run(shlex.split(command, posix=False), cwd=str(path.parent), check=True, capture_output=True, timeout=300, creationflags=0x08000000)
        elif action == "notify": self.notify("AfuDM otomasyon tamamlandı: " + path.name)
        elif action == "power":
            seconds=max(5, int(self.store.get("automation_power_seconds") or 60)); self.store.automation_update(job["id"], progress=20)
            for left in range(seconds, 0, -1):
                current=self.store.automation_jobs_by_id(job["id"])
                if not current or current["status"] == "cancelled": return
                self.store.automation_update(job["id"], progress=max(20, int((seconds-left)*80/seconds)))
                time.sleep(1)
            if self.store.get("automation_power") == "shutdown": subprocess.Popen(["shutdown","/s","/t","0","/c","AfuDM otomasyonu"], creationflags=0x08000000)
            else: guc.uyut()
        self.store.automation_update(job["id"], payload=__import__("json").dumps(p), status="complete", progress=100, finished_at=time.time())
