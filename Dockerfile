FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /build
COPY pyproject.toml ./
COPY src/ src/
RUN pip install --no-cache-dir --user .[server]


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN groupadd --system --gid 1001 crmd && \
    useradd --system --uid 1001 --gid crmd --create-home --shell /bin/bash crmd

COPY --from=builder /root/.local /home/crmd/.local

RUN chown -R crmd:crmd /home/crmd/.local

WORKDIR /home/crmd

ENV PATH=/home/crmd/.local/bin:$PATH
ENV CRMD_API_KEY=""
ENV CRMD_DATA_DIR="/data"

RUN mkdir /data && chown crmd:crmd /data
VOLUME /data

USER crmd

EXPOSE 8050

CMD exec crmd serve --host 0.0.0.0 --api-key "$CRMD_API_KEY" --path "$CRMD_DATA_DIR"
