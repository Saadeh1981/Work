
I am continuing development of the AI Onboarding Tool.

Read the project context below and use it as the working state of the project.

<PASTE PROJECT_CONTEXT.md HERE>

AI Onboarding Tool – Project Context
Project goal

Build an AI assisted onboarding tool that reads plant documents and generates structured plant metadata and device configuration for Unity onboarding.

The system processes plant documents such as:

single line diagrams

equipment specifications

layout drawings

inverter datasheets

Excel tag lists

The output becomes a structured plant model.

Current Architecture

Pipeline has two phases.

Phase 1 – Light Run (Preflight)

Purpose: analyze documents and plan extraction.

Modules:

document ingestion

document profiling

summary engine

page clustering

extraction planning

Output:

summary.json

This file lists:

detected document types

extraction plan

high level findings

Phase 2 – Deep Run (Extraction)

Purpose: extract structured metadata.

Modules:

pdf extractor

excel extractor

catalog mapper

output builder

Outputs:

extraction_results.json
mapped_items.json
output_v1.json

Current Progress

Completed components:

✔ ingestion
✔ summary engine
✔ page clustering
✔ extraction planning
✔ extraction orchestrator
✔ pdf extraction
✔ excel extraction
✔ catalog mapper
✔ confidence scoring
✔ evidence tracking
✔ output builder
✔ pipeline runner

The pipeline runs successfully using:

python -m scripts.run_full_pipeline

Outputs are written to:

data/runs/<timestamp>/

Remaining Features

Not implemented yet:

Missing field questions

Human answer loop

Excel / CSV outputs

AI extraction fallback

Plant merge engine

Azure deployment

Immediate Goal

Prepare a strong internal demo next week.

Demo flow:

Run pipeline on folder of plant documents

Show summary stage

Show extraction stage

Show structured plant model

Export Excel output

Long Term Goal

Turn the tool into a shared onboarding platform where engineers upload plant documents and receive a structured plant configuration.

Folder Structure

Key directories:

backend/services

scripts

data/input
data/runs

schemas

Important Scripts

Run full pipeline

python -m scripts.run_full_pipeline

Catalog mapper test

python -m scripts.test_catalog_mapper

Expected Next Development Tasks

Excel export from output_v1

Missing question generator

Answer import

AI extraction fallback

Azure deployment