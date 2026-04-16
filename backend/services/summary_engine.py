from __future__ import annotations

from typing import List

from backend.schemas.summary import FileSummary, SummaryResponse
from backend.services.preflight_service import scan_folder, preflight, DocProfile
from backend.services.summary_pdf import summarize_pdf
from backend.services.summary_docx import summarize_docx
from backend.services.summary_xlsx import summarize_xlsx


def summarize_folder(root_path: str, sample_pages: int = 5) -> SummaryResponse:
    paths = scan_folder(root_path)
    profiles = preflight(paths, sample_pages=sample_pages)

    file_summaries: List[FileSummary] = []

    for prof in profiles:
        summary = summarize_profile(prof)
        file_summaries.append(summary)

    return SummaryResponse(
        files=file_summaries,
        global_findings=build_global_findings(file_summaries),
        extraction_plan=build_extraction_plan(file_summaries),
    )


def summarize_profile(prof: DocProfile) -> FileSummary:
    if prof.kind == "pdf":
        return summarize_pdf(prof)

    if prof.kind == "xlsx":
        return summarize_xlsx(prof)

    if prof.kind == "docx":
        return summarize_docx(prof)

    return FileSummary(
        file_name=prof.name,
        file_type=prof.kind,
        path=prof.path,
        page_count=prof.page_count,
        text_layer_present=prof.has_text_layer,
        scan_likelihood=prof.scan_likelihood,
        warnings=prof.warnings or [],
        likely_contents=[],
        sections=[],
        recommended_actions=[prof.plan or "manual_review"],
    )


def build_global_findings(files: List[FileSummary]) -> List[str]:
    findings: List[str] = []
    findings.append(f"{len(files)} supported files scanned")

    pdf_count = sum(1 for f in files if f.file_type == "pdf")
    xlsx_count = sum(1 for f in files if f.file_type == "xlsx")
    docx_count = sum(1 for f in files if f.file_type == "docx")
    image_count = sum(1 for f in files if f.file_type == "image")

    if pdf_count:
        findings.append(f"{pdf_count} PDF files found")
    if xlsx_count:
        findings.append(f"{xlsx_count} Excel files found")
    if docx_count:
        findings.append(f"{docx_count} Word files found")
    if image_count:
        findings.append(f"{image_count} image files found")

    return findings


def build_extraction_plan(files: List[FileSummary]) -> List[dict]:
    plan: List[dict] = []

    for f in files:
        targets = []

        for sec in f.sections:
            if sec.start_page is not None:
                targets.append(
                    {
                        "label": sec.label,
                        "start_page": sec.start_page,
                        "end_page": sec.end_page,
                    }
                )
            elif sec.sheet_name:
                targets.append(
                    {
                        "label": sec.label,
                        "sheet_name": sec.sheet_name,
                    }
                )

        if targets:
            plan.append(
                {
                    "file_name": f.file_name,
                    "file_type": f.file_type,
                    "targets": targets,
                }
            )

    return plan