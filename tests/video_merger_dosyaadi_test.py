"""yt-dlp birlestirme ciktilarinda son dosya adinin korunmasi."""
import io
import sys
import tempfile
from pathlib import Path

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
    cases = [
        ('[VideoRemuxer] Remuxing video from "X.f5.mp4" to "X.mp4"', "X.mp4"),
        ('[VideoConvertor] Converting video from "X.webm" to "X.mp4"', "X.mp4"),
        ("[ExtractAudio] Destination: X.mp3", "X.mp3"),
        ('[FixupM3u8] Fixing MPEG-TS in MP4 container of "X.mp4"', "X.mp4"),
    ]
    for line, expected in cases:
        job = VideoJob("yt:test", "https://ornek.com/video", "C:/downloads/Genel")
        job._hedef_satirini_isle(line)
        check(f"son islem hedefi yakalanir: {line}", job.filename == expected, job.filename)
        check(f"son islem parcaya girmez: {line}", not job.parca_dosyalari)


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
    test_manager_resolves_old_record_and_repairs_db()
    print("OK: video merger dosya adi")
