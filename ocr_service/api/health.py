from typing import Any

import psutil
from fastapi import APIRouter, Request, status
from fastapi.responses import ORJSONResponse

from ocr_service.dto.info_response import InfoResponse
from ocr_service.utils.utils import get_app_info

health_api = APIRouter(prefix="/api")


@health_api.get("/health", response_class=ORJSONResponse)
def health() -> ORJSONResponse:
    return ORJSONResponse(content={"status": "healthy"})


def _collect_readiness_issues(request: Request) -> list[str]:
    issues: list[str] = []

    processor = getattr(request.app.state, "processor", None)
    if processor is None:
        return ["processor_not_initialized"]

    loffice_process_list = getattr(processor, "loffice_process_list", None)
    if not isinstance(loffice_process_list, dict) or len(loffice_process_list) == 0:
        return ["libreoffice_process_list_empty"]

    for port, proc_data in loffice_process_list.items():
        if not isinstance(proc_data, dict):
            issues.append(f"libreoffice_process_invalid_metadata:{port}")
            continue

        if proc_data.get("unhealthy"):
            issues.append(f"libreoffice_process_marked_unhealthy:{port}")
            continue

        process_obj = proc_data.get("process")
        process_pid: Any = getattr(process_obj, "pid", None) or proc_data.get("pid")

        try:
            process_pid = int(process_pid)
        except (TypeError, ValueError):
            issues.append(f"libreoffice_process_missing_pid:{port}")
            continue

        if process_obj is not None and hasattr(process_obj, "poll") and process_obj.poll() is not None:
            issues.append(f"libreoffice_process_exited:{port}")
            continue

        if not psutil.pid_exists(process_pid):
            issues.append(f"libreoffice_process_pid_not_found:{port}")
            continue

        try:
            lo_process = psutil.Process(process_pid)
            if not lo_process.is_running():
                issues.append(f"libreoffice_process_not_running:{port}")
                continue
            if lo_process.status() == psutil.STATUS_ZOMBIE:
                issues.append(f"libreoffice_process_zombie:{port}")
        except psutil.Error:
            issues.append(f"libreoffice_process_not_accessible:{port}")

    return issues


@health_api.get("/ready", response_class=ORJSONResponse)
def ready(request: Request) -> ORJSONResponse:
    issues = _collect_readiness_issues(request)
    if len(issues) > 0:
        return ORJSONResponse(
            content={"status": "not_ready", "issues": issues},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    process_count = len(request.app.state.processor.loffice_process_list)
    return ORJSONResponse(content={"status": "ready", "libreoffice_processes": process_count})


@health_api.get("/info", response_model=InfoResponse, response_class=ORJSONResponse)
def info() -> ORJSONResponse:
    return ORJSONResponse(content=get_app_info())
