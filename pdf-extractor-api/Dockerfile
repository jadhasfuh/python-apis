FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY extractor_api.py .

EXPOSE 5050

CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5050", "extractor_api:app"]
