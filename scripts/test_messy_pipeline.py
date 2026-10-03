"""Integration test script for messy document ingestion, OCR, and Gemini extraction.

Processes one synthetic scanned document through the end-to-end pipeline:
messy PDF/image
-> ingestion
-> quality check
-> OCR
-> structured text
-> Gemini extraction
-> Pydantic validation

STRICT BOUNDARY:
- Uses ONLY synthetic test data.
- Enforces cancer-care non-interpretation safety boundaries.
"""

from pathlib import Path
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.services.document_ingestion import DocumentIngestionService
from app.services.document_quality import DocumentQualityChecker
from app.services.extractor import ExtractionService
from app.services.ocr import OCREngine


def run_messy_pipeline_test(
    file_path: Path = Path("data/messy_documents/messy_scanned_lab_report.pdf"),
) -> None:
    """Run end-to-end integration test on a synthetic messy document."""
    file_path = Path(file_path)
    if not file_path.is_file():
        raise FileNotFoundError(
            f"Test messy document not found at: {file_path}. "
            "Please run scripts/generate_messy_documents.py first."
        )

    print(f"Starting Messy Document Ingestion Pipeline for: {file_path.name}\n")
    start_time = time.perf_counter()

    # 1. Ingestion classification
    ingestion_service = DocumentIngestionService()
    ingest_res = ingestion_service.ingest(file_path)

    # 2. Quality check
    quality_checker = DocumentQualityChecker()
    q_rep = quality_checker.check_pdf(file_path)

    # 3. OCR Processing
    ocr_engine = OCREngine()
    ocr_res = ocr_engine.process_document(file_path, document_id="doc-003-scanned")

    # 4. Text Quality Check
    for page in ocr_res.pages:
        t_rep = quality_checker.check_ocr_text(page.text, ocr_confidence=page.ocr_confidence)
        if t_rep.issues:
            q_rep.issues.extend(t_rep.issues)

    # 5. Gemini Structured Extraction
    extractor = ExtractionService()
    extracted_facts = {}
    pydantic_valid = True
    provenance_pass = True
    safety_pass = True
    total_facts = 0

    page_1 = ocr_res.pages[0]
    extracted_facts = extractor.extract_page(
        document_id=ocr_res.document_id,
        file_name=ocr_res.file_name,
        page_number=page_1.page_number,
        page_text=page_1.text,
    )

    for category, facts in extracted_facts.items():
        total_facts += len(facts)
        for fact in facts:
            # Check Pydantic validation (is instance of BaseModel)
            if not hasattr(fact, "model_dump"):
                pydantic_valid = False

            # Check Provenance
            src = getattr(fact, "source", None)
            if not src or src.document_id != ocr_res.document_id or src.page_number != 1:
                provenance_pass = False

            # Check Safety: verify no prohibited clinical fields
            fact_dict = fact.model_dump()
            prohibited_keys = {
                "cancer_stage", "stage", "prognosis", "progression", "treatment_response",
                "severity", "risk_score", "recommendation",
            }
            if prohibited_keys.intersection(fact_dict.keys()):
                safety_pass = False

    elapsed = round(time.perf_counter() - start_time, 2)

    # Output formatted report
    print("=" * 60)
    print("MESSY DOCUMENT PIPELINE INTEGRATION REPORT")
    print("=" * 60)
    print(f"Input type:          {ingest_res.classification.value}")
    print(f"Pages:               {ingest_res.page_count}")
    print(f"OCR used:            {ocr_res.ocr_used}")
    print(f"OCR confidence:      {ocr_res.average_ocr_confidence}")
    print(f"Gemini used:         {extractor.provider.model_name}")
    print(f"Facts extracted:     {total_facts}")
    print(f"Pydantic validation: {'PASS' if pydantic_valid else 'FAIL'}")
    print(f"Provenance:          {'PASS' if provenance_pass else 'FAIL'}")
    print(f"Safety:              {'PASS' if safety_pass else 'FAIL'}")
    print(f"Processing time:     {elapsed}s")
    print("=" * 60)

    # Print fact highlights
    print("\nExtracted Clinical Fact Highlights:")
    for cat, items in extracted_facts.items():
        print(f"  [{cat}] ({len(items)} items)")
        for it in items[:4]:
            summary_attr = getattr(it, "test_name", None) or getattr(it, "finding_name", None) or getattr(it, "medicine_name", None) or getattr(it, "description", None)
            val = getattr(it, "value", "")
            unit = getattr(it, "unit", "")
            print(f"    - {summary_attr} {val} {unit}".strip())


if __name__ == "__main__":
    run_messy_pipeline_test()
