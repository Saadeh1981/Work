import re
from typing import Dict, List, Any


def _safe(val):
    return val if val is not None else ""


def parse_devices_from_text(text: str) -> Dict[str, List[Dict[str, Any]]]:
    devices = {
        "Inverters": [],
        "Meters": [],
        "Transformers": [],
        "WeatherStations": [],
    }

    if not text:
        return devices

    text_upper = text.upper()

    # ---------------------------
    # Inverters (very simple rule)
    # ---------------------------
    inverter_matches = re.findall(r"(ADVANCED ENERGY|SMA|ABB).*?(AE_[A-Z0-9\-_]+)", text_upper)

    for i, match in enumerate(inverter_matches):
        manufacturer, model = match
        devices["Inverters"].append({
            "name": f"INV_{i+1}",
            "manufacturer": manufacturer,
            "model": model,
            "quantity": 1,
        })

    # ---------------------------
    # Meters
    # ---------------------------
    meter_matches = re.findall(r"METER\s*#\s*([0-9]+)", text_upper)

    for m in meter_matches:
        devices["Meters"].append({
            "name": f"METER_{m}",
            "meter_number": m,
        })

    # ---------------------------
    # Transformer
    # ---------------------------
    tx_matches = re.findall(r"(\d+KVA).*?(\d+Y/\d+Y)", text_upper)

    for i, match in enumerate(tx_matches):
        kva, voltage = match
        devices["Transformers"].append({
            "name": f"TX_{i+1}",
            "power_kva": kva,
            "voltage": voltage,
        })

    # ---------------------------
    # Sensors
    # ---------------------------
    if "TEMPERATURE SENSOR" in text_upper:
        devices["WeatherStations"].append({
            "name": "TEMP_SENSOR",
            "type": "Temperature",
        })

    if "PYRANOMETER" in text_upper:
        devices["WeatherStations"].append({
            "name": "PYRANOMETER",
            "type": "Irradiance",
        })

    return devices