"""Utility helpers for the OCR service.

This module centralizes shared behaviors across the API and processor layers,
including response shaping, file type detection, text heuristics, LibreOffice
process management, and logging setup. It also contains a legacy HTML-to-image
converter kept for reference.
"""

import contextlib
import fcntl
import json
import logging
import os
import shutil
import string
import sys
import xml.sax
from datetime import datetime
from pathlib import Path
from sys import platform
from typing import Any

import filetype
import psutil
from html2image import Html2Image
from PIL import Image

from config import (
    LIBRE_OFFICE_LISTENER_PORT_RANGE,
    OCR_CONVERT_GRAYSCALE_IMAGES,
    OCR_SERVICE_VERSION,
    TESSDATA_PREFIX,
    TMP_FILE_DIR,
    WORKER_PORT_MAP_FILE_PATH,
)

INPUT_FILTERS: dict[str, str] = {
    # ── Writer / text ──
    ".odt":   "writer8",
    ".ott":   "writer8_template",
    ".fodt":  "OpenDocument Text Flat XML",
    ".sxw":   "StarOffice XML (Writer)",
    ".stw":   "writer_StarOffice_XML_Writer_Template",
    ".hwp":   "writer_MIZI_Hwp_97",
    ".psw":   "PocketWord File",
    ".rtf":   "Rich Text Format",
    ".doc":   "MS Word 97",
    ".wps":   "MS Word 97",
    ".dot":   "MS Word 97 Vorlage",
    ".docx":  "MS Word 2007 XML",
    ".dotx":  "MS Word 2007 XML Template",
    ".dotm":  "MS Word 2007 XML Template",
    ".html":  "HTML (StarWriter)",   # picked Writer as the default
    ".htm":   "HTML (StarWriter)",
    ".xhtml": "HTML (StarWriter)",
    ".txt":   "Text",                # treat as Writer text, not Calc CSV

    # ── Calc / spreadsheets ──
    ".ods":   "calc8",
    ".ots":   "calc8_template",
    ".fods":  "OpenDocument Spreadsheet Flat XML",
    ".sxc":   "StarOffice XML (Calc)",
    ".stc":   "calc_StarOffice_XML_Calc_Template",

    ".csv":   "Text - txt - csv (StarCalc)",
    ".tsv":   "Text - txt - csv (StarCalc)",
    ".tab":   "Text - txt - csv (StarCalc)",
    ".dbf":   "dBase",

    ".wk1":   "Lotus",
    ".wks":   "Lotus",
    ".123":   "Lotus",
    ".wb2":   "Quattro Pro 6.0",

    ".xls":   "MS Excel 97",
    ".xlc":   "MS Excel 97",
    ".xlm":   "MS Excel 97",
    ".xlw":   "MS Excel 97",
    ".xlk":   "MS Excel 97",
    ".et":    "MS Excel 97",

    ".xlt":   "MS Excel 97 Vorlage/Template",
    ".ett":   "MS Excel 97 Vorlage/Template",

    ".xlsx":  "Calc Office Open XML",
    ".xlsm":  "Calc Office Open XML",
    ".xltx":  "Calc Office Open XML Template",
    ".xltm":  "Calc Office Open XML Template",
    ".xlsb":  "Calc MS Excel 2007 Binary",

    ".gnumeric": "Gnumeric Spreadsheet",
    ".gnm":      "Gnumeric Spreadsheet",
    ".parquet":  "Apache Parquet Spreadsheet",
    ".cwk":      "Claris_Resolve_Calc",
    ".numbers":  "Apple Numbers",

    # ── Impress / presentations ──
    ".odp":   "impress8",
    ".otp":   "impress8_template",
    ".sxi":   "StarOffice XML (Impress)",
    ".sti":   "impress_StarOffice_XML_Impress_Template",
    ".ppt":   "MS PowerPoint 97",
    ".pptx":  "Impress MS PowerPoint 2007 XML",
    ".key":   "Apple Keynote",

    # ── Draw / graphics ──
    ".odg":   "draw8",
    ".std":   "draw_StarOffice_XML_Draw_Template",

    # ── Math / formulas ──
    ".odf":   "math8",
}

def get_app_info() -> dict:
    """Return general information about the application.

    Used by the `/api/info` endpoint.

    Returns:
        dict: Application information (name, version, model path, config placeholder).
    """
    return {"service_app_name": "ocr-service",
            "service_version": OCR_SERVICE_VERSION,
            "service_model": TESSDATA_PREFIX,
            "config": ""}


