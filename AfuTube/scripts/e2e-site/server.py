#!/usr/bin/env python3
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import os
ROOT = Path(__file__).resolve().parent
LOG = Path(os.environ.get("AFUTUBE_E2E_REFERER_LOG", "/tmp/afutube-referer.log"))
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(ROOT), **kwargs)
    def do_GET(self):
        if self.path.split("?", 1)[0] in ("/clip.mp4", "/ads/vast/preroll.mp4"):
            with LOG.open("a", encoding="utf-8") as f: f.write(f"{self.path}\tReferer: {self.headers.get('Referer', '')}\n")
        super().do_GET()
ThreadingHTTPServer(("0.0.0.0", 8765), Handler).serve_forever()
