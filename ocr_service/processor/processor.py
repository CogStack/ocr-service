from __future__ import annotations

import logging
import os
import sys
import time
import traceback
import uuid
from io import BytesIO
from multiprocessing.dummy import Pool, Queue
from subprocess import PIPE, Popen
from threading import Timer
from typing import Any, TypeVar

import pypdfium2 as pdfium
from bs4 import BeautifulSoup
from filetype.types import DOCUMENT, IMAGE, archive
from html2image import Html2Image
from PIL import Image
from striprtf.striprtf import rtf_to_text
from tesserocr import PyTessBaseAPI

from config import (
    CONVERTER_THREAD_NUM,
    CPU_THREADS,
    LIBRE_OFFICE_NETWORK_INTERFACE,
    LIBRE_OFFICE_PROCESS_TIMEOUT,
    LIBRE_OFFICE_PYTHON_PATH,
    LOG_LEVEL,
    OCR_CONVERT_GRAYSCALE_IMAGES,
    OCR_IMAGE_DPI,
    OPERATION_MODE,
    TESSDATA_PREFIX,
    TESSERACT_LANGUAGE,
    TESSERACT_TIMEOUT,
    TMP_FILE_DIR,
)
from ocr_service.utils.utils import (
    INPUT_FILTERS,
    TextChecks,
    delete_tmp_files,
    detect_file_type,
    normalise_file_name_with_ext,
    setup_logging,
    terminate_hanging_process,
)

sys.path.append("..")

PILImage = TypeVar('PILImage', bound=Image.Image)