def build_response(
    text,
    success: bool = True,
    log_message: str = "",
    footer: dict | None = None,
    metadata: dict | None  = None,
    allow_empty_text: bool = False
) -> dict[str, Any]:
    """Build a standard API response payload.

    Args:
        text: Extracted/OCR'd text.
        success: Default success value (overridden by text/allow_empty_text).
        log_message: Optional status message to attach to metadata.
        footer: Optional footer payload from the original request.
        metadata: Document metadata (content-type, pages, confidence, etc.).
        allow_empty_text: Treat empty text as success (e.g., NO_OCR image inputs).

    Returns:
        dict[str, Any]: Normalized response structure for the API.
    """

    if metadata is None:
        metadata = {}

    if len(text) > 0:
        success = True
    elif allow_empty_text:
        success = True
        if not log_message:
            log_message = "OCR skipped; no text generated."
    else:
        success = False
        log_message = "No text has been generated."

    metadata["log_message"] = log_message

    return {
        "text": text,
        "footer": footer,
        "metadata": metadata,
        "success": str(success),
        "timestamp": str(datetime.now())
    }


def delete_tmp_files(file_paths: list[str]) -> None:
    """Delete temporary files if they exist.

    Args:
        file_paths: Paths to delete (missing paths are ignored).
    """
    for file_path in file_paths:
        if os.path.exists(file_path):
            os.remove(file_path)

PRINTABLE = set(bytes(string.printable, "ascii")) | {9, 10, 13}

def is_file_content_plain_text(stream: bytes, threshold: float = 0.95) -> bool:
    """Heuristic to determine whether a byte stream is likely plain text.

    Args:
        stream: Raw bytes to inspect.
        threshold: Ratio of printable ASCII bytes required to treat as text.

    Returns:
        bool: True if the stream appears to be text-like.
    """
    if not stream:
        return False

    sample = stream[:4096]

    # If it can't be decoded as UTF-8 at all, treat as binary
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return False

    printable = sum(1 for b in sample if b in PRINTABLE)
    return printable / len(sample) >= threshold

def is_file_type_html(stream: bytes) -> bool:
    """Detect HTML content by scanning the head of the stream.

    Args:
        stream: Raw bytes to inspect.

    Returns:
        bool: True if HTML markers are found.
    """
    head = stream[:2048].decode(errors="ignore").lower()
    return "<html" in head or "<!doctype html" in head

def is_file_type_xml(stream: bytes) -> bool:
    """Detect XML content by attempting to parse the stream.

    Args:
        stream: Raw bytes to inspect.

    Returns:
        bool: True if XML parsing succeeds.
    """
    try:
        xml.sax.parseString(stream, xml.sax.ContentHandler())
        return True
    except Exception:
        logging.warning("Could not determine if file is XML.")
    return False

def is_file_type_rtf(stream: bytes) -> bool:
    """Detect RTF content by checking for the RTF header magic bytes.

    Args:
        stream: Raw bytes to inspect.

    Returns:
        bool: True if the stream starts with the RTF header.
    """
    head = stream[:32].lstrip()
    return head.startswith(b"{\\rtf")


class TextChecks:
    """Lazy, cached text-type detection helpers for a single stream."""
    __slots__ = ("stream", "_is_html", "_is_xml", "_is_rtf", "_is_plain_text")

    def __init__(self, stream: bytes) -> None:
        """Initialize with the stream to inspect."""
        self.stream = stream
        self._is_html: bool | None = None
        self._is_xml: bool | None = None
        self._is_rtf: bool | None = None
        self._is_plain_text: bool | None = None

    def is_html(self) -> bool:
        """Return True if the stream appears to be HTML."""
        if self._is_html is None:
            self._is_html = is_file_type_html(self.stream)
        return self._is_html

    def is_xml(self) -> bool:
        """Return True if the stream appears to be XML."""
        if self._is_xml is None:
            self._is_xml = is_file_type_xml(self.stream)
        return self._is_xml

    def is_rtf(self) -> bool:
        """Return True if the stream appears to be RTF."""
        if self._is_rtf is None:
            self._is_rtf = is_file_type_rtf(self.stream)
        return self._is_rtf

    def is_plain_text(self) -> bool:
        """Return True if the stream appears to be plain text."""
        if self._is_plain_text is None:
            self._is_plain_text = is_file_content_plain_text(self.stream)
        return self._is_plain_text

    def is_text_like(self) -> bool:
        """Return True if the stream is HTML/XML/RTF/plain text."""
        return self.is_plain_text() or self.is_html() or self.is_xml() or self.is_rtf()


