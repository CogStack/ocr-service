from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProcessRequest(BaseModel):
    """JSON payloads sent to /api/process."""

    model_config = ConfigDict(extra="ignore")

    binary_data: str | None = Field(
        ...,
        description=(
            "Base64-encoded document bytes. "
            "Use null when the record has no attachment and OCR should be skipped."
        ),
    )
    footer: dict[str, Any] | None = Field(default=None, description="Optional passthrough payload.")
