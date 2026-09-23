"""yt-dlp birlestirme ciktilarinda son dosya adinin korunmasi."""
import io
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from video import ytdlp  # noqa: E402
from video.ytdlp import VideoJob  # noqa: E402
from core.manager import Manager  # noqa: E402


class _FakeProc:
    def __init__(self, output: str) -> None:
        self.stdout = io.StringIO(output)

    def wait(self) -> int:
        return 0


class _FakeRpc:
    def tell_status(self, gid: str) -> dict:
        return {}


class _FakeStore:
    def __init__(self, row: dict) -> None:
        self.row = row
        self.updates: list[tuple[int, dict]] = []

    def by_gid(self, gid: str) -> dict | None:
        return self.row if self.row.get("gid") == gid else None

    def update_by_id(self, row_id: int, **fields) -> None:
        self.updates.append((row_id, fields))
        self.row.update(fields)


def check(ad: str, kosul: bool, detay: str = "") -> None:
    if not kosul:
        raise AssertionError(ad + (f" <- {detay}" if detay else ""))


def test_ytdlp_merge_filename_and_parts() -> None:
    job = VideoJob("yt:test", "https://ornek.com/video", "C:/downloads/Genel")
    job.proc = _FakeProc(
        "\n".join(
            [
                "[download] Destination: C:/downloads/Genel/X.f5.mp4",
                "[download] Destination: C:/downloads/Genel/X.f10.m4a",
                '[Merger] Merging formats into "C:/downloads/Genel/X.mp4"',
            ]
        )
    )

    job._akisi_oku(None)

    check("birlesik hedef filename olarak tutulur", job.filename == "X.mp4", job.filename)
    check(
        "yalniz iki indirme parcasi listelenir",
        job.parca_dosyalari == [
            "C:/downloads/Genel/X.f5.mp4",
            "C:/downloads/Genel/X.f10.m4a",
        ],
        repr(job.parca_dosyalari),
    )


def test_old_split_filename_finds_merged_output() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        merged = folder / "X.mp4"
        merged.write_bytes(b"birlesik")

        finder = getattr(ytdlp, "birlesik_dosya_bul", None)
        found = finder(folder, "X.f10.m4a") if finder else None

        check("eski f10 kaydi birlesik dosyaya doner", found == merged, str(found))


def test_postprocessor_targets_replace_filename_without_becoming_parts() -> None:
    unicode_name = "Orman Çocuğu 2 izle, 720p Türkçe Dublaj izle ~ Film izle.mp4"
    cases = [
        ('[VideoRemuxer] Remuxing video from webm to mp4; Destination: X.mp4', "X.mp4"),
        ('[VideoConvertor] Converting video from webm to mp4; Destination: X.mp4', "X.mp4"),
        ("[ExtractAudio] Destination: X.mp3", "X.mp3"),
        ('[FixupM3u8] Fixing MPEG-TS in MP4 container of "X.mp4"', "X.mp4"),
        (f'[Merger] Merging formats into "{unicode_name}"', unicode_name),
    ]
    for line, expected in cases:
        job = VideoJob("yt:test", "https://ornek.com/video", "C:/downloads/Genel")
        job._hedef_satirini_isle(line)
        check(f"son islem hedefi yakalanir: {line}", job.filename == expected, job.filename)
        check(f"son islem parcaya girmez: {line}", not job.parca_dosyalari)


def test_download_already_exists_and_unicode_filename_are_parsed() -> None:
    filename = "Orman Çocuğu 2 izle, 720p Türkçe Dublaj izle ~ Film izle.mp4"
    job = VideoJob("yt:test", "https://ornek.com/video", "C:/downloads/Genel")
    job._hedef_satirini_isle(f"[download] {filename} has already been downloaded")

    check("zaten indirilmis dosyanin adi yakalanir", job.filename == filename, job.filename)
    check("zaten indirilmis iz [download] parcasi olarak tutulur",
          job.parca_dosyalari == [filename], repr(job.parca_dosyalari))


def test_merged_finder_rejects_traversal_and_non_split_names() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        folder = root / "dest"
        folder.mkdir()
        (root / "outside.mp4").write_bytes(b"outside")
        (folder / "plain.mp4").write_bytes(b"plain")

        finder = ytdlp.birlesik_dosya_bul
        check("path traversal disina cikamaz",
              finder(folder, "../outside.f10.m4a") is None)
        check("fNNN olmayan ad yanlis dosyaya donmez",
              finder(folder, "plain.m4a") is None)


