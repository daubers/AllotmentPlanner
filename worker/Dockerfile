# Mapping worker: the app's Celery code plus OpenSfM (structure from motion) and GDAL (orthophoto,
# tiles). Build context is ./backend:  docker build -f worker/Dockerfile backend
#
# OpenSfM lives in its own virtualenv and is run as a subprocess, so its pinned numpy/OpenCV never
# touch the app's environment. It has no published image or wheel, so it is compiled from a pinned
# commit in a build stage; the final image carries only the result and the libraries it needs.
# Layers are kept deliberately small (several RUN/COPY steps, not one): registries behind a
# reverse proxy often cap the size of a single blob upload.

# --- build: compilers and -dev packages never reach the final image ---------------------------
FROM ubuntu:24.04 AS build

ARG DEBIAN_FRONTEND=noninteractive
# mapillary/OpenSfM master as of 2026-10-21 (v0.5.2 development)
ARG OPENSFM_REF=65571c8ae9ac6a1d0bcd3fdc1ea5fff97b1b5611

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential ca-certificates cmake git \
        libceres-dev libeigen3-dev libopencv-dev \
        python3 python3-dev python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Keep the compiler from using more memory than a laptop-sized Docker VM has.
ENV CMAKE_BUILD_PARALLEL_LEVEL=4

RUN git init -q /opt/OpenSfM \
    && git -C /opt/OpenSfM fetch -q --depth 1 https://github.com/mapillary/OpenSfM "$OPENSFM_REF" \
    && git -C /opt/OpenSfM checkout -q FETCH_HEAD \
    && git -C /opt/OpenSfM submodule update -q --init --recursive --depth 1 \
    && python3 -m venv /opt/opensfm-venv \
    && /opt/opensfm-venv/bin/pip install --no-cache-dir /opt/OpenSfM

# Which Ubuntu packages provide the shared libraries the compiled extensions link against
# (readlink: dpkg knows the real /usr/lib path, not the /lib alias that ldd prints).
RUN find /opt/opensfm-venv/lib -name '*.so' -path '*opensfm*' -print0 \
    | xargs -0 ldd 2>/dev/null | awk '/=> \//{print $3}' | sort -u \
    | xargs readlink -f | sort -u \
    | xargs dpkg -S 2>/dev/null | grep -E '^[a-z0-9][a-z0-9+.-]*(:[a-z0-9]+)?: /' | cut -d: -f1 | sort -u \
    > /opt/opensfm-runtime-packages.txt \
    && cat /opt/opensfm-runtime-packages.txt

# --- runtime ----------------------------------------------------------------------------------
FROM ubuntu:24.04 AS runtime

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl libatomic1 libpq5 python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y --no-install-recommends gdal-bin python3-gdal \
    && rm -rf /var/lib/apt/lists/*

# Libraries the OpenSfM extensions need (OpenCV, Ceres, glog, ...), computed in the build stage.
COPY --from=build /opt/opensfm-runtime-packages.txt /tmp/opensfm-runtime-packages.txt
RUN apt-get update \
    && xargs -a /tmp/opensfm-runtime-packages.txt apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* /tmp/opensfm-runtime-packages.txt

COPY --from=build /opt/opensfm-venv /opt/opensfm-venv
COPY --from=build /opt/OpenSfM/bin /opt/OpenSfM/bin

# The app, in a separate environment.
RUN python3 -m venv /opt/app-venv
COPY . /app
RUN /opt/app-venv/bin/pip install --no-cache-dir /app

# Which PyTorch build: "cpu" (default), "cu126" (NVIDIA), or "rocm7.1" (AMD). GPU builds are several
# GB larger and are meant to be built on the GPU machine itself (deploy/docker-compose.remote-worker.yml),
# not pushed to a registry that caps layer size. Set TORCH_DEVICE=auto (default) to use the GPU.
ARG TORCH_INDEX=cpu

# Object recognition (Grounding DINO + SAM through transformers); CPU unless TORCH_INDEX says
# otherwise. torch's wheel is one
# big file, so it goes in a layer of its own; its smaller dependencies follow in another. The
# models themselves are NOT baked in (hundreds of MB of weights in one layer would be refused by
# the registry's proxy): they download into /data/models the first time a job needs them.
# (torch's own tests and C++ headers are about 180 MB that inference never touches.)
RUN /opt/app-venv/bin/pip install --no-cache-dir --retries 10 --timeout 120 --no-deps torch torchvision \
    --index-url https://download.pytorch.org/whl/${TORCH_INDEX} \
    && rm -rf /opt/app-venv/lib/python3.12/site-packages/torch/test \
              /opt/app-venv/lib/python3.12/site-packages/torch/include
RUN /opt/app-venv/bin/pip install --no-cache-dir torch torchvision scipy "transformers>=4.45" \
    --extra-index-url https://download.pytorch.org/whl/${TORCH_INDEX}

ENV PATH="/opt/app-venv/bin:$PATH" \
    HF_HOME=/data/models \
    OPENSFM_PYTHON=/opt/opensfm-venv/bin/python \
    OPENSFM_MAIN=/opt/OpenSfM/bin/opensfm_main.py \
    MAPPING_WORK_DIR=/data/mapping

RUN useradd --create-home allotment && mkdir -p /data/media /data/mapping /data/models \
    && chown -R allotment /data
USER allotment
WORKDIR /app
CMD ["celery", "-A", "allotment.celery_app:celery", "worker", "-Q", "mapping", "-c", "1", "-l", "INFO"]
