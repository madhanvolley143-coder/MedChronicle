"""Unit tests for deterministic JourneyBrief generator.

Verifies:
1. JourneyBrief generation completes deterministically without LLM calls.
2. Every brief item has a source reference.
3. No unsupported clinical interpretation (no diagnosis, staging, prognosis, progression, response).
4. Source references are preserved with valid document_id, file_name, and page_number.
"""

from pathlib import Path
import unittest

from app.models.source import SourceReference
from app.services.journey_brief import JourneyBrief, JourneyBriefGenerator


class TestJourneyBriefGenerator(unittest.TestCase):
    """Test suite for deterministic JourneyBrief generation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.generator = JourneyBriefGenerator(
            structured_dir=Path("data/structured"),
            extracted_dir=Path("data/extracted"),
        )
        cls.brief = cls.generator.generate_brief(patient_id="SYN-CANCER-001")

    def test_01_journey_brief_generation(self) -> None:
        """1. Verify JourneyBrief generates with complete sections and synthetic banner."""
        self.assertIsInstance(self.brief, JourneyBrief)
        self.assertEqual(self.brief.header.patient_id, "SYN-CANCER-001")
        self.assertEqual(
            self.brief.header.synthetic_notice,
            "SYNTHETIC DATA — DEMONSTRATION ONLY",
        )
        self.assertIn("clinician review required", self.brief.header.disclaimer.lower())
        self.assertGreaterEqual(self.brief.header.source_documents_count, 10)
        self.assertGreater(len(self.brief.recent_timeline), 0)
        self.assertGreater(len(self.brief.what_changed), 0)
        self.assertGreater(len(self.brief.documentation_flags), 0)
        self.assertGreater(len(self.brief.medications), 0)
        self.assertGreater(len(self.brief.investigations), 0)
        self.assertGreaterEqual(len(self.brief.source_documents), 10)

    def test_02_every_brief_item_has_a_source(self) -> None:
        """2. Verify every factual item in every section has an explicit SourceReference."""
        # Overview milestones
        for item in self.brief.overview:
            self.assertIsInstance(item.source, SourceReference)
            self.assertTrue(item.source.document_id)
            self.assertGreaterEqual(item.source.page_number, 1)

        # Recent timeline
        for ev in self.brief.recent_timeline:
            self.assertIsInstance(ev.source, SourceReference)
            self.assertTrue(ev.source.document_id)
            self.assertGreaterEqual(ev.source.page_number, 1)

        # What changed (both previous and latest sources)
        for chg in self.brief.what_changed:
            self.assertIsInstance(chg.previous_source, SourceReference)
            self.assertTrue(chg.previous_source.document_id)
            self.assertGreaterEqual(chg.previous_source.page_number, 1)

            self.assertIsInstance(chg.latest_source, SourceReference)
            self.assertTrue(chg.latest_source.document_id)
            self.assertGreaterEqual(chg.latest_source.page_number, 1)

        # Documentation flags
        for flg in self.brief.documentation_flags:
            self.assertGreater(len(flg.sources), 0, f"Flag {flg.flag_id} missing sources")
            for src in flg.sources:
                self.assertIsInstance(src, SourceReference)
                self.assertTrue(src.document_id)
                self.assertGreaterEqual(src.page_number, 1)

        # Medications
        for med in self.brief.medications:
            self.assertIsInstance(med.source, SourceReference)
            self.assertTrue(med.source.document_id)
            self.assertGreaterEqual(med.source.page_number, 1)

        # Investigations
        for inv in self.brief.investigations:
            self.assertIsInstance(inv.source, SourceReference)
            self.assertTrue(inv.source.document_id)
            self.assertGreaterEqual(inv.source.page_number, 1)

    def test_03_no_unsupported_clinical_interpretation(self) -> None:
        """3. Verify strictly no inferred diagnosis, staging, prognosis, or progression."""
        # Convert entire brief to lowercase text dump
        brief_dump = self.brief.model_dump_json().lower()

        # Prohibited speculative/interpretive diagnostic phrases
        prohibited_phrases = [
            "stage iii",  # Must not infer or assert un-documented staging
            "stage iv",
            "prognosis is",
            "prognosis:",
            "disease progression",
            "treatment failure",
            "clinical deterioration",
            "high risk of mortality",
            "dangerous condition",
            "poor response",
            "complete response",
            "curative intent",
        ]

        for phrase in prohibited_phrases:
            self.assertNotIn(
                phrase,
                brief_dump,
                f"Prohibited interpretive phrase '{phrase}' found in JourneyBrief.",
            )

        # Flags must strictly use neutral phrasing
        for flg in self.brief.documentation_flags:
            self.assertEqual(flg.notice, "Documentation / information issue")
            self.assertNotIn("risk score", flg.title.lower())
            self.assertNotIn("clinical alert", flg.title.lower())

    def test_04_source_references_are_preserved(self) -> None:
        """4. Verify source references match valid files in uploaded documents."""
        valid_doc_ids = {d.document_id for d in self.brief.source_documents}
        self.assertEqual(len(valid_doc_ids), 10)

        for ev in self.brief.recent_timeline:
            self.assertIn(ev.source.document_id, valid_doc_ids)

        for chg in self.brief.what_changed:
            self.assertIn(chg.previous_source.document_id, valid_doc_ids)
            self.assertIn(chg.latest_source.document_id, valid_doc_ids)

    def test_05_markdown_export(self) -> None:
        """5. Verify human-readable markdown export includes required sections and disclaimers."""
        md = self.generator.generate_markdown(self.brief)
        self.assertIn("# JourneyBrief", md)
        self.assertIn("SYNTHETIC DATA — DEMONSTRATION ONLY", md)
        self.assertIn("clinician review required", md.lower())
        self.assertIn("What Changed", md)
        self.assertIn("Documentation / Information Flags", md)
        self.assertIn("Based on 10 uploaded documents", md)


if __name__ == "__main__":
    unittest.main()
