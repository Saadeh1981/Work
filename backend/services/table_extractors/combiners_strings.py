# backend/services/table_extractors/combiners_strings.py
#
# Robust combiner strings extraction.
# Adds pixel OCR fallback using free Tesseract when Azure DI table content is wrong or blank.
#
# Dependencies:
#   pip install pymupdf pillow pytesseract
#
# System:
#   Install Tesseract OCR and set PATH, or set env var TESSERACT_CMD to tesseract.exe
#
import csv
import os
import re
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from difflib import SequenceMatcher

try:
    from PIL import Image as PILImage
    from PIL import ImageOps, ImageFilter
except Exception:
    PILImage = None
    ImageOps = None
    ImageFilter = None

if TYPE_CHECKING:
    from PIL.Image import Image as PILImageType
else:
    PILImageType = Any

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    import pytesseract
except Exception:
    pytesseract = None


# ----------------------------
# Patterns
# ----------------------------

_COMB_FULL = re.compile(r"^\d+\.\d+\.\d+\.[cC]\d+$")

_ROW_COMB_RE_1 = re.compile(r"(\d+\.\d+\.\d+)\s*[\.\s]*([cC])\s*[\.\s]*([0-9Il|Oo]{1,2})")
_ROW_COMB_RE_2 = re.compile(r"(\d+\.\d+\.\d+)[^\d]{0,3}([cC])[^\d]{0,3}([0-9Il|Oo]{1,2})")

_STR_MIN = 1
_STR_MAX = 200
_STR_PREFERRED_MIN = 30
_STR_PREFERRED_MAX = 200


# ----------------------------
# Text helpers
# ----------------------------

