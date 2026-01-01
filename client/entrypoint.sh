#!/bin/bash

# Wait for STUN server to be ready
echo "⏳ Waiting for STUN server..."
max_attempts=30
attempt=1

# Get container IP (برای ثبت‌نام در STUN)
CONTAINER_IP=$(hostname -i)
echo "📦 Container IP: $CONTAINER_IP"

while [ $attempt -le $max_attempts ]; do
    if curl -s http://stun-server:8000/health > /dev/null; then
        echo "✅ STUN server is ready!"
        break
    fi
    echo "Attempt $attempt/$max_attempts: STUN server not ready yet..."
    sleep 2
    ((attempt++))
done

if [ $attempt -gt $max_attempts ]; then
    echo "❌ STUN server not available after $max_attempts attempts"
    exit 1
fi

# Set defaults if not provided
USERNAME=${USERNAME:-"user_$(date +%s | tail -c 4)"}
PORT=${PORT:-5000}

echo "👤 Username: $USERNAME"
echo "📍 Port: $PORT"
echo "🔗 STUN Server: http://stun-server:8000"
echo "🏠 Container IP: $CONTAINER_IP"

# Run the client with container IP
exec python main.py --username "$USERNAME" --port "$PORT" --ip "$CONTAINER_IP" --stun "http://stun-server:8000"