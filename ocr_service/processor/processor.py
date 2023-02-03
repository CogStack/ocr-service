from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
import traceback
import uuid
from io import BytesIO
from typing import List, TypeVar

import injector
import pypdfium2 as pdfium
import tesserocr
from filetype.types import DOCUMENT, IMAGE, archive, document, image
from html2image import Html2Image
from PIL import Image

from threading import Timer

from multiprocessing.dummy import Pool

from config import *
from ocr_service.utils.utils import *

sys.path.append("..")

PILImage = TypeVar('PILImage', bound=Image)


class Processor:

    @injector.inject
    def __init__(self):
        app_log_level = os.getenv("LOG_LEVEL", LOG_LEVEL)
        self.log = logging.getLogger(self.__class__.__name__)
        self.log.setLevel(level=app_log_level)
        self.log.debug("Processor log level set to : ", str(app_log_level))

    def _preprocess_html_to_img(self, stream: bytes, file_name: str) -> List[PILImage]:

        hti = Html2Image(output_path=TMP_FILE_DIR, temp_path=TMP_FILE_DIR)
        html_file_path = os.path.join(TMP_FILE_DIR, file_name)
        png_img_file_path = html_file_path + ".png"
        
        with open(file=html_file_path, mode="wb") as tmp_html_file:
            tmp_html_file.write(stream)

        hti.screenshot(html_str=html_file_path, save_as=png_img_file_path)

        delete_tmp_files([png_img_file_path])

        return [Image.open(BytesIO(png_img_file_path))]
    
    def _preprocess_pdf_to_img(self, stream: bytes) -> List[PILImage]:
        """
            :descripton: converts a stream of bytes from a PDF file into images
            
            :param stream: byte array from file
            :type stream: bytes

            :returns: list of PIL images
            :rtype: List[PILImage]
        """

        self.log.info("pre-processing pdf...")

        with pdfium.PdfDocument(stream) as pdf:
            doc_metadata = {}
            try:
                pdf_conversion_start_time = time.time()
                renderer = pdf.render_topil(pdfium.BitmapConv.pil_image,
                        page_indices = range(len(pdf)),
                        scale = OCR_IMAGE_DPI/72,
                        n_processes=CONVERTER_THREAD_NUM)

                pdf_image_pages = list(renderer)
                pdf_conversion_end_time = time.time()

                self.log.info("PDF conversion to image(s) finished | Elapsed : " + str(pdf_conversion_end_time - pdf_conversion_start_time) + " seconds")
            except Exception:
                raise Exception("preprocessing_pdf exception: " + str(traceback.format_exc()))

        return pdf_image_pages, doc_metadata
    
    def _preprocess_doc(self, stream: bytes, file_name: str) -> List[PILImage]:
        """
            :descripton: pre-processing step, all non-pdf(docx/doc/odt/ppt/xls etc.) 
                office doc type files are sent as a stream so that they 
                can be converted to PDF using libreoffice,
                stream -> pdf tmp file, it will delete all the temporary files created
                in the TMP_FILE_DIR after getting the images into memory
            
            :param stream: byte array from file
            :type stream: bytes

            :param file_name: required file name, it will be used to create
                temporary files on disk (TMP_FILE_DIR)
            :type file_name: str

            :returns: list of PIL images
            :rtype: List[PILImage]
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

            loffice_subprocess = subprocess.Popen(args=[LIBRE_OFFICE_PYTHON_PATH, "-m", "unoserver.converter", doc_file_path, pdf_file_path,
                "--interface", LIBRE_OFFICE_NETWORK_INTERFACE, "--port", LIBRE_OFFICE_LISTENER_PORT, "--convert-to", "pdf"],
                cwd=TMP_FILE_DIR, close_fds=False, shell=False) 

            timer = Timer(LIBRE_OFFICE_PROCESS_TIMEOUT, loffice_subprocess.kill)

            try:
                timer.start()
                output, stderr = loffice_subprocess.communicate()
                terminate_hanging_process(get_process_id_by_process_name(LIBRE_OFFICE_EXEC_PATH))
            finally:
                timer.cancel()
                loffice_subprocess.kill()

            conversion_time_end = time.time()
            self.log.info("doc conversion to PDF finished | Elapsed : " + str(conversion_time_end - conversion_time_start) + " seconds")
            time.sleep(50)
            with open(file=pdf_file_path, mode="rb") as tmp_pdf_file:
                pdf_stream = tmp_pdf_file.read()
                delete_tmp_files([pdf_file_path, doc_file_path])

        except Exception:
            raise Exception("doc name:" + str(file_name) + " | "  "preprocessing_doc exception: " + str(traceback.format_exc()))

        return pdf_stream

    def _process_image(self, img: Image, img_id: int) -> str:
        """
            :description: processes a PIL(Pillow) Image, calls tesseract ocr with the configured params
            
            :param img: the actual image of a page from a PDF file
            :type img: Image

            :img_id: page number of the image
            :type img_id: int

            :returns: text from the image, post-ocr
            :rtype: str
        """

        output_str = tesserocr.image_to_text(img)
         
        self.log.info("finished processing img: " + str(img_id))

        return (output_str, img_id)

    def _process(self, stream: bytes, file_name: str) -> str:
        """
            :description: processes a stream of bytes, resulting in the output string
                files have their type detected and then managed accordingly to their requirements
                images will be directly OCRed, while actual documents will undergo
                the following process : byte_stream -> convert to pdf -> convert each pdf page to images ->
                -> multiprocess ocr for the images -> output string text

            :param stream: byte array from file
            :type stream: bytes

            :param file_name: required file name, it will be used to create
                temporary files on disk (TMP_FILE_DIR)
            :type file_name: str

            :raises: :class:`Exception`: if ocr-ing fails

            :returns: output_text, the resulting text post-ocr
            :rtype: str
        """

        file_type = detect_file_type(stream)
        output_text = ""
        images = []
        doc_metadata = {}

        if file_type != None:
            doc_metadata["content-type"] = str(file_type.mime)
        else:
            doc_metadata["content-type"] = "text/plain"
        
        self.log.info("Detect file type for doc id: " + file_name + " | " + str(doc_metadata["content-type"]))

        if type(file_type) == archive.Pdf:
            images, _doc_metadata = self._preprocess_pdf_to_img(stream)
        elif file_type in DOCUMENT:
            pdf_stream = self._preprocess_doc(stream, file_name=file_name) 
            images, _doc_metadata = self._preprocess_pdf_to_img(pdf_stream)
        elif file_type in IMAGE:
            images = [Image.open(BytesIO(stream))]
        else:
            # if the file has no type attempt to convert it to pdf anyways
            pdf_stream = self._preprocess_doc(stream, file_name=file_name) 
            images, _doc_metadata = self._preprocess_pdf_to_img(pdf_stream)

        doc_metadata.update(_doc_metadata)

        image_count = len(images)

        if image_count > 0:
            self.log.info("A total of " + str(image_count) + " images have been generated from " + file_name)
            ocr_start_time = time.time()
            proc_results = list()

            with Pool(CPU_THREADS) as process_pool:
                count = 0
                for img in images:
                    count += 1
                    proc_results.append(process_pool.starmap_async(self._process_image,[(img, count)], chunksize=1))

                try:
                    for result in proc_results:
                        output_text += str((result.get(timeout=TESSERACT_TIMEOUT))[0][0])
                except Exception:
                    raise Exception("OCR exception generated by worker: " + str(traceback.format_exc()))
            
            ocr_end_time = time.time()

            self.log.info("OCR processing finished | Elapsed : " + str("{:.4f}".format(ocr_end_time - ocr_start_time)) + " seconds")

        doc_metadata["pages"] = image_count

        output_text = output_text.replace('\\n', '\n').replace('\\t', '\t')

        return output_text, doc_metadata

    def process_stream(self, stream: bytes, file_name: str = None) -> json:
        """
            :description: sends the stream of bytes to the `_process` function
                that will do all the pre-processing + ocr-ing work

            :param stream: byte array from file
            :type stream: bytes

            :param file_name: file id generated by the service(if none provided)
                 or the actual file name if the file was provided with the `file` parameter
            :type file_name: str

            :raises: :class:`Exception`: if ocr-ing fails

            :returns: output_text, the resulting text post-ocr
            :rtype: str

            :returns: doc_metadata containing doc info like number of pages, author etc
            :rtype: dict
        """

        output_text = ""
        doc_metadata = {}
        elapsed_time = 0

        try:
            self.log.info("Processing file name:" + file_name)
            start_time = time.time()
            output_text, doc_metadata = self._process(stream, file_name=file_name)

            end_time = time.time()
            elapsed_time = str("{:.4f}".format(end_time - start_time))
            doc_metadata["elapsed_time"] = elapsed_time

            self.log.info("Finished processing file: " + file_name + " | Elapsed time: " + elapsed_time + " seconds")
        except Exception as exception:
            traceback.print_exc(file=sys.stdout)

        return output_text, doc_metadata