def _clean_cell_text(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _sim(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _extract_suffix(comb: str) -> Optional[int]:
    m = re.search(r"\.C(\d+)$", (comb or "").upper())
    return int(m.group(1)) if m else None


def _comb_key(comb: str) -> Tuple[Optional[str], Optional[int]]:
    if not comb:
        return None, None
    comb_u = (comb or "").strip().upper()
    m = re.match(r"^(\d+\.\d+\.\d+)\.C(\d+)$", comb_u)
    if not m:
        return None, None
    return m.group(1), int(m.group(2))


def _normalize_combiner(text: str) -> Optional[str]:
    t = _clean_cell_text(text)
    if not t:
        return None

    t = t.upper().replace("O", "0")
    t = re.sub(r"\s+", "", t)
    t = t.rstrip(".")

    m = re.match(r"^(\d+\.\d+\.\d+)\.?C\.?([0-9IL|O]{1,2})$", t)
    if not m:
        return None

    base = m.group(1)
    suf_raw = m.group(2)
    suf_norm = (
        suf_raw.replace("|", "1")
        .replace("I", "1")
        .replace("L", "1")
        .replace("O", "0")
    )

    if not re.fullmatch(r"\d{1,2}", suf_norm):
        return None

    return f"{base}.C{int(suf_norm)}"

    return None


def _find_combiner_in_row_text(row_text: str) -> Optional[str]:
    s = _clean_cell_text(row_text)
    if not s:
        return None

    s = s.upper()

    m = re.search(
        r"(\d+\.\d+\.\d+)\s*\.?\s*C\s*\.?\s*([0-9IL|O]{1,2})(?!\d)",
        s
    )
    if not m:
        return None

    base = m.group(1)
    suf_raw = m.group(2)
    suf_norm = (
        suf_raw.replace("|", "1")
        .replace("I", "1")
        .replace("L", "1")
        .replace("O", "0")
    )

    if not re.fullmatch(r"\d{1,2}", suf_norm):
        return None

    return f"{base}.C{int(suf_norm)}"

    return None


# ----------------------------
# Azure DI table geometry helpers
# ----------------------------

def _cell_poly(cell: dict) -> Optional[List[float]]:
    br = (cell.get("boundingRegions") or [])
    if not br:
        return None
    poly = br[0].get("polygon")
    return poly if poly and len(poly) >= 8 else None


def _cell_page_number(cell: dict) -> Optional[int]:
    br = (cell.get("boundingRegions") or [])
    if not br:
        return None
    pn = br[0].get("pageNumber")
    return int(pn) if pn is not None else None


def _poly_bounds(poly: List[float]) -> Tuple[float, float, float, float]:
    xs = poly[0::2]
    ys = poly[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def _cell_x_center(cell: dict) -> Optional[float]:
    poly = _cell_poly(cell)
    if not poly:
        return None
    x0, _, x1, _ = _poly_bounds(poly)
    return (x0 + x1) / 2.0


def _cell_x_window(cell: dict, pad: float = 0.01) -> Optional[Tuple[float, float]]:
    poly = _cell_poly(cell)
    if not poly:
        return None
    x0, _, x1, _ = _poly_bounds(poly)
    w = max(0.0, x1 - x0)
    return (x0 - w * pad, x1 + w * pad)


def _find_header_cell(cells: List[dict], max_header_row: int, needles: List[str], thr: float = 0.78) -> Optional[dict]:
    needles_n = [_norm(x) for x in needles]
    best = (0.0, None)
    for c in cells:
        r = c.get("rowIndex")
        if r is None or r > max_header_row:
            continue
        txt = _norm(c.get("content") or "")
        if not txt:
            continue
        for n in needles_n:
            sc = _sim(txt, n)
            if n and n in txt:
                sc = max(sc, 0.95)
            if sc > best[0]:
                best = (sc, c)
    return best[1] if best[0] >= thr else None


def _pick_cell_in_row_by_xwin(cells: List[dict], row_index: int, xwin: Tuple[float, float]) -> Optional[dict]:
    x0, x1 = xwin
    best = None
    best_dist = 1e9
    for c in cells:
        if c.get("rowIndex") != row_index:
            continue
        xc = _cell_x_center(c)
        if xc is None:
            continue
        if x0 <= xc <= x1:
            dist = abs((x0 + x1) / 2.0 - xc)
            if dist < best_dist:
                best = c
                best_dist = dist
    return best


# ----------------------------
# Strings parsing
# ----------------------------

def _strings_fix_common_80(t2: str) -> str:
    if len(t2) <= 6:
        t2 = (
            t2.replace("BO", "80")
              .replace("B0", "80")
              .replace("8O", "80")
              .replace("SO", "80")
        )
    return t2


def _parse_strings_cell(text: str) -> Optional[int]:
    t = _clean_cell_text(text)
    if not t:
        return None

    if "'" in t or "FT" in t.upper():
        return None

    t2 = t.upper().replace(" ", "")
    t2 = _strings_fix_common_80(t2)

    if t2 and t2[0] in ("|", "I", "L"):
        t2 = t2[1:]

    t2 = t2.replace("O", "0")
    m = re.search(r"\b(\d{2,3})\b", re.sub(r"[^0-9]", " ", t2))
    if not m:
        return None

    v = int(m.group(1))
    if not (_STR_MIN <= v <= _STR_MAX):
        return None
    return v


def _parse_float_amp(text: str) -> Optional[float]:
    t = _clean_cell_text(text)
    if not t:
        return None
    t2 = t.upper().replace("O", "0").replace(",", "")
    m = re.search(r"\d+(?:\.\d+)?", t2)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def _parse_totals_int(text: str) -> Optional[int]:
    t = _clean_cell_text(text)
    if not t:
        return None
    t2 = t.upper().replace(" ", "").replace("O", "0")
    m = re.search(r"\d{1,6}", t2)
    if not m:
        return None
    v = int(m.group(0))
    return v if 1 <= v <= 20000 else None


def _find_strings_before_module(row_all: str) -> Optional[int]:
    """
    Extract strings from row text:
      ... <distance> <strings> <module_type>
    Remove inverter/combiner ids first so we do not pick a suffix from equipment ids.
    """
    s = _clean_cell_text(row_all)

    m = re.search(r"\bFS[-–]\d+", s, flags=re.IGNORECASE)
    if not m:
        return None

    left = s[:m.start()]
    left = re.sub(r"\b\d+\.\d+\.\d+\.[cC]\.\d+\b", " ", left)
    left = re.sub(r"\b\d+\.\d+\.\d+\b", " ", left)

    ints = [int(x) for x in re.findall(r"\b\d+\b", left)]
    cands = [v for v in ints if 30 <= v <= 200]
    if not cands:
        return None

    return cands[-1]


# ----------------------------
# Header fallback
# ----------------------------

def _find_header_col_fuzzy(cells: List[dict], max_header_row: int, needles: List[str], thr: float = 0.78) -> Optional[int]:
    needles_n = [_norm(x) for x in needles]
    best = (0.0, None)

    for c in cells:
        r = c.get("rowIndex")
        k = c.get("columnIndex")
        if r is None or k is None or r > max_header_row:
            continue

        txt = _norm(c.get("content") or "")
        if not txt:
            continue

        for n in needles_n:
            sc = _sim(txt, n)
            if n and n in txt:
                sc = max(sc, 0.95)
            if sc > best[0]:
                best = (sc, k)

    return best[1] if best[0] >= thr else None


def _is_totals_row(row_all: str, first_cell: str) -> bool:
    s1 = _norm(row_all)
    s0 = _norm(first_cell)
    return ("total" in s1) or (s0 == "totals") or ("totals" in s0)


# ----------------------------
# Pixel OCR fallback
# ----------------------------

class _PixelOcr:
    """
    Renders PDF pages at high DPI and OCRs cropped regions.
    Uses multiple passes and majority vote.
    """
    def __init__(self, pdf_path: str, dpi: int = 350):
        self.pdf_path = pdf_path
        self.dpi = int(dpi)
        self._doc = None
        self._page_img_cache: Dict[int, PILImageType] = {}
        self._unit_by_page: Dict[int, str] = {}
        self._page_wh_by_page: Dict[int, Tuple[float, float]] = {}

        cmd = os.getenv("TESSERACT_CMD")
        if cmd and pytesseract is not None:
            pytesseract.pytesseract.tesseract_cmd = cmd

    def set_page_meta(self, page_number: int, unit: str, width: float, height: float) -> None:
        self._unit_by_page[page_number] = (unit or "").lower()
        self._page_wh_by_page[page_number] = (float(width), float(height))

    def _ensure_doc(self) -> bool:
        if fitz is None or PILImage is None or ImageOps is None or pytesseract is None:
            return False
        if self._doc is None:
            self._doc = fitz.open(self.pdf_path)
        return True

    def _render_page(self, page_number: int) -> Optional[PILImageType]:
        if not self._ensure_doc():
            return None
        if page_number in self._page_img_cache:
            return self._page_img_cache[page_number]

        idx = page_number - 1
        if idx < 0 or idx >= len(self._doc):
            return None

        page = self._doc[idx]
        mat = fitz.Matrix(self.dpi / 72.0, self.dpi / 72.0)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self._page_img_cache[page_number] = img
        return img

    def _units_to_pixels(self, page_number: int, x: float, y: float) -> Tuple[int, int]:
        unit = self._unit_by_page.get(page_number, "inch")
        if unit == "inch":
            return int(round(x * self.dpi)), int(round(y * self.dpi))
        if unit == "pixel":
            return int(round(x)), int(round(y))
        return int(round(x * self.dpi)), int(round(y * self.dpi))

    def ocr_int_from_poly(self, page_number: int, poly: List[float]) -> Optional[int]:
        img = self._render_page(page_number)
        if img is None:
            return None

        x0u, y0u, x1u, y1u = _poly_bounds(poly)

        pad_x_u = max(0.01, (x1u - x0u) * 0.10)
        pad_y_u = max(0.01, (y1u - y0u) * 0.20)

        x0u -= pad_x_u
        x1u += pad_x_u
        y0u -= pad_y_u
        y1u += pad_y_u

        x0p, y0p = self._units_to_pixels(page_number, x0u, y0u)
        x1p, y1p = self._units_to_pixels(page_number, x1u, y1u)

        x0p = max(0, min(img.width - 1, x0p))
        x1p = max(1, min(img.width, x1p))
        y0p = max(0, min(img.height - 1, y0p))
        y1p = max(1, min(img.height, y1p))
        if x1p <= x0p or y1p <= y0p:
            return None

        crop = img.crop((x0p, y0p, x1p, y1p))

        candidates: List[int] = []
        for cand in self._ocr_digits_multi(crop):
            if _STR_MIN <= cand <= _STR_MAX:
                candidates.append(cand)

        if not candidates:
            return None

        freq: Dict[int, int] = {}
        for v in candidates:
            freq[v] = freq.get(v, 0) + 1
        best = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        return best

    def _ocr_digits_multi(self, crop: PILImageType) -> List[int]:
        if pytesseract is None or PILImage is None or ImageOps is None or ImageFilter is None:
            return []

        out: List[int] = []
        variants: List[PILImageType] = []

        g = crop.convert("L")
        g = ImageOps.autocontrast(g)
        variants.append(g)

        up = g.resize((g.width * 2, g.height * 2))
        variants.append(up)

        variants.append(up.point(lambda p: 255 if p > 160 else 0, mode="1").convert("L"))
        variants.append(up.point(lambda p: 255 if p > 190 else 0, mode="1").convert("L"))
        variants.append(up.filter(ImageFilter.SHARPEN))

        cfgs = [
            "--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789",
            "--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789",
        ]

        for im in variants:
            for cfg in cfgs:
                try:
                    txt = pytesseract.image_to_string(im, config=cfg) or ""
                except Exception:
                    continue
                v = _parse_strings_cell(txt)
                if v is not None:
                    out.append(v)

                dd = re.sub(r"[^0-9]", "", txt.strip())
                if dd:
                    try:
                        vv = int(dd[:3])
                        if _STR_MIN <= vv <= _STR_MAX:
                            out.append(vv)
                    except Exception:
                        pass

        return out


# ----------------------------
# Word-scan fallback
# ----------------------------

def _extract_from_word_scan(ar: dict, target_pages: Optional[set[int]] = None) -> List[Dict[str, Any]]:
    out2: List[Dict[str, Any]] = []
    for page in (ar.get("pages") or []):
        page_num = page.get("pageNumber")

        if target_pages and page_num not in target_pages:
            continue

        words = page.get("words") or []
        if not words:
            continue

        items = []
        for w in words:
            t = (w.get("content") or "").strip()
            if not t:
                continue
            poly = w.get("polygon") or []
            xs = poly[0::2]
            ys = poly[1::2]
            if not xs or not ys:
                continue
            cy = (min(ys) + max(ys)) / 2.0
            cx = (min(xs) + max(xs)) / 2.0
            items.append((cy, cx, t))
        items.sort()

        lines: List[List[Tuple[float, float, str]]] = []
        y_tol = 0.12
        for cy, cx, t in items:
            if not lines:
                lines.append([(cy, cx, t)])
                continue
            if abs(cy - lines[-1][0][0]) <= y_tol:
                lines[-1].append((cy, cx, t))
            else:
                lines.append([(cy, cx, t)])

        header_idx = None
        for i, ln in enumerate(lines[:40]):
            s = " ".join(_norm(x[2]) for x in ln)
            if "from" in s and "combiner" in s and "strings" in s:
                header_idx = i
                break
        if header_idx is None:
            continue

        header_ln = sorted(lines[header_idx], key=lambda z: z[1])
        x_strings = None
        for _, cx, t in header_ln:
            if _norm(t) == "strings":
                x_strings = cx
                break

        if x_strings is None:
            continue

        for ln in lines[header_idx + 1:]:
            ln2 = sorted(ln, key=lambda z: z[1])
            joined = " ".join(x[2] for x in ln2)
            if "totals" in _norm(joined):
                break

            comb = _normalize_combiner(joined) or _find_combiner_in_row_text(joined)
            if not comb or not _COMB_FULL.match(comb):
                continue

            near = [t for _, cx, t in ln2 if abs(cx - x_strings) <= 0.35]
            strings_val = _parse_strings_cell(" ".join(near))
            if strings_val is None:
                continue

            out2.append({
                "from_combiner_box": comb,
                "strings": strings_val,
                "page": page_num,
                "evidence": {"method": "word_scan"},
            })

    return out2


# ----------------------------
# Derivation helpers
# ----------------------------

def _flag(it: Dict[str, Any], reason: Dict[str, Any]) -> None:
    ev = it.get("evidence") or {}
    ev["needs_review"] = True
    ev.setdefault("review_reasons", [])
    ev["review_reasons"].append(reason)
    it["evidence"] = ev


def _safe_round_candidate(x: float) -> Optional[int]:
    if x <= 0:
        return None
    r = int(round(x))
    if r < _STR_MIN or r > _STR_MAX:
        return None
    if abs(x - r) > 0.35:
        return None
    return r


def _compute_ratio_from_totals(total_val: Optional[float], total_strings: Optional[int]) -> Optional[float]:
    if total_val is None or total_strings is None or total_strings <= 0:
        return None
    v = float(total_val) / float(total_strings)
    return v if 0.1 <= v <= 50.0 else None


def _majority_int(vals: List[int]) -> Optional[int]:
    if not vals:
        return None
    freq: Dict[int, int] = {}
    for v in vals:
        freq[v] = freq.get(v, 0) + 1
    return max(freq.items(), key=lambda kv: kv[1])[0]


def _compute_ratio_from_rows(items: List[Dict[str, Any]], key: str) -> Optional[float]:
    ratios: List[float] = []
    for it in items:
        s = it.get("strings")
        v = it.get(key)
        if s is None or v is None:
            continue
        try:
            s_int = int(s)
            v_f = float(v)
        except Exception:
            continue
        if not (_STR_PREFERRED_MIN <= s_int <= _STR_MAX):
            continue
        if v_f <= 0:
            continue
        r = v_f / float(s_int)
        if 0.1 <= r <= 50.0:
            ratios.append(r)
    if len(ratios) < 2:
        return None
    return float(median(ratios))


def _infer_total_strings_from_majority(items: List[Dict[str, Any]], totals_val: Optional[float], key: str) -> Optional[int]:
    if totals_val is None or totals_val <= 0:
        return None

    strings_vals: List[int] = []
    for it in items:
        try:
            s_int = int(it.get("strings")) if it.get("strings") is not None else None
        except Exception:
            s_int = None
        if s_int is not None and _STR_PREFERRED_MIN <= s_int <= _STR_MAX:
            strings_vals.append(s_int)

    maj = _majority_int(strings_vals)
    if maj is None:
        return None

    ratios: List[float] = []
    for it in items:
        if it.get(key) is None:
            continue
        try:
            s_int = int(it.get("strings"))
            v_f = float(it.get(key))
        except Exception:
            continue
        if s_int != maj or v_f <= 0:
            continue
        ratios.append(v_f / float(s_int))

    if len(ratios) < 2:
        return None

    r = float(median(ratios))
    if not (0.1 <= r <= 50.0):
        return None

    inferred = float(totals_val) / r
    inferred_int = int(round(inferred))
    if inferred_int < 1 or inferred_int > 20000:
        return None
    if abs(inferred - inferred_int) > 0.75:
        return None
    return inferred_int


def _derive_strings_for_group(items: List[Dict[str, Any]], totals: Dict[str, Any]) -> None:
    total_strings = totals.get("strings_total")
    feeder_total = totals.get("feeder_total")
    stub_total = totals.get("stub_total")
    mca_total = totals.get("mca_total")

    inferred = (
        _infer_total_strings_from_majority(items, feeder_total, "feeder_isc")
        or _infer_total_strings_from_majority(items, stub_total, "max_stub")
        or _infer_total_strings_from_majority(items, mca_total, "mca")
    )
    if inferred is not None:
        try:
            ts = int(total_strings) if total_strings is not None else None
        except Exception:
            ts = None
        if ts is None or abs(ts - inferred) >= 3:
            total_strings = inferred
            totals["strings_total"] = inferred

    r_feeder = _compute_ratio_from_totals(feeder_total, total_strings) or _compute_ratio_from_rows(items, "feeder_isc")
    r_stub = _compute_ratio_from_totals(stub_total, total_strings) or _compute_ratio_from_rows(items, "max_stub")
    r_mca = _compute_ratio_from_totals(mca_total, total_strings) or _compute_ratio_from_rows(items, "mca")

    for it in items:
        ev = it.get("evidence") or {}
        ev["ratio_feeder"] = r_feeder
        ev["ratio_stub"] = r_stub
        ev["ratio_mca"] = r_mca
        ev["strings_total_used"] = total_strings
        it["evidence"] = ev

    for it in items:
        cands: Dict[str, int] = {}
        if r_feeder and it.get("feeder_isc") is not None:
            c = _safe_round_candidate(float(it["feeder_isc"]) / float(r_feeder))
            if c is not None:
                cands["from_feeder_isc"] = c
        if r_stub and it.get("max_stub") is not None:
            c = _safe_round_candidate(float(it["max_stub"]) / float(r_stub))
            if c is not None:
                cands["from_max_stub"] = c
        if r_mca and it.get("mca") is not None:
            c = _safe_round_candidate(float(it["mca"]) / float(r_mca))
            if c is not None:
                cands["from_mca"] = c

        ev = it.get("evidence") or {}
        ev["derived_candidates"] = cands
        it["evidence"] = ev

        if not cands:
            continue

        values = list(cands.values())
        rec = values[0]
        it["evidence"]["suggested_strings"] = int(rec)

        if it.get("strings") is None:
            it["strings"] = int(rec)
            _flag(it, {"type": "missing_strings_filled_by_derived", "suggested": int(rec)})
            continue

        try:
            ocr_v = int(it.get("strings"))
        except Exception:
            ocr_v = None

        if ocr_v is None or ocr_v != int(rec):
            _flag(it, {"type": "ocr_vs_derived_mismatch", "ocr": it.get("strings"), "suggested": int(rec)})


# ----------------------------
# Overrides
# ----------------------------

def _load_overrides(path: str) -> Dict[str, int]:
    p = Path(path)
    if not p.exists():
        return {}
    out: Dict[str, int] = {}
    with p.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            comb = (row.get("From Combiner Box") or row.get("from_combiner_box") or "").strip()
            val = (row.get("StringsOverride") or row.get("strings_override") or "").strip()
            if not comb or not val:
                continue
            try:
                out[comb] = int(val)
            except Exception:
                continue
    return out


# ----------------------------
# Table extraction with pixel OCR fallback
# ----------------------------

def _extract_from_tables(
    ar: dict,
    pdf_path: Optional[str],
    pixel_ocr_dpi: int,
    target_pages: Optional[set[int]] = None,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    tables = ar.get("tables") or []
    if not tables:
        return out

    pixel = None
    if pdf_path:
        pixel = _PixelOcr(pdf_path=pdf_path, dpi=pixel_ocr_dpi)

    for p in (ar.get("pages") or []):
        pn = p.get("pageNumber")
        if pn is None:
            continue
        if pixel is not None:
            pixel.set_page_meta(
                page_number=int(pn),
                unit=str(p.get("unit") or "inch"),
                width=float(p.get("width") or 0.0),
                height=float(p.get("height") or 0.0),
            )

    for table_idx, t in enumerate(tables):
        cells = t.get("cells") or []
        if not cells:
            continue

        table_page_numbers = {
            _cell_page_number(c)
            for c in cells
            if _cell_page_number(c) is not None
        }

        if target_pages and table_page_numbers and table_page_numbers.isdisjoint(target_pages):
            continue

        grid: Dict[Tuple[int, int], str] = {}
        max_r = -1
        max_c = -1

        for c in cells:
            r = c.get("rowIndex")
            k = c.get("columnIndex")
            if r is None or k is None:
                continue
            txt = (c.get("content") or "").strip()
            grid[(r, k)] = txt
            max_r = max(max_r, r)
            max_c = max(max_c, k)

        if max_r < 1 or max_c < 1:
            continue

        header_r = None
        for r in range(0, min(max_r, 8) + 1):
            row_txt = " ".join(grid.get((r, c), "") for c in range(0, max_c + 1)).lower()
            if "combiner" in row_txt and "strings" in row_txt:
                header_r = r
                break
        if header_r is None:
            continue

        max_header_row = min(header_r + 3, max_r)

        hdr_strings = _find_header_cell(cells, max_header_row, ["strings", "string5", "string"])
        hdr_from = _find_header_cell(cells, max_header_row, ["from combiner boxes", "from combiner", "combiner boxes", "combiner"])

        strings_xwin = _cell_x_window(hdr_strings) if hdr_strings else None
        from_xwin = _cell_x_window(hdr_from) if hdr_from else None

        col_strings = _find_header_col_fuzzy(cells, max_header_row, ["strings", "string5", "string"])
        col_from = _find_header_col_fuzzy(cells, max_header_row, ["from combiner boxes", "from combiner", "combiner boxes", "combiner"])

        col_feeder = _find_header_col_fuzzy(cells, max_header_row, ["feeder isc at stc", "isc at stc", "feeder isc", "feeder"])
        col_stub = _find_header_col_fuzzy(cells, max_header_row, ["max current per nec 690.8", "max current", "current per stub", "stub"])
        col_mca = _find_header_col_fuzzy(cells, max_header_row, ["mca 690.8", "mca", "690.8(b)"])

        if (from_xwin is None and col_from is None) or (strings_xwin is None and col_strings is None):
            continue

        def _get_cell_text(ridx: int, xwin: Optional[Tuple[float, float]], col: Optional[int]) -> str:
            if xwin is not None:
                cc = _pick_cell_in_row_by_xwin(cells, ridx, xwin)
                return (cc.get("content") or "").strip() if cc else ""
            if col is not None:
                return (grid.get((ridx, col), "") or "").strip()
            return ""

        def _get_cell_obj(ridx: int, xwin: Optional[Tuple[float, float]], col: Optional[int]) -> Optional[dict]:
            if xwin is not None:
                return _pick_cell_in_row_by_xwin(cells, ridx, xwin)
            if col is None:
                return None
            for cc in cells:
                if cc.get("rowIndex") == ridx and cc.get("columnIndex") == col:
                    return cc
            return None

        score = 0
        checked = 0
        for rr in range(header_r + 1, min(header_r + 10, max_r + 1)):
            row_all0 = " ".join(grid.get((rr, cc), "") for cc in range(0, max_c + 1))
            if "totals" in row_all0.lower():
                break
            comb0 = _normalize_combiner(_get_cell_text(rr, from_xwin, col_from)) or _find_combiner_in_row_text(row_all0)
            s0 = _parse_strings_cell(_get_cell_text(rr, strings_xwin, col_strings))
            if comb0 and _COMB_FULL.match(comb0):
                score += 2
            if s0 is not None and _STR_PREFERRED_MIN <= s0 <= _STR_MAX:
                score += 2
            checked += 1
        if checked >= 3 and score < 6:
            continue

        rows_by_base: Dict[str, List[Dict[str, Any]]] = {}
        totals_by_base: Dict[str, Dict[str, Any]] = {}

        for r in range(header_r + 1, max_r + 1):
            row_cells = [grid.get((r, c), "") for c in range(0, max_c + 1)]
            row_all = " ".join(row_cells)
            first_cell = (grid.get((r, 0), "") or "").strip()

            if _is_totals_row(row_all, first_cell):
                totals_strings_txt = _get_cell_text(r, strings_xwin, col_strings)
                totals_strings = _parse_totals_int(totals_strings_txt)
                totals = {
                    "strings_total": totals_strings,
                    "feeder_total": _parse_float_amp((grid.get((r, col_feeder), "") or "").strip()) if col_feeder is not None else None,
                    "stub_total": _parse_float_amp((grid.get((r, col_stub), "") or "").strip()) if col_stub is not None else None,
                    "mca_total": _parse_float_amp((grid.get((r, col_mca), "") or "").strip()) if col_mca is not None else None,
                }
                for base in rows_by_base.keys():
                    totals_by_base[base] = totals
                break

            from_txt = _get_cell_text(r, from_xwin, col_from)
            strings_txt = _get_cell_text(r, strings_xwin, col_strings)

            comb = _normalize_combiner(from_txt)

            if not comb or not _COMB_FULL.match(comb):
                if col_strings is not None:
                    left_text = " ".join(row_cells[:col_strings])
                else:
                    left_text = row_all
                comb = _find_combiner_in_row_text(left_text)
            if not comb or not _COMB_FULL.match(comb):
                continue

            strings_val = _parse_strings_cell(strings_txt)
            if strings_val is None and not strings_txt.strip():
                strings_val = _find_strings_before_module(row_all)

            if strings_val is not None and not (_STR_PREFERRED_MIN <= strings_val <= _STR_MAX):
                strings_val = None

            used_pixel = False
            page_num = None

            if (strings_val is None) and (pixel is not None):
                cell_obj = _get_cell_obj(r, strings_xwin, col_strings)
                if cell_obj is not None:
                    poly = _cell_poly(cell_obj)
                    page_num = _cell_page_number(cell_obj) or 1
                    if poly:
                        pv = pixel.ocr_int_from_poly(page_number=page_num, poly=poly)
                        if pv is not None and _STR_PREFERRED_MIN <= pv <= _STR_MAX:
                            strings_val = pv
                            used_pixel = True

            if page_num is None:
                from_cell_obj = _get_cell_obj(r, from_xwin, col_from)
                if from_cell_obj is not None:
                    page_num = _cell_page_number(from_cell_obj)

            feeder_val = _parse_float_amp((grid.get((r, col_feeder), "") or "").strip()) if col_feeder is not None else None
            stub_val = _parse_float_amp((grid.get((r, col_stub), "") or "").strip()) if col_stub is not None else None
            mca_val = _parse_float_amp((grid.get((r, col_mca), "") or "").strip()) if col_mca is not None else None

            base = ".".join(comb.split(".")[:3])
            rows_by_base.setdefault(base, []).append({
                "r": r,
                "comb": comb,
                "strings": strings_val,
                "page": page_num,
                "table_index": table_idx,
                "raw_from_text": from_txt,
                "raw_strings_text": strings_txt,
                "feeder_isc": feeder_val,
                "max_stub": stub_val,
                "mca": mca_val,
                "evidence": {
                    "method": "table_geom_or_index",
                    "pixel_ocr_used": bool(used_pixel),
                    "source_table_type": "combiner_strings",
                },
            })

        for base, items in rows_by_base.items():
            totals = totals_by_base.get(base, {})
            _derive_strings_for_group(items, totals)

        for base, items in rows_by_base.items():
            totals = totals_by_base.get(base, {})
            totals_strings = totals.get("strings_total")

            if totals_strings is None:
                continue

            vals = [it["strings"] for it in items if it.get("strings") is not None]
            ssum = sum(vals)

            if ssum == totals_strings:
                continue

            suspect = [
                it for it in items
                if it.get("strings") is None or it.get("strings") < 30 or it.get("strings") > 200
            ]

            if len(suspect) == 1:
                known_sum = sum(
                    it["strings"]
                    for it in items
                    if it.get("strings") is not None and it is not suspect[0]
                )
                inferred = totals_strings - known_sum
                if 30 <= inferred <= 200:
                    suspect[0]["strings"] = inferred

        for base, items in rows_by_base.items():
            items.sort(key=lambda x: x["r"])
            for it in items:
                out.append({
                    "from_combiner_box": it["comb"],
                    "strings": it.get("strings"),
                    "page": it.get("page"),
                    "source_table_index": it.get("table_index"),
                    "source_row_index": it.get("r"),
                    "raw_from_combiner_box": it.get("raw_from_text"),
                    "raw_strings_text": it.get("raw_strings_text"),
                    "evidence": it.get("evidence") or {},
                })

    return out


# ----------------------------
# Post-processing for clean test output
# ----------------------------

def filter_valid_combiner_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Keep rows that have the minimum usable fields for downstream review/export.

    Valid row rules:
    - must have a combiner identifier
    - must have a numeric strings value
    - strings must be > 0

    Do not reject rows only because:
    - needs_review is True
    - OCR and derived values disagree
    - raw OCR fields are blank
    """
    out: List[Dict[str, Any]] = []

    for r in rows:
        comb = (r.get("from_combiner_box") or "").strip()
        strings = r.get("strings")

        if not comb:
            continue

        if strings is None:
            continue

        try:
            strings_num = int(round(float(strings)))
        except (TypeError, ValueError):
            continue

        if strings_num <= 0:
            continue

        r["strings"] = strings_num
        out.append(r)

    return out


def dedupe_combiner_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best: Dict[str, Dict[str, Any]] = {}

    def score(row: Dict[str, Any]) -> int:
        ev = row.get("evidence") or {}
        sc = 0

        if row.get("strings") is not None:
            sc += 50
        if ev.get("override_applied"):
            sc += 40
        if ev.get("pixel_ocr_used"):
            sc += 20
        if ev.get("filled_by_word_scan") or ev.get("filled_by_word_scan_base_suffix"):
            sc += 10
        if not ev.get("needs_review", False):
            sc += 15
        if row.get("page") is not None:
            sc += 5

        return sc

    for r in rows:
        comb = (r.get("from_combiner_box") or "").strip()
        if not comb:
            continue

        current = best.get(comb)
        if current is None or score(r) > score(current):
            best[comb] = r

    return sorted(best.values(), key=lambda x: x.get("from_combiner_box") or "")


def simplify_combiner_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    for r in rows:
        ev = r.get("evidence") or {}
        out.append({
            "combiner_name": r.get("from_combiner_box"),
            "strings": r.get("strings"),
            "page": r.get("page"),
            "source_table_index": r.get("source_table_index"),
            "source_row_index": r.get("source_row_index"),
            "raw_from_combiner_box": r.get("raw_from_combiner_box"),
            "raw_strings_text": r.get("raw_strings_text"),
            "method": ev.get("method"),
            "pixel_ocr_used": bool(ev.get("pixel_ocr_used", False)),
            "needs_review": bool(ev.get("needs_review", False)),
            "suggested_strings": ev.get("suggested_strings"),
        })

    return out
import re
from typing import Optional

def _normalize_combiner_box_name(value: Optional[str]) -> str:
    s = (value or "").strip().upper()
    if not s:
        return ""

    s = s.replace(" ", "")
    s = s.replace("..", ".")
    s = re.sub(r"\.C\.(\d+)$", r".C\1", s)

    m = re.match(r"^(\d+\.\d+\.\d+)\.C(\d+)$", s)
    if m:
        return f"{m.group(1)}.C{int(m.group(2))}"

    return s


def _pick_best_strings_value(row: Dict[str, Any]) -> Optional[int]:
    val = row.get("strings")
    suggested = (row.get("evidence") or {}).get("suggested_strings")

    def to_int(x):
        if x is None:
            return None
        try:
            return int(round(float(x)))
        except (TypeError, ValueError):
            return None

    val_i = to_int(val)
    sug_i = to_int(suggested)

    if val_i is not None and val_i > 0:
        return val_i

    if sug_i is not None and sug_i > 0:
        row.setdefault("evidence", {})["used_suggested_strings"] = True
        row.setdefault("evidence", {})["needs_review"] = True
        return sug_i

    return None

# ----------------------------
# Public entry
# ----------------------------

def extract_combiners_strings(
    di_result: dict,
    overrides_path: Optional[str] = None,
    pdf_path: Optional[str] = None,
    pixel_ocr_dpi: int = 350,
    target_pages: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """
    Main public entry for combiner -> strings extraction.
    """
    ar = (di_result or {}).get("analyzeResult") or {}
    page_set = set(target_pages) if target_pages else None

    table_rows = _extract_from_tables(
        ar,
        pdf_path=pdf_path,
        pixel_ocr_dpi=pixel_ocr_dpi,
        target_pages=page_set,
    )
    word_rows = _extract_from_word_scan(ar, target_pages=page_set)

    print("table_rows:", len(table_rows))
    print("word_rows:", len(word_rows))
    for i, row in enumerate(word_rows[:10]):
        print(f"WORD_ROW {i+1}: {row}")

    word_map_exact: Dict[str, Dict[str, Any]] = {
        r["from_combiner_box"]: r
        for r in word_rows
        if r.get("from_combiner_box")
    }

    word_map_bs: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for r in word_rows:
        b, s = _comb_key(r.get("from_combiner_box") or "")
        if b and s is not None:
            word_map_bs[(b, s)] = r

    if table_rows:
        merged: List[Dict[str, Any]] = []
        for r in table_rows:
            comb = (r.get("from_combiner_box") or "").strip()
            if r.get("strings") is None and comb:
                if comb in word_map_exact:
                    r["strings"] = word_map_exact[comb]["strings"]
                    r["page"] = word_map_exact[comb].get("page")
                    r.setdefault("evidence", {})["filled_by_word_scan"] = True
                else:
                    b, s = _comb_key(comb)
                    if b and s is not None and (b, s) in word_map_bs:
                        r["strings"] = word_map_bs[(b, s)]["strings"]
                        r["page"] = word_map_bs[(b, s)].get("page")
                        r.setdefault("evidence", {})["filled_by_word_scan"] = True
            merged.append(r)
        rows = merged
    else:
        rows = word_rows

    if overrides_path:
        overrides = _load_overrides(overrides_path)
        if overrides:
            for r in rows:
                comb = (r.get("from_combiner_box") or "").strip()
                if comb in overrides:
                    r["strings"] = overrides[comb]
                    ev = r.get("evidence") or {}
                    ev["override_applied"] = True
                    ev["needs_review"] = False
                    r["evidence"] = ev

    for r in rows:
        ev = r.get("evidence") or {}
        ev.setdefault(
            "pixel_ocr_available",
            bool(pdf_path and fitz and pytesseract and PILImage),
        )
        ev.setdefault("source_table_type", "combiner_strings")
        r["evidence"] = ev

    for r in rows:
        r["from_combiner_box"] = _normalize_combiner_box_name(
            r.get("from_combiner_box")
        )
        r["strings"] = _pick_best_strings_value(r)

    print("rows before validation:", len(rows))
    for i, row in enumerate(rows[:10]):
        print(f"ROW {i+1}: {row}")

    rows = filter_valid_combiner_rows(rows)
    rows = dedupe_combiner_rows(rows)

    print("rows after validation:", len(rows))
    for i, row in enumerate(rows[:10]):
        print(f"VALID_ROW {i+1}: {row}")

    return rows

# ----------------------------
# CSV writers
# ----------------------------

def write_two_col_csv(rows: List[Dict[str, Any]], out_path: str) -> None:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "From Combiner Box",
            "Strings",
            "Page",
            "Source Table Index",
            "Source Row Index",
            "Raw From Combiner Box",
            "Raw Strings Text",
            "Pixel OCR Used",
            "Filled By Word Scan",
            "Needs Review",
            "Suggested Strings",
            "Derived Candidates",
            "Strings Total Used",
            "Ratio Feeder",
            "Ratio Stub",
            "Ratio MCA",
            "Override Applied",
        ])

        for r in rows:
            ev = r.get("evidence") or {}
            needs = bool(ev.get("needs_review", False))
            suggested = ev.get("suggested_strings")
            cands = ev.get("derived_candidates") or {}
            override_applied = bool(ev.get("override_applied", False))

            w.writerow([
                r.get("from_combiner_box"),
                r.get("strings"),
                r.get("page"),
                r.get("source_table_index"),
                r.get("source_row_index"),
                r.get("raw_from_combiner_box"),
                r.get("raw_strings_text"),
                bool(ev.get("pixel_ocr_used", False)),
                bool(ev.get("filled_by_word_scan", False) or ev.get("filled_by_word_scan_base_suffix", False)),
                needs,
                suggested,
                ";".join(f"{k}={v}" for k, v in cands.items()) if cands else "",
                ev.get("strings_total_used"),
                ev.get("ratio_feeder"),
                ev.get("ratio_stub"),
                ev.get("ratio_mca"),
                override_applied,
            ])


def write_combiner_test_csv(rows: List[Dict[str, Any]], out_path: str) -> None:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    simple_rows = simplify_combiner_rows(rows)

    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "Combiner Name",
            "Strings",
            "Page",
            "Source Table Index",
            "Source Row Index",
            "Raw Combiner Text",
            "Raw Strings Text",
            "Method",
            "Pixel OCR Used",
            "Needs Review",
            "Suggested Strings",
        ])

        for r in simple_rows:
            w.writerow([
                r.get("combiner_name"),
                r.get("strings"),
                r.get("page"),
                r.get("source_table_index"),
                r.get("source_row_index"),
                r.get("raw_from_combiner_box"),
                r.get("raw_strings_text"),
                r.get("method"),
                r.get("pixel_ocr_used"),
                r.get("needs_review"),
                r.get("suggested_strings"),
            ])