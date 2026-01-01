.PHONY: build up down logs clean test

# Build all containers
build:
	docker-compose build

# Start all services
up:
	docker-compose up -d

# Start with development configuration
up-dev:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Stop all services
down:
	docker-compose down

# View logs
logs:
	docker-compose logs -f

# Clean everything
clean:
	docker-compose down -v --rmi all --remove-orphans

# Run tests
test:
	docker-compose run --rm peer1 python -c "import requests; r = requests.get('http://stun-server:8000/health'); print('STUN Server:', r.status_code, r.json())"

# Scale to N peers
scale:
	docker-compose up -d --scale peer=3

# Attach to peer1 console
attach-peer1:
	docker attach p2p-peer-1

# Attach to peer2 console
attach-peer2:
	docker attach p2p-peer-2

# Show running containers
ps:
	docker-compose ps

# Build and run full system
all: build up
	echo "System is running!"
	docker-compose ps