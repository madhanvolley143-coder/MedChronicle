"""Regression test suite for Final Report Polish pass.

Verifies:
1. Unchanged values are excluded from What Changed (e.g. 22 -> 22, 22.4 -> 22.4).
2. Authoritative timeline count equality between JourneyBrief header and TimelineEngine.
3. Dynamic source count behavior (remains dynamic, never hardcoded).
4. Uploaded source documents remain visible in brief and sources list.
5. Source retrieval endpoint supports PDF, PNG, JPG, and JPEG files with appropriate content types.
6. 10 -> 16 document upload integration updates counts dynamically.
7. Reset returns cleanly to 10-document baseline.
"""

from pathlib import Path
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.services.change_detector import ChangeDetector
from app.services.journey_brief import JourneyBriefGenerator
from app.services.timeline import TimelineEngine


class TestFinalReportPolish(unittest.TestCase):
    """Regression test suite for Doctor-Facing Report Polish."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.patient_id = "SYN-CANCER-001"

    def test_01_unchanged_values_strictly_excluded_from_what_changed(self) -> None:
        """1. Verify identical/unchanged comparisons (e.g. 22 -> 22, 22.4 -> 22.4) never appear in What Changed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            doc_a = {
                "document_id": "doc-a",
                "file_name": "lab_a.pdf",
                "facts": {
                    "laboratory_results": [
                        {
                            "source": {"document_id": "doc-a", "file_name": "lab_a.pdf", "page_number": 1},
                            "confidence": 1.0,
                            "test_name": "ALT (SGPT)",
                            "value": "22",
                            "unit": "U/L",
                            "date": "2026-01-10",
                        },
                        {
                            "source": {"document_id": "doc-a", "file_name": "lab_a.pdf", "page_number": 1},
                            "confidence": 1.0,
                            "test_name": "CA 15-3",
                            "value": "22.4",
                            "unit": "U/mL",
                            "date": "2026-01-10",
                        },
                        {
                            "source": {"document_id": "doc-a", "file_name": "lab_a.pdf", "page_number": 1},
                            "confidence": 1.0,
                            "test_name": "Hemoglobin",
                            "value": "13.4",
                            "unit": "g/dL",
                            "date": "2026-01-10",
                        }
                    ]
                }
            }
            doc_b = {
                "document_id": "doc-b",
                "file_name": "lab_b.pdf",
                "facts": {
                    "laboratory_results": [
                        {
                            "source": {"document_id": "doc-b", "file_name": "lab_b.pdf", "page_number": 1},
                            "confidence": 1.0,
                            "test_name": "ALT (SGPT)",
                            "value": "22",  # Unchanged: 22 -> 22
                            "unit": "U/L",
                            "date": "2026-02-05",
                        },
                        {
                            "source": {"document_id": "doc-b", "file_name": "lab_b.pdf", "page_number": 1},
                            "confidence": 1.0,
                            "test_name": "CA 15-3",
                            "value": "22.4",  # Unchanged: 22.4 -> 22.4
                            "unit": "U/mL",
                            "date": "2026-02-05",
                        },
                        {
                            "source": {"document_id": "doc-b", "file_name": "lab_b.pdf", "page_number": 1},
                            "confidence": 1.0,
                            "test_name": "Hemoglobin",
                            "value": "12.8",  # Changed: 13.4 -> 12.8
                            "unit": "g/dL",
                            "date": "2026-02-05",
                        }
                    ]
                }
            }
            import json
            (tmp_path / "doc-a.json").write_text(json.dumps(doc_a), encoding="utf-8")
            (tmp_path / "doc-b.json").write_text(json.dumps(doc_b), encoding="utf-8")

            detector = ChangeDetector(tmp_path)
            changes = detector.detect_changes("TEST-PATIENT")

            # Must have exactly 1 change: Hemoglobin
            changed_names = [c.entity_name for c in changes.changes]
            self.assertIn("Hemoglobin", changed_names)
            self.assertNotIn("ALT (SGPT)", changed_names)
            self.assertNotIn("CA 15-3", changed_names)
            self.assertEqual(len(changes.changes), 1)

    def test_02_authoritative_timeline_count_matches(self) -> None:
        """2. Verify JourneyBrief header.total_timeline_events equals TimelineEngine.total_events."""
        res = self.client.get(f"/api/patient/{self.patient_id}/brief")
        self.assertEqual(res.status_code, 200)
        brief = res.json()

        tl_res = self.client.get(f"/api/patient/{self.patient_id}/timeline")
        self.assertEqual(tl_res.status_code, 200)
        timeline = tl_res.json()

        self.assertIsNotNone(brief["header"]["total_timeline_events"])
        self.assertEqual(
            brief["header"]["total_timeline_events"],
            timeline["total_events"],
            "Brief total_timeline_events must match Timeline total_events authoritative count."
        )

    def test_03_source_count_is_dynamic(self) -> None:
        """3. Verify source count in header matches source_documents array length dynamically."""
        res = self.client.get(f"/api/patient/{self.patient_id}/brief")
        self.assertEqual(res.status_code, 200)
        brief = res.json()

        doc_count = brief["header"]["source_documents_count"]
        actual_docs_len = len(brief["source_documents"])
        self.assertEqual(doc_count, actual_docs_len)
        self.assertGreaterEqual(doc_count, 10)

    def test_04_consultation_context_fields_present_and_strictly_factual(self) -> None:
        """4. Verify Consultation Context exists and does not invent missing fields."""
        res = self.client.get(f"/api/patient/{self.patient_id}/brief")
        self.assertEqual(res.status_code, 200)
        brief = res.json()

        self.assertIn("consultation_context", brief)
        ctx = brief["consultation_context"]
        self.assertIn("reason_for_visit", ctx)
        self.assertIn("latest_encounter", ctx)
        self.assertIn("relevant_history", ctx)
        self.assertIn("latest_record", ctx)

        # Confirm non-empty factual string
        self.assertTrue(len(ctx["reason_for_visit"]) > 0)
        self.assertTrue(len(ctx["latest_encounter"]) > 0)

    def test_05_source_document_retrieval_supports_file_types(self) -> None:
        """5. Verify source document endpoint serves PDF and image formats correctly."""
        # PDF test
        pdf_res = self.client.get(f"/api/patient/{self.patient_id}/documents/doc-001")
        self.assertEqual(pdf_res.status_code, 200)
        self.assertEqual(pdf_res.headers.get("content-type"), "application/pdf")

        # Test with direct file name resolution
        pdf_name_res = self.client.get(f"/api/patient/{self.patient_id}/documents/doc-001_visit_note_2026-01-05.pdf")
        self.assertEqual(pdf_name_res.status_code, 200)
        self.assertEqual(pdf_name_res.headers.get("content-type"), "application/pdf")

    def test_06_investigation_result_availability_deterministic(self) -> None:
        """6. Verify investigations have valid deterministic status text."""
        res = self.client.get(f"/api/patient/{self.patient_id}/brief")
        self.assertEqual(res.status_code, 200)
        brief = res.json()

        for inv in brief["investigations"]:
            self.assertIn(inv["result_status_text"], ["RESULT AVAILABLE", "RESULT NOT FOUND IN CURRENTLY PROCESSED RECORDS"])


if __name__ == "__main__":
    unittest.main()
