# BUILD image
FROM node:18-alpine AS build

RUN apk upgrade --no-cache && \
    apk update && \
    apk add \
        ca-certificates \
        wget \
        curl

WORKDIR /app/frontend

COPY ./frontend/src ./src
COPY ./frontend/public ./public
COPY ./frontend/package* ./
COPY ./frontend/.env.* ./

# build info
ARG VERSION
ARG GIT_COMMIT_HASH
ENV VERSION=${VERSION} \
    GIT_COMMIT_HASH=${GIT_COMMIT_HASH}

# build React app
RUN npm install && \
    npm run build && \
    sleep 5 && \
    rm -rf node_modules

# RUN image
FROM nginx:1.27-alpine3.19-slim AS run

# install certbot
RUN set -ex && \
    apk add --update --no-cache python3 py3-pip certbot && \
    pip install certbot certbot-nginx --break-system-packages

# copy custom boot scripts
ADD --chmod=777 ./docker/frontend/docker-entrypoint.d/ /docker-entrypoint.d/

# copy default nginx config template
ADD --chmod=777 ./docker/frontend/nginx/default.conf.template /etc/nginx/templates/default.conf.template

# copy previously built React bundle
COPY --from=build /app/frontend/build /app/frontend

# build date & version info
ARG VERSION
ARG GIT_COMMIT_HASH

ENV VERSION=${VERSION}
ENV GIT_COMMIT_HASH=${GIT_COMMIT_HASH}

# add OCI labels
LABEL maintainer="buildingSMART.org" \
      org.opencontainers.image.title="IFC Validation Service - Frontend" \
      org.opencontainers.image.description="Frontend for the buildingSMART IFC Validation Service" \
      org.opencontainers.image.authors="buildingSMART.org" \
      org.opencontainers.image.vendor="buildingSMART.org" \
      org.opencontainers.image.documentation="https://github.com/buildingSMART/validate" \
      org.opencontainers.image.url="https://github.com/buildingSMART/validate" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT_HASH}"