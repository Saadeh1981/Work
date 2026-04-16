from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class TimezoneResolution:
    value: Optional[str]
    confidence: float
    source: str
    evidence: Optional[str]
    issue: Optional[str] = None


STATE_TIMEZONE_MAP = {
    "AL": "America/Chicago",
    "ALABAMA": "America/Chicago",
    "AK": "America/Anchorage",
    "ALASKA": "America/Anchorage",
    "AZ": "America/Phoenix",
    "ARIZONA": "America/Phoenix",
    "AR": "America/Chicago",
    "ARKANSAS": "America/Chicago",
    "CA": "America/Los_Angeles",
    "CALIFORNIA": "America/Los_Angeles",
    "CO": "America/Denver",
    "COLORADO": "America/Denver",
    "CT": "America/New_York",
    "CONNECTICUT": "America/New_York",
    "DE": "America/New_York",
    "DELAWARE": "America/New_York",
    "FL": "America/New_York",
    "FLORIDA": "America/New_York",
    "GA": "America/New_York",
    "GEORGIA": "America/New_York",
    "HI": "Pacific/Honolulu",
    "HAWAII": "Pacific/Honolulu",
    "ID": "America/Denver",
    "IDAHO": "America/Denver",
    "IL": "America/Chicago",
    "ILLINOIS": "America/Chicago",
    "IN": "America/New_York",
    "INDIANA": "America/New_York",
    "IA": "America/Chicago",
    "IOWA": "America/Chicago",
    "KS": "America/Chicago",
    "KANSAS": "America/Chicago",
    "KY": "America/New_York",
    "KENTUCKY": "America/New_York",
    "LA": "America/Chicago",
    "LOUISIANA": "America/Chicago",
    "ME": "America/New_York",
    "MAINE": "America/New_York",
    "MD": "America/New_York",
    "MARYLAND": "America/New_York",
    "MA": "America/New_York",
    "MASSACHUSETTS": "America/New_York",
    "MI": "America/New_York",
    "MICHIGAN": "America/New_York",
    "MN": "America/Chicago",
    "MINNESOTA": "America/Chicago",
    "MS": "America/Chicago",
    "MISSISSIPPI": "America/Chicago",
    "MO": "America/Chicago",
    "MISSOURI": "America/Chicago",
    "MT": "America/Denver",
    "MONTANA": "America/Denver",
    "NE": "America/Chicago",
    "NEBRASKA": "America/Chicago",
    "NV": "America/Los_Angeles",
    "NEVADA": "America/Los_Angeles",
    "NH": "America/New_York",
    "NEW HAMPSHIRE": "America/New_York",
    "NJ": "America/New_York",
    "NEW JERSEY": "America/New_York",
    "NM": "America/Denver",
    "NEW MEXICO": "America/Denver",
    "NY": "America/New_York",
    "NEW YORK": "America/New_York",
    "NC": "America/New_York",
    "NORTH CAROLINA": "America/New_York",
    "ND": "America/Chicago",
    "NORTH DAKOTA": "America/Chicago",
    "OH": "America/New_York",
    "OHIO": "America/New_York",
    "OK": "America/Chicago",
    "OKLAHOMA": "America/Chicago",
    "OR": "America/Los_Angeles",
    "OREGON": "America/Los_Angeles",
    "PA": "America/New_York",
    "PENNSYLVANIA": "America/New_York",
    "PR": "America/Puerto_Rico",
    "PUERTO RICO": "America/Puerto_Rico",
    "RI": "America/New_York",
    "RHODE ISLAND": "America/New_York",
    "SC": "America/New_York",
    "SOUTH CAROLINA": "America/New_York",
    "SD": "America/Chicago",
    "SOUTH DAKOTA": "America/Chicago",
    "TN": "America/Chicago",
    "TENNESSEE": "America/Chicago",
    "TX": "America/Chicago",
    "TEXAS": "America/Chicago",
    "UT": "America/Denver",
    "UTAH": "America/Denver",
    "VT": "America/New_York",
    "VERMONT": "America/New_York",
    "VA": "America/New_York",
    "VIRGINIA": "America/New_York",
    "WA": "America/Los_Angeles",
    "WASHINGTON": "America/Los_Angeles",
    "WV": "America/New_York",
    "WEST VIRGINIA": "America/New_York",
    "WI": "America/Chicago",
    "WISCONSIN": "America/Chicago",
    "WY": "America/Denver",
    "WYOMING": "America/Denver",
}

DIRECT_TIMEZONE_PATTERNS = [
    r"\b(America/[A-Za-z_]+)\b",
    r"\b(US/[A-Za-z_]+)\b",
    r"\b(UTC[+-]\d{1,2}(?::\d{2})?)\b",
    r"\b(GMT[+-]\d{1,2}(?::\d{2})?)\b",
]

STATE_PATTERN = re.compile(
    r"\b([A-Z][A-Z\s]+,\s*([A-Z]{2}|[A-Z][A-Z\s]+))\b",
    re.IGNORECASE,
)


def _clean(value: str | None) -> Optional[str]:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip(" ,:-")
    return value or None


def _find_direct_timezone(text: str) -> tuple[Optional[str], Optional[str]]:
    for pattern in DIRECT_TIMEZONE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _clean(match.group(1)), _clean(match.group(0))
    return None, None


def _extract_state_token(*values: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    for value in values:
        cleaned = _clean(value)
        if not cleaned:
            continue

        match = STATE_PATTERN.search(cleaned.upper())
        if match:
            token = _clean(match.group(2))
            if token:
                return token.upper(), cleaned

        parts = [p.strip().upper() for p in cleaned.split(",") if p.strip()]
        if parts:
            last = parts[-1]
            if last in STATE_TIMEZONE_MAP:
                return last, cleaned

    return None, None


def resolve_timezone(
    *,
    raw_text: str = "",
    address: Optional[str] = None,
    site_location: Optional[str] = None,
    explicit_timezone: Optional[str] = None,
) -> TimezoneResolution:
    explicit_timezone = _clean(explicit_timezone)
    if explicit_timezone:
        return TimezoneResolution(
            value=explicit_timezone,
            confidence=0.98,
            source="explicit_field",
            evidence=explicit_timezone,
        )

    direct_value, direct_evidence = _find_direct_timezone(raw_text or "")
    if direct_value:
        return TimezoneResolution(
            value=direct_value,
            confidence=0.95,
            source="document_text",
            evidence=direct_evidence,
        )

    token, evidence = _extract_state_token(address, site_location)
    if token and token in STATE_TIMEZONE_MAP:
        return TimezoneResolution(
            value=STATE_TIMEZONE_MAP[token],
            confidence=0.85,
            source="address_or_location",
            evidence=evidence,
        )

    return TimezoneResolution(
        value=None,
        confidence=0.0,
        source="unresolved",
        evidence=None,
        issue="timezone_not_found",
    )