"""Batch extract structured clinical facts from data/extracted/ to data/structured/.

Processes each extracted document JSON using ExtractionService, validates
facts against Cancer Care Pydantic models, and saves structured results.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.services.extractor import (
    ExtractionService,
    OllamaConnectionError,
    ExtractionError,
)


def extract_all_structured() -> None:
    """Run structured extraction across all documents in data/extracted/."""
    extracted_dir = BASE_DIR / "data" / "extracted"
    structured_dir = BASE_DIR / "data" / "structured"
    structured_dir.mkdir(parents=True, exist_ok=True)

    if not extracted_dir.is_dir():
        raise FileNotFoundError(f"Extracted directory not found at {extracted_dir}")

    extracted_files = sorted(extracted_dir.glob("*.json"))
    if not extracted_files:
        raise FileNotFoundError(f"No extracted JSON documents found in {extracted_dir}")

    print(f"Initializing ExtractionService...")
    service = ExtractionService()
    print(f"Connected to Ollama config: base_url={service.base_url}, model={service.model}, timeout={service.timeout}s")
    print(f"Processing {len(extracted_files)} documents from {extracted_dir}...\n")

    successful_count = 0
    failed_docs = []

    for json_file in extracted_files:
        doc_id = json_file.stem
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                doc_data = json.load(f)

            print(f"Processing {doc_id} ({doc_data.get('file_name', 'unknown')})...")
            structured_result = service.extract_document(doc_data)

            # Count extracted facts
            facts_count = sum(len(items) for items in structured_result["facts"].values())

            # Save to data/structured/<document_id>.json
            out_file = structured_dir / f"{doc_id}.json"
            with open(out_file, "w", encoding="utf-8") as out_f:
                json.dump(structured_result, out_f, indent=2, ensure_ascii=False)

            successful_count += 1
            print(f"  [OK] Successfully extracted {doc_id} -> {out_file.name} ({facts_count} facts extracted)")
        except OllamaConnectionError as conn_err:
            print(f"\n[ERROR] Ollama connection failure: {conn_err}")
            print("Please start the local Ollama server before running live extraction.")
            sys.exit(1)
        except ExtractionError as ext_err:
            print(f"  [FAIL] Extraction error for {doc_id}: {ext_err}")
            failed_docs.append((doc_id, str(ext_err)))
        except Exception as exc:
            print(f"  [FAIL] Unexpected error for {doc_id}: {exc}")
            failed_docs.append((doc_id, str(exc)))

    print("\n=== EXTRACTION SUMMARY ===")
    print(f"Total documents scanned: {len(extracted_files)}")
    print(f"Successfully processed: {successful_count}")
    print(f"Failed: {len(failed_docs)}")

    if failed_docs:
        print("\nFailures:")
        for doc_id, err_msg in failed_docs:
            print(f"  - {doc_id}: {err_msg}")
        sys.exit(1)
    else:
        print(f"All structured extractions saved to {structured_dir}.")


if __name__ == "__main__":
    extract_all_structured()
