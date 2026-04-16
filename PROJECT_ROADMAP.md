Project: Intelligent Document Understanding & Metadata Extraction Platform

Overall Goal
Production grade, cost efficient, self learning onboarding extraction pipeline.

Phase 1 – Ingestion and Preflight

 Ingest service with hashing and run id

 ZIP expansion

 Graph API download

 Preflight bytes based

 Page range planner

Phase 2 – Staged Extraction

 Native PDF parser by page range

 DOCX extractor

 XLSX extractor

 DI Read integration

 DI Layout integration

 Table normalization

Phase 3 – Domain Extraction

 Capacity extractor

 Equipment extractor

 Plant extractor

 Signal extractor

 Conflict detection

 Missing fields builder

Phase 4 – Learning Loop

 Versioned learning store

 Model aliases

 Header mappings

 RFI generator

 Re-run Stage D using learning

Phase 5 – Orchestrator & API

 Unified extraction orchestrator

 /preflight endpoint

 /extract endpoint

 /learn endpoint

 Run report with timing and cost

Phase 6 – Performance & Reliability

 DI caching by hash + range

 Retry with backoff

 Parallelization

 Cost metrics

Daily tracking method
Good. I reviewed both preflight outputs.

1. PDF Preflight

See 

response_1770941245543

Result:

file_type: pdf

page_count: 25

native_text_detected: true

sampled_units: 3

The sample text shows mostly:

Short tokens

Repeated codes

Drawing labels

Site plan metadata

This tells you something important.

This is drawing-heavy PDF.

Even though native text is detected, it is not narrative content. It is layout labels.

So your next logic should classify this as:

plan: drawing_heavy_pdf
next_step: OCR + layout analysis


Phase A worked correctly.

2. Excel Preflight

See 

response_1770941274004

Result:

file_type: xlsx

page_count: 1

native_text_detected: true

Clean structured rows

Controlled sampling

Notes correctly state sheet logic

This is a perfect structured onboarding source.

For Excel you should plan:

plan: structured_table
next_step: schema mapping

You Have Successfully Completed Phase A

You now have:

Safe bounded parsing

Lightweight output

Controlled memory

Fast execution

No crashes on 300+ page PDFs

No heavy payload return

This is production-grade preflight.

The Next Architectural Step

Phase A now tells you:

What type of document

How many logical units

Whether native text exists

What the sample looks like

Now you must add:

A Classification Layer

Based on:

token density

average word length

repetition ratio

presence of grid-like data

sheet structure detection

Return:

extraction_plan: {
    document_class: "structured_excel" | "text_pdf" | "drawing_pdf" | "mixed_pdf",
    recommended_pipeline: "native_parse" | "ocr" | "layout_ai" | "table_mapper"
}


This turns your system from parser into decision engine.

You are no longer building a parser.

You are building an orchestration brain.

Next move.

Do you want to:

A) Implement the document classification logic now
B) Move to Stage B heavy extraction

The correct architectural order is A.