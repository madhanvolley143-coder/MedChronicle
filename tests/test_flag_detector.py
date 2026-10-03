"""Unit tests for deterministic FlagDetector engine.

Verifies:
12. Missing result detection (investigation ordered/pending without uploaded result).
13. Conflicting documented value detection (same test/date with contradictory values).
14. Missing source detection (defensive provenance gap check).
15. Medication documentation mismatch detection (differing documented statuses).
16. Date inconsistency detection (e.g. ordered_date > result_date).
17. Strict non-clinical framing (no 'danger', 'risk', 'deterioration', 'failure' language).

No LLM or network calls.
"""

import json
from pathlib import Path
import tempfile
import unittest

from app.services.flag_detector import FlagDetector


class TestFlagDetector(unittest.TestCase):
    """Test suite for deterministic documentation flag detector."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.structured_dir = Path(self.temp_dir.name)

        # Doc 1: Ordered investigation without a result in the uploaded documents
        # AND an investigation with ordered_date > result_date (date inconsistency)
        doc_001 = {
            "document_id": "doc-001",
            "file_name": "consult_note.pdf",
            "facts": {
                "investigations": [
                    {
                        "source": {"document_id": "doc-001", "file_name": "consult_note.pdf", "page_number": 1},
                        "confidence": 1.0,
                        "investigation_name": "CT Simulation Planning Scan",
                        "status": "ordered",
                        "ordered_date": "2026-02-07",
                    },
                    {
                        "source": {"document_id": "doc-001", "file_name": "consult_note.pdf", "page_number": 2},
                        "confidence": 0.95,
                        "investigation_name": "Chronology Error Test",
                        "status": "completed",
                        "ordered_date": "2026-02-10",
                        "result_date": "2026-02-01",  # Inconsistent: ordered after result
                    },
                ]
            },
        }
        (self.structured_dir / "doc-001.json").write_text(json.dumps(doc_001), encoding="utf-8")

        # Doc 2: Same-day conflicting laboratory value (Hemoglobin 13.4 on 2026-01-10)
        doc_002 = {
            "document_id": "doc-002",
            "file_name": "lab_a.pdf",
            "facts": {
                "laboratory_results": [
                    {
                        "source": {"document_id": "doc-002", "file_name": "lab_a.pdf", "page_number": 1},
                        "confidence": 1.0,
                        "test_name": "Hemoglobin",
                        "value": "13.4",
                        "unit": "g/dL",
                        "date": "2026-01-10",
                    }
                ],
                "medications": [
                    {
                        "source": {"document_id": "doc-002", "file_name": "lab_a.pdf", "page_number": 1},
                        "confidence": 1.0,
                        "medicine_name": "Tamoxifen",
                        "status": "started",
                        "date": "2026-01-10",
                    }
                ],
            },
        }
        (self.structured_dir / "doc-002.json").write_text(json.dumps(doc_002), encoding="utf-8")

        # Doc 3: Contradictory Hemoglobin value 12.0 on the SAME date (2026-01-10)
        # AND medication documented with different status 'continued'
        # AND an item missing source provenance (defensive test)
        doc_003 = {
            "document_id": "doc-003",
            "file_name": "lab_b.pdf",
            "facts": {
                "laboratory_results": [
                    {
                        "source": {"document_id": "doc-003", "file_name": "lab_b.pdf", "page_number": 1},
                        "confidence": 1.0,
                        "test_name": "Hemoglobin",
                        "value": "12.0",
                        "unit": "g/dL",
                        "date": "2026-01-10",  # Same date, conflicting value!
                    },
                    {
                        "source": None,  # Missing source provenance
                        "confidence": 0.8,
                        "test_name": "Bad Provenance Test",
                        "value": "5.0",
                    },
                ],
                "medications": [
                    {
                        "source": {"document_id": "doc-003", "file_name": "lab_b.pdf", "page_number": 1},
                        "confidence": 1.0,
                        "medicine_name": "Tamoxifen",
                        "status": "continued",
                        "date": "2026-01-15",
                    }
                ],
            },
        }
        (self.structured_dir / "doc-003.json").write_text(json.dumps(doc_003), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_12_missing_result_detection(self) -> None:
        """12. Verify ordered investigation without uploaded completed result triggers missing_result flag."""
        detector = FlagDetector(self.structured_dir)
        flags_data = detector.detect_flags("TEST-PATIENT")

        missing_res_flags = [f for f in flags_data.flags if f.flag_type == "missing_result"]
        self.assertGreaterEqual(len(missing_res_flags), 1)
        flag = missing_res_flags[0]
        self.assertIn("CT Simulation", flag.title)
        self.assertEqual(flag.severity, "informational")
        self.assertIn("ordered", flag.description.lower())

    def test_13_conflicting_documented_value_detection(self) -> None:
        """13. Verify conflicting values recorded on the same date trigger conflict flag with both sources."""
        detector = FlagDetector(self.structured_dir)
        flags_data = detector.detect_flags("TEST-PATIENT")

        conflict_flags = [f for f in flags_data.flags if f.flag_type == "conflicting_documented_value"]
        self.assertEqual(len(conflict_flags), 1)
        flag = conflict_flags[0]
        self.assertIn("Hemoglobin", flag.title)
        self.assertEqual(len(flag.sources), 2)
        doc_ids = {s.document_id for s in flag.sources}
        self.assertIn("doc-002", doc_ids)
        self.assertIn("doc-003", doc_ids)

    def test_14_missing_source_detection(self) -> None:
        """14. Verify structured item without source reference is defensively flagged."""
        detector = FlagDetector(self.structured_dir)
        flags_data = detector.detect_flags("TEST-PATIENT")

        src_flags = [f for f in flags_data.flags if f.flag_type == "missing_source"]
        self.assertGreaterEqual(len(src_flags), 1)
        self.assertEqual(src_flags[0].category, "provenance")

    def test_15_medication_documentation_mismatch(self) -> None:
        """15. Verify multiple documented medication statuses trigger medication_documentation_mismatch flag."""
        detector = FlagDetector(self.structured_dir)
        flags_data = detector.detect_flags("TEST-PATIENT")

        med_flags = [f for f in flags_data.flags if f.flag_type == "medication_documentation_mismatch"]
        self.assertEqual(len(med_flags), 1)
        self.assertIn("Tamoxifen", med_flags[0].title)
        self.assertIn("started", med_flags[0].description)
        self.assertIn("continued", med_flags[0].description)

    def test_16_date_inconsistency_detection(self) -> None:
        """16. Verify ordered_date > result_date triggers date_inconsistency flag."""
        detector = FlagDetector(self.structured_dir)
        flags_data = detector.detect_flags("TEST-PATIENT")

        date_flags = [f for f in flags_data.flags if f.flag_type == "date_inconsistency"]
        self.assertEqual(len(date_flags), 1)
        self.assertIn("Chronology Error Test", date_flags[0].title)

    def test_17_no_clinical_risk_language_in_flags(self) -> None:
        """17. Verify all flags use neutral documentation phrasing and strictly avoid clinical threat language."""
        detector = FlagDetector(self.structured_dir)
        flags_data = detector.detect_flags("TEST-PATIENT")
        md_text = detector.generate_markdown(flags_data)

        prohibited_terms = [
            "danger",
            "high risk",
            "clinical risk",
            "patient deterioration",
            "treatment failure",
            "medical error",
            "adverse event",
        ]
        md_lower = md_text.lower()
        for term in prohibited_terms:
            self.assertNotIn(term, md_lower)

        for f in flags_data.flags:
            item_text = f"{f.title} {f.description}".lower()
            for term in prohibited_terms:
                self.assertNotIn(term, item_text)
            self.assertEqual(f.severity, "informational")


if __name__ == "__main__":
    unittest.main()
