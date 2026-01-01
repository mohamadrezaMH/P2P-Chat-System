# P2P Client Dockerfile - Fixed
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ALL client files directly to /app (not in client subdirectory)
COPY main.py .
COPY network.py .
COPY tcp_handler.py .
COPY file_transfer.py .
COPY entrypoint.sh .

# Create directories for file transfer
RUN mkdir -p /app/received_files

# Make entrypoint executable
RUN chmod +x entrypoint.sh

EXPOSE 5000-5010

ENTRYPOINT ["/app/entrypoint.sh"]