FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /opt/termius-exporter

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY termius-exporter.py ./
RUN chmod +x /opt/termius-exporter/termius-exporter.py

ENTRYPOINT ["python3", "/opt/termius-exporter/termius-exporter.py"]
