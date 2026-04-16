from __future__ import annotations

import fitz

from backend.schemas.summary import FileSection, FileSummary
from backend.services.preflight_service import DocProfile
from backend.services.page_topic_cluster import classify_pages, merge_page_topics


def summarize_pdf(prof: DocProfile) -> FileSummary:
    sections = []
    domains = set()
    content_types = set()
    entities = set()
    attributes = set()
    relationships = set()

    try:
        doc = fitz.open(prof.path)
    except Exception:
        return FileSummary(
            file_name=prof.name,
            file_type="pdf",
            path=prof.path,
            sections=[],
            domains=[],
            content_types=[],
            entities=[],
            attributes=[],
            relationships=[],
        )

    page_texts = []
    text_layer_present = False

    for i, page in enumerate(doc):
        try:
            text = page.get_text("text") or ""

            if len(text.strip()) < 20:
                text = page.get_text("blocks")
                text = " ".join(b[4] for b in text) if text else ""
            if len(text.strip()) > 20:
                text_layer_present = True
        except Exception:
            text = ""
        page_texts.append((i + 1, text))

    page_topics = classify_pages(page_texts)
    clusters = merge_page_topics(page_topics)

    for cluster in clusters:
        section_name = cluster.topic
        page_label = (
            f"pages {cluster.start_page}-{cluster.end_page}"
            if cluster.start_page != cluster.end_page
            else f"page {cluster.start_page}"
        )

        sections.append(
            FileSection(
                label=f"{section_name} {page_label}",
                start_page=cluster.start_page,
                end_page=cluster.end_page,
                confidence=cluster.score,
                signals=[cluster.topic],
            )
        )

        if cluster.topic != "unknown":
            domains.add("onboarding")
            content_types.add(cluster.topic)

            if cluster.topic == "single_line_diagram":
                entities.update(["transformer", "breaker", "inverter", "feeder"])
                relationships.update(["electrical_connection"])
            elif cluster.topic == "equipment_schedule":
                entities.update(["equipment", "model", "manufacturer"])
                attributes.update(["qty", "rating", "part_number"])
            elif cluster.topic == "layout":
                entities.update(["site", "block", "equipment"])
                relationships.update(["physical_location"])
            elif cluster.topic == "plant_metadata":
                entities.update(["plant", "project", "site"])
                attributes.update(["capacity", "location", "owner"])

    return FileSummary(
        file_name=prof.name,
        file_type="pdf",
        path=prof.path,
        text_layer_present=text_layer_present,
        sections=sections,
        domains=sorted(domains),
        content_types=sorted(content_types),
        entities=sorted(entities),
        attributes=sorted(attributes),
        relationships=sorted(relationships),
    )