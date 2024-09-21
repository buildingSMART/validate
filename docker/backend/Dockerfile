# BUILD image
FROM python:3.11-slim-bookworm AS build

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1    

WORKDIR /app

RUN set -ex && \
    # install and updates
    apt-get -y update && \
    apt-get -y dist-upgrade && \
    apt-get -y install --no-install-recommends --no-install-suggests \ 
        python3-dev \
        unzip \
        wget \
        && \
    update-ca-certificates -f && \
    # cleanup
    apt-get -y clean && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /tmp/*

# create and activate virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# install requirements
ADD ./backend/requirements.txt /app/backend/requirements.txt
RUN --mount=type=cache,target=/root/.cache \
    pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/backend/requirements.txt && \    
    # use version of ifcopenshell with desired schema parsing
    # TODO: revert to pyPI when schema parsing is published in the future
    wget -O /tmp/ifcopenshell_python.zip "https://s3.amazonaws.com/ifcopenshell-builds/ifcopenshell-python-311-v0.7.9-c18e4ea-linux64.zip" && \
    mkdir -p /opt/venv/lib/python3.11/site-packages  && \
    unzip -d /opt/venv/lib/python3.11/site-packages /tmp/ifcopenshell_python.zip && \
    # some cleanup
    find /         -type d -name setuptools   -prune -exec rm -rf {} \; && \
    find /         -type d -name pip          -prune -exec rm -rf {} \; && \
    find /         -type d -name __pycache__  -prune -exec rm -rf {} \; && \
    find /         -type d -name tests        -prune -exec rm -rf {} \; && \
    find /opt/venv -type f -name "*.ifc"      -prune -exec rm -rf {} \; && \
    find /opt/venv -type f -name "*.pyc"      -prune -exec rm -rf {} \;

# copy code
ADD ./backend /app/backend
RUN rm -f /app/backend/.env || true

# copy entrypoints
ADD --chmod=777 ./docker/backend/server-entrypoint.sh /app/backend
ADD --chmod=777 ./docker/backend/worker-entrypoint.sh /app/backend

# RUN image
# NOTE: don't use Alpine images...
FROM python:3.11-slim-bookworm AS run

WORKDIR /app

# gunicorn/celery concurrency (defaults in *-entrypoint.sh)
ENV DJANGO_GUNICORN_WORKERS= \
    DJANGO_GUNICORN_THREADS_PER_WORKER= \
    CELERY_CONCURRENCY=

RUN set -ex && \
    # install packages and updates
    apt-get -y update && \
    apt-get -y dist-upgrade && \
    apt-get -y install --no-install-recommends --no-install-suggests \
        netcat-openbsd \
        procps \
        htop && \
    update-ca-certificates -f && \
    # cleanup
    apt-get -y clean && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /tmp/*

# copy output from build image
COPY --from=build /app /app
COPY --from=build /opt/venv /opt/venv

# activate virtual environment
ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# build info
ARG VERSION
ARG GIT_COMMIT_HASH

ENV VERSION=${VERSION} \
    GIT_COMMIT_HASH=${GIT_COMMIT_HASH}

# add OCI labels
LABEL org.opencontainers.image.title="IFC Validation Service - Backend" \
      org.opencontainers.image.description="Backend for the buildingSMART IFC Validation Service" \
      org.opencontainers.image.authors="buildingSMART.org" \
      org.opencontainers.image.vendor="buildingSMART.org" \
      org.opencontainers.image.documentation="https://github.com/buildingSMART/validate" \
      org.opencontainers.image.url="https://github.com/buildingSMART/validate" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT_HASH}"
