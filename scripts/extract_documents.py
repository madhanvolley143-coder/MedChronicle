"""Extract text page-by-page from synthetic PDFs in data/documents/ to data/extracted/.

Preserves document provenance, 1-based page numbers, and exact ground-truth metadata.
No external network, OCR, or LLM calls.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.services.document_reader import extract_document_text


def extract_all_documents() -> None:
    """Read all PDFs in data/documents/ and write structured extractions to data/extracted/."""
    documents_dir = BASE_DIR / "data" / "documents"
    extracted_dir = BASE_DIR / "data" / "extracted"
    ground_truth_path = BASE_DIR / "data" / "ground_truth" / "patient_001.json"

    extracted_dir.mkdir(parents=True, exist_ok=True)

    if not documents_dir.is_dir():
        raise FileNotFoundError(f"Documents directory not found at {documents_dir}")

    # Load ground truth for document ID verification
    expected_docs = {}
    if ground_truth_path.is_file():
        with open(ground_truth_path, "r", encoding="utf-8") as f:
            gt_data = json.load(f)
            for doc in gt_data.get("patient", {}).get("documents", []):
                expected_docs[doc["document_id"]] = doc

    pdf_files = sorted(documents_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in {documents_dir}")

    print(f"Scanning {documents_dir}...")
    print(f"Found {len(pdf_files)} PDF documents to extract.")

    extracted_count = 0
    total_pages = 0

    for pdf_path in pdf_files:
        # Determine document ID: from filename prefix (e.g. 'doc-001_...')
        doc_id = pdf_path.name.split("_")[0] if "_" in pdf_path.name else pdf_path.stem

        extracted_data = extract_document_text(pdf_path=pdf_path, document_id=doc_id)

        # Output JSON: data/extracted/<document_id>.json
        out_json_path = extracted_dir / f"{doc_id}.json"
        with open(out_json_path, "w", encoding="utf-8") as out_f:
            json.dump(extracted_data, out_f, indent=2, ensure_ascii=False)

        extracted_count += 1
        total_pages += extracted_data["page_count"]
        print(f"  [OK] Extracted {pdf_path.name} -> {out_json_path.name} ({extracted_data['page_count']} pages)")

    print(f"\nExtraction complete: {extracted_count} documents, {total_pages} total pages extracted to {extracted_dir}.")


if __name__ == "__main__":
    extract_all_documents()
