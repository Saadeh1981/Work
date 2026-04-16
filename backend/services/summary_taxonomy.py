# backend/services/summary_taxonomy.py
from __future__ import annotations


DOMAIN_KEYWORDS = {
    "solar": [
        "solar", "pv", "photovoltaic", "module", "string", "combiner",
        "inverter", "tracker", "irradiance", "gcr", "azimuth", "tilt"
    ],
    "wind": [
        "wind", "turbine", "wtg", "nacelle", "blade", "hub height",
        "cut in", "cut out", "rated wind speed", "air density"
    ],
    "hydro": [
        "hydro", "reservoir", "penstock", "gate", "trash rack",
        "generator", "head water", "spillway", "turbine"
    ],
    "bess": [
        "bess", "battery", "battery rack", "battery bank", "pcs",
        "cell", "string", "container", "energy capacity", "warranty"
    ],
    "hybrid": [
        "hybrid", "pv+bess", "solar+bess", "co-located", "co located"
    ],
}


CONTENT_TYPE_KEYWORDS = {
    "plant_metadata": [
        "customer", "plant name", "site name", "address", "latitude", "longitude",
        "elevation", "timezone", "operator", "o&p operator", "manager",
        "cod", "interconnection date", "billable energy type", "data resolution"
    ],
    "equipment_schedule": [
        "schedule", "equipment list", "equipment schedule", "device list",
        "asset list", "nameplate", "manufacturer", "model"
    ],
    "layout": [
        "layout", "site plan", "general arrangement", "plot plan"
    ],
    "single_line_diagram": [
        "single line", "one line", "sld", "breaker", "bus", "feeder"
    ],
    "relationship_mapping": [
        "connected to", "fed by", "parent", "child", "assigned to",
        "mapped to", "group", "block", "pad"
    ],
}


ENTITY_KEYWORDS = {
    # common
    "plant": ["plant", "site", "facility"],
    "subarray": ["subarray", "sub-array"],
    "switchgear": ["switchgear", "switch gear"],
    "transformer": ["transformer", "gsu"],
    "meter": ["meter", "revenue meter", "utility meter"],

    # solar
    "block": ["block", "array block"],
    "pad": ["pad", "skid", "equipment pad"],
    "inverter_group": ["inverter group", "inv group"],
    "inverter": ["inverter", "pcs"],
    "combiner": ["combiner", "combiner box"],
    "module": ["module", "panel", "pv module"],
    "string": ["string", "dc string"],
    "tracker": ["tracker", "axis tracker"],
    "tcu": ["tcu", "tracker control unit"],
    "mppt_substation": ["mppt", "mppt station", "mppt substation"],
    "met_station": ["met station", "meteorological station", "weather station"],

    # wind
    "wind_turbine": ["wind turbine", "wtg", "turbine"],
    "nacelle": ["nacelle"],
    "tower": ["tower"],

    # bess
    "battery_bank": ["battery bank"],
    "battery_rack": ["battery rack", "rack"],
    "battery_container": ["battery container", "container"],
    "battery_cell": ["cell", "battery cell"],
    "pcs_bess": ["pcs", "power conversion system"],
    "ems": ["ems", "energy management system"],

    # hydro
    "reservoir": ["reservoir"],
    "hydro_turbine": ["hydro turbine", "turbine"],
    "head_water_level": ["head water level"],
    "trash_rack": ["trash rack", "trash"],
    "gate": ["gate"],
    "generator": ["generator"],
    "circuit_breaker": ["circuit breaker", "breaker"],
}


ATTRIBUTE_KEYWORDS = {
    # common plant metadata
    "customer_name": ["customer", "client"],
    "plant_name": ["plant name", "site name", "facility name"],
    "address": ["address", "site address"],
    "latitude": ["latitude", "lat"],
    "longitude": ["longitude", "long", "lon"],
    "elevation": ["elevation", "elev"],
    "timezone": ["timezone", "time zone"],
    "operator": ["operator"],
    "op_operator": ["o&p operator", "operations and maintenance operator", "o&m operator"],
    "manager": ["manager", "asset manager", "site manager"],
    "cod": ["cod", "commercial operation date"],
    "interconnection_date": ["interconnection date", "grid connection date"],
    "manufacturer": ["manufacturer", "vendor", "make"],
    "model": ["model", "model number"],

    # common capacities
    "ac_capacity": ["ac capacity", "mwac", "kwac", "ac mw", "ac kw"],
    "dc_capacity": ["dc capacity", "mwdc", "kwdc", "dc mw", "dc kw"],
    "energy_capacity": ["energy capacity", "mwh", "kwh"],

    # solar plant
    "data_resolution": ["data resolution", "resolution", "interval"],
    "billable_energy_type": ["billable energy type"],
    "gcr": ["gcr", "ground coverage ratio"],
    "azimuth": ["azimuth"],
    "mounting_tilt_degree": ["mounting tilt", "tilt", "tilt degree"],
    "mounting_type": ["mounting type", "fixed tilt", "hsat", "2-axis", "asat"],

    # solar module / subarray
    "module_count": ["module count", "number of modules"],
    "string_count": ["string count", "number of strings"],
    "module_imp": ["module_imp", "imp"],
    "module_isc": ["module_isc", "isc"],
    "module_pmax": ["module_pmax", "pmax"],
    "module_tcoeff": ["module_tcoeff", "temperature coefficient", "tcoeff"],
    "module_vmp": ["module_vmp", "vmp"],
    "module_voc": ["module_voc", "voc"],

    # wind
    "hub_height": ["hub height"],
    "max_operation_power": ["max operation power", "maximum operating power"],
    "rated_air_density": ["rated air density"],
    "rated_cut_in": ["rated cut in", "cut in"],
    "rated_cut_out": ["rated cut out", "cut out"],
    "rated_wind_speed": ["rated wind speed"],

    # bess
    "warranty_start_date": ["warranty start date"],
    "warranty_end_date": ["warranty end date"],
    "battery_count": ["number of batteries", "battery count"],
    "battery_bank_count": ["battery bank count", "number of battery banks"],
    "battery_rack_count": ["battery rack count", "number of racks"],
    "pcs_count": ["pcs count", "number of pcs"],
    "cell_count": ["cell count", "number of cells"],
    "string_count_bess": ["string count", "battery string count"],
}


RELATIONSHIP_KEYWORDS = {
    # solar
    "combiner_to_inverter": [
        "combiner to inverter", "combiner feeds inverter", "inverter input"
    ],
    "inverter_to_pad": [
        "inverter to pad", "mounted on pad", "assigned pad"
    ],
    "pad_to_block": [
        "pad to block", "located in block"
    ],
    "tracker_to_tcu": [
        "tracker to tcu", "tracker controller", "tcu"
    ],
    "tcu_to_pad": [
        "tcu to pad", "controller pad"
    ],
    "subarray_to_inverter": [
        "subarray to inverter", "subarray feeds inverter"
    ],

    # generic
    "parent_child_asset_mapping": [
        "parent", "child", "belongs to", "assigned to", "mapped to"
    ],
}