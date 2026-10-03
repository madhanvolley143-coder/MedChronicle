import json
import unittest
from pathlib import Path
from typing import Dict, Any

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from app.services.document_reader import (
    DocumentReadError,
    PDFDocumentReader,
    extract_document_text,
)


class TestDocumentReader(unittest.TestCase):
    """Test suite verifying PDF document text extraction and provenance retention."""

    EXTRACTED_DIR = Path("data/extracted")
    DOCUMENTS_DIR = Path("data/documents")
    GROUND_TRUTH_PATH = Path("data/ground_truth/patient_001.json")

    EXPECTED_DOC_IDS = [
        "doc-001",
        "doc-002",
        "doc-003",
        "doc-004",
        "doc-005",
        "doc-006",
        "doc-007",
        "doc-008",
        "doc-009",
        "doc-010",
    ]

    @classmethod
    def setUpClass(cls) -> None:
        cls.ground_truth = None
        cls.gt_doc_map: Dict[str, Any] = {}
        if cls.GROUND_TRUTH_PATH.is_file():
            cls.ground_truth = json.loads(cls.GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
            for doc in cls.ground_truth.get("patient", {}).get("documents", []):
                cls.gt_doc_map[doc["document_id"]] = doc

    def test_01_extracted_dir_exists(self) -> None:
        """1. Verify data/extracted/ directory exists."""
        self.assertTrue(
            self.EXTRACTED_DIR.is_dir(),
            f"Extracted directory not found at {self.EXTRACTED_DIR}",
        )

    def test_02_exactly_ten_extracted_json_files_exist(self) -> None:
        """2. Verify exactly 10 extracted JSON files exist."""
        json_files = sorted([f.name for f in self.EXTRACTED_DIR.glob("*.json")])
        expected_files = sorted([f"{doc_id}.json" for doc_id in self.EXPECTED_DOC_IDS])
        self.assertEqual(
            len(json_files),
            10,
            f"Expected exactly 10 JSON files, but found {len(json_files)}: {json_files}",
        )
        self.assertEqual(json_files, expected_files)

    def test_03_every_expected_document_has_extracted_json(self) -> None:
        """3. Verify every expected document in ground truth has a corresponding JSON file."""
        for doc_id in self.EXPECTED_DOC_IDS:
            target_file = self.EXTRACTED_DIR / f"{doc_id}.json"
            self.assertTrue(
                target_file.is_file(),
                f"Missing extracted JSON for document '{doc_id}' at {target_file}",
            )

    def test_04_json_files_load_successfully(self) -> None:
        """4. Verify each extracted JSON file is valid JSON and parses into a dictionary."""
        for doc_id in self.EXPECTED_DOC_IDS:
            target_file = self.EXTRACTED_DIR / f"{doc_id}.json"
            data = json.loads(target_file.read_text(encoding="utf-8"))
            self.assertIsInstance(data, dict)
            self.assertIn("document_id", data)
            self.assertIn("file_name", data)
            self.assertIn("page_count", data)
            self.assertIn("pages", data)

    def test_05_document_id_is_correct(self) -> None:
        """5. Verify the document_id in the JSON matches the filename stem and ground truth."""
        for doc_id in self.EXPECTED_DOC_IDS:
            target_file = self.EXTRACTED_DIR / f"{doc_id}.json"
            data = json.loads(target_file.read_text(encoding="utf-8"))
            self.assertEqual(
                data["document_id"],
                doc_id,
                f"Expected document_id '{doc_id}', got '{data.get('document_id')}'",
            )

    def test_06_file_name_is_correct(self) -> None:
        """6. Verify file_name matches the source PDF filename."""
        for doc_id in self.EXPECTED_DOC_IDS:
            target_file = self.EXTRACTED_DIR / f"{doc_id}.json"
            data = json.loads(target_file.read_text(encoding="utf-8"))
            file_name = data["file_name"]
            # The source file should exist on disk
            pdf_path = self.DOCUMENTS_DIR / file_name
            self.assertTrue(
                pdf_path.is_file(),
                f"Declared source PDF '{file_name}' does not exist at {pdf_path}",
            )
            # Should begin with the document_id
            self.assertTrue(file_name.startswith(f"{doc_id}_"))

    def test_07_page_count_matches_source_pdf(self) -> None:
        """7. Verify page_count in JSON matches both the ground truth and the physical PDF."""
        for doc_id in self.EXPECTED_DOC_IDS:
            target_file = self.EXTRACTED_DIR / f"{doc_id}.json"
            data = json.loads(target_file.read_text(encoding="utf-8"))
            file_name = data["file_name"]
            pdf_path = self.DOCUMENTS_DIR / file_name

            with fitz.open(str(pdf_path)) as pdf_doc:
                actual_pdf_pages = len(pdf_doc)

            self.assertEqual(
                data["page_count"],
                actual_pdf_pages,
                f"Extracted page_count ({data['page_count']}) != physical PDF page count ({actual_pdf_pages})",
            )
            self.assertEqual(
                len(data["pages"]),
                actual_pdf_pages,
                f"Length of pages list ({len(data['pages'])}) != physical PDF page count ({actual_pdf_pages})",
            )

    def test_08_page_numbers_start_at_one(self) -> None:
        """8. Verify page numbering starts at 1 for all documents."""
        for doc_id in self.EXPECTED_DOC_IDS:
            target_file = self.EXTRACTED_DIR / f"{doc_id}.json"
            data = json.loads(target_file.read_text(encoding="utf-8"))
            first_page = data["pages"][0]
            self.assertEqual(
                first_page["page_number"],
                1,
                f"Document {doc_id} first page number is {first_page['page_number']}, expected 1",
            )

    def test_09_page_numbers_are_sequential(self) -> None:
        """9. Verify page numbers are strictly sequential from 1 to page_count."""
        for doc_id in self.EXPECTED_DOC_IDS:
            target_file = self.EXTRACTED_DIR / f"{doc_id}.json"
            data = json.loads(target_file.read_text(encoding="utf-8"))
            expected_numbers = list(range(1, data["page_count"] + 1))
            actual_numbers = [p["page_number"] for p in data["pages"]]
            self.assertEqual(
                actual_numbers,
                expected_numbers,
                f"Page numbers for {doc_id} are not sequential: {actual_numbers}",
            )

    def test_10_every_page_contains_text_field(self) -> None:
        """10. Verify every page object has a 'text' string attribute."""
        for doc_id in self.EXPECTED_DOC_IDS:
            target_file = self.EXTRACTED_DIR / f"{doc_id}.json"
            data = json.loads(target_file.read_text(encoding="utf-8"))
            for p in data["pages"]:
                self.assertIn("text", p, f"Page in {doc_id} missing 'text' field")
                self.assertIsInstance(p["text"], str)

    def test_11_extracted_text_is_non_empty(self) -> None:
        """11. Verify extracted text on every page is non-empty and has substantial content."""
        for doc_id in self.EXPECTED_DOC_IDS:
            target_file = self.EXTRACTED_DIR / f"{doc_id}.json"
            data = json.loads(target_file.read_text(encoding="utf-8"))
            for p in data["pages"]:
                stripped_text = p["text"].strip()
                self.assertGreater(
                    len(stripped_text),
                    50,
                    f"Page {p['page_number']} of {doc_id} has insufficient text: '{stripped_text}'",
                )

    def test_12_extracted_text_contains_patient_id(self) -> None:
        """12. Verify every extracted document contains the synthetic patient ID SYN-CANCER-001."""
        patient_id = "SYN-CANCER-001"
        for doc_id in self.EXPECTED_DOC_IDS:
            target_file = self.EXTRACTED_DIR / f"{doc_id}.json"
            data = json.loads(target_file.read_text(encoding="utf-8"))
            combined_text = "\n".join(p["text"] for p in data["pages"])
            self.assertIn(
                patient_id,
                combined_text,
                f"Patient ID {patient_id} not found in extracted text of {doc_id}",
            )

    def test_13_extracted_document_date_present(self) -> None:
        """13. Verify the document date from ground truth is present somewhere in the extracted text."""
        for doc_id in self.EXPECTED_DOC_IDS:
            target_file = self.EXTRACTED_DIR / f"{doc_id}.json"
            data = json.loads(target_file.read_text(encoding="utf-8"))
            combined_text = "\n".join(p["text"] for p in data["pages"])

            gt_meta = self.gt_doc_map.get(doc_id)
            if gt_meta and gt_meta.get("document_date"):
                expected_date = gt_meta["document_date"]
                self.assertIn(
                    expected_date,
                    combined_text,
                    f"Expected document date '{expected_date}' not found in extracted text of {doc_id}",
                )

    def test_14_no_unexpected_files_in_extracted_dir(self) -> None:
        """14. Verify extraction directory does not contain unexpected files."""
        all_json_files = {f.name for f in self.EXTRACTED_DIR.glob("*.json")}
        expected_files = {f"{doc_id}.json" for doc_id in self.EXPECTED_DOC_IDS}
        unexpected = all_json_files - expected_files
        self.assertEqual(
            unexpected,
            set(),
            f"Unexpected files found in {self.EXTRACTED_DIR}: {unexpected}",
        )

    def test_reader_service_error_handling(self) -> None:
        """15. Verify PDFDocumentReader handles missing or unreadable files properly."""
        with self.assertRaises(FileNotFoundError):
            extract_document_text("data/documents/non_existent_file.pdf")

        # Test error with invalid non-PDF file
        dummy_file = self.EXTRACTED_DIR / "dummy_corrupt.pdf"
        try:
            dummy_file.write_text("Not a real PDF", encoding="utf-8")
            with self.assertRaises(DocumentReadError):
                extract_document_text(dummy_file)
        finally:
            if dummy_file.exists():
                dummy_file.unlink()


if __name__ == "__main__":
    unittest.main()
