# backend/services/apply_library.py
from __future__ import annotations
import re
from typing import Any, Dict, List, Tuple

from backend.services import learning
from backend.services.normalize import normalize_inverter_model, normalize_module_model

def _set_target(payload: dict, target: str, value):
    if "[" not in target:
        payload[target] = value
        return

    m = re.match(r"^([A-Za-z0-9_]+)\[(\d+)\]\.([A-Za-z0-9_]+)$", target)
    if not m:
        return
    group, idx, field = m.group(1), int(m.group(2)), m.group(3)
    payload.setdefault(group, [])
    while len(payload[group]) <= idx:
        payload[group].append({})
    payload[group][idx][field] = value

def _normalize_value(target: str, val: str) -> Any:
    """
    Normalize values based on target field.
    """
    if target in {"inverter_models", "Inverters[0].Model"}:
        norm, _vendor = normalize_inverter_model(val)
        return norm

    if target in {"module_models"}:
        norm, _vendor = normalize_module_model(val)
        return norm

    # numeric fields: pull first number, keep float
    if target in {"AC_Capacity_kW", "DC_Capacity_kW", "ExportLimit_kW"}:
        nums = re.findall(r"[\d,]+(?:\.\d+)?", val or "")
        if nums:
            return float(nums[0].replace(",", ""))
    return val.strip()

def _confidence_from_match(text: str, m: re.Match, rule: dict) -> float:
    """
    Heuristic confidence:
    - base from rule (if provided) else 0.70
    - + if label appears verbatim
    - + if capture is "clean" (not huge / not random)
    """
    base = float(rule.get("confidence") or 0.70)

    # If pattern has a strong anchor word (e.g., PROJECT NAME), reward it.
    pat = rule.get("pattern", "")
    if re.search(r"PROJECT\s+NAME|TOTAL\s+DC|INVERTER|MODULE", pat, flags=re.I):
        base += 0.10

    captured = (m.group(1) if m.groups() else m.group(0)) or ""
    captured = captured.strip()

    # penalize garbage captures
    if len(captured) > 120:
        base -= 0.15
    if re.search(r"(?i)\b(lorem|ipsum)\b", captured):
        base -= 0.20

    # reward structured model-like tokens
    if re.search(r"(?i)\b(AE\s+3TL|SOLARON|CS\d|TSM-|STP\d|SMA)\b", captured):
        base += 0.10

    # clamp
    if base < 0.05:
        base = 0.05
    if base > 0.99:
        base = 0.99
    return round(base, 3)

def flag_low_confidence(extracted: dict, threshold: float = 0.75) -> List[str]:
    meta = extracted.get("_extraction_meta", {})
    low = []
    for k, v in meta.items():
        if isinstance(v, dict) and float(v.get("confidence", 1.0)) < threshold:
            low.append(k)
    return low

def apply_library(text: str, extracted: dict) -> dict:
    """
    Apply all learned regex rules to OCR text, fill extracted fields.
    Also attach _extraction_meta with evidence + confidence per field.
    """
    rules = learning.list_fields()  # your /metadata/library shows {"fields":[...]} but list_fields returns list in your code
    meta: Dict[str, Dict[str, Any]] = extracted.get("_extraction_meta", {})

    for r in (rules or []):
        pat = r.get("pattern")
        tgt = r.get("target_column")
        name = r.get("name") or tgt
        if not pat or not tgt:
            continue

        m = re.search(pat, text or "", flags=re.I | re.S | re.M)
        if not m:
            continue

        raw_val = (m.group(1) if m.groups() else m.group(0)) or ""
        norm_val = _normalize_value(tgt, raw_val)

        # If target is list-like field (module_models/inverter_models), append unique
        if tgt in {"module_models", "inverter_models"}:
            extracted.setdefault(tgt, [])
            if isinstance(norm_val, str) and norm_val and norm_val not in extracted[tgt]:
                extracted[tgt].append(norm_val)
        else:
            _set_target(extracted, tgt, norm_val)

        conf = _confidence_from_match(text, m, r)

        meta_key = tgt
        meta[meta_key] = {
            "rule": name,
            "pattern": pat,
            "confidence": conf,
            "raw": raw_val.strip(),
            "normalized": norm_val,
            "evidence": (m.group(0) or "").strip()[:400],  # keep short
        }

    extracted["_extraction_meta"] = meta
    return extracted
