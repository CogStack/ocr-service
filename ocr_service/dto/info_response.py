from pydantic import BaseModel, Field


class InfoResponse(BaseModel):
    """Response payload for the /api/info endpoint."""

    service_app_name: str = Field(..., description="Service name.")
    service_version: str = Field(..., description="Service version string.")
    service_model: str = Field(..., description="Tesseract model path/prefix.")
    config: str = Field(..., description="Reserved config field.")
