import socket
import threading
import json
import logging
import time
from typing import Dict, Callable, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PeerConnection:
    socket: socket.socket
    address: tuple
    username: str

class TCPServer:
    def __init__(self, host: str, port: int, 
                 on_message: Callable[[str, str], None] = None,
                 on_connection: Callable[[PeerConnection], None] = None):
        self.host = host
        self.port = port
        self.on_message = on_message
        self.on_connection = on_connection
        self.server_socket = None
        self.running = False
        self.connections: Dict[str, PeerConnection] = {}
        self.lock = threading.Lock()
    
    def start(self):
        """Start TCP server in background thread"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10)
        self.server_socket.settimeout(1)
        self.running = True
        
        logger.info(f" TCP Server listening on {self.host}:{self.port}")
        
        # Start accept thread
        accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        accept_thread.start()
    
    def _accept_loop(self):
        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                logger.info(f" New connection from {client_address}")
                
                # Create peer connection
                peer = PeerConnection(
                    socket=client_socket,
                    address=client_address,
                    username=f"unknown_{client_address[1]}"
                )
                
                # Handle in separate thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(peer,),
                    daemon=True
                )
                client_thread.start()
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"❌ Error accepting connection: {e}")
    
    def _handle_client(self, peer: PeerConnection):
        """Handle communication with a connected client"""
        try:
            # First message should be handshake with username
            handshake_data = peer.socket.recv(1024).decode('utf-8')
            handshake = json.loads(handshake_data)
            
            if handshake.get('type') == 'handshake':
                peer.username = handshake.get('username', peer.username)
                
                with self.lock:
                    self.connections[peer.username] = peer
                
                logger.info(f" Handshake complete with {peer.username}")
                
                if self.on_connection:
                    self.on_connection(peer)
                
                # Listen for messages
                while self.running:
                    try:
                        data = peer.socket.recv(4096)
                        if not data:
                            break
                        
                        message = data.decode('utf-8')
                        
                        try:
                            msg_json = json.loads(message)
                            if self.on_message:
                                self.on_message(msg_json, peer.username)
                        except json.JSONDecodeError:
                            # Handle raw text or binary data
                            if self.on_message:
                                self.on_message(
                                    {"type": "text", "content": message},
                                    peer.username
                                )
                                
                    except (ConnectionResetError, ConnectionAbortedError):
                        break
                    except Exception as e:
                        logger.error(f"Error receiving from {peer.username}: {e}")
                        break
                        
        except Exception as e:
            logger.error(f"Error handling client {peer.address}: {e}")
        finally:
            self._remove_connection(peer)
            peer.socket.close()
    
    def _remove_connection(self, peer: PeerConnection):
        """Remove a connection"""
        with self.lock:
            if peer.username in self.connections:
                del self.connections[peer.username]
                logger.info(f" Connection closed with {peer.username}")
    
    def send_to_peer(self, username: str, message: dict) -> bool:
        """Send message to specific peer"""
        with self.lock:
            if username not in self.connections:
                logger.error(f"Peer '{username}' not connected")
                return False
            
            try:
                data = json.dumps(message).encode('utf-8')
                self.connections[username].socket.sendall(data)
                return True
            except Exception as e:
                logger.error(f"Failed to send to {username}: {e}")
                self._remove_connection(self.connections[username])
                return False
    
    def broadcast(self, message: dict, exclude: str = None):
        """Broadcast message to all connected peers"""
        with self.lock:
            for username, peer in list(self.connections.items()):
                if username == exclude:
                    continue
                try:
                    data = json.dumps(message).encode('utf-8')
                    peer.socket.sendall(data)
                except Exception as e:
                    logger.error(f"Failed to broadcast to {username}: {e}")
    
    def stop(self):
        """Stop TCP server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        with self.lock:
            for peer in self.connections.values():
                peer.socket.close()
            self.connections.clear()
        logger.info(" TCP Server stopped")

class TCPClient:
    def __init__(self):
        self.socket = None
        self.connected = False
        self.peer_username = None
    
    def connect(self, ip: str, port: int, my_username: str) -> bool:
        """Connect to another peer"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)
            self.socket.connect((ip, port))
            
            # Send handshake
            handshake = {
                "type": "handshake",
                "username": my_username,
                "timestamp": time.time()
            }
            self.socket.sendall(json.dumps(handshake).encode('utf-8'))
            
            self.connected = True
            logger.info(f" Connected to {ip}:{port}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to {ip}:{port}: {e}")
            return False
    
    def send(self, message: dict) -> bool:
        """Send message to connected peer"""
        if not self.connected or not self.socket:
            return False
        
        try:
            data = json.dumps(message).encode('utf-8')
            self.socket.sendall(data)
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            self.connected = False
            return False
    
    def receive(self, timeout: float = None) -> Optional[dict]:
        """Receive message from connected peer"""
        if not self.connected or not self.socket:
            return None
        
        try:
            if timeout:
                self.socket.settimeout(timeout)
            
            data = self.socket.recv(4096)
            if not data:
                self.connected = False
                return None
            
            message = json.loads(data.decode('utf-8'))
            return message
            
        except socket.timeout:
            return None
        except Exception as e:
            logger.error(f"Error receiving: {e}")
            self.connected = False
            return None
    
    def disconnect(self):
        """Disconnect from peer"""
        if self.socket:
            self.socket.close()
        self.connected = False
        logger.info("Disconnected from peer")