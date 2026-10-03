"""Unit tests for OCREngine and document text routing.

Verifies:
6. OCR output preserves mandatory source metadata (document_id, file_name, page_number).
7. Technical OCR confidence is accurately calculated and recorded.
8. Empty or unreadable OCR output is handled cleanly with technical status.
9. English OCR works on image and scanned documents when Tesseract is available.
11. OCR confidence is strictly technical and distinct from clinical confidence.
12. Clean digital PDFs bypass OCR (ocr_used=False) preserving existing extraction pipeline.
"""

from pathlib import Path
import tempfile
import unittest
from PIL import Image, ImageDraw

from app.services.ocr import OCRDocumentResult, OCREngine


class TestOCREngine(unittest.TestCase):
    """Test suite for local OCR processing and intelligent document routing."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = OCREngine()
        cls.tesseract_ready = cls.engine.is_tesseract_available()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_06_ocr_preserves_source_metadata(self) -> None:
        """6. Verify OCR results preserve document_id, file_name, and page_number."""
        if not self.tesseract_ready:
            self.skipTest("Tesseract not available on system.")

        img_path = self.work_dir / "meta_test.png"
        img = Image.new("RGB", (400, 100), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        d.text((10, 30), "Clinical Note doc-meta", fill=(0, 0, 0))
        img.save(img_path)

        res = self.engine.process_document(img_path, document_id="doc-meta")
        self.assertEqual(res.document_id, "doc-meta")
        self.assertEqual(res.file_name, "meta_test.png")
        self.assertEqual(len(res.pages), 1)
        self.assertEqual(res.pages[0].document_id, "doc-meta")
        self.assertEqual(res.pages[0].page_number, 1)

    def test_07_ocr_confidence_is_recorded(self) -> None:
        """7. Verify technical OCR confidence metrics are recorded between 0.0 and 1.0."""
        if not self.tesseract_ready:
            self.skipTest("Tesseract not available on system.")

        img_path = self.work_dir / "conf_test.png"
        img = Image.new("RGB", (500, 120), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        d.text((20, 40), "Hemoglobin level 12.8 g/dL recorded.", fill=(0, 0, 0))
        img.save(img_path)

        res = self.engine.process_document(img_path, document_id="doc-conf")
        self.assertTrue(res.ocr_used)
        self.assertIsNotNone(res.average_ocr_confidence)
        self.assertGreaterEqual(res.average_ocr_confidence, 0.0)
        self.assertLessEqual(res.average_ocr_confidence, 1.0)
        self.assertGreaterEqual(res.min_ocr_confidence, 0.0)

    def test_08_empty_ocr_handled(self) -> None:
        """8. Verify blank image OCR produces needs_review without throwing unhandled exceptions."""
        if not self.tesseract_ready:
            self.skipTest("Tesseract not available on system.")

        blank_path = self.work_dir / "blank_ocr.png"
        img = Image.new("RGB", (300, 300), color=(255, 255, 255))
        img.save(blank_path)

        res = self.engine.process_document(blank_path, document_id="doc-blank")
        self.assertEqual(res.status, "needs_review")
        self.assertIn("insufficient text", res.reason.lower())

    def test_09_english_ocr_extracts_clean_text(self) -> None:
        """9. Verify English OCR transcribes text accurately from synthetic test image."""
        if not self.tesseract_ready:
            self.skipTest("Tesseract not available on system.")

        img_path = self.work_dir / "eng_test.png"
        img = Image.new("RGB", (600, 150), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        d.text((20, 50), "TAMOXIFEN 20 MG ORAL TABLET DAILY", fill=(0, 0, 0))
        img.save(img_path)

        res = self.engine.process_document(img_path, document_id="doc-med")
        self.assertEqual(res.status, "success")
        self.assertIn("TAMOXIFEN", res.pages[0].text.upper())
        self.assertIn("20", res.pages[0].text)

    def test_11_ocr_confidence_is_not_treated_as_clinical_confidence(self) -> None:
        """11. Verify OCR confidence is documented as technical optical metric."""
        p_res = self.engine.process_document("data/documents/doc-003_laboratory_report_2026-01-10.pdf")
        # Ensure result does not contain clinical fields or risk judgments
        res_json = p_res.model_dump_json().lower()
        self.assertNotIn("clinical_confidence", res_json)
        self.assertNotIn("risk_score", res_json)
        self.assertNotIn("diagnosis", res_json)

    def test_12_clean_pdf_extraction_remains_unchanged(self) -> None:
        """12. Verify clean PDF bypasses OCR and uses direct PyMuPDF extraction."""
        clean_pdf = Path("data/documents/doc-003_laboratory_report_2026-01-10.pdf")
        if not clean_pdf.is_file():
            self.skipTest("Clean PDF doc-003 not found.")

        res = self.engine.process_document(clean_pdf)
        self.assertEqual(res.classification, "TEXT_PDF")
        self.assertFalse(res.ocr_used)
        self.assertEqual(res.average_ocr_confidence, 1.0)
        self.assertIn("Hemoglobin", res.pages[0].text)


if __name__ == "__main__":
    unittest.main()
