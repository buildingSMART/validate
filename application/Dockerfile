FROM ubuntu:latest

ARG DEBIAN_FRONTEND=noninteractive

WORKDIR /
RUN apt-get -y update && apt-get -y --no-install-recommends --no-install-suggests install git python3 python3-pip unzip wget libpq-dev build-essential libssl-dev libffi-dev libxml2-dev libxslt1-dev zlib1g-dev python3-setuptools python3-dev python3-wheel supervisor

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

RUN wget https://downloads.python.org/pypy/pypy3.8-v7.3.7-linux64.tar.bz2
RUN tar -xf pypy3.8-v7.3.7-linux64.tar.bz2
ENV PATH="${PATH}:/pypy3.8-v7.3.7-linux64/bin"

RUN /pypy3.8-v7.3.7-linux64/bin/python3 -m ensurepip

RUN /pypy3.8-v7.3.7-linux64/bin/python3 -m pip install --upgrade pip
RUN /pypy3.8-v7.3.7-linux64/bin/python3 -m pip install lark-parser==0.12.0

RUN python3 -m pip install --upgrade pip


RUN python3 -m pip install flask flask-cors numpy gunicorn rq redis SQLAlchemy==1.4.31 psycopg2 psycopg2cffi sqlalchemy-utils Flask-BasicAuth flasgger requests pyparsing XlsxWriter requests_oauthlib Authlib requests argparse behave pytest --upgrade


# IfcConvert v0.7.0
RUN wget https://s3.amazonaws.com/ifcopenshell-builds/IfcConvert-v0.7.0-476ab50-linux64.zip -O /tmp/IfcConvert.zip
RUN unzip /tmp/IfcConvert.zip -d /usr/bin

# IfcOpenShell-Python v0.7.0
RUN wget -O /tmp/ifcopenshell_python.zip https://s3.amazonaws.com/ifcopenshell-builds/ifcopenshell-python-`python3 -c 'import sys;print("".join(map(str, sys.version_info[0:2])))'`-v0.7.0-476ab50-linux64.zip
RUN mkdir -p `python3 -c 'import site; print(site.getusersitepackages())'`
RUN unzip -d `python3 -c 'import site; print(site.getusersitepackages())'` /tmp/ifcopenshell_python.zip


# Server
WORKDIR /www
COPY . /www

COPY application/checks /www/checks

COPY application/*.yml /www/

COPY .git/HEAD /tmp/.git/HEAD
COPY .git/refs/ /tmp/.git/refs/
RUN /bin/bash -c '(cat /tmp/.git/$(cat /tmp/.git/HEAD | cut -d \  -f 2)) || cat /tmp/.git/HEAD' > /version
RUN sed -i "4i<script>console.log('pipeline version: $(cat /version)');</script>" /www/application/templates/*.html
RUN rm -rf /tmp/.git

COPY application/queue.conf /etc/supervisord.conf

WORKDIR /www/application