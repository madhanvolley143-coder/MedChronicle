"""Unit tests for deterministic ChangeDetector engine.

Verifies:
6. Repeated laboratory value comparison.
7. Detection of different laboratory values over time.
8. Detection of identical laboratory values appearing again.
9. Medication status and dosage comparison.
10. Zero clinical interpretation language ('improved', 'worsened', 'normal', 'abnormal').
11. Preservation of both previous and latest source provenance.

No LLM or network calls.
"""

import json
from pathlib import Path
import tempfile
import unittest

from app.services.change_detector import ChangeDetector


class TestChangeDetector(unittest.TestCase):
    """Test suite for deterministic change detection engine."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.structured_dir = Path(self.temp_dir.name)

        # Doc 1: Initial lab on 2026-01-10 (Hemoglobin 13.4, CA 15-3 22.4)
        doc_003 = {
            "document_id": "doc-003",
            "file_name": "lab_report_2026-01-10.pdf",
            "facts": {
                "laboratory_results": [
                    {
                        "source": {"document_id": "doc-003", "file_name": "lab_report_2026-01-10.pdf", "page_number": 1},
                        "confidence": 1.0,
                        "test_name": "Hemoglobin",
                        "value": "13.4",
                        "unit": "g/dL",
                        "date": "2026-01-10",
                    },
                    {
                        "source": {"document_id": "doc-003", "file_name": "lab_report_2026-01-10.pdf", "page_number": 1},
                        "confidence": 1.0,
                        "test_name": "CA 15-3",
                        "value": "22.4",
                        "unit": "U/mL",
                        "date": "2026-01-10",
                    },
                ]
            },
        }
        (self.structured_dir / "doc-003.json").write_text(json.dumps(doc_003), encoding="utf-8")

        # Doc 2: Medication prescription on 2026-01-15 (Tamoxifen started 20 mg)
        doc_005 = {
            "document_id": "doc-005",
            "file_name": "rx_2026-01-15.pdf",
            "facts": {
                "medications": [
                    {
                        "source": {"document_id": "doc-005", "file_name": "rx_2026-01-15.pdf", "page_number": 1},
                        "confidence": 1.0,
                        "medicine_name": "Tamoxifen",
                        "strength": "20 mg",
                        "dose": "20 mg daily",
                        "status": "started",
                        "date": "2026-01-15",
                    }
                ]
            },
        }
        (self.structured_dir / "doc-005.json").write_text(json.dumps(doc_005), encoding="utf-8")

        # Doc 3: Follow-up lab on 2026-02-05 (Hemoglobin changed to 12.8, CA 15-3 unchanged 22.4)
        doc_008 = {
            "document_id": "doc-008",
            "file_name": "lab_report_2026-02-05.pdf",
            "facts": {
                "laboratory_results": [
                    {
                        "source": {"document_id": "doc-008", "file_name": "lab_report_2026-02-05.pdf", "page_number": 1},
                        "confidence": 1.0,
                        "test_name": "Hemoglobin",
                        "value": "12.8",
                        "unit": "g/dL",
                        "date": "2026-02-05",
                    },
                    {
                        "source": {"document_id": "doc-008", "file_name": "lab_report_2026-02-05.pdf", "page_number": 1},
                        "confidence": 1.0,
                        "test_name": "CA 15-3",
                        "value": "22.4",
                        "unit": "U/mL",
                        "date": "2026-02-05",
                    },
                ]
            },
        }
        (self.structured_dir / "doc-008.json").write_text(json.dumps(doc_008), encoding="utf-8")

        # Doc 4: Post-op note on 2026-02-07 (Tamoxifen continued)
        doc_009 = {
            "document_id": "doc-009",
            "file_name": "followup_2026-02-07.pdf",
            "facts": {
                "medications": [
                    {
                        "source": {"document_id": "doc-009", "file_name": "followup_2026-02-07.pdf", "page_number": 1},
                        "confidence": 1.0,
                        "medicine_name": "Tamoxifen",
                        "strength": "20 mg",
                        "dose": "20 mg daily",
                        "status": "continued",
                        "date": "2026-02-07",
                    }
                ]
            },
        }
        (self.structured_dir / "doc-009.json").write_text(json.dumps(doc_009), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_06_repeated_laboratory_value_comparison(self) -> None:
        """6. Verify repeated laboratory tests are matched and compared, excluding unchanged values."""
        detector = ChangeDetector(self.structured_dir)
        patient_changes = detector.detect_changes("TEST-PATIENT")

        lab_changes = [c for c in patient_changes.changes if c.category == "laboratory_results"]
        entities = {c.entity_name for c in lab_changes}
        self.assertIn("Hemoglobin", entities)
        # Unchanged CA 15-3 (22.4 -> 22.4) must be excluded from What Changed
        self.assertNotIn("CA 15-3", entities)

    def test_07_different_laboratory_values_detected(self) -> None:
        """7. Verify numerical difference is accurately captured for changed test values."""
        detector = ChangeDetector(self.structured_dir)
        patient_changes = detector.detect_changes("TEST-PATIENT")

        hb = next(c for c in patient_changes.changes if c.entity_name == "Hemoglobin")
        self.assertTrue(hb.is_changed)
        self.assertEqual(hb.previous_value, "13.4 g/dL")
        self.assertEqual(hb.latest_value, "12.8 g/dL")
        self.assertEqual(hb.documented_difference, "13.4 g/dL -> 12.8 g/dL")

    def test_08_unchanged_values_excluded_from_what_changed(self) -> None:
        """8. Verify identical values (e.g. CA 15-3 22.4 -> 22.4) are strictly excluded from What Changed."""
        detector = ChangeDetector(self.structured_dir)
        patient_changes = detector.detect_changes("TEST-PATIENT")

        ca = next((c for c in patient_changes.changes if c.entity_name == "CA 15-3"), None)
        self.assertIsNone(ca, "Unchanged CA 15-3 (22.4 -> 22.4) should NOT appear in What Changed!")

        # Verify only_changed=False can still retrieve un-changed comparisons for auditing
        audit_changes = detector.detect_changes("TEST-PATIENT", only_changed=False)
        ca_audit = next(c for c in audit_changes.changes if c.entity_name == "CA 15-3")
        self.assertFalse(ca_audit.is_changed)
        self.assertEqual(ca_audit.previous_value, "22.4 U/mL")
        self.assertEqual(ca_audit.latest_value, "22.4 U/mL")
        self.assertIn("unchanged", ca_audit.documented_difference)

    def test_09_medication_status_comparison(self) -> None:
        """9. Verify medication status transition is detected (started -> continued)."""
        detector = ChangeDetector(self.structured_dir)
        patient_changes = detector.detect_changes("TEST-PATIENT")

        tam = next(c for c in patient_changes.changes if "tamoxifen" in c.entity_name.lower())
        self.assertTrue(tam.is_changed)
        self.assertIn("started", tam.previous_value)
        self.assertIn("continued", tam.latest_value)
        self.assertEqual(tam.documented_difference, "started -> continued")

    def test_10_no_clinical_interpretation_in_changes(self) -> None:
        """10. Verify no clinical interpretation language exists in any change description."""
        detector = ChangeDetector(self.structured_dir)
        patient_changes = detector.detect_changes("TEST-PATIENT")
        md_report = detector.generate_markdown(patient_changes)

        prohibited_words = [
            "improved",
            "worsened",
            "deteriorat",
            "normal",
            "abnormal",
            "concerning",
            "dangerous",
            "safe",
            "effective",
            "progression",
        ]
        report_lower = md_report.lower()
        for word in prohibited_words:
            self.assertNotIn(word, report_lower)

        for chg in patient_changes.changes:
            text_lower = f"{chg.documented_difference} {chg.previous_value} {chg.latest_value}".lower()
            for word in prohibited_words:
                self.assertNotIn(word, text_lower)

    def test_11_source_provenance_preserved_in_changes(self) -> None:
        """11. Verify both previous_source and latest_source are preserved and accurate."""
        detector = ChangeDetector(self.structured_dir)
        patient_changes = detector.detect_changes("TEST-PATIENT")

        for chg in patient_changes.changes:
            self.assertTrue(chg.previous_source.document_id.startswith("doc-"))
            self.assertTrue(chg.latest_source.document_id.startswith("doc-"))
            self.assertGreaterEqual(chg.previous_source.page_number, 1)
            self.assertGreaterEqual(chg.latest_source.page_number, 1)


if __name__ == "__main__":
    unittest.main()
