# scripts/test_extraction_orchestrator.py

from backend.services.summary_engine import summarize_folder
from backend.services.extraction_orchestrator import run_extraction_plan

root = r"C:\Users\SaadaSourkhan\Desktop\Work\ai-onboarding\inputs"

summary = summarize_folder(root)
results = run_extraction_plan(summary)

for r in results:
    print(r)