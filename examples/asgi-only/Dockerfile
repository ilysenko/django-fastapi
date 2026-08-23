FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /package
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip install --no-cache-dir . uvicorn gunicorn "psycopg[binary]"

WORKDIR /app
COPY examples/asgi-only/app ./

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000

CMD ["uvicorn", "acme.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
