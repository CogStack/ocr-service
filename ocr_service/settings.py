import ast
import logging
import multiprocessing
import os
from pathlib import Path
from sys import platform
from typing import Any, Literal

from pydantic import AliasChoices, Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", validate_assignment=True)

    OCR_SERVICE_VERSION: str = Field(
        "dev",
        min_length=1,
        validation_alias=AliasChoices("OCR_SERVICE_VERSION", "OCR_SERVICE_IMAGE_RELEASE_VERSION"),
    )
    OCR_SERVICE_LOG_LEVEL: int = Field(10, ge=0, le=50)
    OCR_SERVICE_DEBUG_MODE: bool = Field(False)
    OCR_TMP_DIR: str | None = None

    OCR_SERVICE_OPERATION_MODE: Literal["OCR", "NO_OCR"] = Field("OCR")
    OCR_SERVICE_PORT: int = Field(8090, ge=1, le=65535)

    OCR_TESSDATA_PREFIX: str = Field("/opt/homebrew/share/tessdata", min_length=1)
    OCR_SERVICE_TESSERACT_TIMEOUT: int = Field(30, gt=0)
    OCR_SERVICE_TESSERACT_LANG: str = Field("eng", min_length=1)
    OCR_SERVICE_TESSERACT_NICE: int = Field(-18, ge=-20, le=19)
    OCR_SERVICE_TESSERACT_CUSTOM_CONFIG_FLAGS: str = ""

    OCR_WEB_SERVICE_THREADS: int = Field(1, ge=1)
    OCR_WEB_SERVICE_WORKERS: int = Field(1, ge=1)

    OCR_SERVICE_CPU_THREADS: int = Field(1, ge=1)
    OCR_SERVICE_CONVERTER_THREADS: int = Field(1, ge=1)
    OCR_SERVICE_IMAGE_DPI: int = Field(200, gt=0)
    OCR_CONVERT_GRAYSCALE_IMAGES: bool = Field(True)

    OCR_SERVICE_LIBRE_OFFICE_PROCESS_TIMEOUT: int = Field(100, gt=0)
    OCR_SERVICE_LIBRE_OFFICE_LISTENER_PORT_RANGE: str | None = None
    DEFAULT_LIBRE_OFFICE_SERVER_PORT: int = Field(9900, ge=1, le=65535)
    LIBRE_OFFICE_NETWORK_INTERFACE: str = Field("localhost", min_length=1)
    LIBRE_OFFICE_PROCESSES_LISTENER_INTERVAL: int = Field(10, gt=0)

    LIBRE_OFFICE_PYTHON_PATH: str = Field(
        "/Applications/LibreOffice.app/Contents/Resources/python",
        min_length=1,
    )
    LIBRE_OFFICE_EXEC_PATH: str = Field(
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        min_length=1,
    )

    @field_validator("OCR_SERVICE_OPERATION_MODE", mode="before")
    @classmethod
    def normalize_operation_mode(cls, value: str) -> str:
        return str(value).upper()

    @field_validator("OCR_WEB_SERVICE_THREADS")
    @classmethod
    def clamp_threads(cls, value: int) -> int:
        if value > 1:
            logging.warning(
                "OCR_WEB_SERVICE_THREADS is deprecated and ignored; forcing to 1. Use OCR_WEB_SERVICE_WORKERS."
            )
            return 1
        return value

    @field_validator("OCR_SERVICE_LIBRE_OFFICE_LISTENER_PORT_RANGE")
    @classmethod
    def validate_lo_port_range(cls, value: str | None) -> str | None:
        if not value:
            return None
        try:
            start, end = ast.literal_eval(value)
            start = int(start)
            end = int(end)
            if start < 1 or end > 65535:
                raise ValueError("listener port range must be within 1-65535")
            if start >= end:
                raise ValueError("listener port range start must be less than end")
        except (ValueError, SyntaxError, TypeError) as exc:
            raise ValueError(f"Invalid OCR_SERVICE_LIBRE_OFFICE_LISTENER_PORT_RANGE: {value}") from exc
        return value

    def model_post_init(self, __context: Any) -> None:
        default_lo_python = "/Applications/LibreOffice.app/Contents/Resources/python"
        default_lo_exec = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        tessdata_prefix = self.OCR_TESSDATA_PREFIX

        if platform in ("linux", "linux2"):
            default_lo_exec = "/usr/bin/soffice"
            default_lo_python = "/usr/bin/python3.12"
            tessdata_prefix = "/usr/share/tesseract-ocr/5/tessdata"

            if not os.path.exists(tessdata_prefix):
                tessdata_prefix = "/usr/share/tesseract-ocr/4.00/tessdata"
        elif platform == "win32":
            default_lo_exec = "%ProgramFiles%/LibreOffice/Program/soffice"
            default_lo_python = "C:/Windows/py.exe"
        elif platform == "darwin":
            default_lo_exec = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
            default_lo_python = "/Applications/LibreOffice.app/Contents/Resources/python"
            tessdata_prefix = "/opt/homebrew/share/tessdata"

        if platform in ("linux", "linux2", "darwin") and "OCR_TESSDATA_PREFIX" not in self.model_fields_set:
            self.OCR_TESSDATA_PREFIX = tessdata_prefix

        if "LIBRE_OFFICE_PYTHON_PATH" not in self.model_fields_set:
            self.LIBRE_OFFICE_PYTHON_PATH = default_lo_python
        if "LIBRE_OFFICE_EXEC_PATH" not in self.model_fields_set:
            self.LIBRE_OFFICE_EXEC_PATH = default_lo_exec

    @computed_field  # type: ignore[prop-decorator]
    @property
    def LOG_LEVEL(self) -> int:
        # 50 - CRITICAL, 40 - ERROR, 30 - WARNING, 20 - INFO, 10 - DEBUG, 0 - NOTSET
        return self.OCR_SERVICE_LOG_LEVEL

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DEBUG_MODE(self) -> bool:
        return self.OCR_SERVICE_DEBUG_MODE

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ROOT_DIR(self) -> str:
        return str(Path(__file__).resolve().parents[1])

    @computed_field  # type: ignore[prop-decorator]
    @property
    def TMP_FILE_DIR(self) -> str:
        return self.OCR_TMP_DIR or os.path.join(self.ROOT_DIR, "tmp")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def WORKER_PORT_MAP_FILE_PATH(self) -> str:
        return os.path.join(self.TMP_FILE_DIR, "./worker_process_data.txt")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def OPERATION_MODE(self) -> str:
        # possible vals : "OCR", "NO_OCR"
        return self.OCR_SERVICE_OPERATION_MODE

    @computed_field  # type: ignore[prop-decorator]
    @property
    def TESSDATA_PREFIX(self) -> str:
        return self.OCR_TESSDATA_PREFIX

    @computed_field  # type: ignore[prop-decorator]
    @property
    def TESSERACT_TIMEOUT(self) -> int:
        return self.OCR_SERVICE_TESSERACT_TIMEOUT

    @computed_field  # type: ignore[prop-decorator]
    @property
    def TESSERACT_LANGUAGE(self) -> str:
        return self.OCR_SERVICE_TESSERACT_LANG

    @computed_field  # type: ignore[prop-decorator]
    @property
    def TESSERACT_NICE(self) -> int:
        return self.OCR_SERVICE_TESSERACT_NICE

    @computed_field  # type: ignore[prop-decorator]
    @property
    def TESSERACT_CUSTOM_CONFIG_FLAGS(self) -> str:
        return self.OCR_SERVICE_TESSERACT_CUSTOM_CONFIG_FLAGS

    @computed_field  # type: ignore[prop-decorator]
    @property
    def CPU_THREADS(self) -> int:
        if self.OCR_SERVICE_CPU_THREADS is not None:
            return int(self.OCR_SERVICE_CPU_THREADS)
        return int(multiprocessing.cpu_count() / self.OCR_WEB_SERVICE_WORKERS)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def CONVERTER_THREAD_NUM(self) -> int:
        if self.OCR_SERVICE_CONVERTER_THREADS is not None:
            return int(self.OCR_SERVICE_CONVERTER_THREADS)
        return int(multiprocessing.cpu_count() / self.OCR_WEB_SERVICE_WORKERS)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def LIBRE_OFFICE_PROCESS_TIMEOUT(self) -> int:
        return self.OCR_SERVICE_LIBRE_OFFICE_PROCESS_TIMEOUT

    @computed_field  # type: ignore[prop-decorator]
    @property
    def LIBRE_OFFICE_PORT_CAP(self) -> int:
        port_cap = self.DEFAULT_LIBRE_OFFICE_SERVER_PORT + 1
        if self.OCR_WEB_SERVICE_THREADS > 1:
            port_cap = self.DEFAULT_LIBRE_OFFICE_SERVER_PORT + self.OCR_WEB_SERVICE_THREADS
        if self.OCR_WEB_SERVICE_WORKERS > 1:
            port_cap = self.DEFAULT_LIBRE_OFFICE_SERVER_PORT + self.OCR_WEB_SERVICE_WORKERS
        return port_cap

    @computed_field  # type: ignore[prop-decorator]
    @property
    def LIBRE_OFFICE_LISTENER_PORT_RANGE(self) -> range:
        if self.OCR_SERVICE_LIBRE_OFFICE_LISTENER_PORT_RANGE:
            start, end = ast.literal_eval(self.OCR_SERVICE_LIBRE_OFFICE_LISTENER_PORT_RANGE)
            return range(start, end)
        return range(self.DEFAULT_LIBRE_OFFICE_SERVER_PORT, self.LIBRE_OFFICE_PORT_CAP)

settings = Settings() # type: ignore[call-arg]
