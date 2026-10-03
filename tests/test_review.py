"""Unit tests for doctor review model and ReviewService.

Verifies:
5. Review creation (returns default pending review for a patient).
6. Review retrieval (loads persisted state).
7. Mark item verified (item-level verification persistence).
8. Mark overall brief reviewed (overall review status update).
9. Human-in-the-loop disclaimer presence.
"""

from pathlib import Path
import tempfile
import unittest

from app.models.review import DoctorReview, ReviewUpdateRequest
from app.services.review_service import ReviewService


class TestDoctorReviewService(unittest.TestCase):
    """Test suite for ReviewService and DoctorReview persistence."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = ReviewService(reviews_dir=Path(self.temp_dir.name))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_05_review_creation_default_state(self) -> None:
        """5. Verify unreviewed patient returns a default 'pending' review object."""
        review = self.service.get_review("SYN-CANCER-001")
        self.assertIsInstance(review, DoctorReview)
        self.assertEqual(review.patient_id, "SYN-CANCER-001")
        self.assertEqual(review.review_status, "pending")
        self.assertEqual(review.reviewed_items, {})
        self.assertIn("clinician review required", review.disclaimer.lower())

    def test_06_review_retrieval(self) -> None:
        """6. Verify persisted review can be retrieved from disk accurately."""
        initial = DoctorReview(
            patient_id="SYN-CANCER-001",
            reviewer_id="dr_oncologist_1",
            review_status="pending",
            reviewed_items={"ev-1": "verified"},
            notes="Initial review started.",
        )
        self.service.save_review(initial)

        loaded = self.service.get_review("SYN-CANCER-001")
        self.assertEqual(loaded.patient_id, "SYN-CANCER-001")
        self.assertEqual(loaded.reviewer_id, "dr_oncologist_1")
        self.assertEqual(loaded.reviewed_items.get("ev-1"), "verified")
        self.assertEqual(loaded.notes, "Initial review started.")

    def test_07_mark_item_verified(self) -> None:
        """7. Verify marking an individual item verified updates the record."""
        update = ReviewUpdateRequest(
            reviewer_id="dr_smith",
            item_id="change-0-hemoglobin",
            item_status="verified",
        )
        updated = self.service.update_review("SYN-CANCER-001", update)
        self.assertEqual(updated.reviewed_items.get("change-0-hemoglobin"), "verified")
        self.assertEqual(updated.review_status, "pending")

        # Verify retrieval matches
        refetched = self.service.get_review("SYN-CANCER-001")
        self.assertEqual(refetched.reviewed_items.get("change-0-hemoglobin"), "verified")

    def test_08_mark_overall_brief_reviewed(self) -> None:
        """8. Verify marking the overall brief as reviewed updates review_status."""
        update = ReviewUpdateRequest(
            reviewer_id="dr_smith",
            review_status="reviewed",
            notes="All 10 source documents verified against documented findings.",
        )
        updated = self.service.update_review("SYN-CANCER-001", update)
        self.assertEqual(updated.review_status, "reviewed")
        self.assertIn("All 10 source documents", updated.notes)

        # Re-fetch from service
        refetched = self.service.get_review("SYN-CANCER-001")
        self.assertEqual(refetched.review_status, "reviewed")

    def test_bulk_reviewed_items_update(self) -> None:
        """Verify bulk update of reviewed items mapping."""
        update = ReviewUpdateRequest(
            reviewed_items={
                "item-1": "verified",
                "item-2": "needs_review",
            }
        )
        updated = self.service.update_review("SYN-CANCER-001", update)
        self.assertEqual(updated.reviewed_items["item-1"], "verified")
        self.assertEqual(updated.reviewed_items["item-2"], "needs_review")


if __name__ == "__main__":
    unittest.main()
