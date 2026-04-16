# AI Onboarding Tool Notes

## Product Vision

Assist implementation engineers and TPMs by:
- automating document understanding
- extracting onboarding data
- ensuring completeness and quality

---

## Target Users

### TPM
- Needs portfolio-level visibility
- Needs missing data detection

### Implementation Engineer
- Needs structured onboarding data
- Needs reduced manual work

---

## Key Problems Solved

- Manual data extraction from documents
- Missing or incomplete onboarding data
- Inconsistent formats across projects
- Duplicate and conflicting information

---

## Current System Behavior

- Scans documents
- Extracts structured data
- Provides confidence and evidence
- Outputs onboarding model

---

## Current Gaps

- No plant type classification
- No requirements validation
- Duplicate entities exist
- Confidence logic needs improvement

---

## Design Principles

- Confidence-driven outputs
- Evidence-backed values
- User-guided corrections
- Modular architecture
- Deterministic core + AI enhancement

---

## Key Concepts

### Confidence
Indicates reliability of extracted value

### Evidence
Source snippet supporting the value

### Missing Fields
Required data not found

### Review Required
Fields needing user confirmation

---

## Next Focus

- Requirements engine
- Renewable classification
- Deduplication
- Question generation