from fastapi import APIRouter
from fastapi.responses import ORJSONResponse

from ocr_service.dto.info_response import InfoResponse
from ocr_service.utils.utils import get_app_info

health_api = APIRouter(prefix="/api")


@health_api.get("/health", response_class=ORJSONResponse)
def health() -> ORJSONResponse:
    return ORJSONResponse(content={"status": "healthy"})


@health_api.get("/info", response_model=InfoResponse, response_class=ORJSONResponse)
def info() -> ORJSONResponse:
    return ORJSONResponse(content=get_app_info())
