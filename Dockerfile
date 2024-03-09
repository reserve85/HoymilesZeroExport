ARG BASE=alpine

FROM gcr.io/distroless/python3-debian12 AS base-distroless
FROM python:3.11-alpine AS base-alpine

FROM debian:12-slim AS build-distroless
RUN apt-get update && \
    apt-get install --no-install-suggests --no-install-recommends --yes python3-venv gcc libpython3-dev && \
    python3 -m venv /venv && \
    /venv/bin/pip install --upgrade pip setuptools wheel

FROM python:3.11-alpine AS build-alpine
RUN python3 -m venv /venv && \
    /venv/bin/pip install --upgrade pip setuptools wheel

FROM build-${BASE} AS build-venv
COPY requirements.txt /requirements.txt
RUN /venv/bin/pip install --disable-pip-version-check -r /requirements.txt

FROM base-${BASE}
COPY --from=build-venv /venv /venv

ENV PATH="/opt/venv/bin:$PATH"
ADD HoymilesZeroExport.py /app/
ADD config_provider.py /app/
ADD HoymilesZeroExport_Config.ini /app/
WORKDIR /app/
ENTRYPOINT ["/venv/bin/python3", "HoymilesZeroExport.py"]
