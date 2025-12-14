from fastapi import APIRouter

from ocr_service.api.health import health_api
from ocr_service.api.process import process_api

api = APIRouter()

api.include_router(health_api)
api.include_router(process_api)
