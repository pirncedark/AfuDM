# -*- coding: utf-8 -*-
"""AfuDM komut satiri aracı (CLI).

Calisan AfuDM'e yerel HTTP API uzerinden is verir (guvenlik: `api_endpoint.json`
icindeki token). GUI kapaliysa "--tepside" ile arka planda acar ve baglanmayi
bekler — boylece `afuadm add` gercek motoru kullanir, GUI acilmaz.

Ornekler:
    afuadm add https://site.com/buyuk-dosya.zip --category yazilim
    afuadm add "https://youtube.com/watch?v=..." --quality 1080p --audio-only
    afuadm list
    afuadm mode snail              # sinirsizdan 100 KB/s'ye canli dus
    afuadm renew <gid> "https://yeni-gecerli-link.com/dosya.zip"
    afuadm watch --json            # NDJSON canli akis
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import engines, paths, surum  # noqa: E402

CREATE_NO_WINDOW = 0x08000000
BAGLANMA_BEKLEME = 20.0
KILIT_BEKLEME = 10.0

# Cikis kodlari (script'lerin guvenle kullanabilmesi icin SoZLESME):
CC_OK = 0      # basarili
CC_YOK = 2     # AfuDM calismiyor / erisilemiyor (ayrica --no-start'ta baslatmadi)
CC_GID = 3     # istenen kayit/gid bulunamadi
CC_API = 4     # API istegi hata dondurdu


class CliHata(RuntimeError):
    """Bir isi sonlandiran hata. `kod` disariya donen exit kodu olur."""

    def __init__(self, mesaj: str, kod: int = CC_API) -> None:
        super().__init__(mesaj)
        self.kod = kod


def _ciktilari_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def human_size(num: float) -> str:
    for unit in ("KB", "MB", "GB", "TB", "PB"):
        if abs(num) < 1024:
            return "%.1f %s" % (num, unit)
        num /= 1024
    return "%.1f %s" % (num, "EB")


def _servis() -> tuple[int, str]:
    """Calisan AfuDM'in port + token'i. Dosya yoksa [0] ' kosmuyor demektir."""
    try:
        bilgi = json.loads((paths.DATA / "api_endpoint.json").read_text("utf-8"))
        port, token = int(bilgi["port"]), str(bilgi["token"])
    except (OSError, ValueError, KeyError):
        return 0, ""
    return port, token


def _ping(port: int, timeout: float = 1.5) -> bool:
    """Port canli mi + UC DEGERI bu AfuDM'e ait mi? (kimlik sagligi)

    Stale endpoint cope karsi: dosyada eski port yaziyor olabilir; o portta
    baska bir sunucu da dinliyor olabilir. `/ping` yaniti gereken her ikisini
    de dogrular: durum 200 ve gövde `app == "AfuDM"`."""
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/ping", timeout=timeout
        ) as resp:
            if resp.status != 200:
                return False
            govde = json.loads(resp.read().decode("utf-8", "replace"))
            return bool(govde.get("ok")) and govde.get("app") == "AfuDM"
    except Exception:
        return False


def _ac(no_start: bool) -> None:
    """AfuDM kapaliysa arka planda (tep-side) baslat ve API'yi bekle."""
    port, token = _servis()
    if port and _ping(port):
        return
    if no_start:
        raise CliHata(
            "AfuDM acik degil. Once AfuDM'i baslat veya --no-start'i kaldir.",
            kod=CC_YOK,
        )
    _baslatmak()


