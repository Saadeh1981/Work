from __future__ import annotations

from collections import OrderedDict
from typing import Dict, List

BASE_COLUMNS: List[str] = [
    "ID (UUID)",
    "Modification status",
    "Name",
    "Parent",
    "Model",
    "Serial No",
    "Inst. Date",
]

# NEW — shared review / confidence columns
COMMON_REVIEW_COLUMNS: List[str] = [
    "Confidence %",
    "Confidence Label",
    "Review Required",
    "Review Reasons",
    "Suggested Value",
    "Evidence Summary",
    "Extraction Method",
    "Source File",
    "Source Pages",
]

# Internal node type -> Excel sheet name
NODE_TYPE_TO_SHEET: Dict[str, str] = {
    "plant": "Plant",
    "site": "Plant",
    "powerplant": "Plant",
    "inverter": "Inverter",
    "central_inverter": "Inverter",
    "string_inverter": "Inverter",
    "combiner": "Combiner",
    "combiner_box": "Combiner",
    "meter": "Meter",
    "revenue_meter": "Meter",
    "weatherstation": "WeatherStation",
    "weather_station": "WeatherStation",
    "met_station": "WeatherStation",
    "powerplantcontroller": "PowerPlantController",
    "power_plant_controller": "PowerPlantController",
    "ppc": "PowerPlantController",
    "tracker": "Tracker",
    "string": "String",
    "array": "Array",
    "block": "Block",
    "transformer": "Transformer",
    "substation": "Substation",
    "battery": "Battery",
    "pcs": "PCS",
    "bess_inverter": "PCS",
}

