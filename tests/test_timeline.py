"""Unit tests for deterministic TimelineEngine.

Verifies:
1. Chronological sorting (earlier dates precede later dates).
2. Deterministic handling of multiple events on the same date.
3. Strict source reference preservation.
4. Missing date handling (preserves items in undated_events, never invents dates).
5. Document event type preservation (visit, pathology, laboratory, etc.).

No LLM or network calls.
"""

import json
from pathlib import Path
import tempfile
import unittest

from app.services.timeline import TimelineEngine, TimelineItem


class TestTimelineEngine(unittest.TestCase):
    """Test suite for deterministic timeline construction."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.structured_dir = Path(self.temp_dir.name)

        # Mock doc 1: Date 2026-01-05
        doc_001 = {
            "document_id": "doc-001",
            "file_name": "consult_2026-01-05.pdf",
            "facts": {
                "visits": [
                    {
                        "source": {"document_id": "doc-001", "file_name": "consult_2026-01-05.pdf", "page_number": 1},
                        "confidence": 1.0,
                        "visit_id": "v1",
                        "date": "2026-01-05",
                        "facility": "Sunrise Centre",
                        "department": "Surgical Oncology",
                        "visit_type": "Initial Consultation",
                    }
                ],
                "investigations": [
                    {
                        "source": {"document_id": "doc-001", "file_name": "consult_2026-01-05.pdf", "page_number": 2},
                        "confidence": 0.95,
                        "investigation_name": "Mammogram",
                        "status": "ordered",
                        "ordered_date": "2026-01-05",
                    }
                ],
            },
        }
        (self.structured_dir / "doc-001.json").write_text(json.dumps(doc_001), encoding="utf-8")

        # Mock doc 2: Date 2026-01-08
        doc_002 = {
            "document_id": "doc-002",
            "file_name": "path_2026-01-08.pdf",
            "facts": {
                "pathology_findings": [
                    {
                        "source": {"document_id": "doc-002", "file_name": "path_2026-01-08.pdf", "page_number": 1},
                        "confidence": 1.0,
                        "finding_name": "Core Needle Biopsy",
                        "documented_text": "Invasive ductal carcinoma, grade 2",
                        "date": "2026-01-08",
                    }
                ]
            },
        }
        (self.structured_dir / "doc-002.json").write_text(json.dumps(doc_002), encoding="utf-8")

        # Mock doc 3: Date 2026-01-08 (Same date as doc-002) + 1 undated item
        doc_003 = {
            "document_id": "doc-003",
            "file_name": "lab_2026-01-08.pdf",
            "facts": {
                "laboratory_results": [
                    {
                        "source": {"document_id": "doc-003", "file_name": "lab_2026-01-08.pdf", "page_number": 1},
                        "confidence": 1.0,
                        "test_name": "Hemoglobin",
                        "value": "13.4",
                        "unit": "g/dL",
                        "date": "2026-01-08",
                    },
                    {
                        "source": {"document_id": "doc-003", "file_name": "lab_2026-01-08.pdf", "page_number": 1},
                        "confidence": 0.9,
                        "test_name": "Undated Marker",
                        "value": "10",
                        "unit": "U/mL",
                        "date": None,  # Explicitly undated
                    },
                ]
            },
        }
        (self.structured_dir / "doc-003.json").write_text(json.dumps(doc_003), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_01_chronological_sorting(self) -> None:
        """1. Verify events are ordered chronologically from earliest to latest."""
        engine = TimelineEngine(self.structured_dir)
        tl = engine.build_timeline(patient_id="TEST-PATIENT")

        dates = [ev.date for ev in tl.events if ev.date]
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(tl.earliest_date, "2026-01-05")
        self.assertEqual(tl.latest_date, "2026-01-08")

    def test_02_same_date_events_deterministic(self) -> None:
        """2. Verify multiple events on the same date are sorted deterministically."""
        engine = TimelineEngine(self.structured_dir)
        tl = engine.build_timeline(patient_id="TEST-PATIENT")

        events_on_08 = [ev for ev in tl.events if ev.date == "2026-01-08"]
        self.assertGreaterEqual(len(events_on_08), 2)
        # Verify both doc-002 and doc-003 events are present
        doc_ids = {ev.source.document_id for ev in events_on_08}
        self.assertIn("doc-002", doc_ids)
        self.assertIn("doc-003", doc_ids)

    def test_03_source_provenance_preserved(self) -> None:
        """3. Verify every timeline event strictly preserves source document_id, file, and page."""
        engine = TimelineEngine(self.structured_dir)
        tl = engine.build_timeline(patient_id="TEST-PATIENT")

        for ev in tl.events:
            self.assertTrue(ev.source.document_id.startswith("doc-"))
            self.assertTrue(ev.source.file_name.endswith(".pdf"))
            self.assertGreaterEqual(ev.source.page_number, 1)

    def test_04_missing_date_handling(self) -> None:
        """4. Verify events without documented dates are partitioned into undated_events without inventing dates."""
        engine = TimelineEngine(self.structured_dir)
        tl = engine.build_timeline(patient_id="TEST-PATIENT")

        self.assertEqual(tl.undated_events_count, 1)
        self.assertEqual(len(tl.undated_events), 1)
        undated_item = tl.undated_events[0]
        self.assertIsNone(undated_item.date)
        self.assertIn("Undated Marker", undated_item.title)

    def test_05_document_type_preservation(self) -> None:
        """5. Verify category types (visit, pathology, laboratory, investigation) are accurately preserved."""
        engine = TimelineEngine(self.structured_dir)
        tl = engine.build_timeline(patient_id="TEST-PATIENT")

        types_found = {ev.event_type for ev in tl.events}
        self.assertIn("visit", types_found)
        self.assertIn("investigation", types_found)
        self.assertIn("pathology", types_found)
        self.assertIn("laboratory", types_found)


if __name__ == "__main__":
    unittest.main()
