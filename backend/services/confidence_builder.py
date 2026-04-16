from __future__ import annotations


def score_text_block(
    text: str,
    method: str,
    file_type: str,
) -> float:
    cleaned = (text or "").strip()

    if not cleaned:
        return 0.0

    score = 0.5

    if len(cleaned) >= 20:
        score += 0.1

    if len(cleaned) >= 80:
        score += 0.1

    if any(ch.isdigit() for ch in cleaned):
        score += 0.05

    if method in {"pdf_page_text", "docx_paragraph", "xlsx_row"}:
        score += 0.1

    if file_type in {"pdf", "docx", "xlsx"}:
        score += 0.05

    return min(score, 0.95)