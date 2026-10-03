from typing import List
from pydantic import BaseModel, ConfigDict, Field
from app.models.document import Document


class Patient(BaseModel):
    """Synthetic patient profile ensuring strict compliance with synthetic data policy."""

    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(..., min_length=1, description="Unique synthetic patient identifier")
    synthetic: bool = Field(
        default=True,
        description="Data policy compliance flag. Must default to True (synthetic data only).",
    )
    documents: List[Document] = Field(
        default_factory=list,
        description="Associated synthetic patient documents",
    )