def _kilit_al() -> object | None:
    """Baslatma kilidi (O_CREAT|O_EXCL): iki terminal/script ayni anda
    afuadm cagirirsa YALNIZ biri AfuDM'i spawn etsin. Kilitliyken digeri
    duzenli olarak /ping'e bakar — ilk surec servisi acar acmaz, ikincisi
    baslatmadan baglanir."""

    os.makedirs(paths.DATA, exist_ok=True)
    hedef = paths.DATA / "afuadm_baslat.lock"
    bitis = time.time() + KILIT_BEKLEME
    while True:
        try:
            fd = os.open(str(hedef), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            return fd
        except OSError:
            port, _ = _servis()
            if port and _ping(port):
                return None  # baska surec acmis; artik baglanabiliyoruz
            if time.time() > bitis:
                return None  # kilit kilitli kaldi; sonuz bekleme, sponsor ol
            time.sleep(0.05)


def _kilit_birak(kilit: object | None) -> None:
    if kilit is None:
        return
    try:
        os.close(kilit)
    except (OSError, TypeError):
        pass
    try:
        (paths.DATA / "afuadm_baslat.lock").unlink(missing_ok=True)
    except OSError:
        pass


def _baslatmak() -> None:
    """Kilidi al, gerekiyorsa AfuDM'i spawn et, baglanmak icin bekle."""
    app = Path(__file__).resolve().parent / "app.py"
    if not app.exists():
        raise CliHata("app.py bulunamadi: %s" % app, kod=CC_API)

    kilit = _kilit_al()
    try:
        port, token = _servis()
        if port and _ping(port):
            return

        print("AfuDM acilmadi — arka planda baslatiliyor...", file=sys.stderr)
        try:
            subprocess.Popen(
                [sys.executable, str(app), "--tepside"],
                cwd=str(app.parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
            )
        except OSError as exc:
            raise CliHata("AfuDM baslatilamadi: %s" % exc, kod=CC_API) from exc

        bitis = time.time() + BAGLANMA_BEKLEME
        while time.time() < bitis:
            port, token = _servis()
            if port and _ping(port):
                print("baglanti kuruldu (port %d)." % port, file=sys.stderr)
                return
            time.sleep(0.4)
        raise CliHata(
            "AfuDM %.0f saniyede acilamadi (port %s). Motor yok veya baska sorun."
            % (BAGLANMA_BEKLEME, paths.DATA / "api_endpoint.json"),
            kod=CC_API,
        )
    finally:
        _kilit_birak(kilit)


def _istek(yontem: str, yol: str, govde: dict | None = None) -> dict:
    port, token = _servis()
    if not port or not token:
        raise CliHata("api_endpoint.json okunamadi — AfuDM calisiyor mu?", kod=CC_YOK)
    basliklar = {"Content-Type": "application/json", "X-AfuDM-Token": token}
    veri = json.dumps(govde or {}).encode("utf-8") if govde is not None else None
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{yol}", data=veri, headers=basliklar, method=yontem
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        govde_hatasi: dict = {}
        try:
            govde_hatasi = json.loads(exc.read().decode("utf-8", "replace"))
        except (json.JSONDecodeError, AttributeError):
            pass
        kod = govde_hatasi.get("code") or ""
        mesaj = govde_hatasi.get("message") or govde_hatasi.get("error") or ""
        cikis = CC_GID if kod == "KAYIT_YOK" else CC_API
        rapor = " -> %s" % mesaj if mesaj else ""
        raise CliHata("%s %s %s%s" % (yol, exc.code, kod, rapor), kod=cikis) from exc
    except (urllib.error.URLError, OSError) as exc:
        # Baglanti kurulamadi: servis ayakta degil (veya erisilemiyor).
        raise CliHata("AfuDM'e erisilemedi (%s)" % exc, kod=CC_YOK) from exc


# --- komutlar -------------------------------------------------------------
def _motor_surumu(ad: str) -> str:
    """Motorun gercek surum satiri (best-effort; zarar gormezse bos doner).

    Senaryo: `afuadm info --json` bir hata raporuna yapistirilir — motorlarin
    durumu (paket/sistem/yok) kadar gercek surumleri de hata ayiklamaya
    yarar. Uzayan hicbir cagri yoktur, her basarisizlik sessizce gecilir."""
    dur = (engines.durum().get(ad) or {})
    yol = ""
    kaynak = dur.get("kaynak")
    if kaynak == "paket":
        yol = str(paths.ENGINE / (ad + ".exe"))
    elif kaynak == "sistem":
        yol = (dur.get("sistem_yolu") or "")
    if not yol:
        return ""
    komut = ([yol, "--version"] if ad != "ffmpeg" else [yol, "-version"])
    try:
        cikti = subprocess.run(
            komut, capture_output=True, timeout=6, creationflags=CREATE_NO_WINDOW
        ).stdout.decode("utf-8", "replace")
        ilk = cikti.splitlines()[0].strip() if cikti.splitlines() else ""
        if ad == "ffmpeg":
            for satir in cikti.splitlines():
                if "ffmpeg version" in satir:
                    return satir.strip()[:80]
            return ilk[:80]
        return (ilk or cikti.strip())[:80]
    except Exception:
        return ""


def komut_info(args) -> int:
    port, _ = _servis()
    calisiyor = bool(port) and _ping(port)
    satir: dict = {
        "app": "AfuDM",
        "surum": surum.SURUM,
        "uzanti": surum.uzanti_surumu(),
        "port": port,
        "durum": "calisiyor" if calisiyor else "kapali",
        "hiz_profili": None,
        "download_dir": None,
        "motorlar": {},
    }
    if calisiyor:
        try:
            snap = _istek("GET", "/snapshot")
            satir["hiz_profili"] = (snap.get("settings") or {}).get("hiz_profili", "normal")
            satir["download_dir"] = snap.get("download_dir")
            satir["engine_ok"] = bool(snap.get("engine_ok"))
        except CliHata:
            pass  # bilgi olabildigince verilir; tek nokta hicbir yerde patlamaz
    for ad, motor in (engines.durum()).items():
        satir["motorlar"][ad] = {
            "kaynak": motor.get("kaynak", "yok"),
            "kullanilabilir": bool(motor.get("kullanilabilir")),
            "zorunlu": bool(motor.get("zorunlu")),
            "surum": _motor_surumu(ad),
        }
    if args.json:
        print(json.dumps(satir, ensure_ascii=False))
    else:
        print("AfuDM v%s (uzanti v%s)" % (surum.SURUM, satir["uzanti"]))
        print("API port %s — %s" % (satir["port"] or "-", satir["durum"]))
        if satir.get("hiz_profili") is not None:
            print("profil: %s   klasor: %s" % (
                satir["hiz_profili"], satir.get("download_dir") or "-"))
        for ad, motor in satir["motorlar"].items():
            print("motor %-8s %-7s %s" % (
                ad, motor["kaynak"], motor["surum"] or "-"))
    return 0


def komut_add(args) -> int:
    if not args.url:
        raise CliHata("add: url gerekli")
    govde: dict = {"url": args.url}
    if args.kind:
        govde["kind"] = args.kind
    if args.dest_dir:
        govde["dest_dir"] = args.dest_dir
    elif args.category:
        govde["kategori"] = args.category
    if args.filename:
        govde["filename"] = args.filename
    if args.quality:
        govde["quality"] = args.quality
    if args.audio_only:
        govde["audio_only"] = True
    if args.playlist:
        govde["playlist"] = True
    if args.start_at:
        govde["start_at"] = args.start_at
    if args.header:
        govde["headers"] = dict(kv.split(":", 1) for kv in args.header if ":" in kv)
    if args.proxy:
        govde["proxy"] = args.proxy
    if args.checksum:
        govde["checksum"] = args.checksum
    sonuc = _istek("POST", "/add", govde)
    if sonuc.get("pending"):
        # Kaydetme penceresi bekliyor: --json'da tek JSON satiri, duz metinde
        # tek satirlik bilgi. STDOUT asla kullanici mesajiyla karismaz.
        if args.json:
            print(json.dumps(sonuc, ensure_ascii=False))
        else:
            print("kaydetme penceresine gonderildi (beklemede)")
        return 0
    if not sonuc.get("ok", True):
        raise CliHata(str(sonuc.get("error") or "bilinmeyen hata"))
    if args.json:
        print(json.dumps(sonuc, ensure_ascii=False))
    else:
        if sonuc.get("scheduled_for"):
            print("zamanlandi: %s" % time.strftime(
                "%Y-%m-%d %H:%M", time.localtime(sonuc["scheduled_for"])))
        else:
            print("eklendi id=%s gid=%s (%s)" % (
                sonuc.get("id", "-"), sonuc.get("gid", "-"), sonuc.get("kind", "")))
    return 0


def komut_list(args) -> int:
    snap = _istek("GET", "/snapshot")
    ogeler = snap.get("items", [])
    if args.json:
        print(json.dumps(ogeler, ensure_ascii=False))
        return 0
    if not ogeler:
        print("is yok")
        return 0
    satirlar = []
    for o in ogeler:
        satirlar.append("%-22s %-7s %-8s %6.1f%% %9s/s %s" % (
            o.get("gid", "")[:22],
            o.get("kind", ""),
            o.get("status", ""),
            float(o.get("progress", 0) or 0),
            human_size(int(o.get("downloadSpeed", 0) or 0)),
            o.get("title", "")[:44],
        ))
    print("\n".join(satirlar))
    if args.verbose:
        print("\ntoplam: %d is" % len(ogeler))
    return 0


def komut_status(args) -> int:
    snap = _istek("GET", "/snapshot")
    if args.json:
        print(json.dumps({
            "engine_ok": snap.get("engine_ok"),
            "download_dir": snap.get("download_dir"),
            "lang": snap.get("lang"),
            "hiz_profili": (snap.get("settings") or {}).get("hiz_profili", "normal"),
            "stat": snap.get("stat"),
        }, ensure_ascii=False))
        return 0
    st = snap.get("stat", {})
    ayar = (snap.get("settings") or {}).get("hiz_profili", "normal")
    print("motor:  %s" % ("OK" if snap.get("engine_ok") else "KAPALI"))
    print("klasor: %s" % (snap.get("download_dir") or "-"))
    print("profil: %s" % ayar)
    print("hiz:    %s/s  (yukleme %s/s)" % (
        human_size(int(st.get("downloadSpeed", 0) or 0)),
        human_size(int(st.get("uploadSpeed", 0) or 0))))
    print("aktif:  %d   bekleyen: %d   biten: %d" % (
        int(st.get("numActive", 0) or 0),
        int(st.get("numWaiting", 0) or 0),
        int(st.get("numStopped", 0) or 0)))
    return 0


def komut_kontrol(args) -> int:
    if args.action in ("pause-all", "resume-all"):
        eylem = args.action.replace("-", "_")
        sonuc = _istek("POST", "/control", {"action": eylem})
    else:
        if not args.gid:
            raise CliHata("%s: gid gerekli" % args.action)
        eylem = args.action.replace("-", "_")
        sonuc = _istek("POST", "/control", {
            "action": eylem, "gid": args.gid,
            "delete_files": bool(args.delete_files),
        })
    if args.json:
        print(json.dumps(sonuc, ensure_ascii=False))
    return 0


def komut_renew(args) -> int:
    if not args.gid or not args.url:
        raise CliHata("renew: gid ve yeni url gerekli")
    sonuc = _istek("POST", "/renew", {"gid": args.gid, "url": args.url})
    if args.json:
        print(json.dumps(sonuc, ensure_ascii=False))
    else:
        print("eski: %s" % sonuc.get("eski", "-"))
        print("yeni: %s" % sonuc.get("yeni", "-"))
        print("kaldirilan URI: %s" % sonuc.get("degisen", 0))
    return 0


def komut_mode(args) -> int:
    if not args.profil:
        # mevcut profili goster; --json istenirse ham JSON
        snap = _istek("GET", "/snapshot")
        profil = (snap.get("settings") or {}).get("hiz_profili", "normal")
        if args.json:
            print(json.dumps({"hiz_profili": profil}, ensure_ascii=False))
        else:
            print(profil)
        return 0
    sonuc = _istek("POST", "/mode", {"profil": args.profil})
    if args.json:
        print(json.dumps(sonuc, ensure_ascii=False))
    else:
        print("profil: %s (sinir %s KB/s)" % (
            sonuc.get("profil", "?"), sonuc.get("limit_kb", 0)))
    return 0


def komut_ayarla(args) -> int:
    """Network Core: calisan isin baglanti/hiz ayarini KESMEDEN degistir."""
    if args.baglanti is None and args.hiz is None:
        raise CliHata("ayarla: en az bir deger gerekli (--baglanti ve/veya --hiz)")
    govde: dict = {"action": "ayarla", "gid": args.gid}
    if args.baglanti is not None:
        govde["baglanti"] = args.baglanti
    if args.hiz is not None:
        govde["hiz_kb"] = args.hiz
    sonuc = _istek("POST", "/control", govde)
    if args.json:
        print(json.dumps(sonuc, ensure_ascii=False))
    else:
        print("gid %s — baglanti: %s  hiz: %s KB/s" % (
            sonuc.get("gid", args.gid),
            "ayirtilmadi" if sonuc.get("baglanti") is None else sonuc.get("baglanti"),
            "deismedi" if sonuc.get("hiz_kb") is None else sonuc.get("hiz_kb")))
    return 0


def _kestir(metin: str):
    """Ayarlar degerini JSON'a cevir (sayi/boolean/string)."""
    kalin = metin.strip()
    if kalin in ("true", "on"):
        return True
    if kalin in ("false", "off"):
        return False
    if kalin.lstrip("-").isdigit():
        return int(kalin)
    try:
        return float(kalin)
    except ValueError:
        return kalin


def komut_ayar(args) -> int:
    """Grup ayarini goster veya degistir.

    `afuadm ayar`                          -> tumu (JSON: --json)
    `afuadm ayar proxy`                    -> tek deger
    `afuadm ayar system_proxy 1`           -> sistem proxy kullan
    `afuadm ayar proxy socks5://127.0.0.1:1080`
    """
    if args.anahtar and args.deger is not None:
        sonuc = _istek("POST", "/settings", {args.anahtar: _kestir(args.deger)})
        ayar = sonuc.get("settings") or {}
        if args.json:
            print(json.dumps({args.anahtar: ayar.get(args.anahtar)}, ensure_ascii=False))
        else:
            print("%s = %s" % (args.anahtar, ayar.get(args.anahtar)))
        return 0
    snap = _istek("GET", "/snapshot")
    ayar = snap.get("settings") or {}
    if args.anahtar:
        if args.json:
            print(json.dumps({args.anahtar: ayar.get(args.anahtar)}, ensure_ascii=False))
        else:
            print(ayar.get(args.anahtar))
        return 0
    if args.json:
        print(json.dumps(ayar, ensure_ascii=False))
        return 0
    for k in sorted(ayar):
        print("%s = %s" % (k, ayar[k]))
    return 0


def komut_watch(args) -> int:
    aralik = max(float(args.interval), 0.2)
    try:
        while True:
            snap = _istek("GET", "/snapshot")
            ogeler = snap.get("items", [])
            if args.gid:
                secilmis = [g for g in ogeler if g.get("gid") == args.gid]
            else:
                secilmis = [
                    g for g in ogeler
                    if g.get("status") in ("active", "waiting", "paused")
                ]
            if args.json:
                print(json.dumps({
                    "t": round(time.time(), 3),
                    "items": secilmis,
                }, ensure_ascii=False), flush=True)
            else:
                parcalar = " | ".join(
                    "%s %-8s %6.1f%% %8s/s %s" % (
                        o.get("gid", "")[:8],
                        o.get("status", ""),
                        float(o.get("progress", 0) or 0),
                        human_size(int(o.get("downloadSpeed", 0) or 0)),
                        o.get("title", "")[:26],
                    )
                    for o in secilmis
                ) or "(aktif is yok)"
                print("\r" + parcalar, end="", flush=True)
            time.sleep(aralik)
    except KeyboardInterrupt:
        # --json (NDJSON) akisinda sona yalniz gordugumuz satirlar gider:
        # yeni satir bile stdout sifrari sorguya takilmasin.
        if not args.json:
            print()
        return 0
    except CliHata:
        raise


def _ortak(baslik: bool = False) -> argparse.ArgumentParser:
    """--json / --no-start hem ana komutta hem alt komutlarda gecerli:
    `afuadm status --json` ve `afuadm --json status` ayni isi yapar.

    default=SUPPRESS: argparse alt komut parser'ının kendi varsayilanini
    ustune bindirip KOKTE verilen degeri silmesini engeller (olculdu:
    '--no-start' komuttan once verilince subparser default'u False'a
    donduyordu). Kok parser `set_defaults` ile garantilenir; SUPPRESS
    yalnizca "verilmedi" anlamina gelir."""
    ortak = argparse.ArgumentParser(add_help=False)
    ortak.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                       help="ciktiyi ham JSON olarak ver")
    ortak.add_argument("--no-start", action="store_true", default=argparse.SUPPRESS,
                       help="AfuDM kapaliysa kendiliginden baslatma")
    return ortak


def komutlar_ayirici() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="afuadm", description="AfuDM komut satiri aracı",
                                parents=[_ortak()])
    alt = p.add_subparsers(dest="komut", required=True)

    ik = alt.add_parser("add", parents=[_ortak()], help="is ekle")
    ik.add_argument("url")
    ik.add_argument("--kind", choices=("http", "video", "torrent"))
    ik.add_argument("--dest-dir")
    ik.add_argument("--category")
    ik.add_argument("--filename")
    ik.add_argument("--quality")
    ik.add_argument("--audio-only", action="store_true")
    ik.add_argument("--playlist", action="store_true")
    ik.add_argument("--start-at", help="'23:30' veya '2026-09-19 23:30'")
    ik.add_argument("--header", action="append", help="'Name: value' (tekrar edilebilir)")
    ik.add_argument("--proxy", help="bu is icin proxy (ornek socks5://127.0.0.1:1080)")
    ik.add_argument("--checksum", help="'sha-256:<hex>' / 'md5:<hex>' — bitince dogrula")
    ik.set_defaults(func=komut_add)

    il = alt.add_parser("list", parents=[_ortak()], help="isi listele")
    il.add_argument("-v", "--verbose", action="store_true")
    il.set_defaults(func=komut_list)

    iks = alt.add_parser("status", parents=[_ortak()], help="motor/genel durum")
    iks.set_defaults(func=komut_status)

    ikk = alt.add_parser("pause", parents=[_ortak()], help="islei duraklat")
    ikk.add_argument("gid")
    ikk.set_defaults(func=komut_kontrol, action="pause")

    for ad in ("resume", "remove"):
        yardim = {"resume": "islei devam ettir",
                  "remove": "isi kaldir (yerel dosyalari da siler: --delete-files)"}
        k = alt.add_parser(ad, parents=[_ortak()], help=yardim[ad])
        k.add_argument("gid")
        if ad == "remove":
            k.add_argument("--delete-files", action="store_true",
                           help="kaydi ve indirilen dosyalari birlikte sil")
        k.set_defaults(func=komut_kontrol, action=ad)

    alt.add_parser("pause-all", parents=[_ortak()], help="hepsini duraklat").set_defaults(
        func=komut_kontrol, action="pause-all")
    alt.add_parser("resume-all", parents=[_ortak()], help="hepsini devam ettir").set_defaults(
        func=komut_kontrol, action="resume-all")

    kr = alt.add_parser("renew", parents=[_ortak()], help="olen linki yeni adresle devam ettir")
    kr.add_argument("gid")
    kr.add_argument("url")
    kr.set_defaults(func=komut_renew)

    km = alt.add_parser("mode", parents=[_ortak()], help="hiz profili: snail | normal | turbo")
    km.add_argument("profil", nargs="?", choices=("snail", "normal", "turbo"))
    km.set_defaults(func=komut_mode)

    ka = alt.add_parser("ayarla", parents=[_ortak()],
                        help="calisan isin baglanti/hiz ayarini kesmeden degistir")
    ka.add_argument("gid")
    ka.add_argument("--baglanti", type=int, help="baglanti sayisi (1-64)")
    ka.add_argument("--hiz", type=int, help="hiz siniri KB/s; 0 = sinirsiz")
    ka.set_defaults(func=komut_ayarla)

    kss = alt.add_parser("ayar", parents=[_ortak()],
                         help="ayarlari goster / degistir (afuadm ayar [ad] [deger])")
    kss.add_argument("anahtar", nargs="?")
    kss.add_argument("deger", nargs="?")
    kss.set_defaults(func=komut_ayar)

    kw = alt.add_parser("watch", parents=[_ortak()], help="canli akis (NDJSON ile --json)")
    kw.add_argument("gid", nargs="?")
    kw.add_argument("--interval", default="0.5", help="yoklama araligi (sn)")
    kw.set_defaults(func=komut_watch)

    ki = alt.add_parser("info", parents=[_ortak()], help="surum + servis bilgisi")
    ki.set_defaults(func=komut_info)

    p.set_defaults(func=komut_info, json=False, no_start=False)
    return p


def main(argv: list[str] | None = None) -> int:
    _ciktilari_utf8()
    p = komutlar_ayirici()
    args = p.parse_args(argv)
    try:
        _ac(args.no_start)
        return args.func(args)
    except CliHata as exc:
        print("AFUADM HATA: %s" % exc, file=sys.stderr)
        return exc.kod
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001 — beklenmeyen hicbir sey stdout'i kirletmesin
        print(
            "AFUADM HATA: beklenmeyen sorun: %s (%s: %s)"
            % (exc, type(exc).__name__, sys.exc_info()[0]),
            file=sys.stderr,
        )
        return 4


if __name__ == "__main__":
    sys.exit(main())