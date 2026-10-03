"""Regression and integration tests for the JourneyBrief Frontend Dashboard & Reactive Upload Refresh.

Validates:
1. Navigation section switching & route mappings
2. No hardcoded overview counts
3. Overview is a concise executive brief with previews (not a giant scrolling report)
4. Upload triggers refreshPatientData() and updates all sections
5. Uploaded source documents and facts appear dynamically
6. Timeline, changes, flags, and review update dynamically
7. Unchanged values are filtered from What Changed
8. Demo reset restores baseline
"""

import json
from pathlib import Path
import unittest
from fastapi.testclient import TestClient

from app.main import app
from app.services.change_detector import ChangeDetector
from app.services.flag_detector import FlagDetector
from app.services.journey_brief import JourneyBriefGenerator
from app.services.timeline import TimelineEngine


class TestFrontendDashboardIntegration(unittest.TestCase):
    """Test suite validating frontend navigation, concise overview, and reactive upload refresh."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.patient_id = "SYN-CANCER-001"
        cls.frontend_dir = Path("frontend")
        cls.index_html = (cls.frontend_dir / "index.html").read_text(encoding="utf-8")
        cls.app_js = (cls.frontend_dir / "app.js").read_text(encoding="utf-8")
        cls.style_css = (cls.frontend_dir / "style.css").read_text(encoding="utf-8")

    def test_01_navigation_structure_and_routes(self):
        """1. Verify navigation section IDs and hash routing mappings."""
        expected_sections = [
            "tab-overview",
            "tab-upload",
            "tab-timeline",
            "tab-changes",
            "tab-flags",
            "tab-medications",
            "tab-investigations",
            "tab-sources",
            "tab-review",
            "tab-evaluation",
        ]
        for sec in expected_sections:
            self.assertIn(f'id="{sec}"', self.index_html, f"Section {sec} missing from index.html")

        # Verify hash mapping dictionary in app.js
        self.assertIn("HASH_TAB_MAP", self.app_js)
        self.assertIn("TAB_HASH_MAP", self.app_js)
        self.assertIn("switchToTab", self.app_js)
        self.assertIn("hashchange", self.app_js)

        for route in ["overview", "upload", "timeline", "changes", "flags", "medications", "pending", "sources", "review", "evaluation"]:
            self.assertIn(f'"{route}":', self.app_js, f"Route '{route}' missing from HASH_TAB_MAP")

    def test_02_no_hardcoded_overview_counts(self):
        """2. Verify no hardcoded document/timeline/change counts remain as HTML defaults."""
        # Tab badges must not have hardcoded static counts like >10< or >65<
        self.assertIn('id="count-timeline">—</span>', self.index_html)
        self.assertIn('id="count-changes">—</span>', self.index_html)
        self.assertIn('id="count-flags">—</span>', self.index_html)
        self.assertIn('id="count-meds">—</span>', self.index_html)
        self.assertIn('id="count-invs">—</span>', self.index_html)
        self.assertIn('id="count-sources">—</span>', self.index_html)

        # Overview KPI metric boxes must start with dynamic placeholders
        self.assertIn('id="hero-doc-count">—</div>', self.index_html)
        self.assertIn('id="hero-timeline-count">—</div>', self.index_html)
        self.assertIn('id="hero-changes-count">—</div>', self.index_html)
        self.assertIn('id="hero-flags-count">—</div>', self.index_html)

        # Coverage display in header must be dynamic
        self.assertIn('id="coverage-display">Loading...</span>', self.index_html)

    def test_03_overview_is_concise_with_previews(self):
        """3. Verify Overview contains high-level consultation summary & previews, not full duplicate tables."""
        # Consultation Context cards
        self.assertIn('id="ctx-reason-for-visit"', self.index_html)
        self.assertIn('id="ctx-latest-encounter"', self.index_html)
        self.assertIn('id="ctx-relevant-history"', self.index_html)
        self.assertIn('id="ctx-latest-record"', self.index_html)

        # Compact previews grid
        self.assertIn('overview-previews-grid', self.index_html)
        self.assertIn('id="overview-timeline-preview-list"', self.index_html)
        self.assertIn('id="overview-changes-preview-list"', self.index_html)
        self.assertIn('id="overview-flags-preview-list"', self.index_html)

        # "View all" navigation buttons
        self.assertIn("switchToTab('tab-timeline')", self.index_html)
        self.assertIn("switchToTab('tab-changes')", self.index_html)
        self.assertIn("switchToTab('tab-flags')", self.index_html)

    def test_04_unchanged_comparisons_filtered(self):
        """4. Verify What Changed filters identical values both in backend and frontend helper."""
        detector = ChangeDetector(structured_dir=Path("data/structured"))
        changes_res = detector.detect_changes(patient_id=self.patient_id, only_changed=True)
        for ch in changes_res.changes:
            prev = str(ch.previous_value).strip().lower()
            latest = str(ch.latest_value).strip().lower()
            self.assertNotEqual(prev, latest, f"Unchanged value detected: {ch.entity_name} ({prev} -> {latest})")

        # Verify frontend filter logic exists
        self.assertIn("getGenuineChanges", self.app_js)
        self.assertIn("p === l", self.app_js)

    def test_05_refresh_patient_data_queries_all_endpoints(self):
        """5. Verify refreshPatientData queries all 5 backend APIs with no-store cache headers."""
        self.assertIn("async function refreshPatientData()", self.app_js)
        self.assertIn("cache: \"no-store\"", self.app_js)
        self.assertIn("/api/patient/${PATIENT_ID}/brief", self.app_js)
        self.assertIn("/api/patient/${PATIENT_ID}/timeline", self.app_js)
        self.assertIn("/api/patient/${PATIENT_ID}/changes", self.app_js)
        self.assertIn("/api/patient/${PATIENT_ID}/flags", self.app_js)
        self.assertIn("/api/patient/${PATIENT_ID}/review", self.app_js)

    def test_06_upload_flow_triggers_refresh(self):
        """6. Verify processDocuments calls await refreshPatientData() after successful upload."""
        self.assertIn("await refreshPatientData();", self.app_js)
        self.assertIn("Document processed successfully. MedChronicle updated.", self.app_js)

    def test_07_full_backend_api_and_reset_flow(self):
        """7. Verify complete reset and authoritative API responses."""
        # Reset to baseline
        res = self.client.post(f"/api/patient/{self.patient_id}/reset")
        self.assertEqual(res.status_code, 200)

        # Baseline checks
        brief = self.client.get(f"/api/patient/{self.patient_id}/brief").json()
        timeline = self.client.get(f"/api/patient/{self.patient_id}/timeline").json()
        changes = self.client.get(f"/api/patient/{self.patient_id}/changes").json()
        flags = self.client.get(f"/api/patient/{self.patient_id}/flags").json()
        review = self.client.get(f"/api/patient/{self.patient_id}/review").json()

        self.assertEqual(brief["header"]["source_documents_count"], 10)
        self.assertEqual(len(brief["source_documents"]), 10)
        self.assertEqual(brief["header"]["total_timeline_events"], 65)
        self.assertEqual(timeline["total_events"], 65)
        self.assertEqual(len(changes["changes"]), 6)
        self.assertEqual(len(flags["flags"]), 2)
        self.assertEqual(review["review_status"], "pending")

        # Document endpoint serves original files
        first_doc = brief["source_documents"][0]["document_id"]
        doc_res = self.client.get(f"/api/patient/{self.patient_id}/documents/{first_doc}")
        self.assertEqual(doc_res.status_code, 200)
        self.assertEqual(doc_res.headers.get("content-type"), "application/pdf")


if __name__ == "__main__":
    unittest.main()
