from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple


TOPIC_ORDER = [
    "single_line_diagram",
    "equipment_schedule",
    "layout",
    "plant_metadata",
    "unknown",
]


TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "single_line_diagram": [
        "single line diagram",
        "single-line diagram",
        "sld",
        "one line diagram",
        "one-line diagram",
        "electrical single line",
        "switchgear",
        "transformer",
        "inverter",
        "combiner",
        "breaker",
        "feeder",
        "busbar",
        "substation",
        "interconnection",
        "mcc",
        "ac collection",
        "dc collection",
        "medium voltage",
        "high voltage",
        "hv",
        "mv",
        "kv",
        "one line",
        "electrical diagram",
        "dc combiner",
        "combiner box",
        "relay",
        "meter",
        "protection",
        "panelboard",
        "disconnect",
        "recloser",
        "fuse",
        "conductor",
        "circuit",
    ],
    "equipment_schedule": [
        "equipment schedule",
        "panel schedule",
        "schedule",
        "bill of materials",
        "bom",
        "equipment list",
        "device list",
        "cable schedule",
        "transformer schedule",
        "inverter schedule",
        "module schedule",
        "tag",
        "qty",
        "quantity",
        "manufacturer",
        "model",
        "part number",
        "rating",
        "equipment legend",
        "legend",
        "device schedule",
        "circuit schedule",
        "wire schedule",
        "cable tray",
        "conduit",
        "combiner schedule",
        "string table",
        "equipment designation",
    ],
    "layout": [
        "layout",
        "site layout",
        "general arrangement",
        "ga drawing",
        "plot plan",
        "plan view",
        "elevation",
        "section view",
        "detail view",
        "array layout",
        "block layout",
        "equipment layout",
        "fence",
        "road",
        "access road",
        "north arrow",
        "property line",
        "dimensions",
        "roof plan",
        "yard layout",
        "module layout",
        "array plan",
        "equipment pad",
        "fence line",
        "property boundary",
    ],
    "plant_metadata": [
        "project name",
        "plant name",
        "site name",
        "owner",
        "customer",
        "location",
        "address",
        "latitude",
        "longitude",
        "coordinates",
        "capacity",
        "dc capacity",
        "ac capacity",
        "mw",
        "kw",
        "point of interconnection",
        "poi",
        "utility",
        "revision",
        "sheet index",
        "drawing index",
        "cover sheet",
        "title sheet",
        "project number",
        "drawing number",
        "issued for construction",
        "revision description",
        "customer name",
        "site address",
    ],
}


TOPIC_PATTERNS: Dict[str, List[str]] = {
    "single_line_diagram": [
        r"\b\d{1,3}\.?\d*\s?k[vV]\b",
        r"\btransformer\b",
        r"\bbreaker\b",
        r"\bfeeder\b",
        r"\binverter\b",
    ],
    "equipment_schedule": [
        r"\bqty\b",
        r"\bmanufacturer\b",
        r"\bmodel\b",
        r"\bpart number\b",
        r"\btag\b",
        r"\brating\b",
    ],
    "layout": [
        r"\bplan view\b",
        r"\belevation\b",
        r"\bsection\b",
        r"\bnorth\b",
        r"\bscale\b",
        r"\bdimensions?\b",
    ],
    "plant_metadata": [
        r"\bproject\b",
        r"\bsite\b",
        r"\blat(?:itude)?\b",
        r"\blon(?:gitude)?\b",
        r"\bcapacity\b",
        r"\bowner\b",
    ],
}


@dataclass
class PageTopic:
    page_number: int
    topic: str
    score: float
    scores: Dict[str, float]
    preview: str


@dataclass
class PageCluster:
    topic: str
    start_page: int
    end_page: int
    pages: List[int]
    score: float
    preview: str


def normalize_text(text: str) -> str:
    text = text or ""
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def build_preview(text: str, max_len: int = 180) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 3] + "..."


def score_topic(text: str, topic: str) -> float:
    score = 0.0

    for kw in TOPIC_KEYWORDS.get(topic, []):
        if kw in text:
            score += 2.0

    for pattern in TOPIC_PATTERNS.get(topic, []):
        if re.search(pattern, text, flags=re.IGNORECASE):
            score += 1.5

    lines = text.count(" ")
    if topic == "equipment_schedule":
        if text.count("qty") >= 2:
            score += 1.5
        if text.count("model") >= 2:
            score += 1.5
        if text.count("manufacturer") >= 1:
            score += 1.0

    if topic == "single_line_diagram":
        electric_terms = sum(
            1 for t in ["transformer", "breaker", "feeder", "inverter", "switchgear"] if t in text
        )
        score += min(electric_terms, 4) * 0.75

    if topic == "layout":
        layout_terms = sum(
            1 for t in ["layout", "plan view", "elevation", "section", "north", "scale"] if t in text
        )
        score += min(layout_terms, 4) * 0.75

    if topic == "plant_metadata":
        meta_terms = sum(
            1 for t in ["project name", "plant name", "site name", "location", "capacity", "owner"] if t in text
        )
        score += min(meta_terms, 4) * 0.75

    if lines < 10:
        score -= 0.5

    return round(max(score, 0.0), 2)


def classify_page(page_number: int, raw_text: str) -> PageTopic:
    text = normalize_text(raw_text)
    preview = build_preview(raw_text)

    scores = {
        topic: score_topic(text, topic)
        for topic in TOPIC_ORDER
        if topic != "unknown"
    }

    best_topic = "unknown"
    best_score = 0.0

    for topic in TOPIC_ORDER:
        if topic == "unknown":
            continue
        topic_score = scores.get(topic, 0.0)
        if topic_score > best_score:
            best_topic = topic
            best_score = topic_score

    if best_score < 2.0:
        best_topic = "unknown"

    return PageTopic(
        page_number=page_number,
        topic=best_topic,
        score=best_score,
        scores=scores,
        preview=preview,
    )


def classify_pages(page_texts: List[Tuple[int, str]]) -> List[PageTopic]:
    return [classify_page(page_number, text) for page_number, text in page_texts]


def merge_page_topics(items: List[PageTopic], min_score: float = 2.0) -> List[PageCluster]:
    if not items:
        return []

    clusters: List[PageCluster] = []
    current: PageCluster | None = None

    for item in items:
        topic = item.topic if item.score >= min_score else "unknown"

        if current is None:
            current = PageCluster(
                topic=topic,
                start_page=item.page_number,
                end_page=item.page_number,
                pages=[item.page_number],
                score=item.score,
                preview=item.preview,
            )
            continue

        if topic == current.topic and item.page_number == current.end_page + 1:
            current.end_page = item.page_number
            current.pages.append(item.page_number)
            current.score = max(current.score, item.score)
            if len(current.preview) < 120 and item.preview:
                current.preview = f"{current.preview} | {item.preview}"[:200]
        else:
            clusters.append(current)
            current = PageCluster(
                topic=topic,
                start_page=item.page_number,
                end_page=item.page_number,
                pages=[item.page_number],
                score=item.score,
                preview=item.preview,
            )

    if current is not None:
        clusters.append(current)

    return clusters