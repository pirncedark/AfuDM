"""Local rule evaluation, precedence and allowed action fields."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core import rules  # noqa: E402


ctx = rules.context("https://cdn.example.test/Film.MP4", size_bytes=20 * 1024 * 1024,
                    protocol="http", category="video")
rule = {"id": "r1", "name": "Video", "active": True, "match_type": "all",
        "conditions": [{"field": "extension", "op": "eq", "value": "mp4"}],
        "actions": {"dest_dir": "downloads/Video", "max_speed_kb": 700,
                    "split": 8, "unexpected": "ignored"}}
out = rules.evaluate([rule], {"split": 64}, ctx,
                     {"dest_dir": "D:/Kullanici", "split": 4})
assert out["matched_rules"] == ["r1"]
assert out["effective_options"] == {"dest_dir": "D:/Kullanici", "split": 4,
                                    "max_speed_kb": 700}
assert out["trace"]["dest_dir"]["source"] == "user"
assert out["trace"]["max_speed_kb"]["source"] == "rule"
print("GEÇTİ: uzantı koşulu eşleşti; kural hedef/hız/bölme uygulandı; kullanıcı seçimi öncelikli; bilinmeyen işlem yok sayıldı")
