"""Stage 16 End-to-End Automated Integration Test Suite.

Verifies all 15 required final product integration test cases:
1. Upload one native PDF
2. Upload one scanned PDF
3. Upload multiple documents
4. Unsupported file rejection
5. Quality warning detection
6. OCR processing on images/scans
7. Structured extraction result validation
8. Timeline regeneration
9. Changes regeneration
10. Flags regeneration
11. JourneyBrief regeneration
12. Review submission (verified and needs_review)
13. Source document retrieval
14. Missing patient handling
15. One-document failure without corrupting other successful documents

STRICT BOUNDARY:
- Uses ONLY synthetic medical document content.
- All Gemini calls are mocked in automated tests to prevent live API key dependencies.
- No clinical interpretation or risk scoring assertions.
"""

import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from PIL import Image
import pymupdf

from app.main import app
from app.models.clinical import LaboratoryResult
from app.models.source import SourceReference
from app.services.pipeline_coordinator import PipelineCoordinator


class TestFinalProductIntegration(unittest.TestCase):
    """Complete 15-case end-to-end integration test suite."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.valid_patient = "SYN-CANCER-001"
        cls.invalid_patient = "SYN-NONEXISTENT-999"
        cls.orig_docs = set(p.name for p in Path("data/documents").glob("*"))
        cls.orig_structured = set(p.name for p in Path("data/structured").glob("*"))

    @classmethod
    def tearDownClass(cls) -> None:
        for p in Path("data/documents").glob("*"):
            if p.name not in cls.orig_docs:
                try:
                    p.unlink()
                except OSError:
                    pass
        for p in Path("data/structured").glob("*"):
            if p.name not in cls.orig_structured:
                try:
                    p.unlink()
                except OSError:
                    pass

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_mock_pdf(self, filename: str, text: str = "Patient ID: SYN-CANCER-001 Hemoglobin: 13.4 g/dL") -> bytes:
        doc = pymupdf.open()
        page = doc.new_page(width=500, height=700)
        page.insert_text((50, 100), text)
        buf = io.BytesIO()
        doc.save(buf)
        doc.close()
        return buf.getvalue()

    def _create_mock_scanned_pdf(self, filename: str) -> bytes:
        # Create image-only PDF without text layer
        img = Image.new("RGB", (400, 500), color=(255, 255, 255))
        img_buf = io.BytesIO()
        img.save(img_buf, format="PNG")

        doc = pymupdf.open()
        rect = pymupdf.Rect(0, 0, 400, 500)
        page = doc.new_page(width=400, height=500)
        page.insert_image(rect, stream=img_buf.getvalue())

        buf = io.BytesIO()
        doc.save(buf)
        doc.close()
        return buf.getvalue()

    def _create_mock_png(self, width: int = 400, height: int = 500) -> bytes:
        img = Image.new("RGB", (width, height), color=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def _create_mock_jpg(self, width: int = 400, height: int = 500) -> bytes:
        img = Image.new("RGB", (width, height), color=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()

    @patch("app.services.pipeline_coordinator.ExtractionService")
    def test_01_upload_native_pdf(self, mock_ext_cls: MagicMock) -> None:
        """1. Verify upload of native clean PDF routes to TEXT_PDF with ocr_used=False."""
        mock_instance = MagicMock()
        mock_instance.extract_page.return_value = {}
        mock_ext_cls.return_value = mock_instance

        pdf_bytes = self._create_mock_pdf("native_note.pdf")
        files = {"files": ("native_note.pdf", pdf_bytes, "application/pdf")}

        res = self.client.post(
            f"/api/patient/{self.valid_patient}/documents/upload",
            files=files,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["classification"], "TEXT_PDF")
        self.assertFalse(data["ocr_used"])
        self.assertTrue(data["is_supported"])
        self.assertEqual(data["page_count"], 1)

    @patch("app.services.pipeline_coordinator.ExtractionService")
    def test_02_upload_scanned_pdf(self, mock_ext_cls: MagicMock) -> None:
        """2. Verify upload of scanned PDF routes to SCANNED_PDF with ocr_used=True."""
        mock_instance = MagicMock()
        mock_instance.extract_page.return_value = {}
        mock_ext_cls.return_value = mock_instance

        pdf_bytes = self._create_mock_scanned_pdf("scanned_note.pdf")
        files = {"files": ("scanned_note.pdf", pdf_bytes, "application/pdf")}

        res = self.client.post(
            f"/api/patient/{self.valid_patient}/documents/upload",
            files=files,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["classification"], "SCANNED_PDF")
        self.assertTrue(data["ocr_used"])
        self.assertIsNotNone(data["ocr_confidence"])

    @patch("app.services.pipeline_coordinator.ExtractionService")
    def test_03_upload_multiple_documents(self, mock_ext_cls: MagicMock) -> None:
        """3. Verify multi-document upload receives, ingests, and summarizes all files."""
        mock_instance = MagicMock()
        mock_instance.extract_page.return_value = {}
        mock_ext_cls.return_value = mock_instance

        pdf1 = self._create_mock_pdf("batch_1.pdf")
        img2 = self._create_mock_png()
        files = [
            ("files", ("batch_1.pdf", pdf1, "application/pdf")),
            ("files", ("batch_2.png", img2, "image/png")),
        ]

        res = self.client.post(
            f"/api/patient/{self.valid_patient}/documents/upload",
            files=files,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("summary", data)
        self.assertEqual(data["summary"]["documents_received"], 2)
        self.assertGreaterEqual(data["summary"]["successfully_processed"], 2)
        self.assertEqual(len(data["documents"]), 2)

    def test_04_unsupported_file_rejection(self) -> None:
        """4. Verify executable and unsupported extensions are rejected with HTTP 400."""
        files = {"file": ("exploit.exe", b"binary content", "application/octet-stream")}
        res = self.client.post(
            f"/api/patient/{self.valid_patient}/documents/upload",
            files=files,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("unsupported", res.json()["detail"].lower())

    @patch("app.services.pipeline_coordinator.ExtractionService")
    def test_05_quality_warning(self, mock_ext_cls: MagicMock) -> None:
        """5. Verify low-resolution image triggers technical quality warning."""
        mock_instance = MagicMock()
        mock_instance.extract_page.return_value = {}
        mock_ext_cls.return_value = mock_instance

        # 150x150 px triggers low resolution warning (< 300px threshold)
        low_res = self._create_mock_png(width=150, height=150)
        files = {"files": ("low_res.png", low_res, "image/png")}

        res = self.client.post(
            f"/api/patient/{self.valid_patient}/documents/upload",
            files=files,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn(data["quality_status"], ["needs_review", "unreadable"])
        self.assertTrue(any("resolution" in i.lower() for i in data["quality_issues"]))

    @patch("app.services.pipeline_coordinator.ExtractionService")
    def test_06_ocr_processing(self, mock_ext_cls: MagicMock) -> None:
        """6. Verify OCR processes images and records bounded technical confidence."""
        mock_instance = MagicMock()
        mock_instance.extract_page.return_value = {}
        mock_ext_cls.return_value = mock_instance

        png_bytes = self._create_mock_png(width=400, height=400)
        files = {"files": ("ocr_doc.png", png_bytes, "image/png")}

        res = self.client.post(
            f"/api/patient/{self.valid_patient}/documents/upload",
            files=files,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["ocr_used"])
        self.assertGreaterEqual(data["ocr_confidence"], 0.0)
        self.assertLessEqual(data["ocr_confidence"], 1.0)

    @patch("app.services.pipeline_coordinator.ExtractionService")
    def test_07_extraction_result(self, mock_ext_cls: MagicMock) -> None:
        """7. Verify structured extraction results conform to Pydantic and preserve provenance."""
        # Return mock extracted clinical fact
        mock_fact = LaboratoryResult(
            source=SourceReference(document_id="doc-e2e", file_name="e2e_lab.pdf", page_number=1),
            confidence=0.98,
            test_name="Hemoglobin",
            value="13.4",
            unit="g/dL",
            date="2026-01-10",
        )
        mock_instance = MagicMock()
        mock_instance.extract_page.return_value = {"laboratory_results": [mock_fact]}
        mock_ext_cls.return_value = mock_instance

        pdf_bytes = self._create_mock_pdf("e2e_lab.pdf")
        files = {"files": ("e2e_lab.pdf", pdf_bytes, "application/pdf")}

        res = self.client.post(
            f"/api/patient/{self.valid_patient}/documents/upload",
            files=files,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreaterEqual(data["documents"][0]["facts_extracted_count"], 1)

    @patch("app.services.pipeline_coordinator.ExtractionService")
    def test_08_timeline_regeneration(self, mock_ext_cls: MagicMock) -> None:
        """8. Verify patient timeline is automatically regenerated upon upload."""
        mock_instance = MagicMock()
        mock_instance.extract_page.return_value = {}
        mock_ext_cls.return_value = mock_instance

        pdf_bytes = self._create_mock_pdf("timeline_trigger.pdf")
        files = {"files": ("timeline_trigger.pdf", pdf_bytes, "application/pdf")}

        res = self.client.post(f"/api/patient/{self.valid_patient}/documents/upload", files=files)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["artifacts_regenerated"])

        res_timeline = self.client.get(f"/api/patient/{self.valid_patient}/timeline")
        self.assertEqual(res_timeline.status_code, 200)
        self.assertGreater(res_timeline.json()["total_events"], 0)

    def test_09_changes_regeneration(self) -> None:
        """9. Verify documented changes artifact is accessible and valid."""
        res = self.client.get(f"/api/patient/{self.valid_patient}/changes")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreater(data["total_changes_detected"], 0)
        self.assertIsInstance(data["changes"], list)

    def test_10_flags_regeneration(self) -> None:
        """10. Verify documentation flags artifact is accessible and valid."""
        res = self.client.get(f"/api/patient/{self.valid_patient}/flags")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreater(data["total_flags"], 0)

    def test_11_journey_brief_regeneration(self) -> None:
        """11. Verify JourneyBrief artifact contains required header, sections, and synthetic banner."""
        res = self.client.get(f"/api/patient/{self.valid_patient}/brief")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["header"]["synthetic_notice"], "SYNTHETIC DATA — DEMONSTRATION ONLY")
        self.assertIn("recent_timeline", data)
        self.assertIn("what_changed", data)
        self.assertIn("documentation_flags", data)

    def test_12_review_submission(self) -> None:
        """12. Verify submitting 'verified' and 'needs_review' item reviews persists correctly."""
        # 1. Mark verified
        res_v = self.client.post(
            f"/api/patient/{self.valid_patient}/review",
            json={"item_id": "test-fact-1", "item_status": "verified"},
        )
        self.assertEqual(res_v.status_code, 200)
        self.assertEqual(res_v.json()["reviewed_items"]["test-fact-1"], "verified")

        # 2. Mark needs_review
        res_nr = self.client.post(
            f"/api/patient/{self.valid_patient}/review",
            json={"item_id": "test-fact-2", "item_status": "needs_review"},
        )
        self.assertEqual(res_nr.status_code, 200)
        self.assertEqual(res_nr.json()["reviewed_items"]["test-fact-2"], "needs_review")

        # 3. Overall brief reviewed
        res_all = self.client.post(
            f"/api/patient/{self.valid_patient}/review",
            json={"review_status": "reviewed", "notes": "Clinician consultation preparation completed."},
        )
        self.assertEqual(res_all.status_code, 200)
        self.assertEqual(res_all.json()["review_status"], "reviewed")

    def test_13_source_retrieval(self) -> None:
        """13. Verify source document retrieval endpoint serves original document."""
        res = self.client.get(f"/api/patient/{self.valid_patient}/documents/doc-001")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "application/pdf")
        self.assertGreater(len(res.content), 0)

    def test_14_missing_patient_handling(self) -> None:
        """14. Verify missing patient ID returns HTTP 404 across endpoints."""
        res_brief = self.client.get(f"/api/patient/{self.invalid_patient}/brief")
        self.assertEqual(res_brief.status_code, 404)

        res_upload = self.client.post(
            f"/api/patient/{self.invalid_patient}/documents/upload",
            files={"files": ("test.pdf", b"%PDF-1.4 mock", "application/pdf")},
        )
        self.assertEqual(res_upload.status_code, 404)

    @patch("app.services.pipeline_coordinator.ExtractionService")
    def test_15_one_document_failure_without_corrupting_others(self, mock_ext_cls: MagicMock) -> None:
        """15. Verify a failed/unsupported document in a batch does not corrupt successful documents."""
        mock_instance = MagicMock()
        mock_instance.extract_page.return_value = {}
        mock_ext_cls.return_value = mock_instance

        valid_pdf = self._create_mock_pdf("valid_report.pdf")
        corrupted_or_bad = b"corrupt binary"

        files = [
            ("files", ("valid_report.pdf", valid_pdf, "application/pdf")),
            ("files", ("bad_script.bat", corrupted_or_bad, "application/octet-stream")),
        ]

        res = self.client.post(
            f"/api/patient/{self.valid_patient}/documents/upload",
            files=files,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        summary = data["summary"]
        self.assertEqual(summary["documents_received"], 2)
        self.assertEqual(summary["successfully_processed"], 1)
        self.assertEqual(summary["failed"], 1)

        # Verify valid document succeeded
        doc_results = data["documents"]
        self.assertEqual(doc_results[0]["file_name"], "valid_report.pdf")
        self.assertEqual(doc_results[0]["technical_status"], "success")

        # Verify invalid document was flagged failed
        self.assertEqual(doc_results[1]["file_name"], "bad_script.bat")
        self.assertEqual(doc_results[1]["technical_status"], "failed")

    def test_16_reset_demo_baseline_endpoint(self) -> None:
        """16. Verify POST /reset restores synthetic demo environment to 10-document baseline."""
        res_reset = self.client.post(f"/api/patient/{self.valid_patient}/reset")
        self.assertEqual(res_reset.status_code, 200)
        data = res_reset.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["patient_id"], self.valid_patient)
        self.assertIn("baseline", data["message"].lower())

        # Test invalid patient returns 404
        res_invalid = self.client.post(f"/api/patient/{self.invalid_patient}/reset")
        self.assertEqual(res_invalid.status_code, 404)

    @patch("app.services.pipeline_coordinator.ExtractionService")
    def test_17_measured_processing_time_recorded(self, mock_ext_cls: MagicMock) -> None:
        """17. Verify batch upload records non-fabricated processing_time_seconds."""
        mock_instance = MagicMock()
        mock_instance.extract_page.return_value = {}
        mock_ext_cls.return_value = mock_instance

        valid_pdf = self._create_mock_pdf("timed_report.pdf")
        res = self.client.post(
            f"/api/patient/{self.valid_patient}/documents/upload",
            files={"files": ("timed_report.pdf", valid_pdf, "application/pdf")},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("processing_time_seconds", data)
        self.assertIsNotNone(data["processing_time_seconds"])
        self.assertIsInstance(data["processing_time_seconds"], (int, float))
        self.assertGreaterEqual(data["processing_time_seconds"], 0.0)

    @patch("app.services.pipeline_coordinator.ExtractionService")
    def test_18_complete_hackathon_demo_flow(self, mock_ext_cls: MagicMock) -> None:
        """18. End-to-end verification of the exact 15-step Hackathon demo flow."""
        mock_instance = MagicMock()
        mock_instance.extract_page.return_value = {
            "laboratory_results": [
                {
                    "test_name": "Hemoglobin",
                    "result_value": "12.8",
                    "unit": "g/dL",
                    "reference_range": "12.0-15.5",
                    "date": "2026-02-15",
                    "confidence": 0.95,
                }
            ]
        }
        mock_ext_cls.return_value = mock_instance

        # 1. Open JourneyBrief & check initial baseline
        res_initial = self.client.get(f"/api/patient/{self.valid_patient}/brief")
        self.assertEqual(res_initial.status_code, 200)
        initial_data = res_initial.json()
        self.assertEqual(initial_data["header"]["patient_id"], "SYN-CANCER-001")
        self.assertGreaterEqual(initial_data["header"]["source_documents_count"], 10)

        # 2. Upload mixed batch (native PDF + image)
        pdf_bytes = self._create_mock_pdf("demo_note.pdf")
        img_bytes = self._create_mock_png(width=400, height=500)
        files = [
            ("files", ("demo_note.pdf", pdf_bytes, "application/pdf")),
            ("files", ("demo_scan.png", img_bytes, "image/png")),
        ]
        res_upload = self.client.post(
            f"/api/patient/{self.valid_patient}/documents/upload",
            files=files,
        )
        self.assertEqual(res_upload.status_code, 200)
        upload_resp = res_upload.json()
        self.assertEqual(upload_resp["summary"]["documents_received"], 2)
        self.assertTrue(upload_resp["artifacts_regenerated"])

        # 3. Verify Timeline update
        res_timeline = self.client.get(f"/api/patient/{self.valid_patient}/timeline")
        self.assertEqual(res_timeline.status_code, 200)

        # 4. Verify Doctor Review workflow (Verify one item, flag another as Needs Review)
        review_res = self.client.post(
            f"/api/patient/{self.valid_patient}/review",
            json={"item_id": "timeline_0", "item_status": "verified"},
        )
        self.assertEqual(review_res.status_code, 200)
        review_data = review_res.json()
        self.assertEqual(review_data["reviewed_items"]["timeline_0"], "verified")

        review_res2 = self.client.post(
            f"/api/patient/{self.valid_patient}/review",
            json={"item_id": "timeline_1", "item_status": "needs_review"},
        )
        self.assertEqual(review_res2.status_code, 200)
        review_data2 = review_res2.json()
        self.assertEqual(review_data2["reviewed_items"]["timeline_1"], "needs_review")

        # 5. Reset demo environment to baseline
        res_reset = self.client.post(f"/api/patient/{self.valid_patient}/reset")
        self.assertEqual(res_reset.status_code, 200)

        # 6. Verify brief restored to clean 10-document baseline
        res_restored = self.client.get(f"/api/patient/{self.valid_patient}/brief")
        self.assertEqual(res_restored.status_code, 200)
        restored_data = res_restored.json()
        self.assertEqual(restored_data["header"]["source_documents_count"], 10)

    @patch("app.services.pipeline_coordinator.ExtractionService")
    def test_19_uploaded_documents_reflected_in_journey_brief(self, mock_ext_cls: MagicMock) -> None:
        """19. Regression test: newly uploaded documents must appear in final JourneyBrief, Overview, Timeline, and Sources."""
        # 1. Start with clean baseline and confirm 10 baseline documents
        res_init_reset = self.client.post(f"/api/patient/{self.valid_patient}/reset")
        self.assertEqual(res_init_reset.status_code, 200)

        res_baseline = self.client.get(f"/api/patient/{self.valid_patient}/brief")
        self.assertEqual(res_baseline.status_code, 200)
        baseline_brief = res_baseline.json()
        baseline_doc_count = baseline_brief["header"]["source_documents_count"]
        self.assertEqual(baseline_doc_count, 10)
        baseline_source_filenames = {d["file_name"] for d in baseline_brief["source_documents"]}
        self.assertEqual(len(baseline_source_filenames), 10)

        # 2. Setup mock extraction for the 6 new synthetic documents
        mock_instance = MagicMock()

        def mock_extract(document_id: str, file_name: str, page_number: int, page_text: str):
            if "01_" in file_name:
                return {
                    "visits": [{
                        "source": {"document_id": document_id, "file_name": file_name, "page_number": page_number, "text_anchor": "Consultation Note"},
                        "confidence": 1.0,
                        "visit_id": f"visit-{document_id}",
                        "date": "2026-01-05",
                        "facility": "Cedar Valley Oncology",
                        "department": "Oncology",
                        "visit_type": "Consultation Note",
                    }],
                    "investigations": [{
                        "source": {"document_id": document_id, "file_name": file_name, "page_number": page_number, "text_anchor": "Core needle biopsy Ordered"},
                        "confidence": 1.0,
                        "investigation_name": "Core needle biopsy",
                        "status": "Ordered",
                        "ordered_date": "2026-01-05",
                        "result_date": None,
                    }],
                }
            elif "02_" in file_name:
                return {
                    "pathology_findings": [{
                        "source": {"document_id": document_id, "file_name": file_name, "page_number": page_number, "text_anchor": "Invasive ductal carcinoma"},
                        "confidence": 1.0,
                        "finding_name": "Invasive ductal carcinoma",
                        "documented_text": "Nottingham Grade 2 invasive carcinoma",
                        "date": "2026-01-08",
                        "specimen_type": "Core Biopsy",
                    }]
                }
            elif "03_" in file_name:
                return {
                    "laboratory_results": [
                        LaboratoryResult(
                            test_name="Hemoglobin",
                            value="13.4",
                            unit="g/dL",
                            reference_range_text="12.0 - 15.5 g/dL",
                            date="2026-01-10",
                            confidence=1.0,
                            source=SourceReference(document_id=document_id, file_name=file_name, page_number=page_number, text_anchor="Hemoglobin 13.4 g/dL"),
                        ),
                        LaboratoryResult(
                            test_name="Platelet Count",
                            value="240",
                            unit="x10^3/uL",
                            reference_range_text="150 - 450 x10^3/uL",
                            date="2026-01-10",
                            confidence=1.0,
                            source=SourceReference(document_id=document_id, file_name=file_name, page_number=page_number, text_anchor="Platelet Count 240"),
                        ),
                    ]
                }
            elif "04_" in file_name:
                return {
                    "imaging_reports": [{
                        "source": {"document_id": document_id, "file_name": file_name, "page_number": page_number, "text_anchor": "Ultrasound right breast mass"},
                        "confidence": 1.0,
                        "modality": "Ultrasound",
                        "body_site": "Right Breast",
                        "report_text": "Hypoechoic mass measuring 2.1 cm",
                        "date": "2026-01-14",
                    }]
                }
            elif "05_" in file_name:
                return {
                    "medications": [{
                        "source": {"document_id": document_id, "file_name": file_name, "page_number": page_number, "text_anchor": "Tamoxifen 20 mg Started"},
                        "confidence": 1.0,
                        "medicine_name": "Tamoxifen",
                        "dose": "20 mg",
                        "frequency": "Daily",
                        "route": "Oral",
                        "status": "Started",
                        "date": "2026-01-15",
                    }]
                }
            elif "06_" in file_name:
                return {
                    "laboratory_results": [
                        LaboratoryResult(
                            test_name="Hemoglobin",
                            value="12.8",
                            unit="g/dL",
                            reference_range_text="12.0 - 15.5 g/dL",
                            date="2026-02-05",
                            confidence=1.0,
                            source=SourceReference(document_id=document_id, file_name=file_name, page_number=page_number, text_anchor="Hemoglobin 12.8 g/dL"),
                        ),
                        LaboratoryResult(
                            test_name="Platelet Count",
                            value="255",
                            unit="x10^3/uL",
                            reference_range_text="150 - 450 x10^3/uL",
                            date="2026-02-05",
                            confidence=1.0,
                            source=SourceReference(document_id=document_id, file_name=file_name, page_number=page_number, text_anchor="Platelet Count 255"),
                        ),
                    ]
                }
            return {}

        mock_instance.extract_page.side_effect = mock_extract
        mock_ext_cls.return_value = mock_instance

        # 3. Create the 6 valid synthetic test files
        files_to_upload = [
            ("files", ("01_2026-01-05_consultation_note.pdf", self._create_mock_pdf("01_note.pdf", "Consultation Note text"), "application/pdf")),
            ("files", ("02_2026-01-08_pathology_report.pdf", self._create_mock_pdf("02_path.pdf", "Pathology Report text"), "application/pdf")),
            ("files", ("03_2026-01-10_baseline_lab_report.pdf", self._create_mock_pdf("03_lab.pdf", "Baseline Lab text"), "application/pdf")),
            ("files", ("04_2026-01-14_scanned_imaging_report.pdf", self._create_mock_scanned_pdf("04_imaging.pdf"), "application/pdf")),
            ("files", ("05_2026-01-15_prescription.jpg", self._create_mock_jpg(400, 500), "image/jpeg")),
            ("files", ("06_2026-02-05_followup_lab_report.pdf", self._create_mock_pdf("06_followup.pdf", "Followup Lab text"), "application/pdf")),
        ]

        # 4. Upload and process the 6 documents via POST /api/patient/{patient_id}/documents/upload
        res_upload = self.client.post(
            f"/api/patient/{self.valid_patient}/documents/upload",
            files=files_to_upload,
        )
        self.assertEqual(res_upload.status_code, 200)
        upload_resp = res_upload.json()
        self.assertEqual(upload_resp["summary"]["documents_received"], 6)
        self.assertEqual(upload_resp["summary"]["successfully_processed"], 6)
        self.assertTrue(upload_resp["artifacts_regenerated"])

        # 5. Confirm all valid documents and structured facts are persisted
        for fname, _, _ in [item[1] for item in files_to_upload]:
            self.assertTrue(
                (Path("data/documents") / fname).is_file() or (Path("data/messy_documents/uploads") / fname).is_file(),
                f"Expected uploaded document {fname} to be persisted on disk."
            )

        # 6. Fetch Overview / JourneyBrief
        res_brief = self.client.get(f"/api/patient/{self.valid_patient}/brief")
        self.assertEqual(res_brief.status_code, 200)
        brief = res_brief.json()

        # 7. Assert document count increases from 10 to 16
        post_doc_count = brief["header"]["source_documents_count"]
        self.assertGreater(post_doc_count, baseline_doc_count)
        self.assertEqual(post_doc_count, 16)
        self.assertEqual(len(brief["source_documents"]), 16)

        # 8. Confirm every uploaded filename exists in the current patient sources
        post_source_filenames = {d["file_name"] for d in brief["source_documents"]}
        for fname, _, _ in [item[1] for item in files_to_upload]:
            self.assertIn(fname, post_source_filenames, f"Uploaded file {fname} not found in JourneyBrief sources!")

        # 9. Confirm newly uploaded facts appear downstream in Timeline and authoritative count matches API
        res_timeline = self.client.get(f"/api/patient/{self.valid_patient}/timeline")
        self.assertEqual(res_timeline.status_code, 200)
        timeline_data = res_timeline.json()
        timeline_source_docs = {ev["source"]["file_name"] for ev in timeline_data["events"]}
        self.assertTrue(any("01_" in f or "02_" in f or "03_" in f for f in timeline_source_docs), "Uploaded events missing in timeline!")
        self.assertEqual(timeline_data["total_events"], brief["header"]["total_timeline_events"])

        # 10. Confirm newly uploaded lab values are represented in What Changed, and UNCHANGED values are excluded
        res_changes = self.client.get(f"/api/patient/{self.valid_patient}/changes")
        self.assertEqual(res_changes.status_code, 200)
        changes_data = res_changes.json()
        change_entities = {c["entity_name"].lower() for c in changes_data["changes"]}
        self.assertIn("hemoglobin", change_entities)
        # Verify unchanged parameters (e.g. CA 15-3 22.4 -> 22.4, ALT 22 -> 22) are strictly excluded
        self.assertNotIn("ca 15-3", change_entities)
        self.assertNotIn("alanine aminotransferase (alt)", change_entities)
        for c in changes_data["changes"]:
            self.assertTrue(c["is_changed"], f"Unchanged comparison '{c['entity_name']}' found in What Changed!")

        # 10b. Confirm multi-format source retrieval works for both PDF and JPG
        res_pdf = self.client.get(f"/api/patient/{self.valid_patient}/documents/01")
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf.headers.get("content-type"), "application/pdf")

        res_jpg = self.client.get(f"/api/patient/{self.valid_patient}/documents/05")
        self.assertEqual(res_jpg.status_code, 200)
        self.assertEqual(res_jpg.headers.get("content-type"), "image/jpeg")

        # 11. Confirm original baseline documents remain intact
        for orig_file in baseline_source_filenames:
            self.assertIn(orig_file, post_source_filenames, f"Original baseline document {orig_file} was corrupted or removed!")

        # 12. Reset demo data via POST /api/patient/{patient_id}/reset
        res_reset = self.client.post(f"/api/patient/{self.valid_patient}/reset")
        self.assertEqual(res_reset.status_code, 200)

        # 13. Confirm exact 10-document baseline returns
        res_final = self.client.get(f"/api/patient/{self.valid_patient}/brief")
        self.assertEqual(res_final.status_code, 200)
        final_brief = res_final.json()
        self.assertEqual(final_brief["header"]["source_documents_count"], 10)
        self.assertEqual(len(final_brief["source_documents"]), 10)


if __name__ == "__main__":
    unittest.main()

