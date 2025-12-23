from typing import Any

from pydantic import BaseModel, Field


class ProcessResult(BaseModel):
    """Inner OCR result payload for /api/process endpoints."""

    text: str = Field(..., description="Extracted/OCR text.")
    footer: dict[str, Any] | None = Field(default=None, description="Optional passthrough payload.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Document metadata.")
    success: str = Field(..., description="Success flag encoded as a string.")
    timestamp: str = Field(..., description="Processing timestamp.")


class ProcessResponse(BaseModel):
    """Response payload for /api/process endpoints."""

    result: ProcessResult = Field(..., description="OCR processing result.")