def test_merged_finder_prefers_newest_output_extension() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        old = folder / "X.mp4"
        newest = folder / "X.mkv"
        old.write_bytes(b"old")
        newest.write_bytes(b"new")
        os.utime(old, (100, 100))
        os.utime(newest, (200, 200))

        found = ytdlp.birlesik_dosya_bul(folder, "X.f10.m4a")

        check("birden fazla cikti arasinda en yeni secilir", found == newest, str(found))


def test_manager_prefers_merged_output_over_remaining_old_fragment() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        fragment = folder / "X.f10.m4a"
        merged = folder / "X.mp4"
        fragment.write_bytes(b"fragment")
        merged.write_bytes(b"merged output")
        row = {
            "id": 146,
            "gid": "yt:146",
            "kind": "video",
            "source": "https://ornek.com/video",
            "title": "X",
            "dest_dir": str(folder),
            "filename": fragment.name,
            "total_bytes": len(b"fragment"),
            "done_bytes": len(b"fragment"),
            "status": "complete",
            "error": None,
            "start_after": None,
            "target_path": None,
        }
        store = _FakeStore(row)
        manager = Manager.__new__(Manager)
        manager.rpc = _FakeRpc()
        manager.store = store
        manager.video_jobs = {}
        manager.snapshot = lambda: {"items": []}
        manager.current_download_dir = lambda: str(folder)

        found = manager.resolve_item_path("yt:146")

        check("eski parca yerine birlesik cikti acilir", found == merged, str(found))
        check("UI icin birlesik boyutu DBye yazilir",
              store.row["total_bytes"] == len(b"merged output"), repr(store.row))
        check("duzeltilen kayit UI boyutunu gosterir",
              manager._shape_row(store.row)["totalLength"] == len(b"merged output"),
              repr(manager._shape_row(store.row)))


def test_ffmpegless_own_merge_still_consumes_two_download_parts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        video = folder / "X.f5.mp4"
        audio = folder / "X.f10.m4a"
        video.write_bytes(b"video")
        audio.write_bytes(b"audio")
        job = VideoJob("yt:test", "https://ornek.com/video", str(folder))
        job.parca_dosyalari = [str(video), str(audio)]
        original_probe = ytdlp.mp4mux.izi_oku
        original_merge = ytdlp.mp4mux.birlestir
        try:
            ytdlp.mp4mux.izi_oku = lambda path: SimpleNamespace(
                tur="vide" if Path(path) == video else "soun")

            def fake_merge(video_path, audio_path, target):
                Path(target).write_bytes(Path(video_path).read_bytes() + Path(audio_path).read_bytes())

            ytdlp.mp4mux.birlestir = fake_merge
            job._kendi_birlestir()
        finally:
            ytdlp.mp4mux.izi_oku = original_probe
            ytdlp.mp4mux.birlestir = original_merge

        check("ffmpeg yokken kendi birlestirici ciktiyi yazar",
              (folder / "X.mp4").read_bytes() == b"videoaudio")
        check("ffmpeg yokken parcalar temizlenir",
              not video.exists() and not audio.exists())


def test_manager_resolves_old_record_and_repairs_db() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        merged = folder / "X.mp4"
        merged.write_bytes(b"gercek cikti")
        row = {
            "id": 146,
            "gid": "yt:146",
            "dest_dir": str(folder),
            "filename": "X.f10.m4a",
            "target_path": None,
        }
        store = _FakeStore(row)
        manager = Manager.__new__(Manager)
        manager.rpc = _FakeRpc()
        manager.store = store
        manager.video_jobs = {}
        manager.snapshot = lambda: {"items": []}
        manager.current_download_dir = lambda: str(folder)

        found = manager.resolve_item_path("yt:146")

        check("yonetici eski kaydi bulur", found == merged, str(found))
        check(
            "eski kayit DBde duzeltilir",
            store.updates == [(146, {"filename": "X.mp4", "total_bytes": len(b"gercek cikti")})],
            repr(store.updates),
        )


if __name__ == "__main__":
    test_ytdlp_merge_filename_and_parts()
    test_old_split_filename_finds_merged_output()
    test_postprocessor_targets_replace_filename_without_becoming_parts()
    test_download_already_exists_and_unicode_filename_are_parsed()
    test_merged_finder_rejects_traversal_and_non_split_names()
    test_merged_finder_prefers_newest_output_extension()
    test_manager_resolves_old_record_and_repairs_db()
    test_manager_prefers_merged_output_over_remaining_old_fragment()
    test_ffmpegless_own_merge_still_consumes_two_download_parts()
    print("OK: video merger dosya adi")
