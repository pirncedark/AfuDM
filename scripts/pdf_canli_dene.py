"""Send a PDF to running AfuDM and record completion + events as JSON evidence.

python scripts/pdf_canli_dene.py --url https://example.org/paper.pdf
Approve the normal download dialog while this command waits.
No token, cookies, or signed source URL is written to the evidence file.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def snapshot(data: Path, source: str, started: float):
    with closing(sqlite3.connect((data / "afudm.db").resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT gid, status, filename, dest_dir, error FROM downloads "
                           "WHERE source=? AND added_at>=? ORDER BY id DESC LIMIT 1",
                           (source, started)).fetchone()
        events = conn.execute("SELECT id, level, message, gid FROM events WHERE at>=? ORDER BY id",
                              (started,)).fetchall()
    return dict(row) if row else None, [dict(e) for e in events]


def run(args):
    endpoint = json.loads((args.data / "api_endpoint.json").read_text("utf-8"))
    port = int(endpoint["port"])
    if not 1 <= port <= 65535:
        raise ValueError("Invalid local API port")
    started = time.time()
    payload = {"url": args.url, "filename": args.filename, "kind": "http",
               "mime": "application/pdf", "interactive": True}
    request = urllib.request.Request(f"http://127.0.0.1:{port}/add",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json",
                                                  "X-AfuDM-Token": endpoint["token"]})
    report = {"ok": False, "pending": False, "download": None, "events": []}
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            result = json.load(response)
        report["pending"] = bool(result.get("pending"))
        report["request_id"] = result.get("id")
        if result.get("ok") is False:
            raise RuntimeError("AfuDM rejected the PDF request")
        print("PDF istegi gonderildi. AfuDM penceresinde indirmeyi onayla.")
        deadline = time.monotonic() + args.wait
        while time.monotonic() < deadline:
            row, events = snapshot(args.data, args.url, started)
            report["download"], report["events"] = row, events
            if row and row["status"] == "complete":
                path = Path(row["dest_dir"]) / row["filename"]
                with path.open("rb") as handle:
                    report["pdf_header_valid"] = handle.read(5) == b"%PDF-"
                report["approval_event_valid"] = any(e["gid"] == row["gid"] and
                    e["message"] == "Download approval accepted" for e in events)
                report["ok"] = report["pdf_header_valid"] and report["approval_event_valid"]
                break
            if row and row["status"] == "error":
                break
            time.sleep(0.5)
        if not report["ok"]:
            report["error"] = "PDF completion or approval evidence missing"
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        report["error"] = type(exc).__name__
        try:
            report["download"], report["events"] = snapshot(args.data, args.url, started)
        except (OSError, sqlite3.Error):
            pass
    # Error messages may echo URL or credentials; retain event identity and level only.
    for event in report["events"]:
        event["message"] = ("Download approval accepted" if event["message"] ==
                            "Download approval accepted" else "[recorded in local events]")
    if report["download"]:
        report["download"].pop("error", None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PDF evidence: {args.output} (ok={report['ok']})")
    return 0 if report["ok"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--filename", default="afudm-proof.pdf")
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--output", type=Path, default=ROOT / "pdf_canli_kanit.json")
    parser.add_argument("--wait", type=float, default=120)
    args = parser.parse_args()
    if not args.url.startswith(("http://", "https://")) or args.wait <= 0:
        parser.error("HTTP(S) URL and positive wait required")
    try:
        return run(args)
    except (OSError, ValueError, KeyError) as exc:
        print(f"PDF evidence failed: {type(exc).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
