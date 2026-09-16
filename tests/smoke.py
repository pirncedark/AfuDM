"""AfuDM duman testi — GERCEK indirme yapar, sonucu kanitla gosterir.

Calistirma:  python tests/smoke.py [--skip-video] [--skip-torrent]

Test ettigi sey:
  1. aria2 motoru ayaga kalkiyor mu
  2. HTTP dosyasi COK BAGLANTIYLA iniyor mu (baglanti sayisi > 1)
  3. Duraklat / surdur calisiyor mu, ilerleme kaldigi yerden devam ediyor mu
  4. Magnet ekleniyor, CANLI seed sayisi geliyor mu
  5. yt-dlp video bilgisi ve ses indirmesi calisiyor mu
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import paths  # noqa: E402
from core.manager import Manager, human_size  # noqa: E402

# Range (kismi istek) destekleyen kaynak sart: parcalama ancak oyle kanitlanir.
HTTP_SOURCES = [
    "https://download.thinkbroadband.com/100MB.zip",
    "https://proof.ovh.net/files/100Mb.dat",
    "https://speed.cloudflare.com/__down?bytes=52428800",
]
# Ubuntu ISO torrenti: yasal, cok seedli, aria2 --follow-torrent ile devralir.
TORRENT_URL = (
    "https://releases.ubuntu.com/24.04/ubuntu-24.04.3-desktop-amd64.iso.torrent"
)
# Sintel — Blender Vakfi'nin acik lisansli filmi; magnet ayristirma testi.
MAGNET = (
    "magnet:?xt=urn:btih:08ada5a7a6183aae1e09d831df6748d566095a10"
    "&dn=Sintel&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337%2Fannounce"
    "&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A6969%2Fannounce"
)
VIDEO_URL = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"  # Big Buck Bunny (CC)

results: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    results.append((name, passed, detail))
    mark = "GECTI" if passed else "BASARISIZ"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""), flush=True)


def find(manager: Manager, gid: str) -> dict | None:
    for item in manager.snapshot()["items"]:
        if item["gid"] == gid:
            return item
    return None


def wait_until(manager: Manager, gid: str, predicate, timeout: float, label: str) -> dict | None:
    deadline = time.time() + timeout
    last: dict | None = None
    while time.time() < deadline:
        last = find(manager, gid)
        if last and predicate(last):
            return last
        time.sleep(1)
    print(f"      (zaman asimi: {label}; son durum: "
          f"{last.get('status') if last else 'kayit yok'})", flush=True)
    return None


def test_http(manager: Manager) -> None:
    print("\n2) HTTP cok parcali indirme")
    # Kaynaklardan ilk GERCEKTEN akani sec: olu bir adrese karsi duraklatma
    # testi yapmak anlamsiz olur (hataya dusmus indirme duraklatilamaz).
    gid = ""
    item = None
    for url in HTTP_SOURCES:
        try:
            gid = manager.add(url, kind="http")["gid"]
        except Exception as exc:
            print(f"      {url[:46]} eklenemedi: {exc}")
            continue
        item = wait_until(manager, gid, lambda i: i["completedLength"] > 1_000_000, 40,
                          "1 MB inmesi")
        if item:
            print(f"      kaynak: {url}")
            break
        manager.remove(gid, delete_files=True)
        gid = ""
    record("HTTP indirme akiyor", bool(item),
           f"{human_size(item['completedLength'])} indi, {human_size(item['downloadSpeed'])}/s"
           if item else "hicbir kaynaktan veri gelmedi")
    if not item:
        return

    peak_conn = 0
    peak_speed = 0
    for _ in range(12):
        current = find(manager, gid)
        if current:
            peak_conn = max(peak_conn, current["connections"])
            peak_speed = max(peak_speed, current["downloadSpeed"])
        time.sleep(0.7)
    record("Cok baglantili (IDM tarzi parcalama)", peak_conn > 1,
           f"en yuksek {peak_conn} es zamanli baglanti, tepe hiz {human_size(peak_speed)}/s")

    # duraklat
    before = find(manager, gid)
    manager.pause(gid)
    paused = wait_until(manager, gid, lambda i: i["status"] == "paused", 15, "duraklama")
    record("Duraklat", bool(paused), f"durum: {paused['status']}" if paused else "")

    # surdur ve kaldigi yerden devam
    resume_from = paused["completedLength"] if paused else 0
    manager.resume(gid)
    resumed = wait_until(
        manager, gid,
        lambda i: i["status"] == "active" and i["completedLength"] > resume_from,
        30, "surdurme",
    )
    record("Surdur + kaldigi yerden devam", bool(resumed),
           f"{human_size(resume_from)} -> {human_size(resumed['completedLength'])}"
           if resumed else "")
    if before:
        record("Ilerleme geriye gitmedi",
               bool(resumed) and resumed["completedLength"] >= resume_from,
               "bayt kaybi yok")
    manager.remove(gid, delete_files=True)


def follow_child_gid(manager: Manager, row_id: int, parent_gid: str, timeout: float) -> str:
    """aria2, .torrent/magnet ustverisini indirince gercek indirmeyi YENI bir
    GID'e devreder. Manager bunu izleyip kaydin GID'ini guncellemeli."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        row = manager.store.by_id(row_id)
        if row and row["gid"] and row["gid"] != parent_gid:
            return row["gid"]
        time.sleep(1)
    return parent_gid


