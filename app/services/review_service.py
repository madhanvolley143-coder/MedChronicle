"""JSON-backed doctor review store for JourneyBrief prototype.

Persists review status and item-level clinician verifications under data/reviews/.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Optional

from app.models.review import DoctorReview, ReviewUpdateRequest


class ReviewService:
    """Manages clinician review records in local JSON storage."""

    def __init__(self, reviews_dir: Path = Path("data/reviews")) -> None:
        self.reviews_dir = Path(reviews_dir)
        self.reviews_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, patient_id: str) -> Path:
        sanitized = patient_id.lower().replace("-", "_")
        return self.reviews_dir / f"{sanitized}_review.json"

    def get_review(self, patient_id: str) -> DoctorReview:
        """Retrieve existing doctor review or return a default pending review."""
        fpath = self._file_path(patient_id)
        if fpath.is_file():
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                return DoctorReview.model_validate(data)
            except Exception:
                pass

        # Return default pending review
        return DoctorReview(patient_id=patient_id, review_status="pending")

    def save_review(self, review: DoctorReview) -> DoctorReview:
        """Persist a doctor review to disk."""
        fpath = self._file_path(review.patient_id)
        fpath.write_text(json.dumps(review.model_dump(mode="json"), indent=2), encoding="utf-8")
        return review

    def update_review(self, patient_id: str, update: ReviewUpdateRequest) -> DoctorReview:
        """Apply updates to a review and persist changes."""
        review = self.get_review(patient_id)

        if update.reviewer_id:
            review.reviewer_id = update.reviewer_id

        if update.review_status:
            review.review_status = update.review_status

        if update.item_id and update.item_status:
            review.reviewed_items[update.item_id] = update.item_status

        if update.reviewed_items:
            review.reviewed_items.update(update.reviewed_items)

        if update.notes is not None:
            review.notes = update.notes

        review.updated_at = datetime.now(timezone.utc).isoformat()
        return self.save_review(review)
