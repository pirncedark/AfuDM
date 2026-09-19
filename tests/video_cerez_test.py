"""Video tarayici cerezi 403 yedegi — AGSIZ, yt-dlp calistirilmaz."""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from video.ytdlp import VideoJob  # noqa: E402


class _SahteProc:
    def __init__(self) -> None:
        self.stdout = io.StringIO("ERROR: HTTP Error 403: Forbidden\n")

    def wait(self) -> int:
        return 1


def main() -> int:
    job = VideoJob("yt:test", "https://ornek.com/v", ".", tarayici_cerezi="chrome")
    job.proc = _SahteProc()  # type: ignore[assignment]
    observed: list[bool] = []
    original = VideoJob.yedek_karari

    def karar(metin: str, aria2c_var: bool, cerez_var: bool,
              aria_denendi: bool, cerezsiz_denendi: bool) -> str:
        observed.append(cerez_var)
        return ""

    VideoJob.yedek_karari = staticmethod(karar)
    try:
        job._pump(None)
    finally:
        VideoJob.yedek_karari = original

    retry = job.build_cmd(aria2c="__yok__", dis_indirici=False, cerezsiz=True)
    ok = (observed == [True] and "--cookies" not in retry
          and "--cookies-from-browser" not in retry)
    print(f"  [{'GECTI' if ok else 'BASARISIZ'}] tarayici cerezi 403'te cerezsiz yedegi tetikler")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
