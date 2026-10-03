"""Integration tests for FastAPI patient consultation readiness endpoints.

Verifies:
9. API endpoint responses (brief, timeline, changes, flags, documents, review GET/POST).
10. Missing patient and missing document handling (returns HTTP 404).
"""

import unittest
from fastapi.testclient import TestClient

from app.main import app


class TestPatientEndpoints(unittest.TestCase):
    """Test suite for FastAPI endpoints."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.valid_patient = "SYN-CANCER-001"
        cls.invalid_patient = "PATIENT-NONEXISTENT-999"

    @classmethod
    def tearDownClass(cls) -> None:
        from pathlib import Path
        for p in [Path("data/documents/test_upload.png"), Path("data/structured/test_upload.json")]:
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass

    def test_09a_health_endpoint(self) -> None:
        """Verify GET /health returns 200 OK and healthy status."""
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ok")

    def test_09b_get_brief_endpoint(self) -> None:
        """Verify GET /api/patient/{patient_id}/brief returns 200 and valid schema."""
        res = self.client.get(f"/api/patient/{self.valid_patient}/brief")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["header"]["patient_id"], "SYN-CANCER-001")
        self.assertEqual(
            data["header"]["synthetic_notice"],
            "SYNTHETIC DATA — DEMONSTRATION ONLY",
        )
        self.assertGreaterEqual(data["header"]["source_documents_count"], 10)
        self.assertIn("recent_timeline", data)
        self.assertIn("what_changed", data)
        self.assertIn("documentation_flags", data)
        self.assertIn("medications", data)
        self.assertIn("investigations", data)
        self.assertIn("source_documents", data)

    def test_09c_get_timeline_endpoint(self) -> None:
        """Verify GET /api/patient/{patient_id}/timeline returns 200."""
        res = self.client.get(f"/api/patient/{self.valid_patient}/timeline")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["patient_id"], "SYN-CANCER-001")
        self.assertGreater(data["total_events"], 0)
        self.assertIsInstance(data["events"], list)

    def test_09d_get_changes_endpoint(self) -> None:
        """Verify GET /api/patient/{patient_id}/changes returns 200."""
        res = self.client.get(f"/api/patient/{self.valid_patient}/changes")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["patient_id"], "SYN-CANCER-001")
        self.assertGreater(data["total_changes_detected"], 0)
        self.assertIsInstance(data["changes"], list)

    def test_09e_get_flags_endpoint(self) -> None:
        """Verify GET /api/patient/{patient_id}/flags returns 200."""
        res = self.client.get(f"/api/patient/{self.valid_patient}/flags")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["patient_id"], "SYN-CANCER-001")
        self.assertGreater(data["total_flags"], 0)
        self.assertIsInstance(data["flags"], list)

    def test_09f_get_document_pdf_endpoint(self) -> None:
        """Verify GET /api/patient/{patient_id}/documents/{document_id} returns PDF."""
        res = self.client.get(f"/api/patient/{self.valid_patient}/documents/doc-001")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "application/pdf")
        self.assertGreater(len(res.content), 0)

        # Check with page query param
        res_page = self.client.get(f"/api/patient/{self.valid_patient}/documents/doc-003?page=1")
        self.assertEqual(res_page.status_code, 200)
        self.assertEqual(res_page.headers["X-Page-Number"], "1")

    def test_09g_get_and_post_review_endpoint(self) -> None:
        """Verify GET and POST /api/patient/{patient_id}/review."""
        # Initial GET
        res_get = self.client.get(f"/api/patient/{self.valid_patient}/review")
        self.assertEqual(res_get.status_code, 200)
        data_get = res_get.json()
        self.assertEqual(data_get["patient_id"], "SYN-CANCER-001")

        # POST update item
        payload = {
            "reviewer_id": "dr_test",
            "item_id": "timeline-item-test",
            "item_status": "verified",
            "review_status": "pending",
        }
        res_post = self.client.post(
            f"/api/patient/{self.valid_patient}/review",
            json=payload,
        )
        self.assertEqual(res_post.status_code, 200)
        data_post = res_post.json()
        self.assertEqual(data_post["reviewed_items"]["timeline-item-test"], "verified")
        self.assertEqual(data_post["reviewer_id"], "dr_test")

    def test_09h_root_ui_endpoint(self) -> None:
        """Verify GET / serves frontend HTML with safety notices."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers["content-type"])
        self.assertIn("MedChronicle", res.text)
        self.assertIn("SYNTHETIC DATA — DEMONSTRATION ONLY", res.text)
        self.assertIn("clinician review required", res.text.lower())

    def test_10a_missing_patient_brief(self) -> None:
        """10. Verify missing patient ID returns 404 for /brief."""
        res = self.client.get(f"/api/patient/{self.invalid_patient}/brief")
        self.assertEqual(res.status_code, 404)
        self.assertIn("not found", res.json()["detail"].lower())

    def test_10b_missing_patient_timeline(self) -> None:
        """10. Verify missing patient ID returns 404 for /timeline."""
        res = self.client.get(f"/api/patient/{self.invalid_patient}/timeline")
        self.assertEqual(res.status_code, 404)

    def test_10c_missing_patient_changes(self) -> None:
        """10. Verify missing patient ID returns 404 for /changes."""
        res = self.client.get(f"/api/patient/{self.invalid_patient}/changes")
        self.assertEqual(res.status_code, 404)

    def test_10d_missing_patient_flags(self) -> None:
        """10. Verify missing patient ID returns 404 for /flags."""
        res = self.client.get(f"/api/patient/{self.invalid_patient}/flags")
        self.assertEqual(res.status_code, 404)

    def test_10e_missing_document(self) -> None:
        """10. Verify requesting nonexistent document returns 404."""
        res = self.client.get(f"/api/patient/{self.valid_patient}/documents/doc-999")
        self.assertEqual(res.status_code, 404)
        self.assertIn("not found", res.json()["detail"].lower())

    def test_11a_upload_supported_document(self) -> None:
        """Verify POST /upload accepts supported image file and returns technical metrics."""
        import io
        from PIL import Image

        buf = io.BytesIO()
        img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        files = {"file": ("test_upload.png", png_bytes, "image/png")}
        res = self.client.post(
            f"/api/patient/{self.valid_patient}/documents/upload",
            files=files,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["file_name"], "test_upload.png")
        self.assertEqual(data["classification"], "IMAGE")
        self.assertTrue(data["is_supported"])
        self.assertEqual(data["page_count"], 1)
        self.assertTrue(data["ocr_used"])
        self.assertIn("technical_status", data)

    def test_11b_upload_unsupported_document(self) -> None:
        """Verify POST /upload rejects executable and unsupported extensions with HTTP 400."""
        files = {"file": ("malicious.exe", b"fake binary", "application/octet-stream")}
        res = self.client.post(
            f"/api/patient/{self.valid_patient}/documents/upload",
            files=files,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("unsupported", res.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()

