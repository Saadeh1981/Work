from backend.services.page_topic_cluster import classify_pages, merge_page_topics


def test_classify_and_merge_pdf_topics():
    pages = [
        (1, "Project Name Alpha Solar. Site Name ABC. Capacity 50 MW. Location Texas."),
        (2, "Single Line Diagram. Transformer breaker feeder inverter 34.5 kV."),
        (3, "Single Line Diagram. Switchgear feeder breaker 34.5 kV interconnection."),
        (4, "Equipment Schedule. Qty Manufacturer Model Part Number Rating."),
        (5, "Equipment Schedule. Qty Manufacturer Model Part Number Rating."),
        (6, "Site Layout. Plan View. North Arrow. Fence. Access Road. Dimensions."),
    ]

    topics = classify_pages(pages)
    clusters = merge_page_topics(topics)

    assert topics[0].topic == "plant_metadata"
    assert topics[1].topic == "single_line_diagram"
    assert topics[3].topic == "equipment_schedule"
    assert topics[5].topic == "layout"

    assert len(clusters) == 4
    assert clusters[1].topic == "single_line_diagram"
    assert clusters[1].start_page == 2
    assert clusters[1].end_page == 3