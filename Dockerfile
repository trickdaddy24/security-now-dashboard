# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py sn-download VERSION ./
COPY grc_downloader/ ./grc_downloader/
COPY static/ ./static/
RUN chmod +x sn-download

RUN mkdir -p /data/downloads

ENV SN_DOWNLOAD_DIR=/data/downloads
EXPOSE 8787

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8787"]