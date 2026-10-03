"""Unit tests for DocumentIngestionService.

Verifies:
1. Clean PDF with selectable text is classified as TEXT_PDF.
2. Scanned raster-only PDF is classified as SCANNED_PDF.
3. PNG / JPG image files are classified as IMAGE.
4. Unsupported and executable files are rejected as UNSUPPORTED.
5. Accurate page counts are calculated for PDFs and images.
"""

from pathlib import Path
import tempfile
import unittest
from PIL import Image
import pymupdf

from app.services.document_ingestion import DocumentClassification, DocumentIngestionService


class TestDocumentIngestionService(unittest.TestCase):
    """Test suite for document ingestion and technical file classification."""

    def setUp(self) -> None:
        self.service = DocumentIngestionService()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_01_clean_pdf_classified_as_text_pdf(self) -> None:
        """1. Verify clean PDF with selectable text is classified as TEXT_PDF."""
        clean_pdf_path = Path("data/documents/doc-001_visit_note_2026-01-05.pdf")
        if not clean_pdf_path.is_file():
            self.skipTest("Clean PDF doc-001 not found.")

        result = self.service.ingest(clean_pdf_path)
        self.assertEqual(result.classification, DocumentClassification.TEXT_PDF)
        self.assertTrue(result.has_selectable_text)
        self.assertTrue(result.is_supported)
        self.assertEqual(result.page_count, 2)
        self.assertEqual(result.document_id, "doc-001")

    def test_02_scanned_pdf_classified_as_scanned_pdf(self) -> None:
        """2. Verify raster-only PDF without text layer is classified as SCANNED_PDF."""
        scanned_pdf_path = Path("data/messy_documents/messy_scanned_lab_report.pdf")
        if not scanned_pdf_path.is_file():
            # Create a mock raster PDF if file not present
            scanned_pdf_path = self.work_dir / "mock_scanned.pdf"
            doc = pymupdf.open()
            page = doc.new_page(width=300, height=300)
            # Solid white pixmap inserted as image without text
            img = Image.new("RGB", (300, 300), color=(255, 255, 255))
            temp_img = self.work_dir / "temp.png"
            img.save(temp_img)
            page.insert_image(page.rect, filename=str(temp_img))
            doc.save(str(scanned_pdf_path))
            doc.close()

        result = self.service.ingest(scanned_pdf_path)
        self.assertEqual(result.classification, DocumentClassification.SCANNED_PDF)
        self.assertFalse(result.has_selectable_text)
        self.assertTrue(result.is_supported)

    def test_03_image_classified_as_image(self) -> None:
        """3. Verify PNG and JPG files are classified as IMAGE with page_count = 1."""
        # Create test PNG
        png_path = self.work_dir / "test_doc.png"
        img = Image.new("RGB", (200, 200), color=(255, 255, 255))
        img.save(png_path)

        res_png = self.service.ingest(png_path)
        self.assertEqual(res_png.classification, DocumentClassification.IMAGE)
        self.assertEqual(res_png.page_count, 1)
        self.assertFalse(res_png.has_selectable_text)
        self.assertTrue(res_png.is_supported)

        # Create test JPEG
        jpg_path = self.work_dir / "test_doc.jpg"
        img.save(jpg_path, "JPEG")

        res_jpg = self.service.ingest(jpg_path)
        self.assertEqual(res_jpg.classification, DocumentClassification.IMAGE)
        self.assertEqual(res_jpg.page_count, 1)
        self.assertTrue(res_jpg.is_supported)

    def test_04_unsupported_file_rejected(self) -> None:
        """4. Verify executable and unsupported files are flagged as UNSUPPORTED."""
        exe_path = self.work_dir / "malicious_script.exe"
        exe_path.write_bytes(b"MZ\x90\x00executable content")

        result = self.service.ingest(exe_path)
        self.assertEqual(result.classification, DocumentClassification.UNSUPPORTED)
        self.assertFalse(result.is_supported)
        self.assertIn("unsupported", result.details.get("reason", "").lower())

        py_path = self.work_dir / "script.py"
        py_path.write_text("print('hello')", encoding="utf-8")

        result_py = self.service.ingest(py_path)
        self.assertEqual(result_py.classification, DocumentClassification.UNSUPPORTED)
        self.assertFalse(result_py.is_supported)

    def test_05_page_count_works(self) -> None:
        """5. Verify multi-page and single-page count determination."""
        doc = pymupdf.open()
        doc.new_page(width=200, height=200)
        doc.new_page(width=200, height=200)
        doc.new_page(width=200, height=200)
        three_page_pdf = self.work_dir / "three_pages.pdf"
        doc.save(str(three_page_pdf))
        doc.close()

        res = self.service.ingest(three_page_pdf)
        self.assertEqual(res.page_count, 3)


if __name__ == "__main__":
    unittest.main()
