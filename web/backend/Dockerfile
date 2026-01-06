# P2P Web Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application - اینجا همه چیز کپی میشه
COPY . .

# Create necessary directories - این خط را تغییر/اضافه کنید
RUN mkdir -p /app/uploads /app/templates /app/static/css /app/static/js /app/static/lib

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# Start server
CMD ["python", "app.py"]