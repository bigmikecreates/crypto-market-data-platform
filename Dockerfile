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
ENV PATH=/home/crmd/.local/bin:$PATH

RUN groupadd --system --gid 1001 crmd && \
    useradd --system --uid 1001 --gid crmd --create-home --shell /bin/bash crmd

COPY --from=builder /root/.local /home/crmd/.local
RUN chown -R crmd:crmd /home/crmd/.local

WORKDIR /home/crmd
RUN mkdir /data && chown crmd:crmd /data

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

VOLUME /data
USER crmd
EXPOSE 8050

ENTRYPOINT ["/docker-entrypoint.sh"]
