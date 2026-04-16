# backend/services/extractors.py
import re
from . import patterns as P
from .learning import detect_unknown_fields
from .plant_name_resolver import pick_plant_name


def _first(*vals):
    for v in vals:
        if v:
            return v


def _to_float(s: str) -> float:
    return float(s.replace(",", ""))


def _kw_to_mw(x: str | float) -> float:
    v = _to_float(x) if isinstance(x, str) else float(x)
    return round(v / 1000.0, 4)


def _unique_clean(items):
    seen, out = set(), []
    for it in items:
        t = (it or "").strip()
        t = re.sub(r"\s{2,}", " ", t)
        t = re.sub(r"\s*\(\d+v\)\s*", "", t, flags=re.I)
        t = t.strip(" -/")
        if not t or t.upper() in {"TOTAL", "UPDATED"}:
            continue
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _pull_text(analyze_result: dict, pdf_bytes: bytes | None = None) -> str:
    ar = analyze_result or {}

    # BEST CASE: full content already provided
    if isinstance(ar.get("content"), str) and ar["content"].strip():
        return ar["content"]

    pages = ar.get("pages", []) or []
    if not pages:
        return ""

    texts = []

    for page in pages:
        lines = page.get("lines") or []
        for ln in lines:
            txt = ln.get("content")
            if txt:
                texts.append(txt)

        full_text = "\n".join(texts)
        print("DEBUG EXTRACTOR text_len:", len(full_text))
        return full_text
    

def _top_band_lines(ar: dict, band: float = 0.30) -> list[dict]:
    pages = ar.get("pages", []) or []
    if not pages:
        return []

    p1 = pages[0]
    height = float(p1.get("height") or 1.0)

    out = []

    for ln in (p1.get("lines") or []):
        text = ln.get("content") or ""
        if not text.strip():
            continue

        poly = ln.get("polygon") or ln.get("boundingPolygon") or []
        ys = []

        if isinstance(poly, list) and poly and isinstance(poly[0], (int, float)):
            ys = [float(poly[i]) for i in range(1, len(poly), 2)]
        else:
            for p in poly:
                if isinstance(p, dict) and "y" in p:
                    ys.append(float(p["y"]))

        top_y = min(ys) if ys else 1e9

        if top_y <= height * band:
            out.append(
                {
                    "text": text,
                    "evidence": {
                        "page": 1,
                        "source_type": "document_intelligence",
                        "snippet": text[:200],
                    },
                }
            )

    return out


def parse_asbuilt(result: dict) -> dict:
    ar = result.get("analyzeResult", {}) or {}
    text = _pull_text(
        ar,
        pdf_bytes=result.get("file_bytes")
    )

    # -----------------------
    # Plant name detection
    # -----------------------

    lines_top = _top_band_lines(ar, band=0.30)
    name_result = pick_plant_name(lines_top)

    plant_name = name_result.get("plant_name")
    plant_name_confidence = name_result.get("confidence")
    plant_name_candidates = name_result.get("candidates", [])

    # fallback using regex if low confidence
    if not plant_name or (plant_name_confidence or 0) < 0.6:
        candidates = []
        for m in P.PLANT_LINE.finditer(text):
            cand = m.group(1).strip()
            if cand.upper() not in P.PLANT_SKIP and 2 <= len(cand.split()) <= 5:
                candidates.append(cand.title())
        if candidates:
            plant_name = candidates[0]
    # fallback using regex if low confidence
    if not plant_name or (plant_name_confidence or 0) < 0.6:
        candidates = []
        for m in P.PLANT_LINE.finditer(text):
            cand = m.group(1).strip()
            if cand.upper() not in P.PLANT_SKIP and 2 <= len(cand.split()) <= 5:
                candidates.append(cand.title())
        if candidates:
            plant_name = candidates[0]
    # -----------------------
    # Derive plant type
    # -----------------------

    text_lower = text.lower()
    plant_type = "unknown"

    if (
        "photovoltaic" in text_lower
        or "solar" in text_lower
        or "pv system" in text_lower
    ):
        plant_type = "solar"

    # -----------------------
    # Build output dict
    # -----------------------

    out = {
        "plant_name": plant_name,
        "plant_name_confidence": plant_name_confidence,
        "plant_name_candidates": plant_name_candidates,
        "title_block": "\n".join(
            [c.get("text", "") for c in plant_name_candidates if c.get("text")]
        ),
        "plant_type": plant_type,
        "ac_capacity_mw": None,
        "dc_capacity_mw": None,
        "ac_kw": None,
        "dc_kw": None,
        "inverter_count": None,
        "inverter_models": [],
        "module_count": None,
        "module_models": [],
    }

    # -----------------------
    # Capacities
    # -----------------------

    m = P.KWDC.search(text)
    if m:
        num = _first(m.group(1), m.group(2))
        out["dc_capacity_mw"] = _kw_to_mw(num)
        out["dc_kw"] = round(out["dc_capacity_mw"] * 1000.0, 3)

    m = P.KWAC.search(text)
    if m:
        num = _first(m.group(1), m.group(2))
        out["ac_capacity_mw"] = _kw_to_mw(num)
        out["ac_kw"] = round(out["ac_capacity_mw"] * 1000.0, 3)

    # -----------------------
    # Counts
    # -----------------------

    m = P.MOD_COUNT.search(text)
    if m:
        out["module_count"] = int(_to_float(m.group(1)))

    m = P.INV_COUNT.search(text)
    if m:
        out["inverter_count"] = int(_to_float(m.group(1)))

    # -----------------------
    # Models
    # -----------------------

    out["module_models"] = _unique_clean(
        [m.group("model") for m in P.MOD_MODEL.finditer(text)]
    )

    out["inverter_models"] = _unique_clean(
        [m.group("model") for m in P.INV_MODEL.finditer(text)]
    )

    # -----------------------
    # Missing + debug
    # -----------------------

    missing = [k for k in ("plant_name", "ac_kw", "dc_kw") if not out.get(k)]
    preview = text[:1200]
    unknown = detect_unknown_fields(text, out)

    return {
        "extracted": out,
        "missing_fields": missing,
        "unknown_metadata": unknown,
        "evidence_preview": preview,
        "text": text,
        "combined_text": text,
    }
