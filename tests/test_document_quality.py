"""Unit tests for DocumentQualityChecker.

Verifies:
1. Low resolution images are detected and flagged.
2. Blank or contrast-less pages are flagged.
3. Rotated PDF pages are detected.
4. Low text density or empty text is identified.
5. Strict safety boundary: quality issues strictly contain technical descriptions
   and never include clinical threat language (risk, diagnosis, severity, prognosis).
"""

from pathlib import Path
import tempfile
import unittest
from PIL import Image
import pymupdf

from app.services.document_quality import DocumentQualityChecker, QualityStatus


class TestDocumentQualityChecker(unittest.TestCase):
    """Test suite for technical document quality checking."""

    def setUp(self) -> None:
        self.checker = DocumentQualityChecker()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_01_low_resolution_image_detected(self) -> None:
        """1. Verify image below 300px threshold is flagged with needs_review."""
        low_res = self.work_dir / "low_res.png"
        img = Image.new("RGB", (200, 250), color=(200, 200, 200))
        img.save(low_res)

        report = self.checker.check_image_file(low_res)
        self.assertIn(report.status, [QualityStatus.NEEDS_REVIEW, QualityStatus.UNREADABLE])
        self.assertTrue(any("low image resolution" in i.lower() for i in report.issues))

    def test_02_blank_page_detected(self) -> None:
        """2. Verify solid color blank page is detected as blank."""
        blank_path = self.work_dir / "blank.png"
        img = Image.new("RGB", (400, 400), color=(255, 255, 255))
        img.save(blank_path)

        report = self.checker.check_image_file(blank_path)
        self.assertEqual(report.status, QualityStatus.UNREADABLE)
        self.assertTrue(any("blank" in i.lower() for i in report.issues))

    def test_03_rotated_pdf_detected(self) -> None:
        """3. Verify rotated PDF pages are identified in quality check."""
        rotated_pdf = self.work_dir / "rotated.pdf"
        doc = pymupdf.open()
        p = doc.new_page(width=400, height=600)
        p.set_rotation(90)
        doc.save(str(rotated_pdf))
        doc.close()

        report = self.checker.check_pdf(rotated_pdf)
        self.assertEqual(report.status, QualityStatus.NEEDS_REVIEW)
        self.assertTrue(any("rotated by 90" in i.lower() for i in report.issues))

    def test_04_empty_and_low_text_density(self) -> None:
        """4. Verify empty text is unreadable and low text density needs review."""
        rep_empty = self.checker.check_ocr_text("", ocr_confidence=0.0)
        self.assertEqual(rep_empty.status, QualityStatus.UNREADABLE)
        self.assertTrue(any("no readable text" in i.lower() for i in rep_empty.issues))

        rep_low = self.checker.check_ocr_text("Just five words.", ocr_confidence=0.85)
        self.assertEqual(rep_low.status, QualityStatus.NEEDS_REVIEW)
        self.assertTrue(any("low text density" in i.lower() for i in rep_low.issues))

    def test_05_strictly_no_clinical_risk_language_in_quality_issues(self) -> None:
        """5. Verify all quality issues use technical terms and avoid clinical threat phrases."""
        # Generate various reports
        rep1 = self.checker.check_ocr_text("", ocr_confidence=0.1)
        rep2 = self.checker.check_ocr_text("Brief test text", ocr_confidence=0.45)

        all_issues = rep1.issues + rep2.issues
        combined_text = " ".join(all_issues).lower()

        prohibited_clinical_terms = [
            "clinical risk",
            "patient risk",
            "diagnosis",
            "severity",
            "prognosis",
            "deterioration",
            "treatment failure",
            "unreliable patient",
        ]

        for term in prohibited_clinical_terms:
            self.assertNotIn(
                term,
                combined_text,
                f"Prohibited clinical term '{term}' found in technical quality issues.",
            )


if __name__ == "__main__":
    unittest.main()
