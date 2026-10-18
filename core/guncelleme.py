"""AfuDM surumunu GitHub Releases uzerinden indirip guvenle gunceller."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from . import paths, surum

VARSAYILAN_API = "https://api.github.com/repos/pirncedark/AfuDM/releases/latest"
# Indirme yalniz bu depodaki yayin dosyalarindan yapilir.
IZINLI_ONEK = "https://github.com/pirncedark/AfuDM/releases/download/"
ZAMAN_ASIMI = 10


def _istek(url: str):
    req = urllib.request.Request(url, headers={
        "User-Agent": f"AfuDM/{surum.SURUM}",
        "Accept": "application/vnd.github+json",
    })
    return urllib.request.urlopen(req, timeout=ZAMAN_ASIMI)


def _parcala(s: str) -> tuple[int, ...]:
    temiz = str(s or "").strip()
    if temiz.startswith("v"):
        temiz = temiz[1:]
    if not re.fullmatch(r"\d+(?:\.\d+)*", temiz):
        raise ValueError("Gecersiz surum")
    return tuple(int(x) for x in temiz.split("."))


def kontrol(api_url: str = VARSAYILAN_API) -> dict:
    mevcut = surum.SURUM
    try:
        with _istek(api_url) as yanit:
            veri = json.loads(yanit.read().decode("utf-8"))
        if veri.get("draft") or veri.get("prerelease"):
            return {"ok": True, "var": False, "mevcut": mevcut, "yeni": mevcut,
                    "notlar": "", "zip_url": "", "sha_url": ""}
        tag = str(veri.get("tag_name") or "")
        yeni = tag[1:] if tag.startswith("v") else tag
        assets = {a.get("name"): a.get("browser_download_url")
                  for a in veri.get("assets", []) if isinstance(a, dict)}
        zip_name = f"AfuDM-v{yeni}-win64.zip"
        zip_url = assets.get(zip_name)
        sha_url = assets.get(zip_name + ".sha256")
        if not zip_url or not sha_url or not all(
                str(u).startswith(IZINLI_ONEK) for u in (zip_url, sha_url)):
            raise ValueError("Yayin dosyalari bulunamadi")
        var = _parcala(yeni) > _parcala(mevcut)
        return {"ok": True, "var": var, "mevcut": mevcut, "yeni": yeni,
                "notlar": str(veri.get("body") or "")[:600],
                "zip_url": zip_url, "sha_url": sha_url}
    except Exception:
        return {"ok": False, "hata": "Güncelleme denetlenemedi. İnternet bağlantını kontrol et."}


def _indir(url: str, hedef: Path, ilerleme=None) -> None:
    with _istek(url) as yanit, hedef.open("wb") as out:
        toplam = int(yanit.headers.get("Content-Length") or 0)
        inen = 0
        while True:
            blok = yanit.read(128 * 1024)
            if not blok:
                break
            out.write(blok)
            inen += len(blok)
            if ilerleme:
                ilerleme(inen, toplam)


def _guvenli_zip_yolu(ad: str) -> bool:
    p = PurePosixPath(ad.replace("\\", "/"))
    return not p.is_absolute() and not re.match(r"^[A-Za-z]:", ad) and all(
        kisim not in ("..", "") for kisim in p.parts
    )


def indir_ve_dogrula(bilgi: dict, ilerleme=None) -> dict:
    hedef_klasor = paths.DATA / "guncelleme"
    zip_path = hedef_klasor / "AfuDM-guncelleme.zip"
    hazir_kaydi = hedef_klasor / "hazir.json"
    try:
        hazir_kaydi.unlink(missing_ok=True)
        if not bilgi.get("ok") or not bilgi.get("var"):
            raise ValueError
        if not all(str(bilgi.get(key, "")).startswith(IZINLI_ONEK)
                   for key in ("zip_url", "sha_url")):
            raise ValueError("Untrusted release URL")
        surum_yeni = ".".join(str(n) for n in _parcala(bilgi.get("yeni", "")))
        if _parcala(surum_yeni) <= _parcala(surum.SURUM):
            raise ValueError("Update must be newer")
        zip_path = hedef_klasor / f"AfuDM-v{surum_yeni}-win64.zip"
        hedef_klasor.mkdir(parents=True, exist_ok=True)
        _indir(bilgi["zip_url"], zip_path, ilerleme)
        with _istek(bilgi["sha_url"]) as yanit:
            sha_text = yanit.read(4096).decode("ascii", errors="strict")
        eslesme = re.match(r"\s*([0-9a-fA-F]{64})\s+(.+?)\s*$", sha_text)
        if not eslesme or eslesme.group(2) != zip_path.name:
            raise ValueError
        digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        if digest.lower() != eslesme.group(1).lower():
            zip_path.unlink(missing_ok=True)
            return {"ok": False, "hata": "Güncelleme dosyası doğrulanamadı."}

        with zipfile.ZipFile(zip_path) as zf:
            if any(not _guvenli_zip_yolu(item.filename) for item in zf.infolist()):
                raise ValueError
            yeni = hedef_klasor / "yeni"
            if yeni.exists():
                shutil.rmtree(yeni)
            yeni.mkdir(parents=True, exist_ok=True)
            zf.extractall(yeni)
        if not (hedef_klasor / "yeni" / "AfuDM" / "AfuDM.exe").is_file():
            raise ValueError
        paket = hedef_klasor / "yeni" / "AfuDM"
        dosyalar = {p.relative_to(paket).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in paket.rglob("*") if p.is_file()}
        hazir_kaydi.write_text(json.dumps({"surum": surum_yeni, "dosyalar": dosyalar}),
                              encoding="utf-8")
        return {"ok": True, "yol": str(hedef_klasor / "yeni" / "AfuDM")}
    except Exception:
        try:
            zip_path.unlink(missing_ok=True)
        except OSError:
            pass
        return {"ok": False, "hata": "Güncelleme indirilemedi veya dosya bozuk."}


def hazir() -> bool:
    """Only a fully verified, still unchanged newer package can be applied."""
    try:
        klasor = paths.DATA / "guncelleme"
        kayit = json.loads((klasor / "hazir.json").read_text(encoding="utf-8"))
        if _parcala(kayit["surum"]) <= _parcala(surum.SURUM):
            return False
        paket = klasor / "yeni" / "AfuDM"
        dosyalar = kayit["dosyalar"]
        if not isinstance(dosyalar, dict) or "AfuDM.exe" not in dosyalar:
            return False
        mevcut = {p.relative_to(paket).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in paket.rglob("*") if p.is_file() and not p.is_symlink()}
        return mevcut == dosyalar
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _ps_q(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _uygulama_betigi() -> str:
    base, data = paths.BASE, paths.DATA
    source = data / "guncelleme" / "yeni" / "AfuDM"
    backup = data / "guncelleme" / "yedek"
    return f'''$ErrorActionPreference = "Stop"
$base = {_ps_q(base)}
$source = {_ps_q(source)}
$backup = {_ps_q(backup)}
$pidToWait = {os.getpid()}
while (Get-Process -Id $pidToWait -ErrorAction SilentlyContinue) {{ Start-Sleep -Milliseconds 400 }}
$skip = @("data", "downloads", "plugins")
# Yalniz yeni paketin ust duzeyinde bulunan ogeler yedeklenir/degistirilir;
# BASE beklenmedik bir klasor olsa bile baska dosyalara dokunulmaz.
$items = @(Get-ChildItem -LiteralPath $source -Force | Where-Object {{ $skip -notcontains $_.Name }} | ForEach-Object {{ $_.Name }})
# engine: kullanicinin sonradan indirdigi araclar (yt-dlp, ffmpeg) silinmez, yalniz uzerine yazilir.
$merge = @("engine")
if (Test-Path -LiteralPath $backup) {{ Remove-Item -LiteralPath $backup -Recurse -Force }}
New-Item -ItemType Directory -Force -Path $backup | Out-Null
try {{
  foreach ($n in $items) {{ $p = Join-Path $base $n; if (Test-Path -LiteralPath $p) {{ Copy-Item -LiteralPath $p -Destination $backup -Recurse -Force }} }}
}} catch {{
  exit 1
}}
try {{
  foreach ($n in $items) {{
    $p = Join-Path $base $n
    if (($merge -notcontains $n) -and (Test-Path -LiteralPath $p)) {{ Remove-Item -LiteralPath $p -Recurse -Force }}
    if ($merge -contains $n) {{
      New-Item -ItemType Directory -Force -Path $p | Out-Null
      Get-ChildItem -LiteralPath (Join-Path $source $n) -Force | ForEach-Object {{ Copy-Item -LiteralPath $_.FullName -Destination $p -Recurse -Force }}
    }} else {{
      Copy-Item -LiteralPath (Join-Path $source $n) -Destination $base -Recurse -Force
    }}
  }}
}} catch {{
  foreach ($n in $items) {{
    $p = Join-Path $base $n
    $b = Join-Path $backup $n
    if (Test-Path -LiteralPath $b) {{
      if ($merge -contains $n) {{ Get-ChildItem -LiteralPath $b -Force | ForEach-Object {{ Copy-Item -LiteralPath $_.FullName -Destination $p -Recurse -Force }} }}
      else {{ if (Test-Path -LiteralPath $p) {{ Remove-Item -LiteralPath $p -Recurse -Force }}; Copy-Item -LiteralPath $b -Destination $base -Recurse -Force }}
    }}
  }}
  exit 1
}}
Start-Process -FilePath (Join-Path $base "AfuDM.exe")
'''


def uygula(son_kontrol=None) -> dict:
    if not getattr(sys, "frozen", False):
        return {"ok": False, "hata": "Güncelleme yalnız paketli sürümde çalışır."}
    if not hazir():
        return {"ok": False, "hata": "Güncelleme hazır değil. Yeniden indir."}
    try:
        script = paths.DATA / "guncelleme" / "uygula.ps1"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(_uygulama_betigi(), encoding="utf-8-sig")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startup = subprocess.STARTUPINFO() if hasattr(subprocess, "STARTUPINFO") else None
        if startup is not None:
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 0
        # Validation may take time; check transfers again immediately before launch.
        if son_kontrol is not None and not son_kontrol():
            return {"ok": True, "bekle": True}
        subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                          "-WindowStyle", "Hidden", "-File", str(script)],
                         creationflags=flags, startupinfo=startup,
                         close_fds=True)
        return {"ok": True, "kapat": True}
    except Exception:
        return {"ok": False, "hata": "Güncelleme başlatılamadı. Lütfen yeniden dene."}
