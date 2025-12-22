# OCR-Service

[![docker-ocr-service](https://github.com/CogStack/ocr-service/actions/workflows/docker_build.yml/badge.svg)](https://github.com/CogStack/ocr-service/actions/workflows/docker_build.yml)
[![tests-ocr-service](https://github.com/CogStack/ocr-service/actions/workflows/run_tests.yml/badge.svg)](https://github.com/CogStack/ocr-service/actions/workflows/run_tests.yml)
[![codeql-analysis-ocr-service](https://github.com/CogStack/ocr-service/actions/workflows/codeql.yml/badge.svg)](https://github.com/CogStack/ocr-service/actions/workflows/codeql.yml)
[![docker-smoke-ocr-service](https://github.com/CogStack/ocr-service/actions/workflows/docker_smoke.yml/badge.svg)](https://github.com/CogStack/ocr-service/actions/workflows/docker_smoke.yml)

## Introduction

This is a Python replacement for the previous Tika service, aiming to resolve scalability and performance issues. It relies on Tesseract OCR without the ambiguities of the Tika framework.

## Asking questions

Feel free to ask questions on the github issue tracker or on our [discourse website](https://discourse.cogstack.org) which is frequently used by our development team!  

## Dependencies

Python 3.11+  
For the Python packages see [`requirements.txt`](./requirements.txt).

Pillow package deps, see <https://pillow.readthedocs.io/en/stable/installation.html>

Tesseract OCR <https://tesseract-ocr.github.io/tessdoc/Downloads.html>

Docker (optional, but recommended for deployments) version 21.10+

## Local development dependencies

LibreOffice 7.4+

Tesseract OCR and its dependencies.

Windows: run inside WSL (preferably Ubuntu). Native Windows paths are not maintained; install dependencies from the Dockerfile.

## Starting the service

Docker (prebuilt image): `cd docker && docker compose -f docker-compose.base.yml up -d` (or `docker-compose`)

Docker (local build/dev): `cd docker && docker compose -f docker-compose.dev.yml up -d` (or `docker-compose`)

Console/debug: `bash start_service_debug.sh` (loads `env/ocr_service.env`)

Console/production: `bash export_env_vars.sh` then `bash start_service_production.sh`

## Docker images

The following docker images are available

```text
  cogstacksystems/cogstack-ocr-service:latest
```

## Available models

Currently, only Tesseract models are supported.
You can load models by setting the `OCR_SERVICE_TESSERACT_LANG` variable, you can load multiple models at the same time, example: English + Latin + French `OCR_SERVICE_TESSERACT_LANG=eng+lat+fra`.

**For performance reasons it is recommended that you load only one model at a time, as processing time will increase slightly per model loaded.**

## API

## API specification

The Service, by default, will be listening on port `8090` and the returned content extraction result will be represented in JSON format.

Check `http://localhost:8090/docs` for input information.

The service exposes:

- *GET* `/api/health` - returns `{"status": "healthy"}`,
- *GET* `/api/info` - returns information about the service with its configuration,
- *POST* `/api/process` - processes a binary data stream with the binary document content ("Content-Type: application/octet-stream"), also accepts binary files directly via the 'file' parameter, if sending via curl. It
- *POST* `/api/process_file` - processes a file via multipart/form-data,
- *POST* `/api/process_bulk` - placeholder; returns `{"response": "Not yet implemented"}`,
also has the extra functionality of accepting json, in case you want to process records and want to keep additional data in the footer , e.g

original record payload must contain the "binary_data" key with a base64 buffer (REQUIREMENT for it to work), and the "footer", that has the other record fields:

```json
{
  "binary_data": "b2NyIHNlcnZpY2U=",
  "footer": {
    "id": 1,
    "source_system_id": 201102
  }
}
```

the result will have the following format:

```json
{
  "result": {
    "text": "........",
    "footer": {
      "id": 1,
      "source_system_id": 201102 
    },
    "metadata": {
      "content-type": "...",
      "pages": "...",
      "confidence": "...",
      "elapsed_time": "...",
      "log_message": "..."
    },
    "success": "True",
    "timestamp": "....."
  }
}
```

When OCR is intentionally skipped (for example `OCR_SERVICE_OPERATION_MODE=NO_OCR` with an image input),
the response returns an empty `text`, `success` remains `True`, and `metadata.ocr_skipped` is set to `true`.

Supports most document formats: pdf, html, doc(x), rtf, odt and also the image formats: png, jpeg/jpg, jpx, tiff, bmp.

## Example use

Using `curl` to send the document to server instance running on localhost on port `8090`:

```bash
curl -F file="@ocr_service/tests/resources/docs/generic/pat_id_1.rtf" \
  http://localhost:8090/api/process | jq
```

output

```json
{
  "result": {
    "text": "This is an example of a clinical document\n\nThe patient’s name is Bart Davidson.\n\nHis carer’s Name Paul Wayne.\n\nHis telephone number is 07754828992\n\nHis Address is 61 Basildon Way,\n\nEast Croyhurst,\n\nAngelton,\n\nAL64 9HT\n\nHis mother’s name is Pauline Smith.\n\nHe is on 100mg Paracetamol, 20 milligrams clozapine\n",
    "metadata": {
      "content-type": "application/rtf",
      "pages": 1,
      "elapsed_time": "0.9800",
      "log_message": ""
    },
    "success": "True",
    "timestamp": "2023-02-05 13:52:25.707112"
  }
}
```

## Current limitations

LibreOffice conversions are single-threaded per worker. To process documents in parallel, use multiple workers or multiple service containers. See the [OCR scenarios](#ocr-ing-scenarios) section for guidance.

Another bottleneck is resource sharing. By default a worker can use all cores and splits documents into pages to OCR on separate cores, which is fast but can cause CPU contention.
You can control this; see the [resource management section](#resource-management) for setup guidance.

## Resource management

This service is fast but it is resource intensive, and will attempt to use all cores on your machine. You can spin up multiple docker services in the hopes of having multiple requests handled at the same time.

Edit `docker/docker-compose.base.yml`, duplicate the `ocr-service` service, and set
`OCR_SERVICE_CPU_THREADS` and `OCR_SERVICE_CONVERTER_THREADS` to `cores / service_count`.
Rename the service/container and update ports (e.g., 8091/8092/8093).

`OCR_WEB_SERVICE_THREADS` is deprecated and forced to 1; use `OCR_WEB_SERVICE_WORKERS` to scale parallel requests and adjust CPU/converter threads accordingly. See the [OCR-ing scenarios](#ocr-ing-scenarios) section.

## OCR-ing scenarios

The speed of the service depends on several factors: image size, page count, number of cores, and CPU clock speed. Both core count and core speed matter for optimal performance.

There are three relevant configuration variables that you will need to take into account when trying to divide resources across services: OCR_WEB_SERVICE_WORKERS (parallel worker processes), OCR_SERVICE_CPU_THREADS, OCR_SERVICE_CONVERTER_THREADS. See the [config variables section](#config-variables) for a description of each setting.

Timeouts are more likely with higher DPI settings. Increase `OCR_SERVICE_TESSERACT_TIMEOUT` if you are seeing response timeouts. Increase `OCR_SERVICE_LIBRE_OFFICE_PROCESS_TIMEOUT` if conversions time out.

Below are some sample scenarios you might come across.

### Docs with high page count

If your documents have many pages (10+), limit the number of service instances based on available resources. For example, on a 64-core machine you could run 4 instances, each with access to 8 cores. Performance also depends on document type; large images may need higher DPI than the default 200, which improves quality but increases processing time. In that case, lower the number of services and increase core allocation.

### Single page docs

This is a reasonable scenario to run many services and limit each service to 1 core: `OCR_SERVICE_CPU_THREADS = OCR_SERVICE_CONVERTER_THREADS = 1`. Spin up as many services as you want; each service will use one CPU.

### Images

Since images do not go through the doc conversion process, you can increase `OCR_WEB_SERVICE_WORKERS` and set
`OCR_SERVICE_CPU_THREADS = OCR_SERVICE_CONVERTER_THREADS = CPU_COUNT / OCR_WEB_SERVICE_WORKERS` to balance cores.

## Config variables

These are the primary service settings read from the environment by `ocr_service/settings.py`.
Defaults shown below are the code defaults; the env templates in `env/*.env` may override them.

```text
OCR_SERVICE_OPERATION_MODE - default "OCR"; use "NO_OCR" to skip OCR and return empty text for images.

OCR_SERVICE_DEBUG_MODE - default false; enables FastAPI debug mode and relaxed LibreOffice startup behavior.

OCR_TMP_DIR - default "./tmp" relative to the repo; temp files and LibreOffice profiles live here.

OCR_TESSDATA_PREFIX - default is OS-specific: macOS "/opt/homebrew/share/tessdata"; Linux "/usr/share/tesseract-ocr/5/tessdata" (fallback "/usr/share/tesseract-ocr/4.00/tessdata"). Override to point at custom Tesseract models.

OCR_SERVICE_TESSERACT_LANG - default "eng", language we are trying to ocr, only English is tested within the unittest, therefore expect variable results with anything else

OCR_WEB_SERVICE_THREADS - deprecated; forced to 1. Use OCR_WEB_SERVICE_WORKERS to scale parallel processing.

OCR_SERVICE_LOG_LEVEL - default 10, possible values : 50 - CRITICAL, 40 - ERROR, 30 - WARNING, 20 - INFO, 10 - DEBUG, 0 - NOTSET

OCR_SERVICE_PORT - default 8090

OCR_SERVICE_TESSERACT_TIMEOUT - default 30 seconds, how much should we wait to OCR a document's image (not the doc itself) before timing out and cancelling the request

OCR_SERVICE_TESSERACT_NICE - default -18, this is just for Linux systems, we need a high priority for our service so it gets prioritized, -19 is the highest possible, lowest is 0 -> +∞

OCR_SERVICE_TESSERACT_CUSTOM_CONFIG_FLAGS - extra parameters that you might want to pass to tesseract

OCR_SERVICE_CPU_THREADS - defaults to core count divided by OCR_WEB_SERVICE_WORKERS; this variable is used by tesseract to spread CPU usage per worker

OCR_SERVICE_CONVERTER_THREADS - defaults to core count divided by OCR_WEB_SERVICE_WORKERS; used for PDF to image conversion

OCR_SERVICE_IMAGE_DPI - default 200 DPI, tesseract image DPI rendering resolution, higher values might mean better text quality at the cost of processing speed

OCR_CONVERT_GRAYSCALE_IMAGES - default true; converts images to grayscale before OCR to reduce noise.

OCR_SERVICE_LIBRE_OFFICE_PROCESS_TIMEOUT - default 100 seconds, used for converting docs to pdf.

OCR_SERVICE_LIBRE_OFFICE_LISTENER_PORT_RANGE - optional override (e.g. "(9900, 9902)") to pin LibreOffice listener ports.

OCR_WEB_SERVICE_WORKERS - number of worker processes running in parallel; balance CPU_THREADS and CONVERTER_THREADS accordingly

LIBRE_OFFICE_NETWORK_INTERFACE - default "localhost"; interface used by unoserver.

LIBRE_OFFICE_PYTHON_PATH / LIBRE_OFFICE_EXEC_PATH - optional overrides for LibreOffice paths.
```

Gunicorn/runtime env vars used by start scripts and docker:

```text
OCR_SERVICE_HOST - bind host (default "0.0.0.0" in env templates)
OCR_SERVICE_WORKER_CLASS - "sync" or "gthread" (env default is "sync")
OCR_SERVICE_GUNICORN_LOG_FILE_PATH, OCR_SERVICE_GUNICORN_LOG_LEVEL
OCR_SERVICE_GUNICORN_MAX_REQUESTS, OCR_SERVICE_GUNICORN_MAX_REQUESTS_JITTER
OCR_SERVICE_GUNICORN_TIMEOUT, OCR_SERVICE_GUNICORN_GRACEFUL_TIMEOUT
```