def preprocess_html_to_img(stream: bytes, file_name: str) -> list[Image.Image]:
    """Render HTML to a screenshot image via html2image.

    This is a legacy path kept for reference. It requires a working installation
    of Chromium/Chrome/Firefox on the host or container. The current pipeline
    uses LibreOffice for HTML to PDF conversion instead.

    Args:
        stream: HTML content bytes.
        file_name: Base name used for the temporary PNG file.

    Returns:
        list[Image.Image]: A single rendered image.
    """
    hti = Html2Image(output_path=TMP_FILE_DIR, temp_path=TMP_FILE_DIR)
    png_img_file_name: str = file_name + ".png"
    png_img_file_path = os.path.join(TMP_FILE_DIR, png_img_file_name)

    image: Image.Image = Image.Image()

    try:
        html_str = stream.decode("utf-8", errors="replace")
        hti.screenshot(html_str=html_str, save_as=png_img_file_name)

        with Image.open(png_img_file_path) as imgf:
            image = imgf.convert("RGB").copy() if not OCR_CONVERT_GRAYSCALE_IMAGES else imgf.convert("L")

    finally:
        delete_tmp_files([png_img_file_path])

    return [image]


def detect_file_type(stream: bytes) -> object | None:
    """Best-effort file type detection using the `filetype` library.

    Args:
        stream: Raw bytes to inspect.

    Returns:
        object | None: Detected type descriptor or None if unknown.
    """
    file_type = None
    try:
        file_type = filetype.guess(stream)
    except Exception:
        logging.error("Could not determine file Type")
    return file_type


def normalise_file_name_with_ext(file_name: str, stream: bytes) -> str:
    """Normalize filename and ensure an extension is present.

    LibreOffice relies on a reasonable filename with an extension to select
    conversion filters. This helper preserves any provided extension and
    falls back to content-based detection when missing.

    Args:
        file_name: Original file name (may be empty or extension-less).
        stream: File content used for extension inference.

    Returns:
        str: Normalized file name with an extension.
    """

    name = file_name or "document"
    base, ext = os.path.splitext(name)

    if not base:
        base = "document"

    # 1) if caller already provided an extension, keep it
    if ext:
        return base + ext

    # 2) let filetype guess it from content
    guessed_ext = filetype.guess_extension(stream)
    if guessed_ext:
        return f"{base}.{guessed_ext}"

    # 3) fallbacks for texty formats our filetype may not catch
    if is_file_type_html(stream):
        return base + ".html"
    if is_file_type_xml(stream):
        return base + ".xml"
    if is_file_type_rtf(stream):
        return base + ".rtf"

    # last resort
    return base + ".txt"

def terminate_hanging_process(process_id: int) -> None:
    """Terminate a process tree by PID.

    Args:
        process_id: Process ID to terminate (no-op if falsy).
    """

    if not process_id:
        logging.warning("No process ID given or process ID is empty")
        return

    try:
        parent = psutil.Process(process_id)
    except psutil.NoSuchProcess:
        logging.warning(f"Process {process_id} does not exist")
        return

    children = parent.children(recursive=True)

    # First try terminate
    for p in children + [parent]:
        with contextlib.suppress(Exception):
            p.terminate()

    gone, alive = psutil.wait_procs(children + [parent], timeout=3)

    # Force kill anything still alive
    for p in alive:
        with contextlib.suppress(Exception):
            p.kill()

    logging.warning(
        "Killed process tree rooted at pid=%s (children=%s)",
        process_id,
        [c.pid for c in children],
    )


def _active_lo_profiles() -> set[str]:
    """Return the set of LibreOffice profile paths used by running processes.

    Returns:
        set[str]: Normalized profile paths discovered in running soffice processes.
    """
    active: set[str] = set()
    for proc in psutil.process_iter(attrs=["cmdline"]):
        try:
            cmd = proc.info.get("cmdline") or []
            if "--user-installation" not in cmd:
                continue
            idx = cmd.index("--user-installation")
            if idx + 1 >= len(cmd):
                continue
            profile = cmd[idx + 1]
            profile = profile.replace("file://", "")
            active.add(os.path.normpath(profile))
        except Exception:
            continue
    return active


