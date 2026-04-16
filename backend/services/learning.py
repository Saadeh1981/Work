# backend/services/learning.py
import json, threading, re
from pathlib import Path
from typing import Dict, List, Any

# Store learned patterns under backend/config/metadata_library.json
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "metadata_library.json"
_lock = threading.Lock()

# Schema:
# {
#   "fields": [
#       {
#         "name": "SCADA_ConnType",
#         "pattern": "(?i)SCADA\\s*(?:Type|Conn(?:ection)?)",
#         "target_column": "SCADA_ConnType"
#       }
#   ]
# }

def _ensure_file(path: Path = DEFAULT_PATH) -> None:
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text('{"fields": []}', encoding="utf-8")

def _load(path: Path = DEFAULT_PATH) -> Dict[str, Any]:
    _ensure_file(path)
    with path.open("r", encoding="utf-8") as f:
        try:
            return json.load(f) or {"fields": []}
        except json.JSONDecodeError:
            return {"fields": []}

def _save(data: Dict[str, Any], path: Path = DEFAULT_PATH) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)

def list_fields() -> List[Dict[str, Any]]:
    with _lock:
        return list(_load().get("fields", []))

def upsert_field(name: str, pattern: str, target_column: str | None = None) -> Dict[str, Any]:
    rec = {"name": name, "pattern": pattern, "target_column": target_column or name}
    with _lock:
        data = _load()
        fields = data.get("fields", [])
        for f in fields:
            if f.get("name") == name:
                f.update(rec)
                break
        else:
            fields.append(rec)
        data["fields"] = fields
        _save(data)
    return rec

# Simple "key: value" line detector for unknown metadata
KEY_VALUE_LINE = re.compile(r"(?m)^\s*([A-Za-z0-9_ /-]{3,40}?)\s*[:=-]\s*([^\n]+)$")

def detect_unknown_fields(text: str, extracted_payload: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Scan OCR text for key: value lines whose label is not in:
      - the existing extracted_payload keys
      - the learned metadata library
    Returns a list of {label, value}.
    """
    known = {k.lower() for k in extracted_payload.keys()}

    library = list_fields()
    for f in library:
        known.add(str(f.get("name", "")).lower())
        known.add(str(f.get("target_column", "")).lower())

    out: List[Dict[str, str]] = []

    for m in KEY_VALUE_LINE.finditer(text):
        key = m.group(1).strip()
        val = m.group(2).strip()
        if not key or key.lower() in known:
            continue
        out.append({"label": key, "value": val})

    # de-duplicate by label
    seen = set()
    uniq: List[Dict[str, str]] = []
    for item in out:
        k = item["label"].lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(item)

    return uniq
