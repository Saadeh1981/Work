
"""
validation.py
-------------
Tiny RTG rule set for MVP. Expand with types/ranges/conditional rules later.
"""
from typing import Dict, List, Tuple

REQUIRED_FIELDS = ["PlantName", "AC_Capacity_MW", "DC_Capacity_MW"]

def validate_payload(payload: Dict[str, str]) -> Tuple[bool, List[str]]:
    missing = [f for f in REQUIRED_FIELDS if f not in payload or not str(payload[f]).strip()]
    return (len(missing) == 0, missing)
