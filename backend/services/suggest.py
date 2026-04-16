# backend/services/suggest.py
import re

def suggest_mappings(unknown_metadata: list[dict]) -> dict:
    candidates = []

    for u in (unknown_metadata or []):
        label = (u.get("label") or "").strip()
        value = (u.get("value") or "").strip()
        blob = f"{label}: {value}"

        suggestions = []

        # Plant name
        if re.search(r"(?i)\bproject\s*name\b", label):
            suggestions.append({
                "target_column": "PlantName",
                "kind": "string",
                "confidence": 0.95,
                "reason": "Label contains PROJECT NAME"
            })

        # DC capacity (TOTAL DC GENERATION - 443,520 WATTS)
        if re.search(r"(?i)TOTAL\s+DC\s+GENERATION", blob) and re.search(r"(?i)\bWATTS?\b", blob):
            suggestions.append({
                "target_column": "DC_Capacity_kW",
                "kind": "number",
                "confidence": 0.97,
                "reason": "TOTAL DC GENERATION in watts → convert to kW"
            })

        # AC export limit
        if re.search(r"(?i)\bexport\b.*\blimit\b", blob) or re.search(r"(?i)\bactive\s+power\b.*\blimit\b", blob):
            suggestions.append({
                "target_column": "ExportLimit_kW",
                "kind": "number",
                "confidence": 0.75,
                "reason": "Looks like an export limit"
            })

        # Module model tokens (Canadian Solar CS..., Suntech STP...)
        if re.search(r"(?i)\bCS[A-Z0-9]{2,}[-_ ]?\d{3}P\b", blob) or re.search(r"(?i)\bSTP\d{3}", blob):
            suggestions.append({
                "target_column": "ModuleModel",
                "kind": "string",
                "confidence": 0.90,
                "reason": "Looks like module model token"
            })

        # Inverter model tokens
        if re.search(r"(?i)\bAE\s+SOLARON\s+\d{3}\b", blob) or re.search(r"(?i)\bAE[_\s-]?3TL[-_]\d{2}_\d{2}\b", blob):
            suggestions.append({
                "target_column": "Inverters[0].Model",
                "kind": "string",
                "confidence": 0.88,
                "reason": "Looks like inverter model token"
            })

        # Voltage
        if re.search(r"(?i)\b\d{3}\/\d{3}V\b", blob) or re.search(r"(?i)\b\d{3}\s*V\b", blob):
            suggestions.append({
                "target_column": "POI_AC_Voltage",
                "kind": "string",
                "confidence": 0.70,
                "reason": "Looks like voltage value"
            })

        candidates.append({
            "label": label,
            "value": value,
            "suggestions": sorted(suggestions, key=lambda s: s["confidence"], reverse=True)
        })

    return {"candidates": candidates}
