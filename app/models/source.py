from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SourceReference(BaseModel):
    """Source provenance tracking back to original patient document and page."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(..., min_length=1, description="Unique identifier for the source document")
    file_name: str = Field(..., min_length=1, description="File name of the source document")
    page_number: int = Field(..., ge=1, description="1-indexed page number in the source document (must be >= 1)")
    text_anchor: Optional[str] = Field(default=None, description="Exact or normalized text segment matched")
    bounding_box: Optional[List[float]] = Field(
        default=None,
        min_length=4,
        max_length=4,
        description="Coordinates [x0, y0, x1, y1] on the page",
    )
