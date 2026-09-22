FROM python:3.12-slim

WORKDIR /app

# System deps: none beyond what reportlab/Flask need at the Python level.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY worksheet.py app.py ./
COPY templates ./templates

ENV OUTPUT_DIR=/data \
    PORT=5000 \
    PYTHONUNBUFFERED=1

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/healthz').read()" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "30", "app:app"]
