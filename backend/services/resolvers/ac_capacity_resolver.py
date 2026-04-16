from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any
import re


@dataclass
class AcCapacityResolution:
    value_kw: Optional[float]
    confidence: float
    source: str
    evidence: Optional[str]
    issue: Optional[str] = None


def _clean(text: str | None) -> Optional[str]:
    if text is None:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _to_kw(value: float, unit: str) -> float:
    unit = (unit or "").upper()
    if unit == "MW":
        return value * 1000.0
    return value


def _extract_labeled_ac_capacity(text: str) -> tuple[Optional[float], Optional[str]]:
    patterns = [
        r"([0-9]+(?:\.[0-9]+)?)\s*MWAC\s*-\s*[0-9]+\s*HR",
        r"([0-9]+(?:\.[0-9]+)?)\s*MWAC\b",
        r"SYSTEM SIZE\s*\(KW-AC\)\s*([0-9]+(?:\.[0-9]+)?)\s*KW",
        r"AC\s*CAPACITY\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(KW|MW)",
        r"PROJECT\s*CAPACITY\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(KW|MW)\s*AC?",
        r"([0-9]+(?:\.[0-9]+)?)\s*(KW|MW)\s*[- ]?AC\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue

        full = _clean(match.group(0))
        if not full:
            continue

        num_match = re.search(r"([0-9]+(?:\.[0-9]+)?)", full, re.IGNORECASE)
        if not num_match:
            continue

        value = float(num_match.group(1))

        if "MWAC" in full.upper():
            return round(value * 1000.0, 3), full

        unit_match = re.search(r"\b(KW|MW)\b", full.upper())
        unit = unit_match.group(1) if unit_match else "KW"
        return round(_to_kw(value, unit), 3), full

    return None, None


def _extract_inverter_model_ac_kw(model: str) -> Optional[float]:
    model = (model or "").upper().strip()

    patterns = [
        r"-(\d+(?:\.\d+)?)_?\d*$",
        r"-(\d+(?:\.\d+)?)KW\b",
        r"\b(\d+(?:\.\d+)?)KW\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, model)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
    return None


def _get_any(d: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = d.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _collect_inverter_rows(groups: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    direct_keys = [
        "Inverters",
        "inverters",
        "Inverter",
        "inverter",
    ]

    for key in direct_keys:
        for item in _as_list(groups.get(key)):
            if isinstance(item, dict):
                candidates.append(item)

    for _, value in groups.items():
        for item in _as_list(value):
            if not isinstance(item, dict):
                continue

            group_type = str(item.get("group_type") or item.get("type") or "").lower()
            name = str(item.get("name") or item.get("section") or "").lower()

            if "inverter" in group_type or "inverter" in name:
                nested_items = item.get("items")
                if isinstance(nested_items, list):
                    for nested in nested_items:
                        if isinstance(nested, dict):
                            candidates.append(nested)
                else:
                    candidates.append(item)

    return candidates


def _sum_inverter_capacity_kw(groups: dict[str, Any]) -> tuple[Optional[float], Optional[str]]:
    total = 0.0
    found = False
    evidence_parts: list[str] = []

    inverter_rows = _collect_inverter_rows(groups)

    for inverter in inverter_rows:
        model = _get_any(
            inverter,
            "model",
            "Model",
            "model_number",
            "ModelNumber",
            "inverter_model",
        )
        quantity = _get_any(
            inverter,
            "quantity",
            "Quantity",
            "qty",
            "Qty",
            "count",
            "Count",
        )

        per_kw = _extract_inverter_model_ac_kw(str(model or ""))

        if per_kw is None:
            explicit_ac = _get_any(
                inverter,
                "ac_capacity_kw",
                "AC_Capacity_kW",
                "ac_kw",
                "AC_kW",
                "rated_ac_kw",
                "nameplate_ac_kw",
                "output_ac_kw",
                "max_ac_kw",
                "nominal_ac_kw",
            )
            try:
                per_kw = float(explicit_ac) if explicit_ac not in (None, "", [], {}) else None
            except (TypeError, ValueError):
                per_kw = None

        if per_kw is None:
            continue

        try:
            qty = float(quantity) if quantity not in (None, "", [], {}) else 1.0
        except (TypeError, ValueError):
            qty = 1.0

        total += per_kw * qty
        found = True
        evidence_parts.append(f"{model or 'unknown_model'} x {qty:g}")

    if not found:
        return None, None

    return round(total, 3), "; ".join(evidence_parts)


def resolve_ac_capacity(
    *,
    raw_text: str = "",
    site_fields: Optional[dict] = None,
    groups: Optional[dict] = None,
) -> AcCapacityResolution:
    site_fields = site_fields or {}
    groups = groups or {}

    direct = site_fields.get("AC_Capacity_kW")
    if direct not in (None, "", [], {}):
        try:
            return AcCapacityResolution(
                value_kw=float(direct),
                confidence=0.95,
                source="site_fields",
                evidence=f"Direct AC_Capacity_kW: {direct}",
            )
        except (TypeError, ValueError):
            pass

    labeled_value, labeled_evidence = _extract_labeled_ac_capacity(raw_text or "")
    inverter_sum, inverter_evidence = _sum_inverter_capacity_kw(groups)

    if labeled_value is not None:
        return AcCapacityResolution(
            value_kw=labeled_value,
            confidence=0.9,
            source="document_text",
            evidence=labeled_evidence,
        )

    if inverter_sum is not None:
        return AcCapacityResolution(
            value_kw=inverter_sum,
            confidence=0.7,
            source="inverter_sum",
            evidence=inverter_evidence,
        )

    dc_value = site_fields.get("DC_Capacity_kW")
    try:
        dc_value = float(dc_value) if dc_value not in (None, "", [], {}) else None
    except (TypeError, ValueError):
        dc_value = None

    if dc_value is not None:
        return AcCapacityResolution(
            value_kw=round(dc_value * 0.8, 3),
            confidence=0.4,
            source="derived_from_dc",
            evidence=f"0.8 × DC ({dc_value} kW)",
            issue="derived_value",
        )

    return AcCapacityResolution(
        value_kw=None,
        confidence=0.0,
        source="unresolved",
        evidence=None,
        issue="ac_capacity_not_found",
    )