FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY event_adapter.py .

ENV HONEYPOT_LOG_DIR=/var/log/honeypot
VOLUME /var/log/honeypot

CMD ["python", "-u", "event_adapter.py"]
