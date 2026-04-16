# Document Summary Engine

## Purpose

The Document Summary Engine is the first pass of the AI Onboarding Tool.

It runs a fast, low-cost scan across uploaded documents and produces a structured summary of what each file likely contains before deep extraction starts.

This stage does not try to extract every final field.  
Its job is to:

- identify document type
- identify likely content by page range or sheet
- recommend what parts of each file should be extracted next
- reduce OCR and LLM cost in later stages
- give the user an understandable summary of the uploaded package

---

## Goals

### Primary goals

- support mixed onboarding document sets
- scan PDF, XLSX, DOCX, and image files
- identify likely topics inside each file
- detect likely page ranges in PDFs
- detect likely sheets in Excel files
- detect likely metadata sections in Word files
- produce a recommended extraction plan
- return structured confidence scores
- support later user-guided extraction

### Non-goals

This component does not:

- perform full final extraction of all metadata
- resolve all document conflicts
- replace deterministic extraction logic
- run expensive OCR on every page
- run LLM extraction on the full file by default

---

## Position in Pipeline

The Document Summary Engine sits after ingestion and preflight.

### Pipeline position

1. Ingestion
2. Preflight
3. **Document Summary Engine**
4. User review of summary and recommended plan
5. Guided extraction run
6. Review questions and conflict handling
7. Learning updates

---

## User Experience

### Step 1
User uploads a document package.

Example:

- PDF drawings
- Excel metadata files
- Word scope documents
- images

### Step 2
System runs a fast scan.

### Step 3
System returns a summary like:

- `PV_SLD.pdf`
  - pages 1 to 2: title block
  - pages 3 to 11: combiner schedule
  - pages 12 to 24: tracker layout
- `Equipment.xlsx`
  - Sheet1: project metadata
  - Sheet3: inverter list
  - Sheet4: combiner list
- `Scope.docx`
  - project overview
  - owner and EPC
  - scope of work

### Step 4
System recommends a next-step extraction plan.

### Step 5
User confirms or edits the plan.

### Step 6
Heavy extraction runs only on selected pages, sheets, and sections.

---

## Design Principles

### Cheap steps first
Use native parsing before OCR. Use OCR only where needed.

### Structured output
Return typed, stable objects that downstream services can consume.

### Explainability
Return signals and reasons for each section classification.

### Confidence-driven
Every section label should include a confidence score.

### User-guided flow
The summary should help the user choose what to extract next.

### Extensible
New document types, labels, and heuristics should be easy to add.

---

## Supported File Types

### PDF
Used for:
- one-line diagrams
- schedules
- equipment layouts
- title blocks
- electrical drawings

### XLSX
Used for:
- project metadata
- equipment lists
- tag mappings
- inverter lists
- combiner lists
- tracker lists

### DOCX
Used for:
- project overview
- owner and EPC details
- scope of work
- narrative equipment descriptions

### Images
Optional in early demo scope.
Used for:
- scanned plans
- screenshots
- drawing snippets

---

## Functional Requirements

The summary engine must:

- inspect all files in a run
- classify file type
- summarize file structure
- detect likely content sections
- identify likely extraction targets
- build a recommended extraction plan
- return confidence and supporting signals
- work with existing preflight outputs

---

## Inputs

### Source inputs

The engine consumes:

- uploaded file metadata
- run metadata
- preflight output
- local file path or blob reference
- optional learned mappings from prior runs

### Preflight dependencies

The engine should reuse preflight results where available:

- file type
- page count
- sheet count
- text layer presence
- scan likelihood
- encryption detection
- native parse availability
- page sampling hints

---

## Outputs

The engine returns a structured summary response.

### Output requirements

For each file, return:

- file name
- file type
- page count or sheet count
- text layer status if relevant
- scan likelihood if relevant
- likely contents
- detected sections
- recommended next actions

At run level, return:

- global findings
- recommended extraction plan

---

## Data Model

### SummaryRequest

```python
class SummaryRequest(BaseModel):
    run_id: str
    file_ids: list[str] | None = None
    options: dict | None = None