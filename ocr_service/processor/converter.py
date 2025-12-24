from __future__ import annotations

import os
import time
import traceback
import uuid
from io import BytesIO
from multiprocessing.dummy import Pool
from subprocess import PIPE, Popen
from threading import Timer
from typing import Any, cast

import pypdfium2 as pdfium
from bs4 import BeautifulSoup
from filetype.types import DOCUMENT, IMAGE, archive
from PIL import Image
from striprtf.striprtf import rtf_to_text

from ocr_service.dto.process_context import ProcessContext
from ocr_service.settings import settings
from ocr_service.utils.utils import INPUT_FILTERS, delete_tmp_files, terminate_hanging_process


class DocumentConverter:
    def __init__(self, log, loffice_process_list: dict[str, Any]) -> None:
        self.log = log
        self.loffice_process_list = loffice_process_list

    @staticmethod
    def resolve_content_type(file_type: object | None) -> str:
        if file_type is not None:
            return str(file_type.mime)  # type: ignore
        return "text/plain"

    @staticmethod
    def finalize_output_text(output_text: str) -> str:
        output_text = output_text.translate({'\\n': '', '\\t': '', '\n\n': '\n'})  # type: ignore
        return str(output_text).encode("utf-8", errors="replace").decode("utf-8")

    def _extract_text_fallback(self, stream: bytes, *, is_html: bool, is_xml: bool, is_rtf: bool) -> str:
        """Best-effort text extraction when LO conversion fails."""
        text = ""

        if is_html or is_xml:
            parser = "html.parser" if is_html else "xml"
            try:
                soup = BeautifulSoup(stream, parser)
            except Exception:
                self.log.warning("Failed to parse HTML/XML during fallback with %s; retrying with html.parser", parser)
                try:
                    soup = BeautifulSoup(stream, "html.parser")
                    text = soup.get_text(separator="\n")
                except Exception:
                    self.log.warning("Failed to parse HTML/XML during fallback; using raw decode")
            else:
                text = soup.get_text(separator="\n")

        if not text and is_rtf:
            try:
                text = rtf_to_text(stream.decode("utf-8", "ignore"))
            except Exception:
                self.log.warning("Failed to parse RTF during fallback; using raw decode")

        if not text:
            text = stream.decode("utf-8", "ignore")

        return text.strip()

    def _pdf_to_img(self, stream: bytes) -> tuple[list[Image.Image], dict]:
        pdf_image_pages = []
        doc_metadata: dict[str, Any] = {}

        pdf = pdfium.PdfDocument(stream)

        pdf_conversion_start_time = time.time()
        scale = int(settings.OCR_SERVICE_IMAGE_DPI / 72)

        def render_page(index: int) -> Image.Image:
            page = pdf[index]
            return page.render(
                scale=scale,
                may_draw_forms=False,
                no_smoothtext=True,
                no_smoothimage=True,
                no_smoothpath=True,
                rotation=0,
                crop=(0, 0, 0, 0),
                grayscale=settings.OCR_CONVERT_GRAYSCALE_IMAGES
            ).to_pil()

        with Pool(settings.CONVERTER_THREAD_NUM) as pool:
            pdf_image_pages = pool.map(render_page, range(len(pdf)))

        pdf_conversion_end_time = time.time()

        self.log.info("PDF conversion to image(s) finished | Elapsed : " +
                      str(pdf_conversion_end_time - pdf_conversion_start_time) + " seconds")

        return pdf_image_pages, doc_metadata

    def _pdf_to_text(self, stream: bytes) -> tuple[str, dict]:
        doc_metadata = {}
        output_text = ""

        pdf = pdfium.PdfDocument(stream)

        doc_metadata["pages"] = len(pdf)
        for page in pdf:
            textpage = page.get_textpage()
            output_text += textpage.get_text_bounded()

        return output_text, doc_metadata

    def _preprocess_pdf_to_img(self, stream: bytes) -> tuple[list[Image.Image], dict]:
        """Converts a stream of bytes from a PDF file into images."""
        self.log.info("pre-processing pdf...")

        pdf_image_pages: list[Image.Image] = []
        doc_metadata: dict[str, Any] = {}

        try:
            pdf_image_pages, doc_metadata = self._pdf_to_img(stream)
        except Exception:
            self.log.error("preprocessing_pdf exception: " + str(traceback.format_exc()))

        return pdf_image_pages, doc_metadata

    def _preprocess_doc(self, stream: bytes, file_name: str) -> bytes:
        """Pre-processing step for non-pdf office docs via LibreOffice."""
        pdf_stream = b""
        doc_file_path = ""
        pdf_file_path = ""
        used_port_num = None

        ext = os.path.splitext(file_name)[1].lower()

        # unoserver 3.0+ (TBD)
        input_filter = INPUT_FILTERS.get(ext)

        try:
            # generate unique id
            uid = uuid.uuid4().hex

            doc_file_path = os.path.join(settings.TMP_FILE_DIR, str(uid) + "_" + file_name)
            pdf_file_path = doc_file_path[:-len(ext)] + ".pdf"

            with open(file=doc_file_path, mode="wb") as tmp_doc_file:
                tmp_doc_file.write(stream)
                os.fsync(tmp_doc_file)

            conversion_time_start = time.time()

            loffice_subprocess = None

            for port_num, loffice_process in self.loffice_process_list.items():
                if loffice_process["used"] is False:
                    used_port_num = str(port_num)
                    lo_python = cast(str, settings.LIBRE_OFFICE_PYTHON_PATH)
                    converter_bootstrap = "from unoserver.client import converter_main; converter_main()"
                    _args = [
                        lo_python,
                        "-c",
                        converter_bootstrap,
                        doc_file_path,
                        pdf_file_path,
                        "--host",
                        settings.LIBRE_OFFICE_NETWORK_INTERFACE,
                        "--port",
                        str(used_port_num),
                        "--convert-to",
                        "pdf"
                    ]

                    if input_filter:
                        _args += ["--input-filter", input_filter]

                    self.log.debug("starting unoserver subprocess with args: " + str(_args))
                    loffice_subprocess = Popen(
                        args=_args,
                        cwd=settings.TMP_FILE_DIR,
                        close_fds=True,
                        shell=False,
                        stdout=PIPE,
                        stderr=PIPE,
                    )
                    self.loffice_process_list[used_port_num]["used"] = True
                    break

            if loffice_subprocess is not None and used_port_num is not None:
                loffice_timer = Timer(
                    interval=float(settings.LIBRE_OFFICE_PROCESS_TIMEOUT),
                    function=loffice_subprocess.kill,
                )
                soffice_timer = Timer(
                    interval=float(settings.LIBRE_OFFICE_PROCESS_TIMEOUT),
                                      function=terminate_hanging_process,
                    args=[self.loffice_process_list[used_port_num]["process"].pid],
                )
                try:
                    loffice_timer.start()
                    stdout, stderr = loffice_subprocess.communicate()
                    soffice_timer.start()

                    rc = loffice_subprocess.returncode
                    if rc != 0:
                        self.log.error(
                            "unoserver failed rc=%s for %s -> %s\nstdout=%s\nstderr=%s",
                            rc, doc_file_path, pdf_file_path,
                            stdout.decode("utf-8", "ignore"),
                            stderr.decode("utf-8", "ignore"),
                        )
                        self.loffice_process_list[used_port_num]["unhealthy"] = True

                finally:
                    loffice_timer.cancel()
                    soffice_timer.cancel()
                    if loffice_subprocess and loffice_subprocess.poll() is None:
                        loffice_subprocess.kill()

                    if os.path.isfile(pdf_file_path):
                        with open(file=pdf_file_path, mode="rb") as tmp_pdf_file:
                            os.fsync(tmp_pdf_file.fileno())
                            pdf_stream = tmp_pdf_file.read()
                    else:
                        self.log.info("libre office did not produce any output for file: " +
                                      str(pdf_file_path) + " | port:" + str(used_port_num))

            else:
                raise Exception("could not find libre office server process on port:" + str(used_port_num))

            conversion_time_end = time.time()
            self.log.info("doc conversion to PDF finished | Elapsed : " +
                          str(conversion_time_end - conversion_time_start) + " seconds")

        except Exception as exception:
            raise Exception("doc name:" + str(file_name)
                            + " | tmp_file internal name: "
                            + str(doc_file_path)
                            + " | preprocessing_doc exception: "
                            + str(traceback.format_exc())) from exception

        finally:
            if used_port_num:
                self.loffice_process_list[used_port_num]["used"] = False
            delete_tmp_files([doc_file_path, pdf_file_path])

        return pdf_stream

    def _preprocess_xml_to_pdf(self, stream: bytes, file_name: str) -> bytes:
        pdf_stream = b""
        pdf_file_path = ""
        xml_file_path = ""

        try:
            from pyxml2pdf.core.initializer import Initializer

            # generate unique id
            uid = uuid.uuid4().hex
            xml_file_path = os.path.join(settings.TMP_FILE_DIR, file_name + "_" + str(uid) + ".xml")
            pdf_file_path = xml_file_path + ".pdf"

            with open(file=xml_file_path, mode="wb") as tmp_doc_file:
                tmp_doc_file.write(stream)
                os.fsync(tmp_doc_file)

            _pdfinit = Initializer(xml_file_path, pdf_file_path)  # noqa: F841

            if os.path.exists(pdf_file_path):
                with open(file=pdf_file_path, mode="rb") as tmp_pdf_file:
                    pdf_stream = tmp_pdf_file.read()
                    os.fsync(tmp_pdf_file)
        except Exception:
            self.log.error("xml doc name:" + str(file_name) + " | "
                           + "preprocess_xml_to_pdf exception: " + str(traceback.format_exc()))
        finally:
            delete_tmp_files([xml_file_path, pdf_file_path])

        return pdf_stream

    def _handle_image_stream(self, ctx: ProcessContext) -> list[Image.Image]:
        if settings.OPERATION_MODE == "NO_OCR":
            self.log.info("Detected image content; OCR skipped in NO_OCR mode")
            ctx.metadata["pages"] = 1
            ctx.metadata["ocr_skipped"] = True
            return []

        with Image.open(BytesIO(ctx.stream)) as imgf:
            image = imgf.copy()

        ctx.metadata["pages"] = 1
        return [image]

    def _handle_pdf_stream(self, ctx: ProcessContext) -> None:
        if settings.OPERATION_MODE == "OCR":
            ctx.images, pdf_metadata = self._preprocess_pdf_to_img(ctx.pdf_stream)
            ctx.metadata.update(pdf_metadata)
        elif settings.OPERATION_MODE == "NO_OCR":
            ctx.output_text, pdf_metadata = self._pdf_to_text(ctx.pdf_stream)
            ctx.metadata.update(pdf_metadata)

    def prepare(self, ctx: ProcessContext) -> None:
        self.log.info("Checking file type for doc id: " + ctx.file_name)

        if type(ctx.file_type) is archive.Pdf:
            ctx.pdf_stream = ctx.stream
        elif ctx.file_type in DOCUMENT or type(ctx.file_type) is archive.Rtf or ctx.checks.is_rtf():
            ctx.pdf_stream = self._preprocess_doc(ctx.stream, file_name=ctx.file_name)
        elif ctx.file_type in IMAGE:
            ctx.images = self._handle_image_stream(ctx)
        elif ctx.checks.is_xml() and not ctx.checks.is_html():
            self.log.info("Detected XML content; converting to pdf")
            ctx.metadata["content-type"] = "text/xml"
            ctx.pdf_stream = self._preprocess_xml_to_pdf(ctx.stream, file_name=ctx.file_name)
            # if we get no content still then just run it through libreoffice converter
            if not ctx.pdf_stream:
                ctx.pdf_stream = self._preprocess_doc(ctx.stream, file_name=ctx.file_name)
        elif ctx.checks.is_html():
            self.log.info("Detected HTML content; converting to pdf via unoserver/LO")
            ctx.pdf_stream = self._preprocess_doc(ctx.stream, file_name=ctx.file_name)
        elif ctx.checks.is_plain_text():
            self.log.info("Unknown text-like content; treating as plain text, skipping unoserver/LO conversion")
            ctx.output_text = ctx.stream.decode("utf-8", "ignore")
            ctx.metadata["pages"] = 1
        else:
            self.log.info("Unknown file type; attempting to convert to pdf via unoserver/LO ")
            ctx.pdf_stream = self._preprocess_doc(ctx.stream, file_name=ctx.file_name)

        # ── LO fallback: no PDF, but maybe we can still return text ──
        if not ctx.pdf_stream and not ctx.output_text and ctx.checks.is_text_like():
            self.log.warning(
                "No PDF produced for %s; falling back to plain-text extraction",
                ctx.file_name,
            )
            ctx.output_text = self._extract_text_fallback(
                ctx.stream,
                is_html=ctx.checks.is_html(),
                is_xml=ctx.checks.is_xml(),
                is_rtf=ctx.checks.is_rtf(),
            )
            ctx.metadata["pages"] = 1
            ctx.metadata["content-type"] = "text/plain"

        if ctx.pdf_stream:
            self._handle_pdf_stream(ctx)
