from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict
import redis
import uvicorn
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="STUN Server", version="1.0.0")

# Redis connection
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
        socket_connect_timeout=5
    )
    # Test connection
    redis_client.ping()
    print("✅ Connected to Redis successfully")
except redis.ConnectionError:
    print("⚠️  Using in-memory storage (Redis not available)")
    # Fallback to in-memory storage
    redis_client = None
    peers_storage = {}

# Data models
class PeerRegistration(BaseModel):
    username: str
    ip_address: str
    port: int

class PeerInfo(BaseModel):
    username: str
    ip_address: str
    port: int
    last_seen: str

class PeerList(BaseModel):
    peers: List[str]
    count: int

# Helper functions
def get_storage():
    """Get storage handler (Redis or in-memory)"""
    if redis_client:
        return redis_client
    return peers_storage

def save_peer_redis(peer: PeerRegistration):
    """Save peer to Redis"""
    peer_key = f"peer:{peer.username}"
    peer_data = {
        "ip_address": peer.ip_address,
        "port": str(peer.port),
        "last_seen": datetime.now().isoformat()
    }
    redis_client.hset(peer_key, mapping=peer_data)
    redis_client.sadd("all_peers", peer.username)

def save_peer_memory(peer: PeerRegistration):
    """Save peer to in-memory storage"""
    peers_storage[peer.username] = {
        "ip_address": peer.ip_address,
        "port": peer.port,
        "last_seen": datetime.now().isoformat()
    }

def get_all_peers_redis():
    """Get all peers from Redis"""
    return list(redis_client.smembers("all_peers"))

def get_all_peers_memory():
    """Get all peers from memory"""
    return list(peers_storage.keys())

def get_peer_info_redis(username: str):
    """Get peer info from Redis"""
    data = redis_client.hgetall(f"peer:{username}")
    if not data:
        return None
    return {
        "username": username,
        "ip_address": data["ip_address"],
        "port": int(data["port"]),
        "last_seen": data["last_seen"]
    }

def get_peer_info_memory(username: str):
    """Get peer info from memory"""
    if username not in peers_storage:
        return None
    data = peers_storage[username]
    return {
        "username": username,
        "ip_address": data["ip_address"],
        "port": data["port"],
        "last_seen": data["last_seen"]
    }

# API Endpoints
@app.post("/register", status_code=status.HTTP_201_CREATED)
async def register_peer(peer: PeerRegistration):
    """
    Register a new peer in the STUN server
    """
    # Validate username
    if not peer.username or len(peer.username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be at least 3 characters long"
        )
    
    # Check if peer already exists
    if redis_client:
        if redis_client.sismember("all_peers", peer.username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Peer '{peer.username}' already registered"
            )
        save_peer_redis(peer)
    else:
        if peer.username in peers_storage:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Peer '{peer.username}' already registered"
            )
        save_peer_memory(peer)
    
    return {
        "message": "Peer registered successfully",
        "peer": {
            "username": peer.username,
            "ip_address": peer.ip_address,
            "port": peer.port
        }
    }

@app.get("/peers", response_model=PeerList)
async def get_all_peers():
    """
    Get list of all registered peers
    """
    if redis_client:
        peers = get_all_peers_redis()
    else:
        peers = get_all_peers_memory()
    
    return {
        "peers": peers,
        "count": len(peers)
    }

@app.get("/peerinfo/{username}", response_model=PeerInfo)
async def get_peer_info(username: str):
    """
    Get detailed information about a specific peer
    """
    if redis_client:
        peer_info = get_peer_info_redis(username)
    else:
        peer_info = get_peer_info_memory(username)
    
    if not peer_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Peer '{username}' not found"
        )
    
    return peer_info

@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "storage": "redis" if redis_client else "memory",
        "peer_count": len(get_all_peers_redis() if redis_client else get_all_peers_memory())
    }
    return status

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )