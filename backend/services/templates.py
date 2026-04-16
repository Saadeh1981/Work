
"""
templates.py
------------
Emit CSV/Excel templates for downstream systems (Drive/Greenbyte/Unity).
Start with a single CSV and expand later.
"""
import csv
import io
from typing import Dict, List

def generate_onboarding_csv(payload: Dict[str, str]) -> bytes:
    """
    payload example:
    {
        "PlantName": "Prairie Breeze",
        "AC_Capacity_MW": "150",
        "DC_Capacity_MW": "180",
        "Inverter_Model": "SMA-xyz",
        "SCADA_ConnType": "ModbusTCP"
    }
    """
    headers = list(payload.keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers)
    writer.writeheader()
    writer.writerow(payload)
    return buf.getvalue().encode("utf-8")
