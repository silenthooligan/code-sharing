FROM python:3.12-slim

## 1. Force Python to log to stdout immediately (FIXES EMPTY LOGS)
ENV PYTHONUNBUFFERED=1

RUN mkdir -p /home/appuser/.streamlit && \
    chown 1000:1000 /home/appuser && \
    chown 1000:1000 /home/appuser/.streamlit
ENV HOME=/home/appuser

# Install system deps
RUN apt-get update && apt-get install -y \
    aria2 \
    procps \
    curl \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Install the tool and Streamlit
RUN pip install --no-cache-dir cyberdrop-dl-patched streamlit requests beautifulsoup4

EXPOSE 8501
WORKDIR /app

RUN mkdir -p /app/AppData && chown -R 1000:1000 /app/AppData
COPY app.py /app/app.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
