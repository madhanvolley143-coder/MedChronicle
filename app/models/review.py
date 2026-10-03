"""Doctor review data models for JourneyBrief.

Enforces human-in-the-loop review semantics:
- The clinician is the final decision-maker.
- AI-generated structured facts must be explicitly reviewed and verified.
- JourneyBrief never claims AI output is clinically verified without doctor review.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DoctorReview(BaseModel):
    """Overall consultation readiness review state for a patient's JourneyBrief."""

    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(..., description="Patient identifier")
    reviewer_id: str = Field(default="demo-doctor", description="Clinician or reviewer ID")
    review_status: str = Field(
        default="pending",
        description="Overall review state: 'pending' or 'reviewed'",
    )
    reviewed_items: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of section/fact item_id to status ('verified' or 'needs_review')",
    )
    notes: Optional[str] = Field(default=None, description="Optional clinician review notes")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Review creation timestamp in UTC ISO format",
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Review update timestamp in UTC ISO format",
    )
    disclaimer: str = Field(
        default="AI-generated document summary — clinician review required. The clinician is the final decision-maker.",
        description="Mandatory clinician responsibility disclaimer",
    )


class ReviewUpdateRequest(BaseModel):
    """Payload to update doctor review status or verify individual items."""

    model_config = ConfigDict(extra="forbid")

    reviewer_id: str = Field(default="demo-doctor", description="Reviewer ID")
    review_status: Optional[str] = Field(
        default=None,
        description="Set overall review status: 'pending' or 'reviewed'",
    )
    item_id: Optional[str] = Field(
        default=None,
        description="Individual item/fact ID to mark (e.g. 'hb-change', 'tamoxifen-rx')",
    )
    item_status: Optional[str] = Field(
        default=None,
        description="Status for item: 'verified' or 'needs_review'",
    )
    reviewed_items: Optional[Dict[str, str]] = Field(
        default=None,
        description="Bulk update of reviewed items mapping",
    )
    notes: Optional[str] = Field(default=None, description="Clinician review notes")
