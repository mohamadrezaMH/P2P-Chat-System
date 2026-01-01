#!/bin/bash
set -e

echo "🚀 Starting STUN Server with Redis..."

# Start Redis in background
echo "Starting Redis..."
redis-server --daemonize yes --bind 0.0.0.0

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
while ! redis-cli ping | grep -q "PONG"; do
  sleep 1
done
echo "✅ Redis is ready!"

# Start FastAPI server
echo "Starting FastAPI server on port 8000..."
exec uvicorn main:app --host 0.0.0.0 --port 8000