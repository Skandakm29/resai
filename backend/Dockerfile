FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --no-deps rapidocr_onnxruntime==1.4.4

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
# Run migrations as a separate release step (see docs/DEPLOYMENT.md).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
