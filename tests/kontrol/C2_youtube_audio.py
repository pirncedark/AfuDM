"""Audio-only extraction from the same single permitted short video used in C1."""
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
    with tempfile.TemporaryDirectory(prefix="C2_audio_", dir=ROOT / "tests" / "kontrol") as tmp:
        job = VideoJob("kontrol-youtube-audio", URL, tmp, audio_only=True)
        job.start()
        deadline = time.time() + 240
        while time.time() < deadline and job.status == "active":
            time.sleep(0.25)
        output = Path(job.filename) if job.filename else None
        if output and not output.is_absolute():
            output = Path(tmp) / output
        if job.status != "complete" or not output or not output.is_file() or output.suffix.lower() != ".mp3":
            print(f"KALDI: status={job.status}; hata={job.error}; filename={job.filename}")
            return 1
        print(f"GEÇTİ: yalnız ses mp3; dosya={output.name}; boyut={output.stat().st_size} bayt")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
