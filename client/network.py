import requests
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class STUNClient:
    def __init__(self, stun_url: str = "http://localhost:8000"):
        self.base_url = stun_url.rstrip('/')
    
    def register(self, username: str, ip: str, port: int) -> bool:
        """Register peer with STUN server"""
        try:
            response = requests.post(
                f"{self.base_url}/register",
                json={
                    "username": username,
                    "ip_address": ip,
                    "port": port
                },
                timeout=5
            )
            
            if response.status_code == 201:
                logger.info(f"✅ Registered as '{username}' with STUN server")
                return True
            else:
                logger.error(f"❌ Registration failed: {response.json()}")
                return False
        except requests.RequestException as e:
            logger.error(f"❌ Cannot connect to STUN server: {e}")
            return False
    
    def get_peers(self) -> List[str]:
        """Get list of all registered peers"""
        try:
            response = requests.get(f"{self.base_url}/peers", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('peers', [])
        except requests.RequestException as e:
            logger.error(f"❌ Failed to fetch peers: {e}")
        return []
    
    def get_peer_info(self, username: str) -> Optional[Dict]:
        """Get detailed info about a specific peer"""
        try:
            response = requests.get(f"{self.base_url}/peerinfo/{username}", timeout=5)
            if response.status_code == 200:
                return response.json()
        except requests.RequestException as e:
            logger.error(f"❌ Failed to get info for '{username}': {e}")
        return None
    
    def unregister(self, username: str) -> bool:
        """Optional: Unregister from STUN server (for clean exit)"""
        # Note: We'll need to add this endpoint to our STUN server
        pass