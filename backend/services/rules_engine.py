# backend/services/rules_engine.py
import os
import re
import yaml
from pathlib import Path
from typing import Dict, Any, List


def _to_float(x):
    """
    Parse a float from a messy string:
    - Handles "12,345.67" (commas as thousands) -> 12345.67
    - Handles "49,56" (comma decimal) -> 49.56
    - Handles "+12.5", "-3", etc.
    Returns float or None.
    """
    s = str(x)
    if "," in s and "." in s:
        # assume commas are thousands separators; drop them
        s = s.replace(",", "")
    elif "," in s and "." not in s:
        # assume comma is the decimal mark
        s = s.replace(",", ".")
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def _to_int(x):
    """
    Parse an int from a messy string:
    - Handles "12,345" -> 12345
    - Handles "+168x" -> 168
    Returns int or None.
    """
    s = str(x)
    if "," in s and "." in s:
        s = s.replace(",", "")
    elif "," in s and "." not in s:
        s = s.replace(",", "")
    m = re.search(r"[-+]?\d+", s)
    return int(m.group(0)) if m else None


def _num(x):
    v = _to_float(x)
    if v is None:
        raise ValueError(f"no numeric token in: {x!r}")
    return v


def _normalize(val: str | float | None, unit: str | None, to: str) -> float | None:
    if val is None:
        return None
    v = _num(val) if isinstance(val, str) else float(val)
    u = (unit or "").lower()
    if to == "mw":
        if u in ("mw", ""):
            return v
        if u == "kw":
            return v / 1000.0
        if u == "mva":
            return v  # assume pf≈1
        if u == "kva":
            return v / 1000.0
    if to == "kw":
        if u in ("kw", ""):
            return v
        if u == "mw":
            return v * 1000.0
    return v


def _apply_one(text: str, patterns: List[str]):
    for pat in patterns or []:
        try:
            m = re.search(pat, text, flags=re.I | re.S | re.M)
        except re.error:
            m = None
        if m:
            return m
    return None


def _safe_groups(m, idx: int, default=None):
    try:
        return m.group(idx)
    except Exception:
        return default


def _pick_group(m, spec: str):
    """
    Flexible group selector:
    - "2" => group 2
    - "2?|1" or "2|1" => try 2 then 1
    - "last" => last capturing group (fallback to 0 if none)
    - "0" => whole match
    Returns the first non-empty group value or None.
    """
    if not spec:
        return None
    parts = [p.strip() for p in spec.split("|") if p.strip()]
    for p in parts:
        if p.lower() == "last":
            idx = m.lastindex or 0
        else:
            p = p.rstrip("?")
            if p.isdigit():
                idx = int(p)
            else:
                # unknown token -> skip
                continue
        val = _safe_groups(m, idx)
        if val not in (None, ""):
            return val
    return None


def _extract_take(m, take: str):
    """
    Parse 'take' expressions and return (val, unit).
    Supports:
      - "group:1"
      - "group:2?|1" (fallbacks)
      - "group:last"
      - "group:2,3"   (value group, unit group)
      - any other string => whole match
    """
    if not take:
        return (m.group(0), None)

    if "," in take:
        first, second = [t.strip() for t in take.split(",", 1)]
        if first.lower().startswith("group:"):
            spec1 = first.split(":", 1)[1].strip()
            val = _pick_group(m, spec1)
        else:
            val = m.group(0)

        unit = None
        if second.lower().startswith("group:"):
            spec2 = second.split(":", 1)[1].strip()
            unit = _pick_group(m, spec2)
        return (val, unit)

    if take.lower().startswith("group:"):
        spec = take.split(":", 1)[1].strip()
        return (_pick_group(m, spec), None)

    return (m.group(0), None)


def load_rules_file(rules_path: str | Path) -> Dict[str, Any]:
    with open(rules_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_rules_file() -> Path:
    # 1) env var override
    rp = os.environ.get("RULES_PATH")
    if rp and Path(rp).exists():
        return Path(rp)

    # 2) common locations
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "rules" / "pv_extractor.rules.yaml",
        here.parents[3] / "ai-onboarding" / "rules" / "pv_extractor.rules.yaml",
        here.parents[3] / "rules" / "pv_extractor.rules.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        "pv_extractor.rules.yaml not found. Set RULES_PATH or place it under ai-onboarding/rules/..."
    )


