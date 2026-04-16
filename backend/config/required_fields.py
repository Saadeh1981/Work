from typing import Dict, List

FIELD_PRIORITIES_BY_PLANT_TYPE: Dict[str, Dict[str, List[str]]] = {
    "solar": {
        "critical": [
            "energy_type",
            "project_name",
            "timezone",
            "ac_capacity_kw",
            "dc_capacity_kw",
        ],
        "important": [
            "country",
            "address",
            "lat",
            "long",
            "elevation",
            "gcr",
            "azimuth",
            "tilt",
            "temperature_coefficient_nominal",
            "calculation_cutover",
            "modules_per_string",
        ],
    
        "optional": [],
    },
    "wind": {
        "critical": [
            "energy_type",
            "project_name",
            "timezone",
            "ac_capacity_kw",
        ],
        "important": [
            "address",
            "lat",
            "long",
            "elevation",
            "country",
        ],
        "optional": [],
    },
    "bess": {
        "critical": [
            "energy_type",
            "project_name",
            "timezone",
            "ac_capacity_kw",
        ],
        "important": [
            "address",
            "lat",
            "long",
            "elevation",
            "country",
        ],
        "optional": [],
    },
    "hydro": {
        "critical": [
            "energy_type",
            "project_name",
            "timezone",
            "ac_capacity_kw",
        ],
        "important": [
            "address",
            "lat",
            "long",
            "elevation",
            "country",
        ],
        "optional": [],
    },
    "hybrid": {
        "critical": [
            "energy_type",
            "project_name",
            "timezone",
            "ac_capacity_kw",
            "dc_capacity_kw",
        ],
        "important": [
            "address",
            "lat",
            "long",
            "elevation",
            "country",
        ],
        "optional": [],
    },
}


def get_required_fields(plant_type: str) -> List[str]:
    priorities = FIELD_PRIORITIES_BY_PLANT_TYPE.get(plant_type.lower(), {})
    return priorities.get("critical", [])


def get_field_priorities(plant_type: str) -> Dict[str, List[str]]:
    return FIELD_PRIORITIES_BY_PLANT_TYPE.get(
        plant_type.lower(),
        {"critical": [], "important": [], "optional": []},
    )