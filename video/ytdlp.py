"""yt-dlp sarmalayici: video/ses indirme, kalite secimi, playlist.

Indirme motoru olarak aria2c'yi kullandirir (--downloader), boylece video
siteleri de cok parcali indirilir. Ilerleme, yt-dlp'nin progress-template
ciktisindan satir satir okunur.
"""
from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from core import lang, netcheck, paths
from . import mp4mux

CREATE_NO_WINDOW = 0x08000000
PROGRESS_TAG = "AFUDM"
PROGRESS_TEMPLATE = (
    PROGRESS_TAG
    + "|%(progress.downloaded_bytes)s|%(progress.total_bytes)s"
    + "|%(progress.total_bytes_estimate)s|%(progress.speed)s|%(progress.eta)s"
)

# ffmpeg VARKEN: en iyi video + en iyi ses ayri inip mp4'e birlestirilir.
QUALITY_FORMATS = {
    "best": "bestvideo*+bestaudio/best",
    "2160": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
    "1440": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
    "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "audio": "bestaudio/best",
}

# ffmpeg YOKKEN: yt-dlp birlestiremez ama BIZ birlestirebiliriz (video/mp4mux.py).
# Bu yuzden iki izi de MP4 ailesinden isteriz — video mp4, ses m4a — yt-dlp ikisini
# ayri dosya olarak birakir, isi biz bitiririz.
# Son care olarak birlesik bir format, en sonda yt-dlp'nin kendi secimi durur;
# boylece hicbir kosulda sessiz video inmez.
_KENDI_MUX = ("bv*{h}[ext=mp4]+ba[ext=m4a]/"
              "best{h}[ext=mp4][acodec!=none][vcodec!=none]/"
              "best{h}[acodec!=none][vcodec!=none]/best{h}")
COMBINED_FORMATS = {
    "best": _KENDI_MUX.format(h=""),
    "2160": _KENDI_MUX.format(h="[height<=2160]"),
    "1440": _KENDI_MUX.format(h="[height<=1440]"),
    "1080": _KENDI_MUX.format(h="[height<=1080]"),
    "720": _KENDI_MUX.format(h="[height<=720]"),
    "480": _KENDI_MUX.format(h="[height<=480]"),
    "audio": "bestaudio[ext=m4a]/bestaudio/best",
}


def ffmpeg_hazir() -> bool:
    """engine/ffmpeg.exe (veya sistemdeki ffmpeg) var mi?"""
    return Path(paths.ffmpeg_exe()).exists()


def format_secimi(quality: str, audio_only: bool, birlestirilebilir: bool) -> str:
    """yt-dlp'ye verilecek -f ifadesi.

    birlestirilebilir=False ise ayri video+ses ISTENMEZ; yoksa kullanici
    sessiz video indirir. Bu, ffmpeg'siz (cekirdek) kurulumun davranisidir.
    """
    if audio_only or quality == "audio":
        quality = "audio"
    if quality and quality.isdigit() and quality not in QUALITY_FORMATS:
        # Video panelinden gelen keyfi yukseklik (360, 540...): tabloda yoksa
        # "best"e DUSMESIN, o yukseklige gore sec.
        h = f"[height<={int(quality)}]"
        if birlestirilebilir:
            return f"bestvideo{h}+bestaudio/best{h}"
        return _KENDI_MUX.format(h=h)
    tablo = QUALITY_FORMATS if birlestirilebilir else COMBINED_FORMATS
    return tablo.get(quality, tablo["best"])


def guvenli_ad(ad: str, sinir: int = 150) -> str:
    """Windows dosya adinda yasak karakterleri at, sonundaki nokta/bosluk kirp."""
    temiz = "".join("_" if ch in '<>:"/\|?*' or ord(ch) < 32 else ch for ch in ad)
    temiz = " ".join(temiz.split())[:sinir].rstrip(". ")
    return temiz or "video"


def ytdlp_path() -> str:
    """Portable: engine/yt-dlp.exe; yoksa sistemdeki yt-dlp."""
    return paths.ytdlp_exe()


