FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sf_upload_proxy.py .

EXPOSE 5051

CMD ["uvicorn", "sf_upload_proxy:app", "--host", "0.0.0.0", "--port", "5051"]
