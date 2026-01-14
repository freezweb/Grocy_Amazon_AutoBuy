FROM python:3.11-slim

LABEL maintainer="Grocy Amazon AutoBuy Contributors"
LABEL description="Automatische Amazon-Nachbestellung basierend auf Grocy Mindestbeständen"

# Arbeitsverzeichnis
WORKDIR /app

# System-Abhängigkeiten
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python-Abhängigkeiten zuerst (für besseres Caching)
COPY pyproject.toml .
COPY README.md .
COPY src/ src/

# Installation (nicht editierbar da Container)
RUN pip install --no-cache-dir .

# Datenverzeichnis
RUN mkdir -p /app/data

# Nicht-Root User
RUN useradd -m -u 1000 grocy && chown -R grocy:grocy /app
USER grocy

# Volume für persistente Daten
VOLUME ["/app/data"]

# Umgebungsvariablen
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Health Check
HEALTHCHECK --interval=60s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from grocy_amazon_autobuy.config import load_settings; load_settings()" || exit 1

# Standardbefehl: Daemon-Modus
ENTRYPOINT ["grocy-autobuy"]
CMD ["--daemon"]