class Processor:

    def __init__(self):
        self.log = setup_logging(component_name="processor", log_level=LOG_LEVEL)
        self.log.debug("log level set to : " + str(LOG_LEVEL))
        self.loffice_process_list = {}

    def _preprocess_html_to_img(self, stream: bytes, file_name: str) -> list[Image.Image]:
        """ Uses html2image to screenshot the page to an PIL image.

        Args:
            stream (bytes): _description_ . File byte buffer.
            file_name (str): _description_ . File Id.

        Returns:
            List[PILImage]: _description_
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
        scale = int(OCR_IMAGE_DPI / 72)

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
                grayscale=OCR_CONVERT_GRAYSCALE_IMAGES
            ).to_pil()

        with Pool(CONVERTER_THREAD_NUM) as pool:
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
        """ Converts a stream of bytes from a PDF file into images.

        Args:
            stream (bytes): _description_ . byte buffer.

        Raises:
            Exception: _description_ , coverting image to pdf exception

        Returns:
            List[PILImage]: _description_
        """

        self.log.info("pre-processing pdf...")

        pdf_image_pages: list[Image.Image] = []
        doc_metadata: dict[str, Any] = {}

        try:
            pdf_image_pages, doc_metadata = self._pdf_to_img(stream)
        except Exception:
            self.log.error("preprocessing_pdf exception: " + str(traceback.format_exc()))

        return pdf_image_pages, doc_metadata

    def _preprocess_doc(self, stream: bytes, file_name: str) -> bytes:
        """ Pre-processing step, all non-pdf(docx/doc/odt/ppt/xls etc.)
        office doc type files are sent as a stream so that they
        can be converted to PDF using libreoffice,
        stream -> pdf tmp file, it will delete all the temporary files created
        in the TMP_FILE_DIR after getting the images into memory

        Args:
            stream (bytes): _description_ . byte array from file
            file_name (str): _description_ . required file name, it will be used to create
                temporary files on disk (TMP_FILE_DIR)

        Raises:
            Exception: _description_

        Returns:
            bytes: _description_ . pdf file stream
        """

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

            doc_file_path = os.path.join(TMP_FILE_DIR, str(uid) + "_" + file_name)
            pdf_file_path =  doc_file_path[:-len(ext)] + ".pdf"

            with open(file=doc_file_path, mode="wb") as tmp_doc_file:
                tmp_doc_file.write(stream)
                os.fsync(tmp_doc_file)

            conversion_time_start = time.time()

            loffice_subprocess = None

            for port_num, loffice_process in self.loffice_process_list.items():
                if loffice_process["used"] is False:
                    used_port_num = str(port_num)
                    converter_bootstrap = "from unoserver.client import converter_main; converter_main()"
                    _args = [
                        LIBRE_OFFICE_PYTHON_PATH,
                        "-c",
                        converter_bootstrap,
                        doc_file_path,
                        pdf_file_path,
                        "--host",
                        LIBRE_OFFICE_NETWORK_INTERFACE,
                        "--port",
                        str(used_port_num),
                        "--convert-to",
                        "pdf"
                    ]

                    if input_filter:
                        _args += ["--input-filter", input_filter]

                    self.log.debug("starting unoserver subprocess with args: " + str(_args))
                    loffice_subprocess = Popen(args=_args,
                                               cwd=TMP_FILE_DIR, close_fds=True, shell=False, stdout=PIPE, stderr=PIPE)
                    self.loffice_process_list[used_port_num]["used"] = True
                    break

            if loffice_subprocess is not None and used_port_num is not None:
                loffice_timer = Timer(interval=float(LIBRE_OFFICE_PROCESS_TIMEOUT), function=loffice_subprocess.kill)
                soffice_timer = Timer(interval=float(LIBRE_OFFICE_PROCESS_TIMEOUT),
                                      function=terminate_hanging_process,
                                      args=[self.loffice_process_list[used_port_num]["process"].pid])
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
            xml_file_path = os.path.join(TMP_FILE_DIR, file_name + "_" + str(uid) + ".xml")
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

    def _process_image(self, img: Image.Image, img_id: int, tess_api: PyTessBaseAPI) -> tuple[str, int, dict]:
        """ Processes a PIL(Pillow) Image, calls tesseract ocr with the configured params

        Args:
            img (Image): _description . the actual image of a page from a PDF file
            img_id (int): _description_ . page number of the image

        Returns:
            str: _description_ . text from the image, post-ocr
        """

        tess_api.SetImage(img)
        output_str = tess_api.GetUTF8Text()

        tess_data = {}
        confidences = tess_api.AllWordConfidences()
        len_confidence = 1 if len(confidences) == 0 else len(confidences)
        tess_data["confidence"] = sum(confidences)/len_confidence

        self.log.info("finished processing img: " + str(img_id))

        return output_str, img_id, tess_data

    def _init_tesseract_api_worker(self) -> PyTessBaseAPI:
        tess_api = PyTessBaseAPI(path=TESSDATA_PREFIX, lang=TESSERACT_LANGUAGE)  # type: ignore
        self.log.debug("Initialised pytesseract api worker for language:" + str(TESSERACT_LANGUAGE))
        return tess_api

    @staticmethod
    def _resolve_content_type(file_type: object | None) -> str:
        if file_type is not None:
            return str(file_type.mime)  # type: ignore
        return "text/plain"

    def _handle_image_stream(self, stream: bytes, doc_metadata: dict[str, Any]) -> list[Image.Image]:
        if OPERATION_MODE == "NO_OCR":
            self.log.info("Detected image content; OCR skipped in NO_OCR mode")
            doc_metadata["pages"] = 1
            doc_metadata["ocr_skipped"] = True
            return []

        with Image.open(BytesIO(stream)) as imgf:
            image = imgf.copy()

        doc_metadata["pages"] = 1
        return [image]

    def _handle_pdf_stream(self, pdf_stream: bytes, doc_metadata: dict[str, Any]) -> tuple[str, list[Image.Image]]:
        output_text = ""
        images: list[Image.Image] = []

        if OPERATION_MODE == "OCR":
            images, pdf_metadata = self._preprocess_pdf_to_img(pdf_stream)
            doc_metadata.update(pdf_metadata)
        elif OPERATION_MODE == "NO_OCR":
            output_text, pdf_metadata = self._pdf_to_text(pdf_stream)
            doc_metadata.update(pdf_metadata)

        return output_text, images

    def _run_ocr_on_images(
        self,
        images: list[Image.Image],
        output_text: str,
        doc_metadata: dict[str, Any],
        file_name: str,
    ) -> str:

        image_count = len(images)
        tess_data = []

        if image_count == 0:
            return output_text

        self.log.info("A total of " + str(image_count) + " images have been generated from " + file_name)
        ocr_start_time = time.time()
        proc_results = list()

        with Pool(processes=CPU_THREADS) as process_pool:
            tess_api_q: Queue = Queue()
            for count, img in enumerate(images):
                tess_api_q.put(self._init_tesseract_api_worker())
                proc_results.append(process_pool.starmap_async(self._process_image,
                                                               [(img, count, tess_api_q.get(),)],
                                                               chunksize=1,
                                                               error_callback=logging.error))
            try:
                for result in proc_results:
                    result_data = result.get(timeout=TESSERACT_TIMEOUT)
                    _output_text, _, _tess_data = result_data[0][0], result_data[0][1], result_data[0][2]
                    output_text += str(_output_text)
                    tess_data.append(_tess_data)
            except Exception as worker_exception:
                raise Exception("OCR exception generated by worker: "
                                + str(traceback.format_exc())) from worker_exception
            finally:
                for tess_api in tess_api_q.queue:
                    tess_api.End()

        ocr_end_time = time.time()

        self.log.info(f"OCR processing finished | Elapsed : {ocr_end_time - ocr_start_time:.4f} seconds")

        doc_metadata["pages"] = image_count
        doc_metadata["confidence"] = round(sum([page["confidence"] for page in tess_data]) / image_count, 4)

        return output_text

    @staticmethod
    def _finalize_output_text(output_text: str) -> str:
        output_text = output_text.translate({'\\n': '', '\\t': '', '\n\n': '\n'})  # type: ignore
        return str(output_text).encode("utf-8", errors="replace").decode("utf-8")

    def _process(self, stream: bytes, file_name: str) -> tuple[str, dict]:
        """ Processes a stream of bytes, resulting in the output string
        files have their type detected and then managed accordingly to their requirements
        images will be directly OCRed, while actual documents will undergo
        the following process : byte_stream -> convert to pdf -> convert each pdf page to images ->
        -> multiprocess ocr for the images -> output string text

        Args:
            stream (bytes): _description_ .  byte array from file
            file_name (str): _description_ . required file name, it will be used to create
                temporary files on disk (TMP_FILE_DIR)

        Raises:
            Exception: _description_

        Returns:
            str: _description_
        """

        file_type = detect_file_type(stream)
        output_text: str = ""
        images: list[Image.Image] = []
        doc_metadata: dict[str, Any] = {"content-type": self._resolve_content_type(file_type)}
        checks = TextChecks(stream)

        file_name = normalise_file_name_with_ext(file_name, stream)

        try:
            pdf_stream: bytes = b""

            self.log.info("Checking file type for doc id: " + file_name)

            if type(file_type) is archive.Pdf:
                pdf_stream = stream
            elif file_type in DOCUMENT or type(file_type) is archive.Rtf or checks.is_rtf():
                pdf_stream = self._preprocess_doc(stream, file_name=file_name)
            elif file_type in IMAGE:
                images = self._handle_image_stream(stream, doc_metadata)
            elif checks.is_xml() and not checks.is_html():
                self.log.info("Detected XML content; converting to pdf")
                doc_metadata["content-type"] = "text/xml"
                pdf_stream = self._preprocess_xml_to_pdf(stream, file_name=file_name)
                # if we get no content still then just run it through libreoffice converter
                if not pdf_stream:
                    pdf_stream = self._preprocess_doc(stream, file_name=file_name)
            elif checks.is_html():
                self.log.info("Detected HTML content; converting to pdf via unoserver/LO")
                pdf_stream = self._preprocess_doc(stream, file_name=file_name)
            elif checks.is_plain_text():
                self.log.info("Unknown text-like content; treating as plain text, skipping unoserver/LO conversion")
                output_text = stream.decode("utf-8", "ignore")
                doc_metadata["pages"] = 1
            else:
                self.log.info("Unknown file type; attempting to convert to pdf via unoserver/LO ")
                # if the file has no type attempt to convert it to pdf anyways
                pdf_stream = self._preprocess_doc(stream, file_name=file_name)

            # ── LO fallback: no PDF, but maybe we can still return text ──
            if not pdf_stream and not output_text and checks.is_text_like():
                self.log.warning(
                    "No PDF produced for %s; falling back to plain-text extraction",
                    file_name,
                )
                output_text = self._extract_text_fallback(
                    stream,
                    is_html=checks.is_html(),
                    is_xml=checks.is_xml(),
                    is_rtf=checks.is_rtf(),
                )
                doc_metadata["pages"] = 1
                doc_metadata["content-type"] = "text/plain"

            if pdf_stream:
                output_text, images = self._handle_pdf_stream(pdf_stream, doc_metadata)

            self.log.info("Detected file type for doc id: " + file_name + " | " + str(doc_metadata["content-type"]))

            output_text = self._run_ocr_on_images(images, output_text, doc_metadata, file_name)
            output_text = self._finalize_output_text(output_text)

        except Exception as converter_exception:
            raise Exception("Failed to convert/generate image content: " 
                            + str(traceback.format_exc())) from converter_exception

        return output_text, doc_metadata

    def process_stream(self, stream: bytes, file_name: str = "") -> tuple[str, dict]:
        """ Sends the stream of bytes to the `_process` function
        that will do all the pre-processing + ocr-ing work

        Args:
            stream (bytes): _description_. byte array from file
            file_name (str, optional): _description_. Defaults to "",
                 file id generated by the service(if none provided)
                 or the actual file name if the file was provided with the `file` parameter

        Returns:
            tuple : _description_ . output_text post-ocr and
                doc_metadata containing doc info like number of pages, author etc
        """

        output_text = ""
        doc_metadata: dict[str, Any] = {}
        elapsed_time: float = 0.0

        try:
            self.log.info("Processing file name:" + file_name)
            start_time = time.time()
            output_text, doc_metadata = self._process(stream, file_name=file_name)

            end_time = time.time()
            elapsed_time = float(round(float(end_time - start_time), 4))
            doc_metadata["elapsed_time"] = elapsed_time

            self.log.info("Finished processing file: " + file_name + " | Elapsed time: " + str(elapsed_time)
                          + " seconds")
        except Exception:
            traceback.print_exc(file=sys.stdout)

        return output_text, doc_metadata
