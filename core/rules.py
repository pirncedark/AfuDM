"""Declarative download rule evaluation; deliberately stateless."""
from __future__ import annotations
import re
from typing import Any
from urllib.parse import urlparse

ACTION_KEYS = ("dest_dir", "proxy", "max_speed_kb", "split", "start_after", "automation_script")

def context(url: str, filename: str = "", size_bytes: int = 0, protocol: str = "http", category: str = "") -> dict[str, Any]:
    parsed = urlparse(url); name = filename or parsed.path.rsplit("/", 1)[-1]
    return {"domain": (parsed.hostname or "").lower(), "extension": name.rsplit(".", 1)[-1].lower() if "." in name else "", "filename": name, "size_mb": size_bytes / 1048576, "protocol": protocol.lower(), "category": category.lower()}

def _one(c: dict, ctx: dict[str, Any]) -> bool:
    value, op, wanted = ctx.get(c.get("field"), ""), c.get("op"), c.get("value")
    try:
        if op == "eq": return value == wanted
        if op == "neq": return value != wanted
        if op == "contains": return str(wanted).lower() in str(value).lower()
        if op == "ends_with": return str(value).lower().endswith(str(wanted).lower())
        if op == "regex": return bool(re.search(str(wanted), str(value), re.I))
        if op == "in": return isinstance(wanted, list) and value in wanted
        if op == "gt": return float(value) > float(wanted)
        if op == "lt": return float(value) < float(wanted)
    except (TypeError, ValueError, re.error): pass
    return False

def matches(rule: dict, ctx: dict[str, Any]) -> bool:
    if not rule.get("active", True): return False
    values = [_one(c, ctx) for c in rule.get("conditions", []) if isinstance(c, dict)]
    return all(values) if rule.get("match_type", "all") == "all" else any(values)

def evaluate(rules: list[dict], defaults: dict[str, Any], ctx: dict[str, Any], overrides: dict[str, Any] | None = None) -> dict:
    options = {k: defaults.get(k) for k in ACTION_KEYS if defaults.get(k) not in (None, "")}
    trace = {k: {"source":"default", "source_id":None, "source_name":"Genel Ayarlar"} for k in options}
    found = [r for r in rules if matches(r, ctx)]
    for rule in sorted(found, key=lambda r: int(r.get("priority", 999999)), reverse=True):
        for key, value in (rule.get("actions") or {}).items():
            if key in ACTION_KEYS and value not in (None, ""):
                options[key] = value; trace[key] = {"source":"rule", "source_id":rule.get("id"), "source_name":rule.get("name", "Kural")}
    for key, value in (overrides or {}).items():
        if key in ACTION_KEYS and value not in (None, ""):
            options[key] = value; trace[key] = {"source":"user", "source_id":None, "source_name":"Bu indirme"}
    return {"matched_rules":[r.get("id") for r in found], "effective_options":options, "trace":trace}
