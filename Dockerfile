# CoPaw Code Dockerfile
FROM python:3.14-slim

LABEL maintainer="CoPaw Team"
LABEL description="CoPaw Code - AI Coding Assistant"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV COPAW_HOME=/app

# Create working directory
WORKDIR $COPAW_HOME

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash copaw \
    && chown -R copaw:copaw $COPAW_HOME
USER copaw

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Alternative: CLI mode
# CMD ["copaw", "cli"]