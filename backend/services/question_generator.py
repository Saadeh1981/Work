from __future__ import annotations

from typing import Any


LOW_CONFIDENCE_THRESHOLD = 0.65


def generate_questions(evidence_blocks: list[dict[str, Any]]) -> list[dict[str, str]]:
    questions = []

    for item in evidence_blocks:
        confidence = item.get("confidence", 1.0)

        if confidence < LOW_CONFIDENCE_THRESHOLD:
            questions.append(
                {
                    "field": "unknown",
                    "reason": "low_confidence",
                    "question": f"Confirm extracted value near: {item.get('snippet','')[:80]}",
                }
            )

    return questions