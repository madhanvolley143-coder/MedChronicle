"""Live extraction validation script using Google Gemini API on doc-003.json.

Processes ONLY data/extracted/doc-003.json, saves output to data/structured/doc-003-gemini.json,
and verifies schema validation, application source provenance, and clinical safety boundaries.

Never prints API keys in console output or logs.

Usage:
    python scripts/test_gemini_extraction.py
"""

import json
from pathlib import Path
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.services.evaluation import EvaluationService
from app.services.extractor import ExtractionService
from app.services.gemini_client import GeminiAuthError, GeminiError, GeminiProvider


def main() -> int:
    print("=" * 60)
    print("JourneyBrief — Live Gemini Extraction Test (doc-003 only)")
    print("=" * 60)

    api_key = settings.GEMINI_API_KEY
    if not api_key:
        print("[SKIPPED] GEMINI_API_KEY is not configured in environment or .env file.")
        print("To enable live extraction with Gemini, add the following to your .env file:")
        print("    GEMINI_API_KEY=your_actual_api_key_here")
        print("    GEMINI_MODEL=gemini-2.5-flash")
        print("=" * 60)
        return 0

    model_name = settings.GEMINI_MODEL or "gemini-2.5-flash"
    doc_path = Path("data/extracted/doc-003.json")
    out_path = Path("data/structured/doc-003-gemini.json")

    if not doc_path.is_file():
        print(f"Error: Target extraction file not found: {doc_path}", file=sys.stderr)
        return 1

    print(f"Model:                 {model_name}")
    print(f"Target Document:       {doc_path}")
    print(f"Output Path:           {out_path}")
    print("-" * 60)

    try:
        provider = GeminiProvider(api_key=api_key, model=model_name)
        service = ExtractionService(provider=provider)

        doc_data = json.loads(doc_path.read_text(encoding="utf-8"))

        t0 = time.time()
        result = service.extract_document(doc_data)
        elapsed = time.time() - t0

        # Save to doc-003-gemini.json (do not overwrite doc-003.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

        # Tally facts
        facts_dict = result.get("facts", {})
        total_facts = sum(len(items) for items in facts_dict.values() if isinstance(items, list))

        # Check provenance
        provenance_passed = True
        provenance_issues = []
        for cat, items in facts_dict.items():
            if isinstance(items, list):
                for item in items:
                    src = item.get("source", {})
                    if src.get("document_id") != "doc-003":
                        provenance_passed = False
                        provenance_issues.append(f"Invalid doc_id: {src.get('document_id')}")
                    if not str(src.get("file_name", "")).endswith(".pdf"):
                        provenance_passed = False
                        provenance_issues.append(f"Invalid file_name: {src.get('file_name')}")
                    if src.get("page_number") != 1:
                        provenance_passed = False
                        provenance_issues.append(f"Invalid page_number: {src.get('page_number')}")

        # Check safety using evaluation service
        eval_service = EvaluationService(
            ground_truth_path=Path("data/ground_truth/patient_001.json"),
            structured_dir=out_path.parent,
        )
        safety_result = eval_service.verify_safety({"doc-003-gemini": result})

        print("\n" + "=" * 60)
        print("GEMINI LIVE EXTRACTION RESULTS")
        print("=" * 60)
        print(f"Model Used:             {model_name}")
        print(f"Document ID:            {result.get('document_id')}")
        print(f"Number of Facts:        {total_facts}")
        print(f"Validation Result:      PASSED (Pydantic validation successful)")
        print(f"Source Provenance:      {'PASSED' if provenance_passed else 'FAILED'}")
        print(f"Clinical Safety:        {'PASSED' if safety_result['passed'] else 'FAILED'}")
        print(f"Processing Time:        {elapsed:.2f} seconds")
        print(f"Output File:            {out_path}")
        print("=" * 60)

        if not safety_result["passed"]:
            print(f"Safety Violations: {safety_result['violations']}", file=sys.stderr)
            return 1

        return 0

    except GeminiAuthError as auth_err:
        print(f"[AUTH ERROR] Failed to authenticate with Gemini: {auth_err}", file=sys.stderr)
        return 1
    except GeminiError as g_err:
        print(f"[GEMINI ERROR] Gemini extraction failed: {g_err}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[ERROR] Unexpected extraction error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