def extract_from_yaml(flat_text: str, rules: Dict[str, Any]) -> Dict[str, Any]:
    """
    Works on the flattened OCR content (Azure DI 'content').
    For MVP we scan the whole text (no per-page logic).
    """
    text = flat_text or ""
    result: Dict[str, Any] = {
        "plant": {},
        "inverters": [],
        "modules": [],
        "metstation": {"sensors": []},
        "substation": {"transformers": []},
        "counts": {},
        "evidence": [],
        "missing": [],
    }

    # --- plant level
    for fld in (rules.get("plant_level", {}) or {}).get("fields", []) or []:
        m = _apply_one(text, fld.get("regex", []))
        if not m:
            continue

        take = fld.get("take", "group:1")
        val, unit = _extract_take(m, take)

        # normalize if requested
        norm = fld.get("normalize") or {}
        to_unit = (norm.get("to") or norm.get("unit") or "").lower()
        if to_unit:
            val = _normalize(val, unit, to_unit)
        else:
            # safe numeric casting (ignore junk chars)
            kind = (fld.get("kind") or "").lower()
            if kind == "int":
                val = _to_int(val)
            elif kind in ("number", "float", "double"):
                val = _to_float(val)
            # else keep as string

        # store result + evidence
        result["plant"][fld["name"]] = val
        result["evidence"].append(
            {
                "field": fld["name"],
                "page": None,
                "text": (m.group(0) or "").strip(),
            }
        )

    # --- equipment buckets (simple whole-text scan)
    for bname, cfg in (rules.get("equipment_buckets") or {}).items():
        fields: Dict[str, Any] = {}

        for fld in cfg.get("fields", []) or []:
            # handle repeating line-based schema
            if (fld.get("kind") or "").lower() == "repeat":
                items: List[Dict[str, Any]] = []
                for line in (text.splitlines() if text else []):
                    item: Dict[str, Any] = {}
                    hit = False

                    for idx, s in enumerate(fld.get("schema", []) or []):
                        sm = _apply_one(line, s.get("regex", []))
                        if not sm:
                            continue
                        hit = True

                        stake = s.get("take", "group:1")
                        sval, sunit = _extract_take(sm, stake)

                        # normalization/casting per schema field
                        snorm = s.get("normalize") or {}
                        sto = (snorm.get("to") or snorm.get("unit") or "").lower()
                        if sto:
                            sval = _normalize(sval, sunit, sto)

                        skind = (s.get("kind") or "").lower()
                        if skind == "int":
                            sval = _to_int(sval)
                        elif skind in ("number", "float", "double"):
                            sval = _to_float(sval)
                        elif skind == "enum" and s.get("map"):
                            for k, v in (s.get("map") or {}).items():
                                if re.search(k, sm.group(0) or "", re.I):
                                    sval = v
                                    break

                        sname = s.get("name") or f"value_{idx+1}"
                        item[sname] = sval

                    if hit and item:
                        items.append(item)
                        result["evidence"].append(
                            {"field": fld.get("name", bname), "page": None, "text": line.strip()}
                        )

                if items:
                    key = fld.get("name") or bname
                    # pluralize if needed
                    if not key.endswith("s"):
                        key = key + "s"
                    fields[key] = items

            else:
                # single-field extraction across the whole text
                m = _apply_one(text, fld.get("regex", []))
                if not m:
                    continue

                take = fld.get("take", "group:1")
                val, unit = _extract_take(m, take)

                norm = fld.get("normalize") or {}
                to_unit = (norm.get("to") or norm.get("unit") or "").lower()
                if to_unit:
                    val = _normalize(val, unit, to_unit)

                kind = (fld.get("kind") or "").lower()
                if kind == "int":
                    val = _to_int(val)
                elif kind in ("number", "float", "double"):
                    val = _to_float(val)
                elif kind == "enum" and fld.get("map"):
                    for k, v in (fld.get("map") or {}).items():
                        if re.search(k, m.group(0) or "", re.I):
                            val = v
                            break

                fields[fld["name"]] = val
                result["evidence"].append(
                    {"field": fld["name"], "page": None, "text": (m.group(0) or "").strip()}
                )

        # place fields into result by bucket
        if not fields:
            continue

        if bname == "inverter":
            result["inverters"].append(fields)
        elif bname == "module":
            result["modules"].append(fields)
        elif bname == "met":
            if "sensors" in fields:
                result["metstation"]["sensors"].extend(fields["sensors"])
        elif bname == "substation":
            # normalize transformer singular/plural
            if "transformer" in fields and isinstance(fields["transformer"], list):
                result["substation"]["transformers"].extend(fields["transformer"])
            for k, v in fields.items():
                if k not in ("transformer", "transformers"):
                    result["substation"][k] = v

    # mark high-priority missing
    must = ["plant.plant_name", "substation.poi_ac_mw", "inverters", "modules", "metstation.sensors"]
    found = set()
    if result["plant"].get("plant_name"):
        found.add("plant.plant_name")
    if result["substation"].get("poi_ac_mw") is not None:
        found.add("substation.poi_ac_mw")
    if result["inverters"]:
        found.add("inverters")
    if result["modules"]:
        found.add("modules")
    if result["metstation"]["sensors"]:
        found.add("metstation.sensors")
    result["missing"] = [m for m in must if m not in found]

    return result
