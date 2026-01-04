FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy offline packages if available
COPY packages/ /app/packages/

# Install Garak - prefer offline packages, fallback to PyPI
RUN if ls /app/packages/*.whl 1> /dev/null 2>&1; then \
    echo "Installing from offline packages..." && \
    pip install --no-cache-dir --find-links=/app/packages/ garak fastapi uvicorn; \
    else \
    echo "Installing from PyPI..." && \
    pip install --no-cache-dir garak fastapi uvicorn; \
    fi

# Copy server code
COPY server.py .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
