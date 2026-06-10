FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY /src /app/src

USER appuser

EXPOSE 8050

CMD ["uvicorn", "crmd_platform.server.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8050"]
