FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY pyproject.toml .
COPY voxbridge/ voxbridge/
RUN pip install --no-cache-dir ".[server]"

# Copy config (can be overridden via volume mount)
COPY examples/config_driven/bridge.yaml /app/bridge.yaml

# Expose the default VoxBridge port
EXPOSE 8765

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8765/health')" || exit 1

# Run VoxBridge
CMD ["voxbridge", "run", "--config", "/app/bridge.yaml"]
