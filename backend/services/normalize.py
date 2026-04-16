# backend/services/normalize.py
from __future__ import annotations
import re
from typing import Optional, Tuple

# Very small vendor alias map (extend over time)
VENDOR_ALIASES = {
    "ADVANCED ENERGY": ["ADVANCED ENERGY", "AE"],
    "SUNTECH": ["SUNTECH"],
    "CANADIAN SOLAR": ["CANADIAN SOLAR", "CS"],
    "TRINA SOLAR": ["TRINA", "TRINASOLAR", "TRINA SOLAR"],
    "SMA": ["SMA"],
    "ENPHASE": ["ENPHASE"],
    "SOLAREDGE": ["SOLAREDGE", "SOLAR EDGE"],
}

def _canon_vendor(text: str) -> Optional[str]:
    t = re.sub(r"\s+", " ", (text or "").upper()).strip()
    for canon, aliases in VENDOR_ALIASES.items():
        if any(a in t for a in aliases):
            return canon
    return None

def _clean_model(text: str) -> str:
    # keep useful chars, normalize separators/spaces
    t = (text or "").strip()
    t = t.replace("–", "-").replace("—", "-").replace("_", "-")
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^\w\-\./ ]+", "", t)  # drop weird punctuation
    return t.strip()

def normalize_inverter_model(raw: str) -> Tuple[str, Optional[str]]:
    """
    Returns (normalized_model, vendor_canon?)
    Example: "UTILITY INTERACTIVE INVERTER AE_3TL-16_10" -> ("AE 3TL-16-10", "ADVANCED ENERGY")
    """
    t = _clean_model(raw)

    # common prefixes from drawings
    t = re.sub(r"(?i)\b(UTILITY\s+INTERACTIVE\s+INVERTER|INVERTER)\b[:\-]?\s*", "", t).strip()

    vendor = _canon_vendor(t)

    # specific cleanups
    # AE_3TL-16_10 -> AE 3TL-16-10
    t = re.sub(r"(?i)\bAE[-_ ]?3TL[-_ ]?(\d{2})[-_ ]?(\d{2})\b", r"AE 3TL-\1-\2", t)

    # "AE SOLARON 500" keep as "AE SOLARON 500"
    t = re.sub(r"(?i)\bAE\s+SOLARON\s+(\d+)\b", r"AE SOLARON \1", t)

    # SMA variants: "SMA SB5000" -> "SMA SB 5000"
    t = re.sub(r"(?i)\bSMA\s+SB\s*([0-9]{3,5})\b", r"SMA SB \1", t)

    return t, vendor

def normalize_module_model(raw: str) -> Tuple[str, Optional[str]]:
    """
    Returns (normalized_model, vendor_canon?)
    Example: "CS6X-305P" -> ("CS6X-305P", "CANADIAN SOLAR")
    """
    t = _clean_model(raw)

    # remove generic words
    t = re.sub(r"(?i)\b(MODULES?|SOLAR\s+MODULES?)\b[:\-]?\s*", "", t).strip()

    vendor = _canon_vendor(t)

    # tighten common module token patterns
    # CS6X-305P, TSM-230PA05, STP210S-18/Ub-1
    # Just normalize spacing:
    t = re.sub(r"\s*-\s*", "-", t)
    t = re.sub(r"\s*/\s*", "/", t)

    return t, vendor
