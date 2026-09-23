"""One permitted short public video through AfuDM's real VideoJob pipeline."""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from video.ytdlp import VideoJob  # noqa: E402

URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
def main() -> int:
    with tempfile.TemporaryDirectory(prefix="C1_video_", dir=ROOT / "tests" / "kontrol") as tmp:
        job = VideoJob("kontrol-youtube", URL, tmp, quality="best")
        job.start()
        deadline = time.time() + 240
        while time.time() < deadline and job.status == "active":
            time.sleep(0.25)
        if job.status == "active":
            if job.proc and job.proc.poll() is None:
                job.proc.terminate()
            print("KALDI: 240 saniyede tamamlanmadı")
            return 1

        output = Path(job.filename) if job.filename else None
        if output and not output.is_absolute():
            output = Path(tmp) / output
        if job.status != "complete" or not output or not output.is_file():
            print(f"KALDI: status={job.status}; hata={job.error}; filename={job.filename}")
            return 1
        size = output.stat().st_size
        print(f"GEÇTİ: status={job.status}; dosya={output.name}; boyut={size} bayt")
        print(f"Kaynak: yalnızca {URL}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
