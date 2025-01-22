from __future__ import annotations

import json
import logging
import os
import sys
import time
import traceback
import uuid

from subprocess import PIPE, Popen
from io import BytesIO
from typing import List, TypeVar

import injector
import pypdfium2 as pdfium

from tesserocr import get_languages, PyTessBaseAPI
from filetype.types import DOCUMENT, IMAGE, archive, document, image
from html2image import Html2Image
from PIL import Image

from threading import Timer

from multiprocessing.dummy import Pool, Queue

from config import CONVERTER_THREAD_NUM, CPU_THREADS, LIBRE_OFFICE_NETWORK_INTERFACE, LOG_LEVEL, TMP_FILE_DIR, \
                   OCR_IMAGE_DPI, OPERATION_MODE, TESSDATA_PREFIX, TESSERACT_LANGUAGE, \
                   TESSERACT_TIMEOUT, LIBRE_OFFICE_PROCESS_TIMEOUT, LIBRE_OFFICE_PYTHON_PATH
from ocr_service.utils.utils import delete_tmp_files, detect_file_type, is_file_type_xml, setup_logging, \
                                    terminate_hanging_process

sys.path.append("..")

PILImage = TypeVar('PILImage', bound=Image)


class Processor:

    @injector.inject
    def __init__(self):
        app_log_level = os.getenv("LOG_LEVEL", LOG_LEVEL)
        self.log = setup_logging(component_name="processor", log_level=app_log_level)
        self.log.debug("log level set to : " + str(app_log_level))
        self.loffice_process_list = {}

    def _preprocess_html_to_img(self, stream: bytes, file_name: str) -> List[PILImage]:
        """ Uses html2image to screenshot the page to an PIL image.

        Args:
            stream (bytes): _description_ . File byte buffer.
            file_name (str): _description_ . File Id.

        Returns:
            List[PILImage]: _description_
        """   
        hti = Html2Image(output_path=TMP_FILE_DIR, temp_path=TMP_FILE_DIR)
        html_file_path = os.path.join(TMP_FILE_DIR, file_name)
        png_img_file_path = html_file_path + ".png"

        try:
            with open(file=html_file_path, mode="wb") as tmp_html_file:
                tmp_html_file.write(stream)

            hti.screenshot(html_str=html_file_path, save_as=png_img_file_path)
        finally:
            delete_tmp_files([png_img_file_path])

        return [Image.open(BytesIO(png_img_file_path))]

    def _pdf_to_img(self, stream: bytes) -> List[PILImage]:
        pdf_image_pages = []
        doc_metadata = {}
        with pdfium.PdfDocument(stream) as pdf:
            pdf_conversion_start_time = time.time()
            renderer = pdf.render_topil(pdfium.BitmapConv.pil_image,
                                        page_indices=range(len(pdf)),
                                        scale=OCR_IMAGE_DPI/72,
                                        n_processes=CONVERTER_THREAD_NUM)

            pdf_image_pages = list(renderer)
            pdf_conversion_end_time = time.time()

            self.log.info("PDF conversion to image(s) finished | Elapsed : " +
                          str(pdf_conversion_end_time - pdf_conversion_start_time) + " seconds")

        return pdf_image_pages, doc_metadata

    def _pdf_to_text(self, stream: bytes) -> str:
        doc_metadata = {}
        output_text = ""
        with pdfium.PdfDocument(stream) as pdf:
            doc_metadata["pages"] = len(pdf)
            for page in pdf:
                textpage = page.get_textpage()
                output_text += textpage.get_text_range()
                output_text += "\n"

        return output_text, doc_metadata

    def _preprocess_pdf_to_img(self, stream: bytes) -> List[PILImage]:
        """ Converts a stream of bytes from a PDF file into images.

        Args:
            stream (bytes): _description_ . byte buffer.

        Raises:
            Exception: _description_ , coverting image to pdf exception

        Returns:
            List[PILImage]: _description_
        """

        self.log.info("pre-processing pdf...")

        pdf_image_pages = []
        doc_metadata = {}

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

        pdf_stream = None

        try:
            # generate unique id
            uid = uuid.uuid4().hex

            doc_file_path = os.path.join(TMP_FILE_DIR, file_name + "_" + str(uid))
            pdf_file_path = doc_file_path + ".pdf"

            with open(file=doc_file_path, mode="wb") as tmp_doc_file:
                tmp_doc_file.write(stream)
                os.fsync(tmp_doc_file)

            conversion_time_start = time.time()

            loffice_subprocess = None
            used_port_num = None

            for port_num, loffice_process in self.loffice_process_list.items():
                if loffice_process["used"] is False:
                    used_port_num = port_num
                    loffice_subprocess = Popen(args=[LIBRE_OFFICE_PYTHON_PATH, "-m", "unoserver.converter",
                                                     doc_file_path, pdf_file_path,
                                                     "--interface", LIBRE_OFFICE_NETWORK_INTERFACE,
                                                     "--port", str(used_port_num), "--convert-to", "pdf"],
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
                finally:
                    loffice_timer.cancel()
                    soffice_timer.cancel()
                    loffice_subprocess.kill()

                    if os.path.isfile(pdf_file_path):
                        with open(file=pdf_file_path, mode="rb") as tmp_pdf_file:
                            os.fsync(tmp_pdf_file)
                            pdf_stream = tmp_pdf_file.read()
                    else:
                        self.log.info("libre office did not produce any output for file: " +
                                      str(pdf_file_path) + " | port:" + str(used_port_num))
            else:
                raise Exception("could not find libre office server process on port:" + str(used_port_num))

            conversion_time_end = time.time()
            self.log.info("doc conversion to PDF finished | Elapsed : " +
                          str(conversion_time_end - conversion_time_start) + " seconds")

        except Exception:
            raise Exception("doc name:" + str(file_name) + " | preprocessing_doc exception: "
                            + str(traceback.format_exc()))

        finally:
            if used_port_num:
                self.loffice_process_list[used_port_num]["used"] = False
            delete_tmp_files([doc_file_path, pdf_file_path])

        return pdf_stream

    def _preprocess_xml_to_pdf(self, stream: bytes, file_name: str) -> bytes:

        pdf_stream = None

        try:
            from pyxml2pdf.core.initializer import Initializer

            # generate unique id
            uid = uuid.uuid4().hex
            xml_file_path = os.path.join(TMP_FILE_DIR, file_name + "_" + str(uid) + ".xml")
            pdf_file_path = xml_file_path + ".pdf"

            with open(file=xml_file_path, mode="wb") as tmp_doc_file:
                tmp_doc_file.write(stream)
                os.fsync(tmp_doc_file)

            pdfinit = Initializer(xml_file_path, pdf_file_path)

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

    def _process_image(self, img: Image, img_id: int, tess_api: PyTessBaseAPI) -> str:
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

    def _init_tesseract_api_worker(self):
        tess_api = PyTessBaseAPI(path=TESSDATA_PREFIX, lang=TESSERACT_LANGUAGE)
        self.log.debug("Initialised pytesseract api worker for language:" + str(TESSERACT_LANGUAGE))
        return tess_api

    def _process(self, stream: bytes, file_name: str) -> str:
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
        output_text = ""
        images = []
        doc_metadata = {}

        if file_type is not None:
            doc_metadata["content-type"] = str(file_type.mime)
        else:
            doc_metadata["content-type"] = "text/plain"

        # tmp metadata received from methods
        _doc_metadata = {}

        try:
            pdf_stream = None

            if type(file_type) is archive.Pdf:
                pdf_stream = stream
            elif file_type in DOCUMENT:
                pdf_stream = self._preprocess_doc(stream, file_name=file_name)
            elif file_type in IMAGE:
                images = [Image.open(BytesIO(stream))]
                _doc_metadata["pages"] = 1
            elif is_file_type_xml(stream):
                doc_metadata["content-type"] = "text/xml"
                pdf_stream = self._preprocess_xml_to_pdf(stream, file_name=file_name)

                # if we get no content still then just run it through libreoffice converter
                if pdf_stream is None:
                    pdf_stream = self._preprocess_doc(stream, file_name=file_name)
            else:
                # if the file has no type attempt to convert it to pdf anyways
                pdf_stream = self._preprocess_doc(stream, file_name=file_name)

            if pdf_stream is not None:
                if OPERATION_MODE == "OCR":
                    images, _doc_metadata = self._preprocess_pdf_to_img(pdf_stream)

                elif OPERATION_MODE == "NO_OCR":
                    output_text, _doc_metadata = self._pdf_to_text(pdf_stream)

            self.log.info("Detected file type for doc id: " + file_name + " | " + str(doc_metadata["content-type"]))

            doc_metadata.update(_doc_metadata)
            image_count = len(images)
            tess_data = []

            if image_count > 0:
                self.log.info("A total of " + str(image_count) + " images have been generated from " + file_name)
                ocr_start_time = time.time()
                proc_results = list()

                with Pool(processes=CPU_THREADS) as process_pool:
                    tess_api_q = Queue()
                    count = 0
                    for img in images:
                        count += 1
                        tess_api_q.put(self._init_tesseract_api_worker())
                        proc_results.append(process_pool.starmap_async(self._process_image,
                                                                       [(img, count, tess_api_q.get())],
                                                                       chunksize=1,
                                                                       error_callback=logging.error))
                    try:
                        for result in proc_results:
                            result_data = result.get(timeout=TESSERACT_TIMEOUT)
                            _output_text, _img_id, _tess_data = result_data[0][0], result_data[0][1], result_data[0][2]
                            output_text += str(_output_text)
                            tess_data.append(_tess_data)
                    except Exception:
                        raise Exception("OCR exception generated by worker: " + str(traceback.format_exc()))
                    finally:
                        for tess_api in tess_api_q.queue:
                            tess_api.End()

                ocr_end_time = time.time()

                self.log.info("OCR processing finished | Elapsed : " +
                              str("{:.4f}".format(ocr_end_time - ocr_start_time)) + " seconds")

                doc_metadata["pages"] = image_count
                doc_metadata["confidence"] = round(sum([page["confidence"] for page in tess_data]) / image_count, 4)

            output_text = output_text.translate({'\\n': '\n', '\\t': '\t'})
        except Exception:
            raise Exception("Failed to convert/generate image content: " + str(traceback.format_exc()))

        return output_text, doc_metadata

    def process_stream(self, stream: bytes, file_name: str = None) -> json:
        """ Sends the stream of bytes to the `_process` function
        that will do all the pre-processing + ocr-ing work

        Args:
            stream (bytes): _description_. byte array from file
            file_name (str, optional): _description_. Defaults to None,
                 file id generated by the service(if none provided)
                 or the actual file name if the file was provided with the `file` parameter

        Returns:
            tuple : _description_ . output_text post-ocr and 
                doc_metadata containing doc info like number of pages, author etc
        """

        output_text = ""
        doc_metadata = {}
        elapsed_time = 0

        try:
            self.log.info("Processing file name:" + file_name)
            start_time = time.time()
            output_text, doc_metadata = self._process(stream, file_name=file_name)

            end_time = time.time()
            elapsed_time = round(end_time - start_time, 4)
            doc_metadata["elapsed_time"] = elapsed_time

            self.log.info("Finished processing file: " + file_name + " | Elapsed time: " + str(elapsed_time)
                          + " seconds")
        except Exception:
            traceback.print_exc(file=sys.stdout)

        return output_text, doc_metadata
