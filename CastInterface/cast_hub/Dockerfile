FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install Python dependencies first for better build caching.
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

# Copy cast hub sources.
COPY . /app

# Startup script for Azure Linux Web App container.
RUN chmod +x /app/start-azure.sh

# Default local container port (Azure overrides with PORT env var).
EXPOSE 8000

CMD ["/app/start-azure.sh"]