def available() -> bool:
    try:
        subprocess.run(
            [ytdlp_path(), "--version"],
            capture_output=True,
            timeout=20,
            creationflags=CREATE_NO_WINDOW,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def version() -> str:
    try:
        out = subprocess.run(
            [ytdlp_path(), "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            creationflags=CREATE_NO_WINDOW,
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def is_video_site(url: str) -> bool:
    """Dosya linki mi, video sayfasi mi? Kaba ama pratik ayrim."""
    lowered = url.lower().split("?")[0]
    if lowered.endswith(
        (
            ".zip", ".rar", ".7z", ".exe", ".msi", ".iso", ".pdf", ".apk",
            ".dmg", ".tar", ".gz", ".torrent", ".deb", ".rpm", ".img",
        )
    ):
        return False
    if url.startswith("magnet:"):
        return False
    hints = (
        "youtube.com", "youtu.be", "instagram.com", "tiktok.com", "twitter.com",
        "x.com", "facebook.com", "vimeo.com", "dailymotion.com", "twitch.tv",
        "reddit.com", "soundcloud.com", "bilibili.com", "odnoklassniki",
        "vk.com", "pinterest.com", "linkedin.com", "threads.net", "rumble.com",
    )
    if any(h in lowered for h in hints):
        return True
    return ".m3u8" in lowered or ".mpd" in lowered


def probe(url: str, timeout: float = 90.0) -> dict:
    """Video bilgisi + format listesi (indirmeden once kalite secimi icin)."""
    cmd = [
        ytdlp_path(), "-J", "--no-warnings", "--no-playlist",
        # --encoding OLMADAN yt-dlp ciktisini Windows konsol kod sayfasiyla yazar
        # ve Turkce harfler '?' olur ("KANALI GERI" -> "KANALI GER?"); OLCULDU.
        "--encoding", "utf-8",
        "--flat-playlist", url,
    ]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, creationflags=CREATE_NO_WINDOW,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "yt-dlp bilgi alamadi").strip()[:500])
    data = json.loads(proc.stdout)
    formats = []
    for fmt in data.get("formats") or []:
        formats.append(
            {
                "id": fmt.get("format_id"),
                "ext": fmt.get("ext"),
                "height": fmt.get("height"),
                "fps": fmt.get("fps"),
                "vcodec": fmt.get("vcodec"),
                "acodec": fmt.get("acodec"),
                "filesize": fmt.get("filesize") or fmt.get("filesize_approx"),
                "note": fmt.get("format_note"),
            }
        )
    return {
        "title": data.get("title") or url,
        "duration": data.get("duration"),
        "thumbnail": data.get("thumbnail"),
        "uploader": data.get("uploader"),
        "is_playlist": data.get("_type") == "playlist",
        "entries": len(data.get("entries") or []) if data.get("entries") else 0,
        "formats": formats,
    }


@dataclass
class VideoJob:
    """Calisan bir yt-dlp indirmesi. aria2 GID'i yoktur; id'si 'yt:<n>' olur."""

    job_id: str
    url: str
    dest_dir: str
    quality: str = "best"
    audio_only: bool = False
    playlist: bool = False
    title: str = ""
    proc: subprocess.Popen | None = None
    status: str = "active"          # active | paused | complete | error | removed
    error: str = ""
    downloaded: int = 0
    total: int = 0
    speed: int = 0
    eta: int = 0
    filename: str = ""
    dil: str = "auto"               # hata metinleri bu dilde yazilir
    parca_dosyalari: list[str] = field(default_factory=list)  # ffmpeg'siz birlestirme icin
    ffmpeg_vardi: bool = True       # is baslarken ffmpeg var miydi (hata metni icin)
    cookie_file: str = ""           # tarayicidan gelen oturum cerezleri (core/cerez.py)
    user_agent: str = ""
    headers: dict = field(default_factory=dict)  # Referer vb. (gomulu oynaticilar ister)
    dosya_adi: str = ""             # sayfa basligi; bossa yt-dlp'nin basligi
    started_at: float = field(default_factory=time.time)
    finished_at: float = 0.0
    _thread: threading.Thread | None = None
    _stop: bool = False
    # aria2c dis indirici dusunce yt-dlp'nin KENDI indiricisiyle bir kez daha denenir
    _yedek_denendi: bool = False
    _aria2c: str | None = None

    # --- komut kurulumu ---------------------------------------------------
    def build_cmd(self, aria2c: str | None = None, ffmpeg_var: bool | None = None,
                  dis_indirici: bool = True) -> list[str]:
        aria2c = (aria2c or str(paths.ARIA2C)) if dis_indirici else ""
        # ffmpeg yoksa birlestirme de mp3'e cevirme de yapilamaz; format secimi buna gore.
        ffmpeg_var = ffmpeg_hazir() if ffmpeg_var is None else ffmpeg_var
        self.ffmpeg_vardi = ffmpeg_var
        fmt = format_secimi(self.quality, self.audio_only, ffmpeg_var)
        govde = "%(title).150B"
        if self.dosya_adi:
            # Sablonda % ozel: kullanici metnindeki % iki katlanir.
            govde = guvenli_ad(self.dosya_adi).replace("%", "%%")
        out_tpl = str(Path(self.dest_dir) / f"{govde}.%(ext)s")
        if self.playlist:
            out_tpl = str(
                Path(self.dest_dir)
                / "%(playlist_title).80B"
                / "%(playlist_index)03d - %(title).120B.%(ext)s"
            )
        cmd = [
            ytdlp_path(),
            "--newline",
            "--no-warnings",
            # Ciktinin kodlamasi: bkz. probe(). Dosya adi satiri buradan okunuyor.
            "--encoding", "utf-8",
            "--progress",
            "--progress-template", PROGRESS_TEMPLATE,
            "--continue",
            "--no-overwrites",
            "--retries", "10",
            "--fragment-retries", "10",
            "--concurrent-fragments", "8",
            "-o", out_tpl,
            "-f", fmt,
        ]
        if ffmpeg_var:
            cmd += ["--ffmpeg-location", paths.ffmpeg_dir()]
            if self.audio_only or self.quality == "audio":
                cmd += ["--extract-audio", "--audio-format", "mp3", "--audio-quality", "0"]
            else:
                # Tek dosya mp4 cikar (IDM gibi): ayri inen izler birlestirilir.
                cmd += ["--merge-output-format", "mp4"]
        # ffmpeg yoksa hicbiri istenmez: video zaten birlesik iner, ses de
        # kaynaktaki bicimiyle (m4a/webm) kalir.
        cmd += ["--yes-playlist"] if self.playlist else ["--no-playlist"]
        if self.cookie_file:
            cmd += ["--cookies", self.cookie_file]
        if self.user_agent:
            cmd += ["--user-agent", self.user_agent]
        for anahtar, deger in (self.headers or {}).items():
            if anahtar.lower() == "referer":
                cmd += ["--referer", str(deger)]
            elif anahtar.lower() not in ("cookie", "user-agent"):
                cmd += ["--add-header", f"{anahtar}:{deger}"]
        if aria2c and Path(aria2c).exists():
            # Video parcalarini da cok baglantili indir.
            # IPv6 yoksa aria2c AAAA adresini deneyip "network unreachable" ile
            # indirmeyi iptal eder; bayrak calisma aninda olculur (netcheck).
            extra = " ".join(netcheck.aria2_ipv6_args())
            args = "aria2c:-x16 -s16 -k1M --file-allocation=none --console-log-level=error"
            if extra:
                args += " " + extra
            cmd += ["--downloader", aria2c, "--downloader-args", args]
        cmd.append(self.url)
        return cmd

    # --- calistirma -------------------------------------------------------
    def start(self, aria2c: str | None = None, on_update=None,
              ffmpeg_var: bool | None = None) -> None:
        Path(self.dest_dir).mkdir(parents=True, exist_ok=True)
        self._aria2c = aria2c
        self._yedek_denendi = False
        self.proc = subprocess.Popen(
            self.build_cmd(aria2c, ffmpeg_var),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=CREATE_NO_WINDOW,
        )
        self._thread = threading.Thread(
            target=self._pump, args=(on_update,), daemon=True
        )
        self._thread.start()

    _DEST_RE = re.compile(r"\[(?:download|Merger|ExtractAudio)\].*?(?:Destination:|to:)\s*(.+)$")
    # aria2c dis indirici olarak calisirken yt-dlp kendi ilerleme satirini
    # BASMAZ; aktaran aria2c oldugu icin ilerleme onun ozet satirindan gelir:
    #   [#da19cb 2.8MiB/9.7MiB(29%) CN:10 DL:3.3MiB ETA:2s]
    _ARIA_RE = re.compile(
        r"\[#\w+\s+(?P<done>[\d.]+)(?P<du>[KMGT]?i?B)"
        r"/(?P<total>[\d.]+)(?P<tu>[KMGT]?i?B)"
        r"\((?P<pct>\d+)%\)"
        r"(?:\s+CN:(?P<cn>\d+))?"
        r"(?:\s+DL:(?P<dl>[\d.]+)(?P<su>[KMGT]?i?B))?"
        r"(?:\s+ETA:(?P<eta>\S+?))?\]"
    )
    _UNITS = {"B": 1, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3, "TiB": 1024**4,
              "KB": 1000, "MB": 1000**2, "GB": 1000**3, "TB": 1000**4}

    @classmethod
    def _bytes(cls, amount: str, unit: str) -> int:
        try:
            return int(float(amount) * cls._UNITS.get(unit, 1))
        except ValueError:
            return 0

    @staticmethod
    def _eta_seconds(text: str | None) -> int:
        """aria2c ETA'si '2s', '1m30s', '1h2m' bicimlerinde gelir."""
        if not text:
            return 0
        total = 0
        for value, unit in re.findall(r"(\d+)([hms])", text):
            total += int(value) * {"h": 3600, "m": 60, "s": 1}[unit]
        return total

    def _parse_aria(self, line: str) -> bool:
        match = self._ARIA_RE.search(line)
        if not match:
            return False
        data = match.groupdict()
        self.downloaded = self._bytes(data["done"], data["du"])
        self.total = self._bytes(data["total"], data["tu"]) or self.total
        if data.get("dl"):
            self.speed = self._bytes(data["dl"], data["su"])
        self.eta = self._eta_seconds(data.get("eta"))
        return True

    def _pump(self, on_update) -> None:
        """Cikti okunur; aria2c ile dusen is yt-dlp'nin KENDI indiricisiyle tekrarlanir.

        aria2c dis indirici bazi CDN'lerde (olculdu: googlevideo) 403 alip
        "exited with code 22" diyor; ayni adres yt-dlp'nin kendi indiricisiyle
        sorunsuz iniyor. Kullaniciya hata gostermeden once bir kez daha denenir:
        hiz icin aria2c, olmazsa calisan yol."""
        while True:
            code, tail = self._akisi_oku(on_update)
            if self._stop:
                self.status = "removed"
                break
            if code == 0:
                if not self.ffmpeg_vardi:
                    self._kendi_birlestir(on_update)
                self.status = "complete"
                if self.total:
                    self.downloaded = self.total
                break
            # Yalniz ARIA2C dustuyse tekrarla: "video yok/ozel" gibi kalici
            # hatalarda ikinci kosu bosuna zaman kaybi olur.
            if (not self._yedek_denendi and self._dis_indirici_vardi()
                    and any("aria2c exited" in satir for satir in tail)):
                self._yedek_denendi = True
                self.downloaded = 0
                self.speed = 0
                self.parca_dosyalari.clear()
                try:
                    self.proc = subprocess.Popen(
                        self.build_cmd(self._aria2c, self.ffmpeg_vardi, dis_indirici=False),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        bufsize=1,
                        creationflags=CREATE_NO_WINDOW,
                    )
                    if on_update:
                        on_update(self)
                    continue
                except OSError:
                    pass                      # yedek de baslatilamadi: hatayi yaz
            self.status = "error"
            ham = " / ".join(tail[-3:])[:500] or f"yt-dlp cikis kodu {code}"
            self.error = self.anlasilir_hata(ham)
            break
        self.speed = 0
        self.finished_at = time.time()
        if on_update:
            on_update(self)

    def _dis_indirici_vardi(self) -> bool:
        """Dusen kosuda aria2c dis indirici kullanildi mi?"""
        yol = self._aria2c or str(paths.ARIA2C)
        return bool(yol) and Path(yol).exists()

    def _akisi_oku(self, on_update) -> tuple[int, list[str]]:
        assert self.proc is not None
        tail: list[str] = []
        buffer = ""
        stream = self.proc.stdout
        assert stream is not None
        while True:
            chunk = stream.read(256)
            if not chunk:
                break
            buffer += chunk
            # aria2c ilerlemeyi \r ile gunceller, yt-dlp \n kullanir: ikisini de bol
            parts = re.split(r"[\r\n]", buffer)
            buffer = parts.pop()
            for line in parts:
                line = line.strip()
                if not line:
                    continue
                if line.startswith(PROGRESS_TAG + "|"):
                    self._parse_progress(line)
                    if on_update:
                        on_update(self)
                    continue
                if self._parse_aria(line):
                    if on_update:
                        on_update(self)
                    continue
                match = self._DEST_RE.search(line)
                if match:
                    hedef = match.group(1).strip()
                    self.filename = Path(hedef).name
                    if hedef not in self.parca_dosyalari:
                        self.parca_dosyalari.append(hedef)
                tail.append(line)
                del tail[:-30]
        if buffer.strip():
            if not self._parse_aria(buffer.strip()):
                tail.append(buffer.strip())
        return self.proc.wait(), tail

    @staticmethod
    def _num(value: str) -> int:
        try:
            if value in ("NA", "None", ""):
                return 0
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    def _parse_progress(self, line: str) -> None:
        parts = line.split("|")
        if len(parts) < 6:
            return
        _, done, total, total_est, speed, eta = parts[:6]
        self.downloaded = self._num(done)
        self.total = self._num(total) or self._num(total_est) or self.total
        self.speed = self._num(speed)
        self.eta = self._num(eta)

    def _kendi_birlestir(self, on_update=None) -> None:
        """ffmpeg yokken iki izi KENDI birlestiricimizle tek mp4'e cevirir.

        yt-dlp ffmpeg bulamayinca "formatlar birlestirilmeyecek" deyip iki dosyayi
        (ornegin Baslik.f137.mp4 + Baslik.f140.m4a) OLDUGU GIBI birakir. Burasi o
        iki dosyayi alip tek dosya yapar ve parcalari siler.

        Basarisiz olursa indirmeyi HATAYA DUSURMEZ: parcalar diskte kalir, kullanici
        en azindan videoya ve sese ayri ayri sahiptir."""
        if len(self.parca_dosyalari) != 2:
            return
        yollar = [Path(d) for d in self.parca_dosyalari]
        if not all(y.exists() for y in yollar):
            return
        try:
            izler = [(y, mp4mux.izi_oku(y)) for y in yollar]
        except Exception:
            return          # MP4 ailesinden degil (webm vb.) — dokunma
        video = next((y for y, iz in izler if iz.tur == "vide"), None)
        ses = next((y for y, iz in izler if iz.tur == "soun"), None)
        if video is None or ses is None:
            return
        # "Baslik.f137.mp4" -> "Baslik.mp4"
        taban = re.sub(r"\.f\d+$", "", video.stem)
        hedef = video.with_name(taban + ".mp4")
        if hedef.exists() and hedef not in (video, ses):
            hedef = video.with_name(taban + " (birlesik).mp4")
        try:
            gecici = hedef.with_suffix(".mp4.yarim")
            mp4mux.birlestir(video, ses, gecici)
            gecici.replace(hedef)
            for y in (video, ses):
                try:
                    y.unlink()
                except OSError:
                    pass
            self.filename = hedef.name
            if on_update:
                on_update(self)
        except Exception as exc:
            # Parcalar duruyor; kullanici kaybetmesin diye sessizce birak.
            self.error = "birlestirilemedi: %s" % str(exc)[:160]

    def anlasilir_hata(self, ham: str) -> str:
        """yt-dlp'nin ham hatasini kullanicinin anlayacagi cumleye cevirir.

        En sik durum: ffmpeg yokken YouTube'dan video istemek. YouTube artik
        ses+video birlesik format VERMIYOR (2026 olcumu), bu yuzden birlestirici
        olmadan istenen format bulunamiyor. Ham mesaj ("Requested format is not
        available") kullaniciya hicbir sey anlatmiyor."""
        if "requested format is not available" in ham.lower() and not self.ffmpeg_vardi:
            anahtar = "err.needFfmpegAudio" if self.audio_only else "err.needFfmpeg"
            return lang.t(anahtar, self.dil)
        return ham

    # --- kontrol ----------------------------------------------------------
    def stop(self) -> None:
        self._stop = True
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.status = "removed"

    def display_title(self) -> str:
        """Gosterilecek baslik: yt-dlp cikti sablonu "%(title)s.%(ext)s" oldugu
        icin dosya adinin govdesi videonun GERCEK basligidir. Dosya adi daha
        bilinmiyorsa eklerken tahmin edilen ada, o da yoksa URL'e duseriz."""
        if self.filename:
            stem = Path(self.filename).stem
            if stem:
                return stem
        return self.title or self.url

    def to_dict(self) -> dict:
        total = self.total or 0
        return {
            "gid": self.job_id,
            "kind": "video",
            "status": self.status,
            "title": self.display_title(),
            "filename": self.filename,
            "totalLength": total,
            "completedLength": self.downloaded,
            "downloadSpeed": self.speed,
            "uploadSpeed": 0,
            "connections": 0,
            "numSeeders": 0,
            "eta": self.eta,
            "dir": self.dest_dir,
            "errorMessage": self.error,
            "source": self.url,
        }