def test_torrent(manager: Manager) -> None:
    print("\n3) Torrent / magnet + canli seed takibi")
    magnet = manager.add(MAGNET, kind="torrent")
    child = follow_child_gid(manager, magnet["id"], magnet["gid"], 90)
    state = find(manager, child)
    record("Magnet ustverisi cozuldu ve devralindi", child != magnet["gid"],
           f"{magnet['gid']} -> {child}"
           + (f" ({state['title'][:32]})" if state else ""))

    item = wait_until(
        manager, child,
        lambda i: i["numSeeders"] > 0 and i["completedLength"] > 1_000_000,
        120, "seed bulunup verinin akmasi",
    )
    if item:
        record("Canli seed takibi", True,
               f"{item['numSeeders']} seed, {item['connections']} peer, "
               f"{human_size(item['completedLength'])} indi, "
               f"{human_size(item['downloadSpeed'])}/s")
        record("Peer listesi okunuyor", True,
               f"{len(manager.peers(child))} peer listelendi")
    else:
        record("Canli seed takibi", False, "120 sn icinde seed bulunup veri akmadi")

    # Ayni torrenti ikinci kez eklemek anlasilir bir mesaj vermeli
    try:
        manager.add(MAGNET, kind="torrent")
        record("Mukerrer torrent engellendi", False, "ikinci ekleme sessizce kabul edildi")
    except ValueError as exc:
        record("Mukerrer torrent engellendi", "zaten" in str(exc).lower(), str(exc)[:70])
    except Exception as exc:
        record("Mukerrer torrent engellendi", False, f"beklenmeyen hata: {exc}"[:70])

    manager.remove(child, delete_files=True)
    if child != magnet["gid"]:
        manager.remove(magnet["gid"], delete_files=True)
    leftovers = list(Path(manager.current_download_dir()).glob("*.aria2"))
    record("Iptal sonrasi kontrol dosyasi kalmadi", not leftovers,
           ", ".join(p.name for p in leftovers) or "temiz")

    # .torrent URL'si: aria2 dosyayi indirip devralir (tracker'a bagli degil)
    print("   .torrent adresi")
    try:
        info = manager.add(TORRENT_URL, kind="torrent")
        handed = follow_child_gid(manager, info["id"], info["gid"], 60)
        record(".torrent adresinden devralma", handed != info["gid"],
               f"{info['gid']} -> {handed}")
        manager.remove(handed, delete_files=True)
        if handed != info["gid"]:
            manager.remove(info["gid"], delete_files=True)
    except Exception as exc:
        record(".torrent adresinden devralma", False, str(exc)[:90])


def test_video(manager: Manager) -> None:
    print("\n4) Video (yt-dlp)")
    try:
        info = manager.probe_video(VIDEO_URL)
        record("Video bilgisi alindi", bool(info.get("title")),
               f"{info.get('title', '')[:60]} | {len(info.get('formats', []))} format")
    except Exception as exc:
        record("Video bilgisi alindi", False, str(exc)[:120])
        return

    added = manager.add(VIDEO_URL, kind="video", quality="audio", audio_only=True)
    gid = added["gid"]
    item = wait_until(manager, gid, lambda i: i["completedLength"] > 200_000, 90,
                      "ses verisi inmesi")
    record("Video/ses indirmesi akiyor", bool(item),
           f"{human_size(item['completedLength'])} indi" if item else "veri gelmedi")
    done = wait_until(manager, gid, lambda i: i["status"] == "complete", 150, "tamamlanma")
    if done:
        target = Path(done.get("dir") or paths.DOWNLOADS)
        mp3s = sorted(target.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
        record("mp3 dosyasi olustu", bool(mp3s),
               f"{mp3s[0].name} ({human_size(mp3s[0].stat().st_size)})" if mp3s else "")
        for leftover in mp3s[:1]:
            leftover.unlink(missing_ok=True)
    else:
        record("mp3 dosyasi olustu", False, "indirme tamamlanmadi")
    manager.remove(gid)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-video", action="store_true")
    parser.add_argument("--skip-torrent", action="store_true")
    args = parser.parse_args()

    print("AfuDM duman testi — gercek indirmeler yapilacak\n")
    print("1) Motor")
    manager = Manager()
    started = time.time()
    manager.start()
    record("aria2 ayaga kalkti", manager.rpc.alive(),
           f"{time.time() - started:.1f} sn, surum "
           f"{manager.rpc.call('aria2.getVersion')['version']}")
    record("yt-dlp motoru gomulu", Path(paths.ytdlp_exe()).exists(), paths.ytdlp_exe())
    record("ffmpeg gomulu", Path(paths.ffmpeg_exe()).exists(), paths.ffmpeg_exe())

    try:
        test_http(manager)
        if not args.skip_torrent:
            test_torrent(manager)
        if not args.skip_video:
            test_video(manager)
    finally:
        manager.stop()

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{'=' * 58}\nSONUC: {passed}/{total} test gecti")
    failures = [name for name, ok, _ in results if not ok]
    if failures:
        print("Gecmeyenler: " + ", ".join(failures))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
