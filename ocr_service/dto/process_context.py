from __future__ import annotations

from typing import Any

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from ocr_service.utils.utils import TextChecks


class ProcessContext(BaseModel):
    """Holds per-request processing state for conversion and OCR steps.

    This model is internal to the processing pipeline and captures the mutable
    state shared between the document conversion and OCR stages.
    """

    stream: bytes
    """Raw document bytes provided by the caller."""

    file_name: str
    """Normalized filename used for temp files and type inference."""

    file_type: object | None
    """Detected file type from the filetype library (or None if unknown)."""

    output_text: str = ""
    """Accumulated extracted/OCR'd text for the current request."""

    images: list[Image.Image] = Field(default_factory=list)
    """Image pages prepared for OCR (empty if not applicable)."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Document metadata such as content-type, pages, confidence, and timing."""

    pdf_stream: bytes = b""
    """Intermediate PDF bytes used for downstream conversion/OCR."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _checks: TextChecks | None = PrivateAttr(default=None)
    """Lazy text-type detection cache. Initialized on first access."""

    @property
    def checks(self) -> TextChecks:
        """Return cached text-type checks for the current stream."""
        if self._checks is None:
            self._checks = TextChecks(self.stream)
        return self._checks
