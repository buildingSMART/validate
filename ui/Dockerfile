FROM ubuntu:latest AS builder

RUN apt-get -y update && apt-get -y --no-install-recommends --no-install-suggests install ca-certificates wget
RUN wget -qO- https://nodejs.org/dist/v18.12.1/node-v18.12.1-linux-x64.tar.gz | tar -xzC /opt
ENV PATH /opt/node-v18.12.1-linux-x64/bin:$PATH

# Build react project
WORKDIR /www/ui
COPY . /www/ui

RUN npm install && npm run build && rm -rf node_modules

FROM nginx:1.17

COPY --from=builder /www/ui/build/ /www/
COPY nginx/app.conf /etc/nginx/conf.d/default.conf
