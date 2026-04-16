from __future__ import annotations

import re
from typing import Dict, List

from backend.services.summary_taxonomy import (
    DOMAIN_KEYWORDS,
    CONTENT_TYPE_KEYWORDS,
    ENTITY_KEYWORDS,
    ATTRIBUTE_KEYWORDS,
    RELATIONSHIP_KEYWORDS,
)


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[_\-\/]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def score_label_map(text: str, label_map: Dict[str, List[str]]) -> Dict[str, int]:
    scores: Dict[str, int] = {}

    for label, keywords in label_map.items():
        score = 0
        for kw in keywords:
            kw_norm = normalize_text(kw)
            if kw_norm and kw_norm in text:
                score += 1
        if score > 0:
            scores[label] = score

    return scores


def sort_matches(scores: Dict[str, int]) -> List[str]:
    return [k for k, _ in sorted(scores.items(), key=lambda x: (-x[1], x[0]))]


def classify_text(text: str) -> dict:
    norm = normalize_text(text)

    domain_scores = score_label_map(norm, DOMAIN_KEYWORDS)
    content_type_scores = score_label_map(norm, CONTENT_TYPE_KEYWORDS)
    entity_scores = score_label_map(norm, ENTITY_KEYWORDS)
    attribute_scores = score_label_map(norm, ATTRIBUTE_KEYWORDS)
    relationship_scores = score_label_map(norm, RELATIONSHIP_KEYWORDS)

    return {
        "domains": sort_matches(domain_scores),
        "content_types": sort_matches(content_type_scores),
        "entities": sort_matches(entity_scores),
        "attributes": sort_matches(attribute_scores),
        "relationships": sort_matches(relationship_scores),
        "scores": {
            "domains": domain_scores,
            "content_types": content_type_scores,
            "entities": entity_scores,
            "attributes": attribute_scores,
            "relationships": relationship_scores,
        },
    }