def cleanup_stale_lo_profiles(tmp_dir: str = TMP_FILE_DIR) -> None:
    """Remove LibreOffice profile folders not used by any running process.

    Args:
        tmp_dir: Base directory containing LibreOffice profile folders.
    """
    base = Path(tmp_dir)
    if not base.exists():
        return

    active_profiles = _active_lo_profiles()

    for profile_dir in base.glob("lo_profile_*"):
        try:
            resolved = os.path.normpath(str(profile_dir))
            if resolved in active_profiles:
                continue
            if profile_dir.is_dir():
                shutil.rmtree(profile_dir, ignore_errors=True)
                logging.info("Removed stale LibreOffice profile: %s", profile_dir)
        except Exception as exc:
            logging.warning("Failed to remove stale LibreOffice profile %s: %s", profile_dir, exc)


def get_process_id_by_process_name(process_name: str = "") -> int:
    """Return the first matching PID for a process name or path fragment.

    Used primarily to locate LibreOffice/soffice processes for cleanup.

    Args:
        process_name: Substring to match against process names.

    Returns:
        int: Matching process ID, or -1 if not found.
    """

    pid: int = -1

    if "soffice" in process_name:
        soffice_process_name = "soffice"
        if platform == "linux" or platform == "linux2":
            soffice_process_name = "soffice.bin"
    else:
        soffice_process_name = ""

    for proc in psutil.process_iter():
        if proc.name() in process_name or proc.name() in soffice_process_name:
            pid = proc.pid
            break

    return pid


def sync_port_mapping(worker_id: int = -1, worker_pid: int = -1):
    """Persist LibreOffice port-to-worker PID mapping for multi-worker setups.

    Args:
        worker_id: Gunicorn worker index.
        worker_pid: Process ID for the worker.
    """
    open_mode = "r+"

    if not os.path.exists(WORKER_PORT_MAP_FILE_PATH):
        open_mode = "w+"

    with open(WORKER_PORT_MAP_FILE_PATH, encoding="utf-8", mode=open_mode) as f:
        fcntl.lockf(f, fcntl.LOCK_EX)

        port_mapping = {}
        text = f.read()

        if len(text) > 0:
            port_mapping = json.loads(text)

        port_mapping[str(LIBRE_OFFICE_LISTENER_PORT_RANGE[0] + worker_id)] = str(worker_pid)
        output = json.dumps(port_mapping, indent=1)
        f.seek(0)
        f.truncate(0)
        f.write(output)
        fcntl.lockf(f, fcntl.LOCK_UN)


def get_assigned_port(current_worker_pid: int) -> int:
    """Return the LibreOffice port previously assigned to a worker PID.

    Args:
        current_worker_pid: PID of the current worker process.

    Returns:
        int: Assigned port, or the default base port if not found.
    """
    port_mapping: dict = {}

    open_mode = "r+"

    if os.path.exists(WORKER_PORT_MAP_FILE_PATH):
        with open(WORKER_PORT_MAP_FILE_PATH, encoding="utf-8", mode=open_mode) as f:
            text = f.read()
            if len(text) > 0:
                port_mapping = json.loads(text)
                for port_num, worker_pid in port_mapping.items():
                    if int(worker_pid) == int(current_worker_pid):
                        return int(port_num)

    return int(LIBRE_OFFICE_LISTENER_PORT_RANGE[0])


def setup_logging(component_name: str = "config_logger", log_level: int = 20) -> logging.Logger:
    """Configure a logger that writes to stdout with a consistent format.

    Args:
        component_name: Logger name to configure.
        log_level: Logging level to set on the logger and handler.

    Returns:
        logging.Logger: Configured logger instance.
    """
    root_logger = logging.getLogger(component_name)
    log_format = '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
    log_handler = logging.StreamHandler(sys.stdout)
    log_handler.setFormatter(logging.Formatter(fmt=log_format))
    log_handler.setLevel(level=log_level)
    root_logger.setLevel(level=log_level)
    root_logger.propagate = False

    # only add the handler if a previous one does not exists
    handler_exists = False
    for h in root_logger.handlers:
        if isinstance(h, logging.StreamHandler) and h.level is log_handler.level:
            handler_exists = True
            break

    if not handler_exists:
        root_logger.addHandler(log_handler)

    return root_logger
