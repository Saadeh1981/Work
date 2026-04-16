from __future__ import annotations

from typing import Any
from pathlib import Path
from backend.schemas.summary import SummaryResponse
from backend.services.pdf_range_extractor import extract_pdf_page_range
from backend.services.xlsx_target_extractor import extract_xlsx_sheet
from backend.services.docx_target_extractor import extract_docx_content

from backend.services.docint_client import DocumentIntelligenceClient
import asyncio


def run_extraction_plan(summary: SummaryResponse) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    file_paths = {}
    for f in summary.files:
        name = getattr(f, "file_name", None) or f.get("file_name")
        path = getattr(f, "path", None) or f.get("path")
        if name:
            file_paths[name] = path or ""

    for item in summary.extraction_plan:
        file_name = item["file_name"]
        file_type = item["file_type"]
        file_path = _resolve_file_path(file_name, file_paths.get(file_name, ""))

        for target in item["targets"]:
            result = route_target(
                file_name=file_name,
                file_path=file_path,
                file_type=file_type,
                target=target,
            )
            results.append(result)

    return results

def _resolve_file_path(file_name: str, file_path: str) -> str:
    if file_path and Path(file_path).exists():
        return file_path

    candidate = Path("inputs") / file_name
    if candidate.exists():
        return str(candidate)

    return file_path or ""

def route_target(
    file_name: str,
    file_path: str,
    file_type: str,
    target: dict[str, Any],
) -> dict[str, Any]:
    label = target.get("label", "")

    if file_type == "pdf":
        return handle_pdf_target(file_name, file_path, label, target)

    if file_type == "xlsx":
        return handle_xlsx_target(file_name, file_path, label, target)

    if file_type == "docx":
        return handle_docx_target(file_name, file_path, label, target)

    return {
        "file_name": file_name,
        "file_path": file_path,
        "file_type": file_type,
        "label": label,
        "status": "unsupported",
        "target": target,
        "fields": [],
    }

def _run_ocr(file_path: str) -> dict:
    if not file_path:
        return {
            "error": True,
            "stage": "open_file",
            "text": "Empty file_path passed to OCR",
        }

    if not Path(file_path).exists():
        return {
            "error": True,
            "stage": "open_file",
            "text": f"File does not exist: {file_path}",
        }

    client = DocumentIntelligenceClient()

    with open(file_path, "rb") as f:
        pdf_bytes = f.read()

    result = asyncio.run(client.analyze_read(pdf_bytes))

    return {
        "analyzeResult": result.get("analyzeResult") or result,
        "file_bytes": pdf_bytes,
    }

def handle_pdf_target(
    file_name: str,
    file_path: str,
    label: str,
    target: dict[str, Any],
) -> dict[str, Any]:
    safe_label = label or ""

    if "plant_metadata" in safe_label:
        method = "extract_pdf_plant_metadata"
    elif "equipment_schedule" in safe_label:
        method = "extract_pdf_equipment_schedule"
    elif "single_line_diagram" in safe_label:
        method = "extract_pdf_single_line_diagram"
    elif "layout" in safe_label:
        method = "skip_layout_pdf"
    else:
        method = "mark_for_ocr_or_manual_review"

    result = {
        "file_name": file_name,
        "file_path": file_path,
        "file_type": "pdf",
        "label": label,
        "status": "routed",
        "target": target,
        "method": method,
        "fields": [],
    }

    if method in {
        "extract_pdf_plant_metadata",
        "extract_pdf_equipment_schedule",
        "extract_pdf_single_line_diagram",
    }:
        start_page = target.get("start_page")
        end_page = target.get("end_page")

        if start_page and end_page:
            extracted = extract_pdf_page_range(file_path, start_page, end_page)

            # 🔥 CHECK IF EMPTY → RUN OCR
            raw_text = (
                extracted.get("combined_text")
                or extracted.get("text")
                or ""
            )

            if not raw_text.strip():
                print("DEBUG OCR triggered from orchestrator:", file_name)

                ocr_result = _run_ocr(file_path)

                extracted = {
                    "text": "",
                    "combined_text": "",
                    "analyzeResult": ocr_result.get("analyzeResult"),
                    "_raw_text": "",  # will be filled downstream
                }

            result["extracted"] = extracted

    return result


def handle_xlsx_target(
    file_name: str,
    file_path: str,
    label: str,
    target: dict[str, Any],
) -> dict[str, Any]:
    if label == "plant_metadata":
        method = "extract_xlsx_plant_metadata"
    elif label == "equipment_schedule":
        method = "extract_xlsx_equipment_schedule"
    elif label == "inverter_list":
        method = "extract_xlsx_inverter_list"
    elif label == "tracker_list":
        method = "extract_xlsx_tracker_list"
    elif label == "string_table":
        method = "extract_xlsx_string_table"
    else:
        method = "skip_unknown_xlsx"

    result = {
        "file_name": file_name,
        "file_path": file_path,
        "file_type": "xlsx",
        "label": label,
        "status": "routed",
        "target": target,
        "method": method,
        "fields": [],
    }

    if method != "skip_unknown_xlsx":
        sheet_name = target.get("sheet_name")
        if sheet_name:
            extracted = extract_xlsx_sheet(file_path, sheet_name)
            result["extracted"] = extracted

    return result


def handle_docx_target(
    file_name: str,
    file_path: str,
    label: str,
    target: dict[str, Any],
) -> dict[str, Any]:
    if label == "layout":
        return {
            "file_name": file_name,
            "file_path": file_path,
            "file_type": "docx",
            "label": label,
            "status": "routed",
            "target": target,
            "method": "skip_layout_docx",
            "fields": [],
            "extracted": {
                "status": "skipped",
                "paragraphs": [],
                "tables": [],
                "paragraph_count": 0,
                "table_count": 0,
                "row_count": 0,
                "error": None,
            },
        }

    result = {
        "file_name": file_name,
        "file_path": file_path,
        "file_type": "docx",
        "label": label,
        "status": "routed",
        "target": target,
        "method": "extract_docx_content",
        "fields": [],
    }

    extracted = extract_docx_content(file_path)
    result["extracted"] = extracted
    return result