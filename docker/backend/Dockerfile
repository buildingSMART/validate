# BUILD image
FROM python:3.11-slim-bookworm as build

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
        git \
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
    # some cleanup
    find /         -type d -name setuptools   -prune -exec rm -rf {} \; && \
    find /         -type d -name pip          -prune -exec rm -rf {} \; && \
    find /         -type d -name __pycache__  -prune -exec rm -rf {} \; && \
    find /         -type d -name tests        -prune -exec rm -rf {} \; && \
    find /opt/venv -type f -name "*.ifc"      -prune -exec rm -rf {} \; && \
    find /opt/venv -type f -name "*.pyc"      -prune -exec rm -rf {} \;

# copy code
ADD ./backend /app/backend

# remove and download git submodules
RUN set -ex && \
    rm -rf /app/backend/apps/ifc_validation/checks/ifc_gherkin_rules && \
    rm -rf /app/backend/apps/ifc_validation/checks/step_file_parser && \
    # KEEP LOCAL DEVELOPMENT VERSION
    #rm -rf /app/backend/apps/ifc_validation_models && \
    echo *** SKIPPED REMOVING MODEL SUBMODULE *** && \
    cd /app/backend/apps && \
    git init . && \
    git submodule add https://github.com/buildingSMART/ifc-gherkin-rules ./ifc_validation/checks/ifc_gherkin_rules && \
    git submodule add https://github.com/IfcOpenShell/step-file-parser ./ifc_validation/checks/step_file_parser && \
    # KEEP LOCAL DEVELOPMENT VERSION
    #git submodule add https://github.com/buildingSMART/ifc-validation-data-model ./ifc_validation_models
    echo *** SKIPPED FETCHING MODEL SUBMODULE ***

# copy entrypoints
ADD --chmod=777 ./docker/backend/server-entrypoint.sh /app/backend
ADD --chmod=777 ./docker/backend/worker-entrypoint.sh /app/backend
ADD --chmod=777 ./docker/backend/server_aio-entrypoint.sh /app/backend

# RUN image
FROM python:3.11-slim-bookworm as run

WORKDIR /app

RUN set -ex && \
    # non-root user/group
    addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 --no-create-home appuser && \
    chown -R appuser:appgroup /app && \
    # install and updates
    apt-get -y update && \
    apt-get -y dist-upgrade && \
    apt-get -y install --no-install-recommends --no-install-suggests \
        git \
        netcat-openbsd \
        procps \
        htop && \
    #pip install --upgrade pip && \
    update-ca-certificates -f && \
    # cleanup
    apt-get -y clean && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /tmp/*

# copy output from build image
COPY --from=build /app /app
COPY --from=build /opt/venv /opt/venv
#COPY --from=build /usr/bin /usr/bin

# activate virtual environment
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# user to run the app
# TODO - fix permission issues
# USER appuser

# add OCI labels
LABEL org.opencontainers.image.title="IFC Validation Service - Backend" \
      org.opencontainers.image.description="Backend for the buildingSMART IFC Validation Service" \
      org.opencontainers.image.authors="buildingSMART.org" \
      org.opencontainers.image.vendor="buildingSMART.org" \
      org.opencontainers.image.documentation="https://github.com/buildingSMART/validate" \
      org.opencontainers.image.url="https://github.com/buildingSMART/validate" \
      org.opencontainers.image.licenses="MIT"
      #org.opencontainers.image.version="{$VERSION}" TODO
      #org.opencontainers.image.created="TODO"