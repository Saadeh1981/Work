from __future__ import annotations

import json
import uuid
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from backend.services.excel.device_sheet_schema import (
    DEVICE_EXTRA_COLUMN_MAPPINGS,
    SHEET_ORDER,
    get_sheet_columns,
    map_node_type_to_sheet,
    normalize_node_type,
)


def _first_attr(attrs: List[Dict[str, Any]], field_name: str) -> Optional[Dict[str, Any]]:
    for a in attrs or []:
        if str(a.get("field") or "").strip().lower() == field_name.strip().lower():
            return a
    return None


def _first_attr_any(
    attrs: List[Dict[str, Any]],
    field_names: List[str],
) -> Optional[Dict[str, Any]]:
    for name in field_names:
        hit = _first_attr(attrs, name)
        if hit:
            return hit
    return (attrs or [None])[0]


def _review_evidence_block(attr: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not attr:
        return {}
    for ev in attr.get("evidence") or []:
        if isinstance(ev, dict) and "needs_review" in ev:
            return ev
    return {}


def _to_conf_pct(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return round(float(value) * 100.0, 1)
    except Exception:
        return None


def _quality_columns_from_attr(attr: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    ev = _review_evidence_block(attr)
    pages = ev.get("source_pages") or []
    reasons = ev.get("review_reasons") or []

    return {
        "Confidence %": _to_conf_pct(attr.get("confidence") if attr else None),
        "Confidence Label": ev.get("confidence_label"),
        "Review Required": bool(ev.get("needs_review", False)),
        "Review Reasons": "; ".join(str(x) for x in reasons) if reasons else None,
        "Suggested Value": ev.get("suggested_value"),
        "Evidence Summary": ev.get("evidence_summary"),
        "Extraction Method": ev.get("extraction_method"),
        "Source File": ev.get("source_file"),
        "Source Pages": ", ".join(str(x) for x in pages) if pages else None,
    }


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _normalize_key(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
        .replace(".", "_")
    )


def _get_first(d: Dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for key in keys:
        if key in d and d[key] not in (None, ""):
            return d[key]
    return default


def _flatten_metadata_dict(value: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    if isinstance(value, dict):
        for k, v in value.items():
            out[_normalize_key(str(k))] = v
        return out

    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            field = _get_first(item, ["field", "key", "name"])
            if not field:
                continue
            v = _get_first(item, ["value", "normalized_value", "raw_value"], "")
            out[_normalize_key(str(field))] = v
        return out

    return out


def _extract_attr_map(node: Dict[str, Any]) -> Dict[str, Any]:
    attr_map: Dict[str, Any] = {}

    for key in ["attributes", "metadata", "fields", "properties", "data"]:
        if key not in node:
            continue
        parsed = _flatten_metadata_dict(node.get(key))
        attr_map.update(parsed)

    for direct_key, value in node.items():
        nk = _normalize_key(direct_key)
        if nk not in attr_map and isinstance(value, (str, int, float, bool)):
            attr_map[nk] = value

    return attr_map


def _get_node_attrs(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    value = node.get("attributes")
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    return []


def _merge_inherited_attrs(
    attrs: List[Dict[str, Any]],
    inherited_attrs: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    if not inherited_attrs:
        return list(attrs or [])

    merged: List[Dict[str, Any]] = []
    seen_fields: set[str] = set()

    for a in attrs or []:
        field = str(a.get("field") or "").strip().lower()
        if field:
            seen_fields.add(field)
        merged.append(a)

    for a in inherited_attrs or []:
        field = str(a.get("field") or "").strip().lower()
        if field and field in seen_fields:
            continue
        merged.append(a)

    return merged


def _pick_quality_attr(
    sheet_name: str,
    attrs: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if sheet_name == "Plant":
        return _first_attr_any(attrs, ["plant_name", "plant_type", "dc_kw", "ac_kw", "name"])

    if sheet_name == "Inverter":
        return _first_attr_any(attrs, ["inverter_model", "model", "manufacturer", "name"])

    if sheet_name == "Combiner":
        return _first_attr_any(attrs, ["name", "combiner_name"])

    if sheet_name == "Array":
        return _first_attr_any(attrs, ["module_model", "module_count", "string_count", "name"])

    if sheet_name == "Meter":
        return _first_attr_any(attrs, ["meter_model", "model", "manufacturer", "name"])

    if sheet_name == "Transformer":
        return _first_attr_any(attrs, ["transformer_model", "model", "manufacturer", "name"])

    if sheet_name == "Weather Station":
        return _first_attr_any(attrs, ["weather_station_model", "model", "manufacturer", "name"])

    return _first_attr_any(attrs, ["name", "model"])


def _dedupe_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []

    for row in rows:
        key = row.get("ID (UUID)") or json.dumps(row, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)

    return out


def _find_plants(output: Dict[str, Any]) -> List[Dict[str, Any]]:
    devices = output.get("devices")
    if isinstance(devices, dict):
        plants = devices.get("plants")
        if isinstance(plants, list) and plants:
            return plants

    plants = output.get("plants")
    if isinstance(plants, list) and plants:
        return plants

    overview = output.get("overview")
    if isinstance(overview, dict):
        plants = overview.get("plants")
        if isinstance(plants, list) and plants:
            return plants

    plant = output.get("plant")
    if isinstance(plant, dict):
        return [plant]

    return []


def _find_device_root(plant: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    candidates = [
        "device_tree",
        "deviceTree",
        "devices",
        "tree",
        "model",
        "asset_tree",
    ]
    for key in candidates:
        value = plant.get(key)

        if isinstance(value, dict):
            return value

        if isinstance(value, list):
            nodes = [x for x in value if isinstance(x, dict)]
            if not nodes:
                continue

            for node in nodes:
                node_type = _safe_str(_get_first(node, ["type", "node_type", "asset_type", "kind"], ""))
                parent_id = node.get("parent_node_id")
                if normalize_node_type(node_type) in {"plant", "site", "powerplant"} and parent_id in (None, "", "null"):
                    return {
                        "__node__": node,
                        "__all_nodes__": nodes,
                    }

            return {
                "__node__": nodes[0],
                "__all_nodes__": nodes,
            }

    return None


def _find_device_list(plant: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates = ["devices", "assets", "equipment", "components", "items", "nodes", "children"]
    for key in candidates:
        value = plant.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    return []


def _get_children(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ["children", "nodes", "assets", "devices", "items"]:
        value = node.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    return []


def _build_node_index(nodes: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for node in nodes:
        node_id = _safe_str(_get_first(node, ["node_id", "id", "uuid"], ""))
        if node_id:
            index[node_id] = node
    return index


def _resolve_children_from_ids(node: Dict[str, Any], all_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    raw_children = node.get("children")
    if not isinstance(raw_children, list):
        return []

    dict_children = [x for x in raw_children if isinstance(x, dict)]
    if dict_children:
        return dict_children

    child_ids = [_safe_str(x) for x in raw_children if x is not None]
    if not child_ids:
        return []

    index = _build_node_index(all_nodes)
    return [index[cid] for cid in child_ids if cid in index]


def _get_node_attr_name(node: Dict[str, Any]) -> str:
    attr_map = _extract_attr_map(node)
    return _safe_str(attr_map.get("name", _get_first(node, ["name", "display_name", "label"], "")))


def _get_node_attr_model(node: Dict[str, Any]) -> str:
    attr_map = _extract_attr_map(node)
    return _safe_str(attr_map.get("model", _get_first(node, ["model", "model_name"], "")))


def _find_inverter_type_node(
    actual_node: Dict[str, Any],
    all_nodes: Optional[List[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    if not isinstance(all_nodes, list):
        return None

    current_model = _get_node_attr_model(actual_node).strip().upper()
    if not current_model:
        return None

    matches: List[Dict[str, Any]] = []

    for node in all_nodes:
        if not isinstance(node, dict):
            continue

        node_type = _safe_str(_get_first(node, ["type", "node_type", "asset_type", "kind"], ""))
        if normalize_node_type(node_type) != "inverter":
            continue

        attr_name = _get_node_attr_name(node).strip().upper()
        if not attr_name.startswith("INV_TYPE_"):
            continue

        model = _get_node_attr_model(node).strip().upper()
        if model == current_model:
            matches.append(node)

    return matches[0] if matches else None


def _build_node_row(
    node: Dict[str, Any],
    sheet_name: str,
    parent_name: str,
    inherited_attr_map: Optional[Dict[str, Any]] = None,
    inherited_attrs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    attr_map = _extract_attr_map(node)
    node_attrs = _get_node_attrs(node)
    merged_attrs = _merge_inherited_attrs(node_attrs, inherited_attrs)

    if inherited_attr_map:
        merged_attr_map = dict(inherited_attr_map)
        merged_attr_map.update(
            {k: v for k, v in attr_map.items() if v not in (None, "", [], {})}
        )
    else:
        merged_attr_map = attr_map

    row: Dict[str, Any] = {col: "" for col in get_sheet_columns(sheet_name)}

    row["ID (UUID)"] = _safe_str(
        _get_first(node, ["uuid", "id", "node_id"], default=str(uuid.uuid4()))
    )
    row["Modification status"] = "New"
    row["Name"] = _safe_str(
        _get_first(
            node,
            ["display_name", "label"],
            default=merged_attr_map.get("name", _get_first(node, ["name"], "")),
        )
    )
    row["Parent"] = parent_name
    row["Model"] = _safe_str(
        _get_first(node, ["model", "model_name"], default=merged_attr_map.get("model", ""))
    )
    row["Serial No"] = _safe_str(
        _get_first(
            node,
            ["serial_no", "serial_number"],
            default=merged_attr_map.get("serial_no", merged_attr_map.get("serial_number", "")),
        )
    )
    row["Inst. Date"] = _safe_str(
        _get_first(
            node,
            ["inst_date", "installation_date", "installed_date"],
            default=merged_attr_map.get("inst_date", merged_attr_map.get("installation_date", "")),
        )
    )

    extra_mappings = DEVICE_EXTRA_COLUMN_MAPPINGS.get(sheet_name, {})
    for output_col, source_keys in extra_mappings.items():
        value = ""
        for source_key in source_keys:
            nk = _normalize_key(source_key)
            if nk in merged_attr_map and merged_attr_map[nk] not in (None, ""):
                value = merged_attr_map[nk]
                break
            if source_key in node and node[source_key] not in (None, ""):
                value = node[source_key]
                break
        row[output_col] = _safe_str(value)

    quality_attr = _pick_quality_attr(sheet_name, merged_attrs)
    row.update(_quality_columns_from_attr(quality_attr))

    if sheet_name == "Inverter" and row["Name"].strip().upper().startswith("INVERTER"):
        if "Quantity [Quantity]" in row:
            row["Quantity [Quantity]"] = "1"

    return row


def _traverse_device_tree(
    node: Dict[str, Any],
    rows_by_sheet: Dict[str, List[Dict[str, Any]]],
    parent_name: str = "",
    all_nodes: Optional[List[Dict[str, Any]]] = None,
) -> None:
    actual_node = node.get("__node__") if "__node__" in node else node
    actual_all_nodes = node.get("__all_nodes__") if "__all_nodes__" in node else all_nodes

    node_type = _get_first(actual_node, ["type", "node_type", "asset_type", "kind"], "")
    sheet_name = map_node_type_to_sheet(_safe_str(node_type))

    current_name = _safe_str(_get_first(actual_node, ["name", "display_name", "label"], ""))

    if sheet_name == "Inverter":
        attr_map = _extract_attr_map(actual_node)
        logical_name = _safe_str(attr_map.get("name", ""))
        if logical_name.startswith("INV_TYPE_"):
            return

    if sheet_name:
        inherited_attr_map = None
        inherited_attrs = None

        if sheet_name == "Inverter":
            inverter_type_node = _find_inverter_type_node(actual_node, actual_all_nodes)
            if inverter_type_node is not None:
                inherited_attr_map = _extract_attr_map(inverter_type_node)
                inherited_attrs = _get_node_attrs(inverter_type_node)

        rows_by_sheet[sheet_name].append(
            _build_node_row(
                node=actual_node,
                sheet_name=sheet_name,
                parent_name=parent_name,
                inherited_attr_map=inherited_attr_map,
                inherited_attrs=inherited_attrs,
            )
        )

    children = _get_children(actual_node)

    if not children and isinstance(actual_all_nodes, list):
        children = _resolve_children_from_ids(actual_node, actual_all_nodes)

    for child in children:
        _traverse_device_tree(
            child,
            rows_by_sheet,
            parent_name=current_name,
            all_nodes=actual_all_nodes,
        )


def build_device_rows_by_sheet(output: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    rows_by_sheet: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    top_level_devices = output.get("devices")
    if isinstance(top_level_devices, list) and top_level_devices:
        for node in top_level_devices:
            if isinstance(node, dict):
                _traverse_device_tree(node, rows_by_sheet, parent_name="")
        cleaned: Dict[str, List[Dict[str, Any]]] = {}
        for sheet_name, rows in rows_by_sheet.items():
            cleaned[sheet_name] = _dedupe_rows(rows)
        return cleaned

    plants = _find_plants(output)
    if not plants:
        return {}

    for plant in plants:
        root = _find_device_root(plant)
        if root:
            all_nodes = root.get("__all_nodes__") if isinstance(root, dict) else None
            _traverse_device_tree(root, rows_by_sheet, parent_name="", all_nodes=all_nodes)
            continue

        device_list = _find_device_list(plant)
        if device_list:
            for node in device_list:
                _traverse_device_tree(node, rows_by_sheet, parent_name="")
            continue

        if isinstance(plant, dict):
            _traverse_device_tree(plant, rows_by_sheet, parent_name="")

    cleaned: Dict[str, List[Dict[str, Any]]] = {}
    for sheet_name, rows in rows_by_sheet.items():
        cleaned[sheet_name] = _dedupe_rows(rows)
    return cleaned


def get_present_device_sheets(output: Dict[str, Any]) -> List[str]:
    rows_by_sheet = build_device_rows_by_sheet(output)
    present = [sheet for sheet, rows in rows_by_sheet.items() if rows]
    ordered = [sheet for sheet in SHEET_ORDER if sheet in present]
    extras = [sheet for sheet in present if sheet not in ordered]
    return ordered + sorted(extras)


def build_info1_rows(output: Dict[str, Any]) -> List[Dict[str, Any]]:
    plants = _find_plants(output)
    overview = output.get("overview", {}) if isinstance(output.get("overview"), dict) else {}
    rows: List[Dict[str, Any]] = []

    output_run = output.get("run", {}) if isinstance(output.get("run"), dict) else {}
    quality = output.get("quality", {}) if isinstance(output.get("quality"), dict) else {}

    rows.append({"Section": "Run", "Key": "run_id", "Value": _safe_str(output_run.get("run_id", ""))})
    rows.append({"Section": "Run", "Key": "created_utc", "Value": _safe_str(output_run.get("created_utc", ""))})
    rows.append({"Section": "Run", "Key": "source_file_count", "Value": _safe_str(output_run.get("source_file_count", ""))})

    plant_count = len(plants)
    if plant_count == 0 and isinstance(overview, dict):
        plant_count = overview.get("plant_count", overview.get("plants_detected", 0)) or 0

    rows.append({"Section": "Run", "Key": "plant_count", "Value": _safe_str(plant_count)})

    if isinstance(quality, dict):
        for key in ["overall_confidence", "completeness", "missing_count", "conflict_count"]:
            if key in quality:
                rows.append({"Section": "Quality", "Key": key, "Value": _safe_str(quality.get(key))})

    if isinstance(overview, dict):
        for key in ["customer_name", "portfolio_name", "technology", "plant_count"]:
            if key in overview:
                rows.append({"Section": "Overview", "Key": key, "Value": _safe_str(overview.get(key))})

    present_sheets = get_present_device_sheets(output)
    for sheet_name in present_sheets:
        rows.append({"Section": "Device Types", "Key": sheet_name, "Value": "Present"})

    for plant in plants:
        plant_name = _safe_str(_get_first(plant, ["plant_name", "name", "site_name"], ""))
        plant_id = _safe_str(_get_first(plant, ["plant_id", "id", "site_id"], ""))
        plant_type = _safe_str(_get_first(plant, ["plant_type", "technology", "type"], ""))
        rows.append({"Section": "Plant", "Key": f"{plant_id or plant_name}.name", "Value": plant_name})
        rows.append({"Section": "Plant", "Key": f"{plant_id or plant_name}.type", "Value": plant_type})

    return rows

def build_info2_rows(output: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows_by_sheet = build_device_rows_by_sheet(output)
    seen: set[Tuple[str, str, str]] = set()
    rows: List[Dict[str, Any]] = []

    for sheet_name, sheet_rows in rows_by_sheet.items():
        for row in sheet_rows:
            manufacturer = ""
            for col_name in row.keys():
                if col_name.startswith("Manufacturer "):
                    manufacturer = _safe_str(row[col_name])
                    break

            record = (
                sheet_name,
                _safe_str(row.get("Model", "")),
                manufacturer,
            )
            if record in seen:
                continue
            seen.add(record)
            rows.append(
                {
                    "Device Type Name": sheet_name,
                    "Device Model Name": record[1] or "Unknown",
                    "Device Manufacturer": record[2] or "Unknown",
                }
            )

    rows.sort(
        key=lambda x: (
            x["Device Type Name"],
            x["Device Manufacturer"],
            x["Device Model Name"],
        )
    )
    return rows
def build_missing_questions_rows(output: Dict[str, Any]) -> List[Dict[str, Any]]:
    quality = output.get("quality", {}) or {}
    missing = quality.get("missing", []) or []

    rows: List[Dict[str, Any]] = []

    for item in missing:
        if not isinstance(item, dict):
            continue

        rows.append(
            {
                "Plant ID": _safe_str(item.get("plant_id", "")),
                "Scope": _safe_str(item.get("scope", "")),
                "Node ID": _safe_str(item.get("node_id", "")),
                "Field": _safe_str(item.get("field", "")),
                "Reason": _safe_str(item.get("reason", "")),
                "Priority": _safe_str(item.get("priority", "")),
                "Question for User": _safe_str(item.get("question_for_user", "")),
                "User Answer": "",
                "Status": "Open",
            }
        )

    rows.sort(
        key=lambda r: (
            r["Plant ID"],
            r["Priority"],
            r["Scope"],
            r["Field"],
        )
    )

    return rows