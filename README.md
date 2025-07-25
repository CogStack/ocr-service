# Introduction

This is a python-replacement of the previous Tika-service in an attempt to resolve scalability and performance issues. It also relies on tesseract ocr but without the ambiguities of the Tika framework.

## Asking questions

Feel free to ask questions on the github issue tracker or on our [discourse website](https://discourse.cogstack.org) which is frequently used by our development team!  

# Dependencies

Python 3.11+  
For the Python packages see [`requirements.txt`](./requirements.txt).

Pillow package deps, see <https://pillow.readthedocs.io/en/stable/installation.html>

Tessaract-ocr <https://tesseract-ocr.github.io/tessdoc/Downloads.html>

Docker (optional, but recommended for deployments) version 21.10+

## Local development dependencies

Libre office 7.4+

Tesseract-ocr package and its dependencies.

Windows: this project can and should be run inside WSL (preferabily ubuntu) with ease, there are some dependencies and paths that are broken outside of it that might be a headache to repair, install necessary deps from the Dockerfile.

# Starting the service

Docker mode: `cd docker && docker-compose up -d`

Console mode: `bash start_service_production.sh`

# Docker images

The following docker images are available

```text
  cogstacksystems/cogstack-ocr-service:latest
```

# Available models

Currently, only TESERRACT models are supported.
You can load models by setting the `OCR_SERVICE_TESSERACT_LANG` variable, you can load multiple models at the same time, example: English + Latin + French `OCR_SERVICE_TESSERACT_LANG=eng+lat+fra`.

**For performance reasons it is recommended that you load only one model at a time, as processing time will increase slightly per model loaded.**

# API

## API specification

Tika Service, by default, will be listening on port `8090` and the returned content extraction result will be represented in JSON format.

The service exposes such endpoints:

- *GET* `/api/info` - returns information about the service with its configuration,
- *POST* `/api/process` - processes a binary data stream with the binary document content ("Content-Type: application/octet-stream"), also accepts binary files directly via the 'file' parameter, if sending via curl. It
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

Supports most document formats: pdf, html, doc(x), rtf, odt and also the image formats: png, jpeg/jpg, jpx, tiff, bmp.

# Example use

Using `curl` to send the document to server instance running on localhost on `8090` port:

```curl -F file="@ocr_service/tests/resources/docs/generic/pat_id_1.rtf" http://localhost:8090/api/process/ | jq```

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

# Current limitations

You will notice that requests are handled sequentially rather than in parallel (one at a time), this is partly due to using libreoffice/soffice binary package (this is likely to change in the future) to convert most documents to a common format, a pdf. Because this background application does not handle parallelisation very well it is recommended to have multiple docker services running instead OR you can spin up multiple workers via the `OCR_WEB_SERVICE_WORKERS` variable, make sure you read the [OCR scenarions](#ocr-ing-scenarios) section.

Another cause for sequential request processing is the sharing of resources,
one thread has access by default to all cores, this matters because the current implementation splits a document into multiple pages and attempts to ocr each page on a separate core, resulting in good speed but a competition for resources.
It is possible to control this however, please see the [resource management section](#resource-management) on how to set up multiple docker services for different screnarios.

# Resource management

This service is fast but it is resource intensive, and will attempt to use all cores on your machine. You can spin up multiple docker services in the hopes of having multiple requests handled at the same time.

Simply edit the `docker-compose.yml` file and copy the same `ocr-service` section and edit the `OCR_SERVICE_CPU_THREADS` and `OCR_SERVICE_CONVERTER_THREADS` parameters to be equal to the number_of_cores on the machine divided by the number of services, i.e for 4 services assuming 16 cores - `OCR_SERVICE_CPU_THREADS = OCR_SERVICE_CONVERTER_THREADS = 16/4` for each docker service, don't forget to rename the service name and container name : ocr-service-1/-2/-3 and to change the output ports from 8090 to something else (pref the same port range for ease of tracking 809(1/2/3)).

You can now also set the `OCR_WEB_SERVICE_THREADS` to a value greater than 1, allowing you to use only one docker container that can process multiple requests, each request having access to limited CPU cores, spread evenly. It might not be advised to use this with a different value than 1 if you are processing docuemnts with a large amount of pages, because each page gets sent to one core, it will take considerably more time to process, check the below [OCR-ing scenarios](#ocr-ing-scenarios).

## OCR-ing scenarios

The speed of the service depends on a lot of factors: the raw size of the images being ocr-ed, the number of pages of a document, and also the number of cores available, as well as a critical factor, the CPU clock, evidently both core count and core speed need to be high for optimal performance.

There are three relevant configuration variables that you will need to take into account when trying to divide resources across services: OCR_WEB_SERVICE_THREADS - web service threads (how many parallel requests it can handle, it is 1 by default), OCR_SERVICE_CPU_THREADS, OCR_SERVICE_CONVERTER_THREADS. See the [config variables section](#config-variables) for a description of each setting.

Service timeouts scenarios are highly likely with higher DPI settings, please change the `OCR_SERVICE_TESSERACT_TIMEOUT` to higher values if you are experiencing response timeouts. Conversion timeouts are also likely, please change the `OCR_SERVICE_LIBRE_OFFICE_PROCESS_TIMEOUT` in this case.

Below are some sample scenarios you might come across.
<br>

### Docs with high page count

If your documents are composed of a large number of pages (10+) it is suggested that you limit your self to a lower number of services (depending on the resources available), as an example, for a machine with 64 cores you could could attempt to run 4 service instances, each service having access to at most 8 cores. Of course, the performance also depends on what kind of document you are ocr-ing, if it is a large scale image you might not get the same text quality with only the default 200 dpi image rendering enabled, and so you would need to increase you dpi and thus increasing the quality and also the processing time, you may wish to lower the number of services in this case and increase the core count.
<br>

### Single page docs

This is a reasonable scenarion in which you can benefit from having as many services as possible, and limiting each service to 1 core `OCR_SERVICE_CPU_THREADS = OCR_SERVICE_CONVERTER_THREADS = 1` . Spin up as many services as you want, each service will only use one CPU.
<br>

### Images

Since images do not go through the doc conversion process, you can run one container service with a higher number of web request threads, set `OCR_WEB_SERVICE_THREADS` to a desired number, it should be no greater than the number of cores on the machine,
and set ocr + converter threads to be the equal to  `OCR_SERVICE_CPU_THREADS = OCR_SERVICE_CONVERTER_THREADS = CPU_COUT / OCR_WEB_SERVICE_THREADS`, so for 16 cores and OCR_WEB_SERVICE_THREADS = 16 you would want `OCR_SERVICE_CPU_THREADS = OCR_SERVICE_CONVERTER_THREADS = 1` .

# Config variables

These are the config variables declared in `config.py`.

```text
OCR_TESSDATA_PREFIX - default "/usr/share/tessdata", this is the path to the Tesseract model, by default the model within the Docker container is Tesseract Fast (https://github.com/tesseract-ocr/tessdata_fast), if you wish to change it for better results please go to https://github.com/tesseract-ocr/tessdata_best , download the zip from the release, extract it and change the path, don't forget to mount that folder on the container if you are using Docker.

OCR_SERVICE_TESSERACT_LANG - default "eng", language we are trying to ocr, only English is tested within the unittest, therefore expect variable results with anything else

OCR_WEB_SERVICE_LIMIT_CONCURRENCY_TASKS - default to 1, how many requests can it process at one time, this is global, not per worker, but should always follow the number of WORKERS.

OCR_SERVICE_LOG_LEVEL - default 40, possible values : 50 - CRITICAL, 40 - ERROR, 30 - WARNING, 20 - INFO, 10 - DEBUG, 0 - NOTSET

OCR_SERVICE_PORT - default 8090

OCR_SERVICE_TESSERACT_TIMEOUT - default 360 seconds, how much should we wait to OCR a document's image (not the doc itself) before timing out and cancelling the request

OCR_SERVICE_TESSERACT_NICE - default -18, this is just for Linux systems, we need a high priority for our service so it gets prioritized, -19 is the highest possible, lowest is 0 -> +∞

OCR_SERVICE_TESSERACT_CUSTOM_CONFIG_FLAGS - extra parameters that you might want to pass to tesseract

OCR_SERVICE_CPU_THREADS - defaults to whatever the core count on the machine is divided by OCR_WEB_SERVICE_WORKERS, this variable is used by tesseract, each web thread will get access to a limited amount of CPUS so that resources are spread evenly

OCR_SERVICE_CONVERTER_THREADS - defaults to whatever the core count on the machine is, this variable is used for converting pdf docs to images

OCR_SERVICE_IMAGE_DPI - default 200 DPI, tesseract image DPI rendering resolution, higher values might mean better text quality at the cost of processing speed

OCR_SERVICE_LIBRE_OFFICE_PROCESS_TIMEOUT - default 10 seconds, used for converting docs to pdf. 

OCR_WEB_SERVICE_WORKERS - number of worker threads (this means running multiple instances in parallel, becareful to balance load out by settings the threads to evenly distribute themselves amongst workers)
```
