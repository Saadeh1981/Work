# AI Implementation Assistant

## Purpose

AI-powered onboarding assistant for renewable energy projects.

The system scans mixed documents, understands their contents, extracts structured data, validates completeness, and prepares onboarding-ready outputs.

---

## Core Capabilities

### 1. Document Understanding
- Supports PDF, Excel, Word, images
- Detects document structure and sections
- Identifies relevant extraction targets

### 2. Data Extraction
- Extracts plant metadata and equipment data
- Builds structured output model
- Links every value to evidence and confidence

### 3. Validation Engine
- Detects missing required fields
- Flags low-confidence values
- Identifies duplicates and inconsistencies

### 4. Renewable Intelligence
- Classifies plant type:
  - Solar
  - Wind
  - BESS
  - Hydro
  - Hybrid
- Applies type-specific requirements

### 5. User Interaction Layer
- Highlights issues requiring review
- Generates targeted questions
- Accepts user corrections
- Learns from feedback

---

## End-to-End Flow

1. Upload documents
2. Run document summary scan
3. Generate extraction plan
4. Execute targeted extraction
5. Build structured output
6. Validate and detect issues
7. Present results and questions
8. Export onboarding-ready data

---

## Output

- Structured JSON (Output V1)
- Excel export for onboarding
- Review layer with:
  - confidence
  - evidence
  - missing fields
  - questions

---

## Key Value

- Reduces onboarding time
- Improves data quality
- Works across mixed document formats
- Scales across portfolios

---

## Run Locally

```bash
python -m scripts.run_full_pipeline
python -m scripts.export_excel