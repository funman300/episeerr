# Use official Python runtime as base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/logs /app/config /app/data /app/temp

# Copy application files
COPY webhook_listener.py .
COPY servertosonarr.py .
COPY modified_episeerr.py .
COPY sonarr_utils.py .
COPY templates/ templates/
COPY static/ static/

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5005/api/series-stats || exit 1

# Expose port
EXPOSE 5005

# Use Gunicorn to serve the application
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5005", "--access-logfile", "-", "--error-logfile", "-", "webhook_listener:app"]