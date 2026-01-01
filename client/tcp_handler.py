import socket
import threading
import json
import logging
from typing import Dict, Callable, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConnectionInfo:
    """Information about a TCP connection"""
    socket: socket.socket
    address: tuple
    username: str = "unknown"


class TCPServer:
    """TCP Server for accepting incoming connections"""
    
    def __init__(self, host: str, port: int,
                 on_connection_request: Callable[[dict], None]):
        self.host = host
        self.port = port
        self.on_connection_request = on_connection_request
        self.server_socket = None
        self.running = False
        self.accept_thread = None
        
        logger.debug(f"TCP Server initialized on {host}:{port}")
    
    def start(self):
        """Start TCP server in background thread"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            self.server_socket.settimeout(1)
            self.running = True
            
            self.accept_thread = threading.Thread(
                target=self._accept_connections,
                daemon=True
            )
            self.accept_thread.start()
            
            logger.info(f"📡 TCP Server listening on {self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"Failed to start TCP server: {e}")
            raise
    
    def _accept_connections(self):
        """Accept incoming connections in a loop"""
        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                logger.info(f"New connection from {client_address}")
                
                # Handle connection in separate thread
                client_thread = threading.Thread(
                    target=self._handle_incoming_connection,
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Error accepting connection: {e}")
    
    def _handle_incoming_connection(self, client_socket: socket.socket, client_address: tuple):
        """Handle a single incoming connection"""
        try:
            # Set timeout for handshake
            client_socket.settimeout(10)
            
            # Receive handshake data
            handshake_data = client_socket.recv(1024).decode('utf-8')
            handshake = json.loads(handshake_data)
            
            if handshake.get('type') == 'connection_request':
                username = handshake.get('username', f'unknown_{client_address[1]}')
                
                # Create connection info
                connection_info = ConnectionInfo(
                    socket=client_socket,
                    address=client_address,
                    username=username
                )
                
                # Notify main client about connection request
                peer_info = {
                    'username': username,
                    'socket': client_socket,
                    'address': client_address
                }
                
                # Call the callback to handle connection request
                if self.on_connection_request:
                    self.on_connection_request(peer_info)
                else:
                    # Default behavior if no callback
                    logger.warning("No connection request handler registered")
                    response = {
                        "type": "connection_response",
                        "status": "rejected",
                        "message": "No handler available"
                    }
                    client_socket.send(json.dumps(response).encode('utf-8'))
                    client_socket.close()
                    
            else:
                logger.warning(f"Invalid handshake from {client_address}")
                client_socket.close()
                
        except socket.timeout:
            logger.warning(f"Handshake timeout from {client_address}")
            client_socket.close()
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in handshake from {client_address}")
            client_socket.close()
        except Exception as e:
            logger.error(f"Error handling incoming connection: {e}")
            try:
                client_socket.close()
            except:
                pass
    
    def stop(self):
        """Stop TCP server"""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        logger.info("🛑 TCP Server stopped")


class TCPClient:
    """TCP Client for making outgoing connections"""
    
    def __init__(self):
        self.socket = None
        self.connected = False
        self.peer_info = {}
        
        logger.debug("TCP Client initialized")
    
    def connect(self, host: str, port: int, timeout: int = 10) -> bool:
        """
        Connect to a remote host
        Returns: True if successful, False otherwise
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(timeout)
            self.socket.connect((host, port))
            self.connected = True
            
            logger.info(f"Connected to {host}:{port}")
            return True
            
        except socket.timeout:
            logger.error(f"Connection timeout to {host}:{port}")
            return False
        except ConnectionRefusedError:
            logger.error(f"Connection refused by {host}:{port}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to {host}:{port}: {e}")
            return False
    
    def send(self, data: bytes) -> bool:
        """Send data through the socket"""
        if not self.connected or not self.socket:
            return False
        
        try:
            self.socket.sendall(data)
            return True
        except Exception as e:
            logger.error(f"Failed to send data: {e}")
            self.connected = False
            return False
    
    def receive(self, buffer_size: int = 4096, timeout: Optional[float] = None) -> Optional[bytes]:
        """Receive data from the socket"""
        if not self.connected or not self.socket:
            return None
        
        try:
            if timeout is not None:
                self.socket.settimeout(timeout)
            
            data = self.socket.recv(buffer_size)
            if not data:
                self.connected = False
                return None
            
            return data
            
        except socket.timeout:
            return None
        except Exception as e:
            logger.error(f"Error receiving data: {e}")
            self.connected = False
            return None
    
    def disconnect(self):
        """Disconnect from remote host"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.connected = False
        logger.info("Disconnected from peer")
    
    def __del__(self):
        """Destructor to ensure socket is closed"""
        self.disconnect()