import requests
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class STUNClient:
    """Client for communicating with STUN server"""
    
    def __init__(self, stun_url: str = None):
        self.base_url = stun_url or "http://stun-server:8000"
        self.base_url = self.base_url.rstrip('/')
        logger.info(f"STUN client initialized with URL: {self.base_url}")
    
    def register(self, username: str, ip: str, port: int) -> bool:
        """
        Register peer with STUN server
        Returns: True if successful, False otherwise
        """
        try:
            actual_ip = "host.docker.internal" if "localhost" in ip else ip
            
            response = requests.post(
                f"{self.base_url}/register",
                json={
                    "username": username,
                    "ip_address": actual_ip,
                    "port": port
                },
                timeout=10
            )
            
            if response.status_code == 201:
                logger.info(f"Registered as '{username}' with STUN server")
                return True
            else:
                logger.error(f"Registration failed (Status {response.status_code}): {response.text}")
                return False
                
        except requests.ConnectionError as e:
            logger.error(f"Cannot connect to STUN server at {self.base_url}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during registration: {e}")
            return False
    
    def get_peers(self) -> List[str]:
        """Get list of all registered peers from STUN server"""
        try:
            response = requests.get(f"{self.base_url}/peers", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('peers', [])
            else:
                logger.error(f"Failed to fetch peers (Status {response.status_code})")
                return []
                
        except requests.RequestException as e:
            logger.error(f"Failed to fetch peers: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from STUN server: {e}")
            return []
    
    def get_peer_info(self, username: str) -> Optional[Dict]:
        """Get detailed information about a specific peer"""
        try:
            response = requests.get(
                f"{self.base_url}/peerinfo/{username}",
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.warning(f"Peer '{username}' not found on STUN server")
                return None
            else:
                logger.error(f"Failed to get peer info (Status {response.status_code})")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Failed to get info for '{username}': {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response for peer info: {e}")
            return None
    
    def unregister(self, username: str) -> bool:
        """
        Unregister peer from STUN server (for clean exit)
        Note: This endpoint needs to be implemented in the STUN server
        """
        try:
            response = requests.delete(
                f"{self.base_url}/unregister/{username}",
                timeout=5
            )
            
            if response.status_code in [200, 204]:
                logger.info(f"Unregistered '{username}' from STUN server")
                return True
            else:
                logger.warning(f"Unregister failed (Status {response.status_code})")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Failed to unregister: {e}")
            return False
    
    def health_check(self) -> bool:
        """Check if STUN server is healthy"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=3)
            return response.status_code == 200
        except:
            return False