DEVICE_EXTRA_COLUMN_MAPPINGS: Dict[str, "OrderedDict[str, List[str]]"] = {
    "Plant": OrderedDict(
        {
            "Plant Code [PlantCode]": ["plant_code", "site_code", "code"],
            "Technology [Technology]": ["technology", "plant_type", "type"],
            "AC Capacity [ACCapacity]": ["ac_capacity_kw", "ac_kw", "ac_capacity"],
            "DC Capacity [DCCapacity]": ["dc_capacity_kw", "dc_kw", "dc_capacity"],
            "Latitude [Latitude]": ["latitude", "lat"],
            "Longitude [Longitude]": ["longitude", "lon", "lng"],
            "Commissioning Date [CommissioningDate]": [
                "commissioning_date",
                "commercial_operation_date",
            ],
            "Manufacturer [Manufacturer]": ["manufacturer"],
        }
    ),
    "Inverter": OrderedDict(
        {
            "Manufacturer [Manufacturer]": ["manufacturer", "vendor", "make"],
            "Model [ModelName]": ["model", "model_name"],
            "Quantity [Quantity]": ["quantity"],
            "Nominal AC Voltage [NominalACVoltage]": ["nominal_ac_voltage", "ac_voltage"],
            "Max DC Voltage [MaxDCVoltage]": ["max_dc_voltage"],
            "Max Power [MaxPower]": ["max_power", "power_kw", "nominal_power"],
            "Max Continuous Current [MaxContinuousCurrent]": [
                "max_continuous_current",
                "current",
            ],
            "AC Capacity [ACCapacity]": ["ac_capacity_kw", "ac_kw", "ac_capacity"],
            "DC Capacity [DCCapacity]": ["dc_capacity_kw", "dc_kw", "dc_capacity"],
            "PPC ID [PPCID]": ["ppc_id", "controller_id"],
            "Nominal Efficiency [NominalEfficiency]": [
                "nominal_efficiency",
                "efficiency",
            ],
            "MPPT Count [MpptCount]": ["mppt_count"],
        }
    ),
    "Combiner": OrderedDict(
        {
            "String Inputs [StringInputs]": ["string_inputs", "string_count"],
            "Fuse Count [FuseCount]": ["fuse_count"],
            "DC Rating [DCRating]": ["dc_rating"],
            "Manufacturer [Manufacturer]": ["manufacturer", "vendor", "make"],
            "Model [ModelName]": ["model", "model_name"],
        }
    ),
    "Meter": OrderedDict(
        {
            "Meter Type [MeterType]": ["meter_type", "type"],
            "Meter Number [MeterNumber]": ["meter_number"],
            "Voltage [Voltage]": ["voltage"],
            "Manufacturer [Manufacturer]": ["manufacturer", "vendor", "make"],
            "Model [ModelName]": ["model", "model_name"],
            "Protocol [Protocol]": ["protocol", "comm_protocol"],
        }
    ),
    "WeatherStation": OrderedDict(
        {
            "Sensor Type [SensorType]": ["sensor_type", "type"],
            "Manufacturer [Manufacturer]": ["manufacturer", "vendor", "make"],
            "Model [ModelName]": ["model", "model_name"],
            "Primary Sensor [PrimarySensor]": ["primary_sensor", "is_primary"],
        }
    ),
    "PowerPlantController": OrderedDict(
        {
            "Manufacturer [Manufacturer]": ["manufacturer", "vendor", "make"],
            "Model [ModelName]": ["model", "model_name"],
            "Controller Type [ControllerType]": ["controller_type", "type"],
            "Firmware Version [FirmwareVersion]": [
                "firmware_version",
                "firmware",
            ],
            "IP Address [IPAddress]": ["ip_address", "ip"],
        }
    ),
    "Tracker": OrderedDict(
        {
            "Axis Type [AxisType]": ["axis_type"],
            "Manufacturer [Manufacturer]": ["manufacturer", "vendor", "make"],
            "Model [ModelName]": ["model", "model_name"],
        }
    ),
    "String": OrderedDict(
        {
            "Module Count [ModuleCount]": ["module_count"],
            "String Voltage [StringVoltage]": ["string_voltage"],
            "String Current [StringCurrent]": ["string_current"],
        }
    ),
    "Array": OrderedDict(
        {
            "Module Count [ModuleCount]": ["module_count"],
            "String Count [StringCount]": ["string_count"],
            "Modules Per String [ModulesPerString]": ["modules_per_string"],
            "Module Make [ModuleMake]": ["module_make", "manufacturer"],
            "Module Model [ModuleModel]": ["module_model", "model"],
            "Tilt [Tilt]": ["tilt"],
            "Azimuth [Azimuth]": ["azimuth"],
        }
    ),
    "Block": OrderedDict(
        {
            "Block Number [BlockNumber]": ["block_number"],
            "AC Capacity [ACCapacity]": ["ac_capacity_kw", "ac_kw", "ac_capacity"],
            "DC Capacity [DCCapacity]": ["dc_capacity_kw", "dc_kw", "dc_capacity"],
        }
    ),
    "Transformer": OrderedDict(
        {
            "Primary Voltage [PrimaryVoltage]": ["primary_voltage"],
            "Secondary Voltage [SecondaryVoltage]": ["secondary_voltage"],
            "Voltage [Voltage]": ["voltage"],
            "Power Rating [PowerRating]": ["power_rating", "rating_kva", "rating_mva"],
            "Manufacturer [Manufacturer]": ["manufacturer", "vendor", "make"],
            "Model [ModelName]": ["model", "model_name"],
        }
    ),
    "Substation": OrderedDict(
        {
            "Voltage Level [VoltageLevel]": ["voltage_level"],
            "Utility [Utility]": ["utility"],
        }
    ),
    "Battery": OrderedDict(
        {
            "Nominal Energy Capacity [NominalEnergyCapacity]": [
                "nominal_energy_capacity",
                "energy_capacity_mwh",
                "energy_capacity_kwh",
            ],
            "Manufacturer [Manufacturer]": ["manufacturer", "vendor", "make"],
            "Model [ModelName]": ["model", "model_name"],
        }
    ),
    "PCS": OrderedDict(
        {
            "Nominal Power [NominalPower]": ["nominal_power", "power_kw", "power_mw"],
            "Manufacturer [Manufacturer]": ["manufacturer", "vendor", "make"],
            "Model [ModelName]": ["model", "model_name"],
        }
    ),
}

SHEET_ORDER: List[str] = [
    "Info 1",
    "Info 2",
    "Plant",
    "Block",
    "Array",
    "Inverter",
    "Combiner",
    "String",
    "Meter",
    "WeatherStation",
    "PowerPlantController",
    "Tracker",
    "Transformer",
    "Substation",
    "Battery",
    "PCS",
]


def normalize_node_type(value: str | None) -> str:
    if not value:
        return ""
    return (
        value.strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
    )


def map_node_type_to_sheet(node_type: str | None) -> str | None:
    normalized = normalize_node_type(node_type)
    return NODE_TYPE_TO_SHEET.get(normalized)


def get_sheet_columns(sheet_name: str) -> List[str]:
    columns = list(BASE_COLUMNS)

    extras = DEVICE_EXTRA_COLUMN_MAPPINGS.get(sheet_name, OrderedDict())
    columns.extend(extras.keys())

    # NEW — append review columns to every sheet
    columns.extend(COMMON_REVIEW_COLUMNS)

    return columns