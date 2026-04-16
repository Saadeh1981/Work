# backend/services/catalog_mapper.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import re
from datetime import datetime

from backend.services.pdf_utils import rasterize_pdf_to_jpegs
import pytesseract
from PIL import Image
import io


def _ocr_pdf_bytes(pdf_bytes: bytes) -> str:
    images = rasterize_pdf_to_jpegs(pdf_bytes, max_pages=4, dpi=150)

    texts = []
    for img_bytes in images:
        img = Image.open(io.BytesIO(img_bytes))
        txt = pytesseract.image_to_string(img)
        if txt:
            texts.append(txt)

    return "\n".join(texts).strip()

# Reuse your normalizers
try:
    from backend.services.normalize import normalize_inverter_model, normalize_module_model
except Exception:
    # allow running tests even if import path differs
    normalize_inverter_model = None
    normalize_module_model = None


# ----------------------------
# Helpers: coercion / validation
# ----------------------------

def _to_bool(v: Any) -> Optional[bool]:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in {"y", "yes", "true", "1"}:
        return True
    if s in {"n", "no", "false", "0"}:
        return False
    return None

def _to_number(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    s = s.replace(",", "")
    s = re.sub(r"[^0-9\.\-\+]", "", s)
    if not s or s in {"+", "-", ".", "+.", "-."}:
        return None
    try:
        return float(s)
    except ValueError:
        return None

def _to_date_yyyy_mm_dd(v: Any) -> Optional[str]:
    """Return ISO date string (yyyy-mm-dd) or None."""
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            return s
        for fmt in ("%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
            except Exception:
                pass
        return None
    return None

def _coerce_by_kind(value: Any, field_def: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
    """
    Returns (coerced_value, warning_reason_if_any)
    """
    kind = (field_def.get("kind") or "string").lower()

    if value is None or value == "":
        return None, None

    if kind == "string":
        return str(value).strip(), None

    if kind == "number":
        n = _to_number(value)
        if n is None:
            return None, "invalid_number"
        return n, None

    if kind == "bool":
        b = _to_bool(value)
        if b is None:
            return None, "invalid_bool"
        return b, None

    if kind == "date":
        d = _to_date_yyyy_mm_dd(value)
        if d is None:
            return None, "invalid_date"
        return d, None

    if kind == "enum":
        allowed = field_def.get("enum") or []
        s = str(value).strip()
        if s in allowed:
            return s, None
        for a in allowed:
            if a.lower() == s.lower():
                return a, None
        return None, "invalid_enum"

    return str(value).strip(), None


# ----------------------------
# Helpers: extraction (mapping-layer)
# ----------------------------

def _normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def _flatten_text(item: Dict[str, Any]) -> str:
    # direct keys
    for k in ("_raw_text", "raw_text", "text", "_text", "content"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v

    # extraction block
    extracted = item.get("extracted")
    if isinstance(extracted, dict):
        for k in ("text", "raw_text", "_raw_text"):
            v = extracted.get(k)
            if isinstance(v, str) and v.strip():
                return v

    # meta block
    meta = item.get("_extraction_meta") or {}
    if isinstance(meta, dict):
        for k in ("_raw_text", "raw_text", "text"):
            v = meta.get(k)
            if isinstance(v, str) and v.strip():
                return v

    return ""


def _normalize_detection_text(text: str) -> str:
    t = text or ""
    t = t.upper()
    t = re.sub(r"\s+", " ", t)
    t = t.replace("I N V E R T E R", "INVERTER")
    return t.strip()

def _extract_inverter_names_from_text(text: str) -> List[str]:
    import re

    if not text:
        return []

    # normalize
    t = text.upper()

    # VERY permissive pattern
    pattern = r"INVERTER\s+([0-9]+(?:\.[0-9]+)+)"

    matches = re.findall(pattern, t)

    out = []
    seen = set()

    for m in matches:
        name = f"INVERTER {m}"
        if name not in seen:
            seen.add(name)
            out.append(name)

    print("DEBUG DETECTED INVERTERS:", len(out))
    print("DEBUG DETECTED INVERTERS SAMPLE:", out[:10])

    return out

def _extract_combiner_names_from_text(text: str) -> List[str]:
    t = _normalize_detection_text(text)

    patterns = [
        r"\bCOMBINER\s+([A-Z0-9\.\-]+)\b",
        r"\bCB[\s\-]?(\d+)\b",
    ]

    seen = set()
    out: List[str] = []

    for pattern in patterns:
        matches = re.findall(pattern, t, flags=re.IGNORECASE)
        for m in matches:
            name = f"COMBINER {m}"
            if name not in seen:
                seen.add(name)
                out.append(name)
    print("DEBUG DETECTED COMBINERS:", len(out))
    return out


def _extract_tracker_names_from_text(text: str) -> List[str]:
    t = _normalize_detection_text(text)

    patterns = [
        r"\bTRACKER\s+([A-Z0-9\.\-]+)\b",
        r"\bROW\s+(\d+)\b",
    ]

    seen = set()
    out: List[str] = []

    for pattern in patterns:
        matches = re.findall(pattern, t, flags=re.IGNORECASE)
        for m in matches:
            name = f"TRACKER {m}"
            if name not in seen:
                seen.add(name)
                out.append(name)
    print("DEBUG DETECTED TRACKERS:", len(out))
    return out


def _extract_meter_names_from_text(text: str) -> List[str]:
    t = _normalize_detection_text(text)
    patterns = [
        r"\bPRIMARY\s+METER\b",
        r"\bREVENUE\s+METER\b",
        r"\bMETER\s+([A-Z0-9][A-Z0-9\.\-_]+)\b",
    ]

    seen = set()
    out: List[str] = []

    for pattern in patterns:
        matches = re.findall(pattern, t, flags=re.IGNORECASE)
        if pattern.endswith(r"\b"):
            # full literal hits like PRIMARY METER / REVENUE METER
            if re.search(pattern, t, flags=re.IGNORECASE):
                literal = re.search(pattern, t, flags=re.IGNORECASE).group(0)
                name = _normalize_space(literal)
                if name not in seen:
                    seen.add(name)
                    out.append(name)
        else:
            for m in matches:
                name = f"METER {m}"
                if name not in seen:
                    seen.add(name)
                    out.append(name)

    return out


def _extract_weather_station_names_from_text(text: str) -> List[str]:
    t = _normalize_detection_text(text)
    patterns = [
        r"\bWEATHER\s+STATION\s+([A-Z0-9][A-Z0-9\.\-_]+)\b",
        r"\bWEATHER\s+STATION\b",
        r"\bMET\s+STATION\b",
        r"\bGHI\s+SENSOR\b",
    ]

    seen = set()
    out: List[str] = []

    for pattern in patterns:
        if pattern.endswith(r"\b") and "(" not in pattern and "[" not in pattern and "+" not in pattern:
            for m in re.finditer(pattern, t, flags=re.IGNORECASE):
                name = _normalize_space(m.group(0))
                if name not in seen:
                    seen.add(name)
                    out.append(name)
        else:
            matches = re.findall(pattern, t, flags=re.IGNORECASE)
            for m in matches:
                name = f"WEATHER STATION {m}"
                if name not in seen:
                    seen.add(name)
                    out.append(name)

    return out


def _extract_transformer_names_from_text(text: str) -> List[str]:
    t = _normalize_detection_text(text)
    patterns = [
        r"\bTRANSFORMER\s+([A-Z0-9][A-Z0-9\.\-_]+)\b",
        r"\bTX\s*[- ]?([A-Z0-9][A-Z0-9\.\-_]+)\b",
        r"\bSUBSTATION\b",
    ]

    seen = set()
    out: List[str] = []

    for pattern in patterns:
        if pattern == r"\bSUBSTATION\b":
            for m in re.finditer(pattern, t, flags=re.IGNORECASE):
                name = "SUBSTATION"
                if name not in seen:
                    seen.add(name)
                    out.append(name)
        else:
            matches = re.findall(pattern, t, flags=re.IGNORECASE)
            for m in matches:
                prefix = "TRANSFORMER" if "TRANSFORMER" in pattern else "TX"
                name = f"{prefix} {m}"
                if name not in seen:
                    seen.add(name)
                    out.append(name)

    return out


def _extract_poa_names_from_text(text: str) -> List[str]:
    t = _normalize_detection_text(text)
    patterns = [
        r"\bPLANE\s+OF\s+ARRAY\b",
        r"\bPOA\b",
    ]

    seen = set()
    out: List[str] = []

    for pattern in patterns:
        for m in re.finditer(pattern, t, flags=re.IGNORECASE):
            name = _normalize_space(m.group(0))
            if name not in seen:
                seen.add(name)
                out.append(name)

    return out

def _extract_project_name(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (value, evidence_snippet)
    Tries a few common patterns seen in as-builts.
    """
    t = text or ""
    # Common labels
    patterns = [
        r"PROJECT\s*NAME\s*[:\-]\s*(?P<v>[^\n\r]{3,120})",
        r"PLANT\s*NAME\s*[:\-]\s*(?P<v>[^\n\r]{3,120})",
        r"SITE\s*NAME\s*[:\-]\s*(?P<v>[^\n\r]{3,120})",
    ]
    for p in patterns:
        m = re.search(p, t, flags=re.IGNORECASE)
        if m:
            v = _normalize_space(m.group("v"))
            # prune common trailing junk
            v = re.sub(r"\s{2,}.*$", "", v).strip()
            if v:
                ev = _normalize_space(m.group(0))[:180]
                return v, ev

    # Fallback: if "PlantName" block already contains a multi-line header,
    # take first line-ish (but keep conservative)
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    for ln in lines[:40]:
        # skip obvious non-names
        if re.search(r"^\s*(SHEET|DATE|DRAWN|REV|SCALE|NOTES|GENERAL\s+NOTES)\b", ln, re.IGNORECASE):
            continue
        if 6 <= len(ln) <= 80 and any(ch.isalpha() for ch in ln):
            # avoid lines that are mostly numbers
            alpha_ratio = sum(c.isalpha() for c in ln) / max(1, len(ln))
            if alpha_ratio >= 0.25:
                return _normalize_space(ln), _normalize_space(ln)[:180]
    return None, None

def _extract_site_address(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Try to capture the site address block that appears under the project/site name.
    Returns (address, evidence_snippet)
    """
    t = text or ""

    patterns = [
        r"FILLMORE ELEMENTARY SCHOOL\s+(?P<line1>\d{1,6}\s+[A-Z0-9\.\- ]+)\s+(?P<line2>[A-Z][A-Z ]+,\s*[A-Z]+)",
        r"SUSD-FILLMORE ES\s+FILLMORE ELEMENTARY SCHOOL\s+(?P<line1>\d{1,6}\s+[A-Z0-9\.\- ]+)\s+(?P<line2>[A-Z][A-Z ]+,\s*[A-Z]+)",
        r"(?P<line1>\d{1,6}\s+[A-Z0-9\.\- ]+)\s+(?P<line2>[A-Z][A-Z ]+,\s*[A-Z]+)",
    ]

    for p in patterns:
        m = re.search(p, t, flags=re.IGNORECASE)
        if not m:
            continue

        line1 = _normalize_space(m.group("line1"))
        line2 = _normalize_space(m.group("line2"))

        candidate = f"{line1}, {line2}".strip(" ,")
        if "PORTLAND" in candidate.upper():
            continue
        if "LOUISVILLE" in candidate.upper():
            continue

        return candidate, _normalize_space(m.group(0))[:200]

    return None, None

def _to_kw(value: float, unit: str) -> float:
    u = (unit or "").lower()
    if u == "mw":
        return value * 1000.0
    if u == "w":
        return value / 1000.0
    # default kW
    return value

def _extract_capacities_kw(text: str) -> Tuple[Optional[float], Optional[float], List[str]]:
    """
    Returns (ac_kw, dc_kw, evidence_snippets[])
    Supports patterns like:
      AC CAPACITY: 5 MW
      DC Capacity (kW): 6200
      6.2MWdc / 5.0MWac
    """
    t = text or ""
    evid: List[str] = []
    ac_kw: Optional[float] = None
    dc_kw: Optional[float] = None

    # 1) Labeled lines
    cap_patterns = [
        # AC
        (r"\bAC\s*(?:CAPACITY|CAP\.?)\s*[:\-]?\s*(?P<num>\d+(?:\.\d+)?)\s*(?P<u>MW|kW|W)\b", "ac"),
        (r"\b(?:CAPACITY)\s*[:\-]?\s*(?P<num>\d+(?:\.\d+)?)\s*(?P<u>MW|kW|W)\s*(?:AC)\b", "ac"),
        # DC
        (r"\bDC\s*(?:CAPACITY|CAP\.?)\s*[:\-]?\s*(?P<num>\d+(?:\.\d+)?)\s*(?P<u>MW|kW|W)\b", "dc"),
        (r"\b(?:CAPACITY)\s*[:\-]?\s*(?P<num>\d+(?:\.\d+)?)\s*(?P<u>MW|kW|W)\s*(?:DC)\b", "dc"),
    ]
    for pat, kind in cap_patterns:
        m = re.search(pat, t, flags=re.IGNORECASE)
        if not m:
            continue
        n = _to_number(m.group("num"))
        if n is None:
            continue
        # 🚫 IGNORE OCR JUNK like 000wAC / 0.0kW
        if float(n) == 0.0:
            continue
        kw = _to_kw(float(n), m.group("u"))
        ev = _normalize_space(m.group(0))[:180]
        evid.append(ev)
        if kind == "ac" and ac_kw is None:
            ac_kw = kw
        if kind == "dc" and dc_kw is None:
            dc_kw = kw

    # 2) Inline combined like "5.0MWac" / "6.2MWdc"
    inline = re.findall(r"(?P<num>\d+(?:\.\d+)?)\s*(?P<u>MW|kW|W)\s*(?P<kind>ac|dc)\b", t, flags=re.IGNORECASE)
    for num, unit, kind in inline:
        n = _to_number(num)
        if n is None:
            continue
        
        # 🚫 IGNORE OCR JUNK like 000wAC
        if float(n) == 0.0:
            continue

        # 🚫 OPTIONAL: ignore inline W entirely (recommended)
        if unit.lower() == "w":
            continue
        
        kw = _to_kw(float(n), unit)
        evid.append(_normalize_space(f"{num}{unit}{kind}")[:180])
        if kind.lower() == "ac" and ac_kw is None:
            ac_kw = kw
        if kind.lower() == "dc" and dc_kw is None:
            dc_kw = kw

    return ac_kw, dc_kw, evid[:6]

def _extract_module_info(text: str) -> Tuple[Optional[int], Optional[str], List[str]]:
    """
    Returns (module_count, module_model, evidence_snippets[])
    """
    t = text or ""
    evid: List[str] = []

    module_count: Optional[int] = None
    module_model: Optional[str] = None

    # Count patterns
    count_patterns = [
        r"\bMODULES?\s*(?:COUNT|QTY|QUANTITY)\s*[:\-]?\s*(?P<num>\d{2,9})\b",
        r"\bTOTAL\s*MODULES?\s*[:\-]?\s*(?P<num>\d{2,9})\b",
        r"\bPV\s*MODULES?\s*[:\-]?\s*(?P<num>\d{2,9})\b",
    ]
    for p in count_patterns:
        m = re.search(p, t, flags=re.IGNORECASE)
        if m:
            n = _to_number(m.group("num"))
            if n is not None:
                module_count = int(n)
                evid.append(_normalize_space(m.group(0))[:180])
                break

    # Model patterns
    model_patterns = [
        r"\bMODULE\s*(?:MODEL|TYPE)\s*[:\-]\s*(?P<v>[A-Z0-9][A-Z0-9\-\./_]{3,80})",
        r"\bPV\s*MODULE\s*(?:MODEL|TYPE)\s*[:\-]\s*(?P<v>[A-Z0-9][A-Z0-9\-\./_]{3,80})",
        # Sometimes listed like "MODULE: STP210S-18/UB-1"
        r"\bMODULES?\s*[:\-]\s*(?P<v>[A-Z0-9][A-Z0-9\-\./_]{3,80})",
    ]
    for p in model_patterns:
        m = re.search(p, t, flags=re.IGNORECASE)
        if m:
            v = _normalize_space(m.group("v"))
            if v:
                if normalize_module_model:
                    try:
                        normalized = normalize_module_model(v)
                        if isinstance(normalized, tuple):
                            v = normalized[0]
                        else:
                            v = normalized
                    except Exception:
                        pass
                module_model = v
                evid.append(_normalize_space(m.group(0))[:180])
                break

    return module_count, module_model, evid[:6]


# ----------------------------
# Path setters for group items
# ----------------------------

_GROUP_PATH_RE = re.compile(r"^(?P<group>[A-Za-z_]\w*)\[(?P<idx>\d+)\]\.(?P<field>[A-Za-z_]\w*)$")

def set_group_path(groups: Dict[str, List[Dict[str, Any]]], path: str, value: Any) -> None:
    """
    Supports paths like: Inverters[0].Model
    """
    m = _GROUP_PATH_RE.match(path)
    if not m:
        return
    group = m.group("group")
    idx = int(m.group("idx"))
    field = m.group("field")

    arr = groups.setdefault(group, [])
    while len(arr) <= idx:
        arr.append({})
    arr[idx][field] = value


# ----------------------------
# Catalog indexing
# ----------------------------

@dataclass
class CatalogIndex:
    version: str
    site_fields: Dict[str, Dict[str, Any]]         # key -> def
    groups: Dict[str, Dict[str, Any]]              # group name -> {max_items, fields_by_key}

def index_catalog(catalog: Dict[str, Any]) -> CatalogIndex:
    site_defs = {f["key"]: f for f in (catalog.get("site_fields") or [])}
    groups_idx: Dict[str, Dict[str, Any]] = {}
    for g in (catalog.get("groups") or []):
        fields_by_key = {f["key"]: f for f in (g.get("fields") or [])}
        groups_idx[g["name"]] = {
            "label": g.get("label"),
            "max_items": int(g.get("max_items") or 0),
            "fields_by_key": fields_by_key,
        }
    return CatalogIndex(
        version=str(catalog.get("version") or "1.0"),
        site_fields=site_defs,
        groups=groups_idx,
    )


# ----------------------------
# Mapping rules (v1)
# ----------------------------

def _mw_to_kw(mw: Any) -> Optional[float]:
    n = _to_number(mw)
    if n is None:
        return None
    return n * 1000.0

def _get_extracted_block(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Your batch item shape is typically:
      {"extracted": {...}, "_extraction_meta": {...}, "warnings": {...}, ...}
    But be tolerant if someone passes just the extracted dict.
    """
    if isinstance(item.get("extracted"), dict):
        return item["extracted"]
    return item

def _get_meta(item: Dict[str, Any]) -> Dict[str, Any]:
    return item.get("_extraction_meta") or {}

def _meta_get(meta: Dict[str, Any], key: str) -> Dict[str, Any]:
    v = meta.get(key)
    return v if isinstance(v, dict) else {}

def _meta_put(out_meta: Dict[str, Any], catalog_key: str, confidence: Optional[float], evidence: Optional[str], source: str) -> None:
    out_meta.setdefault("fields", {})
    out_meta["fields"][catalog_key] = {
        "confidence": confidence,
        "evidence": evidence,
        "source": source,
    }

def _pick_first(*vals: Any) -> Any:
    for v in vals:
        if v is not None and v != "":
            return v
    return None

BAD_PLANT_NAMES = {
    "TITLE SHEET",
    "AS BUILT",
    "FOR CONSTRUCTION",
    "SYMBOL",
    "BATTERY",
    "BESS FIELD",
    "BLOCK ARRAY CONFIGURATION",
    "LINETYPE LEGEND",
    "WARNING SIGNS",
    "KEYED NOTES",
    "CIVIL DETAILS",
    "AREA 1 & 2 SITE MAP",
    "INVERTER 1.1.1",
    "INVERTER SPECIFIC WARNING",
    "COMBINER HARNESS NAMING CONVENTION",
    "COMBINER HARNESS AT TRACKER",
    "DC FEEDER TRENCH",
    "EQUIPMENT SPECIFICATIONS",
    "FIBER OPTIC DIAGRAM",
    "ZONE A",
    "BLYMYER",
    "DANGER",
}

BAD_MODULE_VALUES = {
    "DATA",
    "SHEET",
    "LIQUID",
    "COOLING",
}


def is_valid_plant_name(name: str | None) -> bool:
    if not name:
        return False
    name = str(name).strip().upper()

    if name in BAD_PLANT_NAMES:
        return False
    if len(name) < 5:
        return False
    return True


def score_plant_name(name: str | None) -> int:
    if not name:
        return -999
    n = str(name).strip().upper()
    score = 0
    if "SAN JUAN" in n:
        score += 5
    if "SOLAR" in n:
        score += 5
    if "FACILITY" in n:
        score += 3
    if "MWAC" in n:
        score += 2
    if n in BAD_PLANT_NAMES:
        score -= 100
    return score


def is_valid_address(value: str | None) -> bool:
    if not value:
        return False
    value = str(value).strip().upper()

    if "MWAC" in value:
        return False
    if "AC," in value:
        return False
    if "INSTALL FIBER" in value:
        return False
    if "SLOPE MAXIMUM" in value:
        return False
    if "MARINA VILLAGE" in value:
        return False
    if "PASEO PADRE" in value:
        return False
    return True


def is_valid_module_value(value: str | None) -> bool:
    if not value:
        return False
    return str(value).strip().upper() not in BAD_MODULE_VALUES

def build_site_fields(item: Dict[str, Any], cat: CatalogIndex, out_meta: Dict[str, Any], warnings: Dict[str, Any]) -> Dict[str, Any]:
    extracted = _get_extracted_block(item)
    meta_in = _get_meta(item)

    raw_text = _flatten_text(item)
    print("DEBUG mapper raw_text_len:", len(raw_text))
    print("DEBUG mapper raw_text_sample:", raw_text[:300])

    # Derivations from raw text (mapping-layer helpers)
    derived_plant, plant_ev = _extract_project_name(raw_text)
    derived_address, address_ev = _extract_site_address(raw_text)
    derived_ac_kw, derived_dc_kw, cap_evs = _extract_capacities_kw(raw_text)
    derived_mod_count, derived_mod_model, mod_evs = _extract_module_info(raw_text)

    site: Dict[str, Any] = {}

    # ---- PlantName
    plant_candidates = [
        extracted.get("PlantName"),
        extracted.get("plant_name"),
        derived_plant,
    ]

    valid_plant_candidates = [
        str(p).strip()
        for p in plant_candidates
        if p not in (None, "", [], {}) and is_valid_plant_name(str(p))
    ]

    plant = None
    if valid_plant_candidates:
        plant = max(valid_plant_candidates, key=score_plant_name)

    if "PlantName" in cat.site_fields:
        coerced, reason = _coerce_by_kind(plant, cat.site_fields["PlantName"])
        if reason:
            warnings.setdefault("invalid_fields", []).append({"key": "PlantName", "reason": reason, "value": plant})
        elif coerced is not None:
            site["PlantName"] = coerced

        m = _meta_get(meta_in, "PlantName") or _meta_get(meta_in, "plant_name")
        if m:
            _meta_put(out_meta, "PlantName", m.get("confidence"), m.get("evidence"), m.get("source") or "base_parse")
        else:
            _meta_put(out_meta, "PlantName", 0.6 if plant else None, plant_ev, "derived_text")

    # ---- AC_Capacity_kW (catalog expects kW)
    ac_kw = _pick_first(
        extracted.get("AC_Capacity_kW"),
        extracted.get("ac_capacity_kw"),
        _mw_to_kw(extracted.get("ac_capacity_mw")),
        derived_ac_kw,
    )
    if "AC_Capacity_kW" in cat.site_fields:
        coerced, reason = _coerce_by_kind(ac_kw, cat.site_fields["AC_Capacity_kW"])
        if reason:
            warnings.setdefault("invalid_fields", []).append({"key": "AC_Capacity_kW", "reason": reason, "value": ac_kw})
        else:
            site["AC_Capacity_kW"] = coerced

        m = _meta_get(meta_in, "AC_Capacity_kW") or _meta_get(meta_in, "ac_capacity_mw") or _meta_get(meta_in, "ac_capacity_kw")
        if m:
            _meta_put(out_meta, "AC_Capacity_kW", m.get("confidence"), m.get("evidence"), m.get("source") or "derived")
        else:
            _meta_put(out_meta, "AC_Capacity_kW", 0.6 if derived_ac_kw is not None else None, (cap_evs[0] if cap_evs else None), "derived_text")

    # ---- DC_Capacity_kW
    dc_kw = _pick_first(
        extracted.get("DC_Capacity_kW"),
        extracted.get("dc_capacity_kw"),
        _mw_to_kw(extracted.get("dc_capacity_mw")),
        derived_dc_kw,
    )
    if "DC_Capacity_kW" in cat.site_fields:
        coerced, reason = _coerce_by_kind(dc_kw, cat.site_fields["DC_Capacity_kW"])
        if reason:
            warnings.setdefault("invalid_fields", []).append({"key": "DC_Capacity_kW", "reason": reason, "value": dc_kw})
        else:
            site["DC_Capacity_kW"] = coerced

        m = _meta_get(meta_in, "DC_Capacity_kW") or _meta_get(meta_in, "dc_capacity_mw") or _meta_get(meta_in, "dc_capacity_kw")
        if m:
            _meta_put(out_meta, "DC_Capacity_kW", m.get("confidence"), m.get("evidence"), m.get("source") or "derived")
        else:
            # pick an evidence line that mentions DC if available
            dc_ev = None
            for ev in cap_evs:
                if re.search(r"\bdc\b", ev, re.IGNORECASE):
                    dc_ev = ev
                    break
            _meta_put(out_meta, "DC_Capacity_kW", 0.6 if derived_dc_kw is not None else None, dc_ev or (cap_evs[0] if cap_evs else None), "derived_text")
    # ---- Country
    country = _pick_first(
        extracted.get("Country"),
        extracted.get("country"),
    )
    if "Country" in cat.site_fields:
        coerced, reason = _coerce_by_kind(country, cat.site_fields["Country"])
        if reason:
            warnings.setdefault("invalid_fields", []).append(
                {"key": "Country", "reason": reason, "value": country}
            )
        elif coerced is not None:
            site["Country"] = coerced

        m = _meta_get(meta_in, "Country") or _meta_get(meta_in, "country")
        if m:
            _meta_put(out_meta, "Country", m.get("confidence"), m.get("evidence"), m.get("source") or "base_parse")

    # ---- Latitude
    latitude = _pick_first(
        extracted.get("Latitude"),
        extracted.get("latitude"),
        extracted.get("lat"),
    )
    if "Latitude" in cat.site_fields:
        coerced, reason = _coerce_by_kind(latitude, cat.site_fields["Latitude"])
        if reason:
            warnings.setdefault("invalid_fields", []).append(
                {"key": "Latitude", "reason": reason, "value": latitude}
            )
        elif coerced is not None:
            site["Latitude"] = coerced

        m = (
            _meta_get(meta_in, "Latitude")
            or _meta_get(meta_in, "latitude")
            or _meta_get(meta_in, "lat")
        )
        if m:
            _meta_put(out_meta, "Latitude", m.get("confidence"), m.get("evidence"), m.get("source") or "base_parse")

    # ---- Longitude
    longitude = _pick_first(
        extracted.get("Longitude"),
        extracted.get("longitude"),
        extracted.get("long"),
    )
    if "Longitude" in cat.site_fields:
        coerced, reason = _coerce_by_kind(longitude, cat.site_fields["Longitude"])
        if reason:
            warnings.setdefault("invalid_fields", []).append(
                {"key": "Longitude", "reason": reason, "value": longitude}
            )
        elif coerced is not None:
            site["Longitude"] = coerced

        m = (
            _meta_get(meta_in, "Longitude")
            or _meta_get(meta_in, "longitude")
            or _meta_get(meta_in, "long")
        )
        if m:
            _meta_put(out_meta, "Longitude", m.get("confidence"), m.get("evidence"), m.get("source") or "base_parse")

    # ---- Address
    address_candidates = [
        extracted.get("Address"),
        extracted.get("address"),
        derived_address,
    ]

    valid_addresses = [
        str(a).strip()
        for a in address_candidates
        if a not in (None, "", [], {}) and is_valid_address(str(a))
    ]

    address = valid_addresses[0] if valid_addresses else None

    if address is not None:
        site["Address"] = address

    # ---- ModuleCount (if present in catalog)
    # Your extraction already uses module_count/module_models sometimes; we add derived fallback.
    if "ModuleCount" in cat.site_fields:
        mc = _pick_first(
            extracted.get("ModuleCount"),
            extracted.get("module_count"),
            derived_mod_count,
        )
        coerced, reason = _coerce_by_kind(mc, cat.site_fields["ModuleCount"])
        if reason:
            warnings.setdefault("invalid_fields", []).append({"key": "ModuleCount", "reason": reason, "value": mc})
        else:
            site["ModuleCount"] = coerced

        m = _meta_get(meta_in, "ModuleCount") or _meta_get(meta_in, "module_count")
        if m:
            _meta_put(out_meta, "ModuleCount", m.get("confidence"), m.get("evidence"), m.get("source") or "base_parse")
        else:
            _meta_put(out_meta, "ModuleCount", 0.55 if derived_mod_count is not None else None, (mod_evs[0] if mod_evs else None), "derived_text")
    # ---- ModuleMake (if present in catalog)
    if "ModuleMake" in cat.site_fields:
        mk = _pick_first(
            extracted.get("ModuleMake"),
            extracted.get("module_make"),
        )

        if isinstance(mk, str) and not is_valid_module_value(mk):
            mk = None

        coerced, reason = _coerce_by_kind(mk, cat.site_fields["ModuleMake"])
        if reason:
            warnings.setdefault("invalid_fields", []).append({"key": "ModuleMake", "reason": reason, "value": mk})
        elif coerced is not None:
            site["ModuleMake"] = coerced

    # ---- ModuleModel (if present in catalog)
    if "ModuleModel" in cat.site_fields:
        # prefer extracted module_models list first item, then module_model, then derived
        mm = None
        ml = extracted.get("module_models") or extracted.get("ModuleModels")
        if isinstance(ml, list) and ml:
            mm = ml[0]
        elif isinstance(ml, str) and ml.strip():
            mm = ml.strip()

        mm = _pick_first(
            extracted.get("ModuleModel"),
            extracted.get("module_model"),
            mm,
            derived_mod_model,
        )

        # optional normalize via your normalizer
        if isinstance(mm, str) and normalize_module_model:
            try:
                normalized = normalize_module_model(mm)
                if isinstance(normalized, tuple):
                    mm = normalized[0]
                else:
                    mm = normalized
            except Exception:
                pass
        if isinstance(mm, str) and not is_valid_module_value(mm):
            mm = None

        coerced, reason = _coerce_by_kind(mm, cat.site_fields["ModuleModel"])
        if reason:
            warnings.setdefault("invalid_fields", []).append({"key": "ModuleModel", "reason": reason, "value": mm})
        else:
            site["ModuleModel"] = coerced

        m = _meta_get(meta_in, "ModuleModel") or _meta_get(meta_in, "module_models") or _meta_get(meta_in, "module_model")
        if m:
            _meta_put(out_meta, "ModuleModel", m.get("confidence"), m.get("evidence"), m.get("source") or "base_parse")
        else:
            # choose evidence that includes model label if possible
            ev = None
            for e in mod_evs:
                if re.search(r"\bmodel\b|\btype\b", e, re.IGNORECASE):
                    ev = e
                    break
            _meta_put(out_meta, "ModuleModel", 0.55 if derived_mod_model else None, ev or (mod_evs[0] if mod_evs else None), "derived_text")

    # Add more site field mappings incrementally here:
    # CustomerName, Country, ExportLimit_kW, Latitude, Longitude, CommissioningDate, etc.
    print("DEBUG build_site_fields output:", site)
    return site


def build_inverters_group(item: Dict[str, Any], cat: CatalogIndex, out_meta: Dict[str, Any], warnings: Dict[str, Any]) -> List[Dict[str, Any]]:
    extracted = _get_extracted_block(item)
    meta_in = _get_meta(item)
    raw_text = _flatten_text(item)

    group_def = cat.groups.get("Inverters")
    if not group_def:
        return []

    max_items = int(group_def.get("max_items") or 0)
    fields_by_key: Dict[str, Dict[str, Any]] = group_def["fields_by_key"]

    inv_models = extracted.get("inverter_models") or extracted.get("InverterModels") or []
    if isinstance(inv_models, str):
        inv_models = [inv_models]

    inv_count = extracted.get("inverter_count") or extracted.get("InverterCount")

    fallback_names = _extract_inverter_names_from_text(raw_text)
    print("DEBUG mapper inverter_models:", inv_models[:5] if isinstance(inv_models, list) else inv_models)
    print("DEBUG mapper fallback_inverter_names_count:", len(fallback_names))
    print("DEBUG mapper fallback_inverter_names_preview:", fallback_names[:10])

    out: List[Dict[str, Any]] = []

    if inv_models:
        source_items = inv_models[:max_items]
        source_mode = "model"
    else:
        source_items = fallback_names[:max_items]
        source_mode = "name"

    for idx, raw_value in enumerate(source_items):
        rec: Dict[str, Any] = {}
        vendor = None

        if source_mode == "model":
            model = str(raw_value).strip()
            if normalize_inverter_model:
                try:
                    model, vendor = normalize_inverter_model(model)
                except Exception:
                    pass

            if "Model" in fields_by_key:
                coerced, reason = _coerce_by_kind(model, fields_by_key["Model"])
                if reason:
                    warnings.setdefault("invalid_fields", []).append(
                        {"key": f"Inverters[{idx}].Model", "reason": reason, "value": model}
                    )
                else:
                    rec["Model"] = coerced

                m = _meta_get(meta_in, f"Inverters[{idx}].Model") or _meta_get(meta_in, "inverter_models")
                _meta_put(
                    out_meta,
                    f"Inverters[{idx}].Model",
                    m.get("confidence"),
                    m.get("evidence"),
                    m.get("source") or "library_or_base",
                )

        else:
            inverter_name = str(raw_value).strip()

            if "PlatformName" in fields_by_key:
                coerced, reason = _coerce_by_kind(inverter_name, fields_by_key["PlatformName"])
                if not reason and coerced is not None:
                    rec["PlatformName"] = coerced

            _meta_put(
                out_meta,
                f"Inverters[{idx}].PlatformName",
                0.7,
                inverter_name,
                "derived_text",
            )

        if vendor and "Manufacturer" in fields_by_key:
            coerced, reason = _coerce_by_kind(vendor, fields_by_key["Manufacturer"])
            if not reason:
                rec["Manufacturer"] = coerced

        if "PlatformName" in fields_by_key and "PlatformName" not in rec:
            rec["PlatformName"] = f"INV-{idx+1:02d}"

        if "AC_Capacity_kW" in fields_by_key:
            site_ac_kw = _mw_to_kw(extracted.get("ac_capacity_mw")) if extracted.get("ac_capacity_mw") is not None else extracted.get("AC_Capacity_kW")
            site_ac_kw = _to_number(site_ac_kw)
            c = _to_number(inv_count)
            if site_ac_kw is not None and c and len(source_items) == 1:
                per = site_ac_kw / c
                coerced, reason = _coerce_by_kind(per, fields_by_key["AC_Capacity_kW"])
                if not reason:
                    rec["AC_Capacity_kW"] = coerced

        out.append(rec)

    return out
def _build_name_only_group(
    *,
    item: Dict[str, Any],
    cat: CatalogIndex,
    group_name: str,
    field_key: str,
    detector,
    out_meta: Dict[str, Any],
) -> List[Dict[str, Any]]:
    group_def = cat.groups.get(group_name)
    if not group_def:
        return []

    max_items = int(group_def.get("max_items") or 0)
    fields_by_key: Dict[str, Dict[str, Any]] = group_def["fields_by_key"]

    if field_key not in fields_by_key:
        return []

    raw_text = _flatten_text(item)
    names = detector(raw_text)

    print(f"DEBUG mapper {group_name}_count:", len(names))
    print(f"DEBUG mapper {group_name}_preview:", names[:10])

    out: List[Dict[str, Any]] = []
    for idx, name in enumerate(names[:max_items]):
        rec: Dict[str, Any] = {}

        coerced, reason = _coerce_by_kind(name, fields_by_key[field_key])
        if not reason and coerced is not None:
            rec[field_key] = coerced
            _meta_put(
                out_meta,
                f"{group_name}[{idx}].{field_key}",
                0.7,
                name,
                "derived_text",
            )

        if rec:
            out.append(rec)

    return out


def validate_catalog_payload(payload: Dict[str, Any], cat: CatalogIndex) -> Dict[str, Any]:
    """
    Ensure only known keys exist + types are coerced (already mostly done).
    Here we do light structural checks.
    """
    warnings: Dict[str, Any] = payload.setdefault("_meta", {}).setdefault("warnings", {})

    # site_fields allowed keys
    site = payload.get("site_fields") or {}
    for k in list(site.keys()):
        if k not in cat.site_fields:
            warnings.setdefault("unknown_output_keys", []).append({"key": k, "where": "site_fields"})
            site.pop(k, None)

    # groups allowed keys
    groups = payload.get("groups") or {}
    for gname, arr in list(groups.items()):
        if gname not in cat.groups:
            warnings.setdefault("unknown_output_keys", []).append({"key": gname, "where": "groups"})
            groups.pop(gname, None)
            continue
        fields_by_key = cat.groups[gname]["fields_by_key"]
        if not isinstance(arr, list):
            groups[gname] = []
            continue
        for i, rec in enumerate(arr):
            if not isinstance(rec, dict):
                continue
            for fk in list(rec.keys()):
                if fk not in fields_by_key:
                    warnings.setdefault("unknown_output_keys", []).append({"key": f"{gname}[{i}].{fk}", "where": "groups"})
                    rec.pop(fk, None)

    return payload


# ----------------------------
# Main entry point
# ----------------------------

def map_to_catalog(item: Dict[str, Any], catalog: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert one extraction result item into a field_catalog.json-shaped payload.
    """
    cat = index_catalog(catalog)

    out_meta: Dict[str, Any] = {"fields": {}, "warnings": {}}
    warnings: Dict[str, Any] = out_meta["warnings"]

    # Base contract
    payload: Dict[str, Any] = {
        "version": cat.version,
        "site_fields": {},
        "groups": {},
        "_meta": out_meta,
    }

    # Keep filename (helpful)
    if "filename" in item:
        out_meta["filename"] = item["filename"]

    # Bring forward your low-confidence list (if present)
    if isinstance(item.get("warnings"), dict):
        lc = item["warnings"].get("low_confidence_fields")
        if lc:
            warnings["low_confidence_fields"] = lc

    # Build site fields
    payload["site_fields"] = build_site_fields(item, cat, out_meta, warnings)

    # Build groups
    inv = build_inverters_group(item, cat, out_meta, warnings)
    if inv:
        payload["groups"]["Inverters"] = inv

    meters = _build_name_only_group(
        item=item,
        cat=cat,
        group_name="Meters",
        field_key="Name" if "Name" in (cat.groups.get("Meters", {}).get("fields_by_key", {})) else "PlatformName",
        detector=_extract_meter_names_from_text,
        out_meta=out_meta,
    )
    if meters:
        payload["groups"]["Meters"] = meters

    primary_meters = _build_name_only_group(
        item=item,
        cat=cat,
        group_name="PrimaryMeters",
        field_key="Name" if "Name" in (cat.groups.get("PrimaryMeters", {}).get("fields_by_key", {})) else "PlatformName",
        detector=_extract_meter_names_from_text,
        out_meta=out_meta,
    )
    if primary_meters:
        payload["groups"]["PrimaryMeters"] = primary_meters

    other_meters = _build_name_only_group(
        item=item,
        cat=cat,
        group_name="OtherMeters",
        field_key="Name" if "Name" in (cat.groups.get("OtherMeters", {}).get("fields_by_key", {})) else "PlatformName",
        detector=_extract_meter_names_from_text,
        out_meta=out_meta,
    )
    if other_meters:
        payload["groups"]["OtherMeters"] = other_meters

    weather = _build_name_only_group(
        item=item,
        cat=cat,
        group_name="WeatherStations",
        field_key="Name" if "Name" in (cat.groups.get("WeatherStations", {}).get("fields_by_key", {})) else "PlatformName",
        detector=_extract_weather_station_names_from_text,
        out_meta=out_meta,
    )
    if weather:
        payload["groups"]["WeatherStations"] = weather

    transformers = _build_name_only_group(
        item=item,
        cat=cat,
        group_name="Transformers",
        field_key="Name" if "Name" in (cat.groups.get("Transformers", {}).get("fields_by_key", {})) else "PlatformName",
        detector=_extract_transformer_names_from_text,
        out_meta=out_meta,
    )
    if transformers:
        payload["groups"]["Transformers"] = transformers

    combiners = _build_name_only_group(
        item=item,
        cat=cat,
        group_name="Combiners",
        field_key="Name" if "Name" in (cat.groups.get("Combiners", {}).get("fields_by_key", {})) else "PlatformName",
        detector=_extract_combiner_names_from_text,
        out_meta=out_meta,
    )
    if combiners:
        payload["groups"]["Combiners"] = combiners

    trackers = _build_name_only_group(
        item=item,
        cat=cat,
        group_name="Trackers",
        field_key="Name" if "Name" in (cat.groups.get("Trackers", {}).get("fields_by_key", {})) else "PlatformName",
        detector=_extract_tracker_names_from_text,
        out_meta=out_meta,
    )
    if trackers:
        payload["groups"]["Trackers"] = trackers

    poa = _build_name_only_group(
        item=item,
        cat=cat,
        group_name="PlaneOfArray",
        field_key="Name" if "Name" in (cat.groups.get("PlaneOfArray", {}).get("fields_by_key", {})) else "PlatformName",
        detector=_extract_poa_names_from_text,
        out_meta=out_meta,
    )
    if poa:
        payload["groups"]["PlaneOfArray"] = poa

    # Ensure all groups exist
    for gname in cat.groups.keys():
        payload["groups"].setdefault(gname, [])

    # Validate output keys
    payload = validate_catalog_payload(payload, cat)

    return payload
