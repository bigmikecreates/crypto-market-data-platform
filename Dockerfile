FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "cmpd.server.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
