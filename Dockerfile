FROM ubuntu:lunar

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy

ENV HTTP_PROXY=$HTTP_PROXY
ENV HTTPS_PROXY=$HTTPS_PROXY
ENV NO_PROXY=$NO_PROXY
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY

ENV DEBIAN_FRONTEND=noninteractive
ENV DEBIAN_PRIORITY=critical

# default user
USER root

# Update and install python3
RUN apt-get update && apt-get upgrade -y && \
     apt-get install -y software-properties-common

# add extra repos
RUN apt-add-repository multiverse && \
    apt-add-repository universe && \
    add-apt-repository ppa:graphics-drivers/ppa && \
    apt-get update && apt-get upgrade -y 

RUN apt-get update && apt-get upgrade -y

# install req packages
RUN apt-get install -y python3.11 python3.11-dev python3.11-venv python3.11-doc python3-dev python3-pip

RUN apt-get update && apt-get upgrade -y && \
    apt-get --force-yes -o Dpkg::Options::="--force-confold" --force-yes -o Dpkg::Options::="--force-confdef" -fuy  dist-upgrade  && \
    apt-get install -y \
    gnupg \
    libssl-dev \
    wget \
    curl \
    gnupg \
    gnupg-agent \
    dirmngr \
    ca-certificates \
    apt-transport-https \
    fonts-dejavu \
    build-essential \
    unixodbc \
    unixodbc-dev \
    gfortran \
    gcc \
    g++

##### utils for python and TESSERACT

RUN echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections
RUN apt-get install -y --no-install-recommends fontconfig ttf-mscorefonts-installer
RUN fc-cache -f -v

RUN apt-get install -y libimage-exiftool-perl libtika-java libtomcat9-java libtomcat9-embed-java libtcnative-1 && \
    apt-get install -y ttf-mscorefonts-installer fontconfig && \
    apt-get install -y ffmpeg gstreamer1.0-libav fonts-deva fonts-dejavu fonts-gfs-didot fonts-gfs-didot-classic fonts-junicode fonts-ebgaramond fonts-noto-cjk fonts-takao-gothic fonts-vlgothic && \
    apt-get install -y --fix-missing ghostscript ghostscript-x gsfonts gsfonts-other gsfonts-x11 fonts-croscore fonts-crosextra-caladea fonts-crosextra-carlito fonts-liberation fonts-open-sans fonts-noto-core fonts-ibm-plex fonts-urw-base35 && \
    apt-get install -y --fix-missing imagemagick tesseract-ocr tesseract-ocr-eng tesseract-ocr-osd tesseract-ocr-lat tesseract-ocr-fra tesseract-ocr-deu && \
	apt-get clean autoclean && \
    apt-get autoremove --purge -y

# python3 poppler requirement
RUN apt-get install poppler-utils -y

RUN apt-get install -y libreoffice libreoffice-script-provider-python
RUN rm -rf /var/lib/apt/lists/*

# python3 packages
RUN pip3 install --upgrade pip
RUN pip3 install numpy matplotlib scikit-image
RUN pip3 install setuptools wheel virtualenv cython

# create and copy the app  
RUN mkdir /ocr_service
COPY ./ /ocr_service
WORKDIR /ocr_service

# Install requirements for the app
RUN pip3 install -r ./requirements.txt

# LibreOffice stuff
#RUN export PYTHONPATH="${PYTHONPATH}:/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/3.8/lib/site-packages /Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/3.8/LibreOfficePython"

#RUN export PYTHONPATH=$PYTHONPATH:/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/3.8/lib/site-packages /Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/3.8/bin/python3


# RUN export PYTHONPATH="${PYTHONPATH}:/Applications/LibreOffice.app/Contents/Resources/python"

# RUN export libreoffice="/Applications/LibreOffice.app/Contents/MacOS/soffice"

