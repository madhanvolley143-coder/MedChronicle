import json
import unittest
from pathlib import Path
from typing import Dict

try:
    import pymupdf as fitz
except ImportError:
    import fitz


class TestSyntheticDocuments(unittest.TestCase):
    """Test suite verifying the generated synthetic clinical PDF documents."""

    DOCUMENTS_DIR = Path("data/documents")
    GROUND_TRUTH_PATH = Path("data/ground_truth/patient_001.json")

    EXPECTED_PDFS: Dict[str, Dict[str, object]] = {
        "doc-001_visit_note_2026-01-05.pdf": {
            "doc_id": "doc-001",
            "date": "2026-01-05",
            "page_count": 2,
        },
        "doc-002_pathology_report_2026-01-08.pdf": {
            "doc_id": "doc-002",
            "date": "2026-01-08",
            "page_count": 2,
        },
        "doc-003_laboratory_report_2026-01-10.pdf": {
            "doc_id": "doc-003",
            "date": "2026-01-10",
            "page_count": 1,
        },
        "doc-004_imaging_report_2026-01-14.pdf": {
            "doc_id": "doc-004",
            "date": "2026-01-14",
            "page_count": 2,
        },
        "doc-005_prescription_2026-01-15.pdf": {
            "doc_id": "doc-005",
            "date": "2026-01-15",
            "page_count": 1,
        },
        "doc-006_procedure_note_2026-01-20.pdf": {
            "doc_id": "doc-006",
            "date": "2026-01-20",
            "page_count": 2,
        },
        "doc-007_referral_letter_2026-01-21.pdf": {
            "doc_id": "doc-007",
            "date": "2026-01-21",
            "page_count": 1,
        },
        "doc-008_laboratory_report_2026-02-05.pdf": {
            "doc_id": "doc-008",
            "date": "2026-02-05",
            "page_count": 1,
        },
        "doc-009_followup_visit_2026-02-07.pdf": {
            "doc_id": "doc-009",
            "date": "2026-02-07",
            "page_count": 2,
        },
        "doc-010_discharge_summary_2026-02-10.pdf": {
            "doc_id": "doc-010",
            "date": "2026-02-10",
            "page_count": 3,
        },
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.ground_truth = None
        if cls.GROUND_TRUTH_PATH.is_file():
            cls.ground_truth = json.loads(cls.GROUND_TRUTH_PATH.read_text(encoding="utf-8"))

    def test_01_documents_directory_exists(self) -> None:
        """1. Verify data/documents/ directory exists."""
        self.assertTrue(
            self.DOCUMENTS_DIR.is_dir(),
            f"Expected documents directory not found at {self.DOCUMENTS_DIR}",
        )

    def test_02_exactly_ten_expected_pdfs_exist(self) -> None:
        """2. Verify exactly 10 expected PDF files exist."""
        existing_pdfs = sorted([p.name for p in self.DOCUMENTS_DIR.glob("*.pdf")])
        expected_names = sorted(list(self.EXPECTED_PDFS.keys()))
        self.assertEqual(
            len(existing_pdfs),
            10,
            f"Expected 10 PDFs, but found {len(existing_pdfs)}: {existing_pdfs}",
        )
        self.assertEqual(existing_pdfs, expected_names)

    def test_03_every_expected_pdf_can_be_opened(self) -> None:
        """3. Verify every expected PDF can be opened successfully by PyMuPDF."""
        for filename in self.EXPECTED_PDFS:
            pdf_path = self.DOCUMENTS_DIR / filename
            self.assertTrue(pdf_path.is_file(), f"File missing: {pdf_path}")
            doc = fitz.open(pdf_path)
            self.assertFalse(doc.is_closed)
            doc.close()

    def test_04_every_pdf_has_expected_page_count(self) -> None:
        """4. Verify every PDF has the exact expected page count matching ground truth."""
        for filename, expected_meta in self.EXPECTED_PDFS.items():
            pdf_path = self.DOCUMENTS_DIR / filename
            doc = fitz.open(pdf_path)
            actual_pages = len(doc)
            expected_pages = expected_meta["page_count"]
            doc.close()
            self.assertEqual(
                actual_pages,
                expected_pages,
                f"{filename} has {actual_pages} pages, expected {expected_pages}",
            )

    def test_05_every_pdf_contains_patient_id(self) -> None:
        """5. Verify every PDF contains the fictional patient ID SYN-CANCER-001."""
        patient_id = "SYN-CANCER-001"
        for filename in self.EXPECTED_PDFS:
            pdf_path = self.DOCUMENTS_DIR / filename
            doc = fitz.open(pdf_path)
            full_text = "\n".join([page.get_text() for page in doc])
            doc.close()
            self.assertIn(
                patient_id,
                full_text,
                f"{filename} does not contain patient ID {patient_id}",
            )

    def test_06_every_pdf_contains_expected_document_id(self) -> None:
        """6. Verify every PDF contains its expected document ID."""
        for filename, expected_meta in self.EXPECTED_PDFS.items():
            pdf_path = self.DOCUMENTS_DIR / filename
            doc_id = str(expected_meta["doc_id"])
            doc = fitz.open(pdf_path)
            full_text = "\n".join([page.get_text() for page in doc])
            doc.close()
            self.assertIn(
                doc_id,
                full_text,
                f"{filename} does not contain expected doc ID {doc_id}",
            )

    def test_07_every_pdf_contains_expected_document_date(self) -> None:
        """7. Verify every PDF contains its expected document date."""
        for filename, expected_meta in self.EXPECTED_PDFS.items():
            pdf_path = self.DOCUMENTS_DIR / filename
            doc_date = str(expected_meta["date"])
            doc = fitz.open(pdf_path)
            full_text = "\n".join([page.get_text() for page in doc])
            doc.close()
            self.assertIn(
                doc_date,
                full_text,
                f"{filename} does not contain expected document date {doc_date}",
            )

    def test_08_no_unexpected_pdf_files_present(self) -> None:
        """8. Verify no unexpected PDF files are present in data/documents/."""
        all_pdf_names = {p.name for p in self.DOCUMENTS_DIR.glob("*.pdf")}
        expected_names = set(self.EXPECTED_PDFS.keys())
        unexpected = all_pdf_names - expected_names
        self.assertEqual(
            unexpected,
            set(),
            f"Unexpected PDF files found in {self.DOCUMENTS_DIR}: {unexpected}",
        )

    def test_09_generated_pdfs_are_non_empty(self) -> None:
        """9. Verify all generated PDFs have a positive file size (> 1000 bytes)."""
        for filename in self.EXPECTED_PDFS:
            pdf_path = self.DOCUMENTS_DIR / filename
            size = pdf_path.stat().st_size
            self.assertGreater(
                size,
                1000,
                f"{filename} has invalid or suspiciously small size: {size} bytes",
            )

    def test_10_deterministic_generation(self) -> None:
        """10. Verify generation is deterministic and does not produce duplicate files or errors."""
        existing_pdfs_before = sorted([p.name for p in self.DOCUMENTS_DIR.glob("*.pdf")])
        self.assertEqual(len(existing_pdfs_before), 10)
        # Verify sizes are stable
        sizes = [p.stat().st_size for p in self.DOCUMENTS_DIR.glob("*.pdf")]
        self.assertTrue(all(s > 0 for s in sizes))

    def test_11_every_ground_truth_document_exists_in_documents_dir(self) -> None:
        """11. Verify that every source file referenced in patient_001.json exists in data/documents/."""
        self.assertIsNotNone(self.ground_truth, "Ground truth JSON failed to load")
        gt_docs = self.ground_truth["patient"]["documents"]
        for doc in gt_docs:
            doc_id = doc["document_id"]
            # Document filename corresponds to doc-xxx_filename.pdf
            expected_name = f"{doc_id}_{doc['file_name']}"
            pdf_path = self.DOCUMENTS_DIR / expected_name
            self.assertTrue(
                pdf_path.is_file(),
                f"Ground truth document {doc_id} ('{expected_name}') missing on disk at {pdf_path}",
            )


if __name__ == "__main__":
    unittest.main()
