"""
P2P Chat Client - Main Entry Point with Complete File Transfer Protocol
This file is the main entry point for the P2P chat client with improved file transfer.
"""

import sys
import os
import json
import logging
import threading
import time
import cmd
import socket
import base64
from typing import Dict, List, Optional, Tuple, Any, Callable
from colorama import init, Fore, Style
from dataclasses import dataclass, field
from enum import Enum

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add parent directory to path for imports
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from network import STUNClient
from tcp_handler import TCPServer
from file_transfer import FileTransfer

# Initialize colorama for colored output
init(autoreset=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('p2p_client.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class FileTransferState(Enum):
    """Enumeration of file transfer states"""
    IDLE = "idle"
    WAITING_CONFIRMATION = "waiting_confirmation"
    SENDING_CHUNKS = "sending_chunks"
    RECEIVING_CHUNKS = "receiving_chunks"


@dataclass
class FileTransferSession:
    """Session data for active file transfer"""
    filename: str = ""
    filesize: int = 0
    total_chunks: int = 0
    sent_chunks: int = 0
    received_chunks: int = 0
    file_hash: str = ""
    temp_filepath: str = ""
    state: FileTransferState = FileTransferState.IDLE
    peer_username: str = ""
    start_time: float = field(default_factory=time.time)
    filepath: str = ""  # Add this to store original file path for sending
@dataclass
class ConnectedPeer:
    """Information about a connected peer"""
    username: str
    connection_type: str  # 'incoming' or 'outgoing'
    socket: Any = None  # socket.socket object
    address: Optional[Tuple[str, int]] = None
    connected_at: float = field(default_factory=lambda: time.time())


class P2PClient(cmd.Cmd):
    """
    P2P Chat Client with Interactive Command Line Interface
    Complete implementation with advanced file transfer protocol
    """
    
    intro = f"""
{Fore.YELLOW}═══════════════════════════════════════════════{Style.RESET_ALL}
{Fore.CYAN}      P2P Chat Client v2.1 (Advanced File Transfer){Style.RESET_ALL}
{Fore.YELLOW}═══════════════════════════════════════════════{Style.RESET_ALL}
Type {Fore.GREEN}help{Style.RESET_ALL} or {Fore.GREEN}?{Style.RESET_ALL} to list commands.
    """
    prompt = f'{Fore.BLUE}P2P>{Style.RESET_ALL} '
    
    def __init__(self, username: str, ip: str = "127.0.0.1", port: int = 5000):
        super().__init__()
        self.username = username
        self.ip = ip
        self.port = port
        self.running = True
        
        # Network components
        self.stun_client = STUNClient()
        self.tcp_server = None
        
        # Connection management
        self.peers: Dict[str, ConnectedPeer] = {}
        self.current_chat: Optional[str] = None
        
        # File transfer management
        self.file_session: Optional[FileTransferSession] = None
        self.pending_file_request: Optional[Dict] = None
        
        # Thread management
        self.listener_threads: Dict[str, threading.Thread] = {}
        
        # Start the client
        self.start_client()
    
    def start_client(self):
        """Initialize and start the P2P client"""
        # Register with STUN server
        if not self.stun_client.register(self.username, self.ip, self.port):
            logger.error("Failed to register with STUN server. Exiting.")
            sys.exit(1)
        
        # Start TCP server for incoming connections
        self.tcp_server = TCPServer(
            host=self.ip,
            port=self.port,
            on_connection_request=self.handle_connection_request
        )
        self.tcp_server.start()
        
        print(f"{Fore.GREEN}✅ P2P Client '{self.username}' started at {self.ip}:{self.port}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📡 Waiting for connections...{Style.RESET_ALL}")
    
    def handle_connection_request(self, peer_info: dict):
        """Handle incoming connection requests"""
        peer_username = peer_info['username']
        peer_socket = peer_info['socket']
        peer_address = peer_info['address']
        
        print(f"\n{Fore.CYAN}🔗 Connection request from {peer_username}{Style.RESET_ALL}")
        
        # Ask user to accept or reject connection
        while True:
            response = input(f"Accept connection from {peer_username}? (y/n): ").strip().lower()
            
            if response == 'y':
                # Accept connection
                response_msg = {
                    "type": "connection_response",
                    "status": "accepted",
                    "message": f"Connection accepted by {self.username}"
                }
                peer_socket.send(json.dumps(response_msg).encode('utf-8'))
                
                # Create and store peer connection
                connected_peer = ConnectedPeer(
                    username=peer_username,
                    connection_type='incoming',
                    socket=peer_socket,
                    address=peer_address,
                    connected_at=time.time()
                )
                self.peers[peer_username] = connected_peer
                
                # Start listening for messages from this peer
                self.start_peer_listener(peer_username, peer_socket)
                
                print(f"{Fore.GREEN}✅ Connected to {peer_username}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Type 'chat {peer_username}' to start chatting{Style.RESET_ALL}")
                break
                
            elif response == 'n':
                # Reject connection
                response_msg = {
                    "type": "connection_response",
                    "status": "rejected",
                    "message": "Connection rejected"
                }
                peer_socket.send(json.dumps(response_msg).encode('utf-8'))
                peer_socket.close()
                print(f"{Fore.RED}❌ Connection rejected{Style.RESET_ALL}")
                break
    
    def start_peer_listener(self, peer_username: str, peer_socket: socket.socket):
        """Start a thread to listen for messages from a peer"""
        listener_thread = threading.Thread(
            target=self.listen_to_peer,
            args=(peer_socket, peer_username),
            daemon=True
        )
        self.listener_threads[peer_username] = listener_thread
        listener_thread.start()
    
    def listen_to_peer(self, sock: socket.socket, peer_username: str):
        """Listen for messages from a connected peer"""
        while self.running and peer_username in self.peers:
            try:
                # Set timeout to allow checking for running flag
                sock.settimeout(1.0)
                
                # Receive data
                data = sock.recv(65536)
                if not data:
                    break
                
                # Parse and handle message
                try:
                    message = json.loads(data.decode('utf-8'))
                    self.handle_peer_message(message, peer_username)
                except json.JSONDecodeError:
                    # Handle non-JSON data (could be binary file data)
                    self.handle_binary_data(data, peer_username)
                
            except socket.timeout:
                continue
            except (ConnectionResetError, ConnectionAbortedError):
                break
            except Exception as e:
                logger.error(f"Error receiving from {peer_username}: {e}")
                break
        
        # Cleanup disconnected peer
        self.remove_peer(peer_username)
    
    def handle_peer_message(self, message: dict, sender: str):
        """Handle incoming messages from peers"""
        msg_type = message.get('type', 'text')
        
        if msg_type == 'text':
            content = message.get('content', '')
            timestamp = message.get('timestamp', time.time())
            time_str = time.strftime('%H:%M:%S', time.localtime(timestamp))
            
            print(f"\n{Fore.YELLOW}[{sender}] {time_str}{Style.RESET_ALL}: {content}")
            
            if self.prompt and self.current_chat != sender:
                print(f"{self.prompt}", end='', flush=True)
        
        elif msg_type == 'file_info':
            self.handle_file_info(message, sender)
        
        elif msg_type == 'file_accept':
            self.handle_file_accept(sender)
        
        elif msg_type == 'file_reject':
            self.handle_file_reject(sender)
        
        elif msg_type == 'file_chunk':
            self.handle_file_chunk(message, sender)
        
        elif msg_type == 'file_complete':
            self.handle_file_complete(sender)
        
        elif msg_type == 'connection_response':
            status = message.get('status', 'rejected')
            if status == 'accepted':
                print(f"{Fore.GREEN}✅ Connection accepted by {sender}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}❌ Connection rejected by {sender}{Style.RESET_ALL}")
                self.remove_peer(sender)
    
    def handle_binary_data(self, data: bytes, sender: str):
        """Handle binary data (could be file chunks in raw format)"""
        if self.file_session and self.file_session.state == FileTransferState.RECEIVING_CHUNKS:
            # This is a file chunk in binary format
            self.process_file_chunk_binary(data, sender)
        else:
            logger.warning(f"Received unexpected binary data from {sender}")
    
    def handle_file_info(self, file_info: dict, sender: str):
        """Handle incoming file transfer request"""
        self.pending_file_request = {
            'info': file_info,
            'sender': sender,
            'timestamp': time.time()
        }
        
        print(f"\n{Fore.CYAN}📁 File incoming from {sender}:{Style.RESET_ALL}")
        print(f"   Name: {file_info.get('filename')}")
        print(f"   Size: {file_info.get('size')} bytes")
        print(f"   Type: {file_info.get('extension', 'Unknown')}")
        
        if self.current_chat == sender:
            print(f"{Fore.YELLOW}Type 'accept' to receive or 'reject' to decline{Style.RESET_ALL}")
        else:
            response = input(f"{Fore.YELLOW}Accept file? (y/n): {Style.RESET_ALL}").strip().lower()
            if response == 'y':
                self.accept_file_transfer(sender, file_info)
            else:
                self.reject_file_transfer(sender, file_info)
    
    def accept_file_transfer(self, sender: str, file_info: dict):
        """Accept incoming file transfer"""
        # Send acceptance response
        response = {
            "type": "file_accept",
            "filename": file_info.get('filename')
        }
        self.send_message(sender, response)
        
        # Initialize file session
        self.file_session = FileTransferSession(
            filename=file_info.get('filename'),
            filesize=file_info.get('size', 0),
            total_chunks=file_info.get('total_chunks', 0),
            file_hash=file_info.get('hash', ''),
            state=FileTransferState.RECEIVING_CHUNKS,
            peer_username=sender,
            start_time=time.time()
        )
        
        # Create received files directory
        os.makedirs("./received_files", exist_ok=True)
        
        # Create temporary file
        temp_filename = f"temp_{int(time.time())}_{self.file_session.filename}"
        self.file_session.temp_filepath = os.path.join("./received_files", temp_filename)
        
        print(f"{Fore.GREEN}✅ Waiting for file chunks from {sender}...{Style.RESET_ALL}")
    
    def reject_file_transfer(self, sender: str, file_info: dict):
        """Reject incoming file transfer"""
        response = {
            "type": "file_reject",
            "filename": file_info.get('filename')
        }
        self.send_message(sender, response)
        print(f"{Fore.YELLOW}File transfer rejected{Style.RESET_ALL}")
        self.pending_file_request = None
    
    def handle_file_accept(self, sender: str):
        """Handle file acceptance from receiver"""
        if self.file_session and self.file_session.state == FileTransferState.WAITING_CONFIRMATION:
            print(f"{Fore.GREEN}✅ Receiver accepted file transfer. Starting to send chunks...{Style.RESET_ALL}")
            self.file_session.state = FileTransferState.SENDING_CHUNKS
            self.start_file_sending(sender)
        else:
            print(f"{Fore.YELLOW}Unexpected file accept from {sender}{Style.RESET_ALL}")
    
    def handle_file_reject(self, sender: str):
        """Handle file rejection from receiver"""
        if self.file_session:
            print(f"{Fore.RED}❌ Receiver rejected file transfer{Style.RESET_ALL}")
            self.file_session = None
    
    def handle_file_chunk(self, chunk_info: dict, sender: str):
        """Handle incoming file chunk"""
        if not self.file_session or self.file_session.state != FileTransferState.RECEIVING_CHUNKS:
            print(f"{Fore.RED}Unexpected file chunk from {sender}{Style.RESET_ALL}")
            return
        
        chunk_id = chunk_info.get('chunk_id', 0)
        chunk_data_hex = chunk_info.get('data', '')
        filename = chunk_info.get('filename', self.file_session.filename)
        
        try:
            # Convert hex to bytes
            chunk_data = bytes.fromhex(chunk_data_hex)
            
            # Ensure temp directory exists
            os.makedirs(os.path.dirname(self.file_session.temp_filepath), exist_ok=True)
            
            # Write chunk to temporary file
            mode = 'ab' if chunk_id > 0 else 'wb'  # Write binary, append after first chunk
            with open(self.file_session.temp_filepath, mode) as f:
                f.write(chunk_data)
            
            self.file_session.received_chunks += 1
            self.file_session.filename = filename  # Update filename from chunks
            
            # Calculate progress
            progress = (self.file_session.received_chunks / self.file_session.total_chunks) * 100
            
            # Show progress every 10 chunks or when complete
            if chunk_id % 10 == 0 or self.file_session.received_chunks == self.file_session.total_chunks:
                print(f"{Fore.CYAN}📥 Receiving: {progress:.1f}% ({self.file_session.received_chunks}/{self.file_session.total_chunks}){Style.RESET_ALL}")
            
        except Exception as e:
            logger.error(f"Error processing file chunk: {e}")
            print(f"{Fore.RED}❌ Error processing chunk {chunk_id}: {e}{Style.RESET_ALL}")
    
    def process_file_chunk_binary(self, chunk_data: bytes, sender: str):
        """Process binary file chunk (alternative to JSON chunks)"""
        if not self.file_session or self.file_session.state != FileTransferState.RECEIVING_CHUNKS:
            return
        
        try:
            # Write chunk to temporary file
            with open(self.file_session.temp_filepath, 'ab') as f:
                f.write(chunk_data)
            
            self.file_session.received_chunks += 1
            
            # Calculate progress
            progress = (self.file_session.received_chunks / self.file_session.total_chunks) * 100
            
            if self.file_session.received_chunks % 10 == 0:
                print(f"{Fore.CYAN}📥 Receiving: {progress:.1f}% ({self.file_session.received_chunks}/{self.file_session.total_chunks}){Style.RESET_ALL}")
            
        except Exception as e:
            logger.error(f"Error processing binary chunk: {e}")
    
    def handle_file_complete(self, sender: str):
        """Handle file transfer completion"""
        if not self.file_session:
            print(f"{Fore.YELLOW}⚠️  File transfer complete but no active session{Style.RESET_ALL}")
            return
        
        print(f"{Fore.CYAN}📁 File transfer complete. Verifying...{Style.RESET_ALL}")
        
        # Finalize file
        final_filename = self.file_session.filename
        final_filepath = os.path.join("./received_files", final_filename)
        
        # Check for existing file and rename if necessary
        counter = 1
        original_final_filepath = final_filepath
        while os.path.exists(final_filepath):
            name, ext = os.path.splitext(final_filename)
            final_filename = f"{name}_{counter}{ext}"
            final_filepath = os.path.join("./received_files", final_filename)
            counter += 1
        
        try:
            # Rename temporary file to final name
            os.rename(self.file_session.temp_filepath, final_filepath)
            
            # Verify file size
            actual_size = os.path.getsize(final_filepath)
            expected_size = self.file_session.filesize
            
            if actual_size == expected_size:
                print(f"{Fore.GREEN}✅ File received successfully: {final_filepath}{Style.RESET_ALL}")
                print(f"{Fore.GREEN}   Size: {actual_size} bytes{Style.RESET_ALL}")
                
                # Verify file hash if available
                if self.file_session.file_hash:
                    import hashlib
                    with open(final_filepath, 'rb') as f:
                        file_hash = hashlib.md5()
                        for chunk in iter(lambda: f.read(8192), b''):
                            file_hash.update(chunk)
                        calculated_hash = file_hash.hexdigest()
                    
                    if calculated_hash == self.file_session.file_hash:
                        print(f"{Fore.GREEN}✅ Hash verified: {calculated_hash}{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.YELLOW}⚠️  Hash mismatch!{Style.RESET_ALL}")
                        print(f"   Expected: {self.file_session.file_hash}")
                        print(f"   Calculated: {calculated_hash}")
            else:
                print(f"{Fore.YELLOW}⚠️  File size mismatch!{Style.RESET_ALL}")
                print(f"   Expected: {expected_size} bytes")
                print(f"   Actual: {actual_size} bytes")
            
        except Exception as e:
            print(f"{Fore.RED}❌ Error finalizing file: {e}{Style.RESET_ALL}")
            # Try to save the temp file with a different name
            try:
                backup_path = f"./received_files/backup_{int(time.time())}_{final_filename}"
                os.rename(self.file_session.temp_filepath, backup_path)
                print(f"{Fore.YELLOW}⚠️  Saved backup to: {backup_path}{Style.RESET_ALL}")
            except:
                pass
        
        # Cleanup
        self.file_session = None
        self.pending_file_request = None
    
    # ========== COMMAND METHODS ==========
    
    def do_list(self, arg):
        """List all available peers: list"""
        peers = self.stun_client.get_peers()
        
        print(f"\n{Fore.CYAN}📋 Available Peers ({len(peers)}):{Style.RESET_ALL}")
        for i, peer in enumerate(peers, 1):
            if peer != self.username:
                info = self.stun_client.get_peer_info(peer)
                if info:
                    if peer in self.peers:
                        status = f"{Fore.GREEN}● Connected{Style.RESET_ALL}"
                    else:
                        status = f"{Fore.YELLOW}○ Available{Style.RESET_ALL}"
                    print(f"  {i}. {peer} - {info['ip_address']}:{info['port']} {status}")
    
    def do_connect(self, arg):
        """Connect to a peer: connect <username>"""
        if not arg:
            print(f"{Fore.RED}Usage: connect <username>{Style.RESET_ALL}")
            return
        
        if arg == self.username:
            print(f"{Fore.RED}Cannot connect to yourself!{Style.RESET_ALL}")
            return
        
        if arg in self.peers:
            print(f"{Fore.YELLOW}Already connected to {arg}{Style.RESET_ALL}")
            return
        
        # Get peer info from STUN
        info = self.stun_client.get_peer_info(arg)
        if not info:
            print(f"{Fore.RED}Peer '{arg}' not found{Style.RESET_ALL}")
            return
        
        print(f"{Fore.CYAN}Connecting to {arg} at {info['ip_address']}:{info['port']}...{Style.RESET_ALL}")
        
        # Create TCP connection
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((info['ip_address'], info['port']))
            
            # Send connection request
            request = {
                "type": "connection_request",
                "username": self.username,
                "timestamp": time.time()
            }
            sock.send(json.dumps(request).encode('utf-8'))
            
            # Wait for response
            response_data = sock.recv(1024)
            if not response_data:
                print(f"{Fore.RED}No response from {arg}{Style.RESET_ALL}")
                sock.close()
                return
            
            response = json.loads(response_data.decode('utf-8'))
            
            if response.get('status') == 'accepted':
                # Store connection
                connected_peer = ConnectedPeer(
                    username=arg,
                    connection_type='outgoing',
                    socket=sock,
                    address=(info['ip_address'], info['port']),
                    connected_at=time.time()
                )
                self.peers[arg] = connected_peer
                
                # Start listener thread
                self.start_peer_listener(arg, sock)
                
                print(f"{Fore.GREEN}✅ Successfully connected to {arg}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Type 'chat {arg}' to start chatting{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}❌ Connection rejected by {arg}{Style.RESET_ALL}")
                sock.close()
                
        except Exception as e:
            print(f"{Fore.RED}❌ Failed to connect to {arg}: {e}{Style.RESET_ALL}")
    
    def do_chat(self, arg):
        """Start chatting with a peer: chat <username>"""
        if not arg:
            print(f"{Fore.RED}Usage: chat <username>{Style.RESET_ALL}")
            return
        
        if arg not in self.peers:
            print(f"{Fore.RED}Not connected to {arg}. Use 'connect' first.{Style.RESET_ALL}")
            return
        
        self.current_chat = arg
        print(f"{Fore.GREEN}Now chatting with {arg}{Style.RESET_ALL}")
        print(f"Type {Fore.YELLOW}/exit{Style.RESET_ALL} to end chat, {Fore.YELLOW}/file <filename>{Style.RESET_ALL} to send file")
        print(f"Type {Fore.YELLOW}accept{Style.RESET_ALL} or {Fore.YELLOW}reject{Style.RESET_ALL} for pending file transfers")
        print(f"{Fore.CYAN}═══════════════════════════════════════════════{Style.RESET_ALL}")
        
        self.chat_loop(arg)
    
    def chat_loop(self, peer_username: str):
        """Chat loop with a specific peer"""
        while self.current_chat == peer_username:
            try:
                message = input(f"{Fore.BLUE}You to {peer_username}>{Style.RESET_ALL} ").strip()
                
                if not message:
                    continue
                
                # Check for file transfer responses
                if message.lower() == 'accept':
                    if self.pending_file_request and self.pending_file_request['sender'] == peer_username:
                        self.accept_file_transfer(peer_username, self.pending_file_request['info'])
                        continue
                    else:
                        print(f"{Fore.YELLOW}No pending file transfer from {peer_username}{Style.RESET_ALL}")
                        continue
                
                elif message.lower() == 'reject':
                    if self.pending_file_request and self.pending_file_request['sender'] == peer_username:
                        self.reject_file_transfer(peer_username, self.pending_file_request['info'])
                        continue
                    else:
                        print(f"{Fore.YELLOW}No pending file transfer from {peer_username}{Style.RESET_ALL}")
                        continue
                
                # Check for commands
                if message.lower() == '/exit':
                    self.current_chat = None
                    print(f"{Fore.YELLOW}Exited chat with {peer_username}{Style.RESET_ALL}")
                    break
                
                elif message.lower().startswith('/file '):
                    filename = message[6:].strip()
                    self.send_file_to_peer(filename, peer_username)
                
                elif message.lower() == '/status':
                    self.do_status("")
                
                elif message.lower() == '/help':
                    print(f"{Fore.CYAN}Chat commands:{Style.RESET_ALL}")
                    print(f"  {Fore.YELLOW}/exit{Style.RESET_ALL} - Exit chat")
                    print(f"  {Fore.YELLOW}/file <filename>{Style.RESET_ALL} - Send file")
                    print(f"  {Fore.YELLOW}/status{Style.RESET_ALL} - Show status")
                    print(f"  {Fore.YELLOW}accept{Style.RESET_ALL} - Accept pending file")
                    print(f"  {Fore.YELLOW}reject{Style.RESET_ALL} - Reject pending file")
                
                else:
                    # Send text message
                    msg_data = {
                        "type": "text",
                        "content": message,
                        "sender": self.username,
                        "timestamp": time.time()
                    }
                    
                    if self.send_message(peer_username, msg_data):
                        print(f"{Fore.GREEN}You{Style.RESET_ALL}: {message}")
                    else:
                        print(f"{Fore.RED}Failed to send message. Connection may be lost.{Style.RESET_ALL}")
                        self.current_chat = None
                        break
                        
            except KeyboardInterrupt:
                self.current_chat = None
                print(f"\n{Fore.YELLOW}Chat interrupted{Style.RESET_ALL}")
                break
            except Exception as e:
                logger.error(f"Error in chat loop: {e}")
                break
    
    def do_file(self, arg):
        """Send file to current chat: file <filename>"""
        if not self.current_chat:
            print(f"{Fore.RED}No active chat. Use 'chat <username>' first.{Style.RESET_ALL}")
            return
        
        if not arg:
            print(f"{Fore.RED}Usage: file <filename>{Style.RESET_ALL}")
            return
        
        self.send_file_to_peer(arg, self.current_chat)
    
    def send_file_to_peer(self, filepath: str, receiver: str):
        """Send file to another peer with complete protocol"""
        if receiver not in self.peers:
            print(f"{Fore.RED}Not connected to {receiver}{Style.RESET_ALL}")
            return
        
        if not os.path.exists(filepath):
            print(f"{Fore.RED}File not found: {filepath}{Style.RESET_ALL}")
            return
        
        print(f"{Fore.CYAN}Preparing to send file: {filepath}{Style.RESET_ALL}")
        
        # Prepare file info
        file_info = FileTransfer.prepare_file_info(filepath)
        if not file_info:
            print(f"{Fore.RED}Failed to prepare file info{Style.RESET_ALL}")
            return
        
        # Initialize file transfer session
        self.file_session = FileTransferSession(
            filename=file_info.get('filename'),
            filesize=file_info.get('size', 0),
            total_chunks=file_info.get('total_chunks', 0),
            file_hash=file_info.get('hash', ''),
            state=FileTransferState.WAITING_CONFIRMATION,
            peer_username=receiver,
            start_time=time.time(),
            filepath=filepath  # Store the original file path
        )
        
        # Send file info to receiver
        file_info['type'] = 'file_info'
        file_info['sender'] = self.username
        
        if not self.send_message(receiver, file_info):
            print(f"{Fore.RED}Failed to send file info{Style.RESET_ALL}")
            self.file_session = None
            return
        
        print(f"{Fore.CYAN}📤 File info sent. Waiting for receiver confirmation...{Style.RESET_ALL}")
        
        # Wait for confirmation with timeout (30 seconds)
        timeout = 30
        start_wait = time.time()
        
        while self.file_session and self.file_session.state == FileTransferState.WAITING_CONFIRMATION:
            if time.time() - start_wait > timeout:
                print(f"{Fore.RED}❌ File transfer timeout. Receiver did not respond.{Style.RESET_ALL}")
                self.file_session = None
                return
            
            # Check if we received acceptance in handle_file_accept
            time.sleep(0.5)
    
    def start_file_sending(self, receiver: str):
        """Start sending file chunks after receiver acceptance"""
        if not self.file_session or self.file_session.state != FileTransferState.SENDING_CHUNKS:
            return
        
        if not self.file_session.filepath or not os.path.exists(self.file_session.filepath):
            print(f"{Fore.RED}❌ File not found for sending: {self.file_session.filepath}{Style.RESET_ALL}")
            self.file_session = None
            return
        
        print(f"{Fore.CYAN}📤 Sending file chunks: {self.file_session.filename} ({self.file_session.filesize} bytes){Style.RESET_ALL}")
        
        try:
            # Read and send file chunks
            chunk_size = 4096  # 4KB chunks
            chunk_id = 0
            
            with open(self.file_session.filepath, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    
                    # Create chunk message
                    chunk_message = {
                        "type": "file_chunk",
                        "chunk_id": chunk_id,
                        "data": chunk.hex(),  # Convert bytes to hex for JSON
                        "total_chunks": self.file_session.total_chunks,
                        "filename": self.file_session.filename
                    }
                    
                    # Send chunk
                    if not self.send_message(receiver, chunk_message):
                        print(f"{Fore.RED}❌ Failed to send chunk {chunk_id}{Style.RESET_ALL}")
                        break
                    
                    chunk_id += 1
                    self.file_session.sent_chunks = chunk_id
                    
                    # Show progress every 10 chunks
                    if chunk_id % 10 == 0:
                        progress = (chunk_id / self.file_session.total_chunks) * 100
                        print(f"{Fore.CYAN}📤 Sending: {progress:.1f}% ({chunk_id}/{self.file_session.total_chunks}){Style.RESET_ALL}")
                    
                    # Small delay to prevent overwhelming the receiver
                    time.sleep(0.01)
            
            # Send completion message
            completion_message = {
                "type": "file_complete",
                "filename": self.file_session.filename,
                "hash": self.file_session.file_hash,
                "total_chunks": self.file_session.total_chunks
            }
            self.send_message(receiver, completion_message)
            
            print(f"{Fore.GREEN}✅ File sent successfully!{Style.RESET_ALL}")
            
        except Exception as e:
            print(f"{Fore.RED}❌ Error sending file: {e}{Style.RESET_ALL}")
        
        # Cleanup
        self.file_session = None
    
    def do_peers(self, arg):
        """Show connected peers: peers"""
        if not self.peers:
            print(f"{Fore.YELLOW}No active connections{Style.RESET_ALL}")
            return
        
        print(f"\n{Fore.CYAN}🤝 Connected Peers ({len(self.peers)}):{Style.RESET_ALL}")
        for username, peer in self.peers.items():
            duration = time.time() - peer.connected_at
            conn_type = peer.connection_type
            print(f"  • {username} ({conn_type}) - {duration:.0f}s")
    
    def do_send(self, arg):
        """Send quick message: send <username> <message>"""
        parts = arg.split(' ', 1)
        if len(parts) != 2:
            print(f"{Fore.RED}Usage: send <username> <message>{Style.RESET_ALL}")
            return
        
        username, message = parts
        
        if username not in self.peers:
            print(f"{Fore.RED}Not connected to {username}{Style.RESET_ALL}")
            return
        
        msg_data = {
            "type": "text",
            "content": message,
            "sender": self.username,
            "timestamp": time.time()
        }
        
        if self.send_message(username, msg_data):
            print(f"{Fore.GREEN}Message sent to {username}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}Failed to send message{Style.RESET_ALL}")
    
    def do_status(self, arg):
        """Show current status: status"""
        print(f"\n{Fore.CYAN}📊 Current Status:{Style.RESET_ALL}")
        print(f"  Username: {self.username}")
        print(f"  Address: {self.ip}:{self.port}")
        print(f"  Connected peers: {len(self.peers)}")
        print(f"  Current chat: {self.current_chat or 'None'}")
        
        if self.file_session:
            print(f"  File transfer: {self.file_session.state.value} with {self.file_session.peer_username}")
        
        if self.pending_file_request:
            print(f"  Pending file: from {self.pending_file_request['sender']}")
        
        if self.peers:
            print(f"\n{Fore.CYAN}Active connections:{Style.RESET_ALL}")
            for peer in self.peers.keys():
                print(f"  • {peer}")
    
    def do_clear(self, arg):
        """Clear screen: clear"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print(self.intro)
    
    def do_exit(self, arg):
        """Exit the client: exit"""
        print(f"\n{Fore.YELLOW}Shutting down client...{Style.RESET_ALL}")
        
        self.running = False
        
        # Close all connections
        for username, peer in list(self.peers.items()):
            if peer.socket:
                try:
                    peer.socket.close()
                except:
                    pass
        
        # Stop TCP server
        if self.tcp_server:
            self.tcp_server.stop()
        
        print(f"{Fore.GREEN}✅ Client shut down successfully{Style.RESET_ALL}")
        return True
    
    def do_help(self, arg):
        """Show help message: help"""
        print(f"\n{Fore.CYAN}Available Commands:{Style.RESET_ALL}")
        print(f"  {Fore.YELLOW}list{Style.RESET_ALL} - List available peers")
        print(f"  {Fore.YELLOW}connect <username>{Style.RESET_ALL} - Connect to a peer")
        print(f"  {Fore.YELLOW}chat <username>{Style.RESET_ALL} - Start chatting with a peer")
        print(f"  {Fore.YELLOW}send <username> <message>{Style.RESET_ALL} - Send quick message")
        print(f"  {Fore.YELLOW}file <filename>{Style.RESET_ALL} - Send file to current chat")
        print(f"  {Fore.YELLOW}peers{Style.RESET_ALL} - Show connected peers")
        print(f"  {Fore.YELLOW}status{Style.RESET_ALL} - Show current status")
        print(f"  {Fore.YELLOW}clear{Style.RESET_ALL} - Clear screen")
        print(f"  {Fore.YELLOW}exit{Style.RESET_ALL} - Exit client")
        print(f"  {Fore.YELLOW}help{Style.RESET_ALL} - Show this help")
        print(f"\n{Fore.CYAN}Chat Commands:{Style.RESET_ALL}")
        print(f"  {Fore.YELLOW}/exit{Style.RESET_ALL} - Exit chat")
        print(f"  {Fore.YELLOW}/file <filename>{Style.RESET_ALL} - Send file")
        print(f"  {Fore.YELLOW}/status{Style.RESET_ALL} - Show status")
        print(f"  {Fore.YELLOW}accept{Style.RESET_ALL} - Accept pending file transfer")
        print(f"  {Fore.YELLOW}reject{Style.RESET_ALL} - Reject pending file transfer")
    
    # ========== HELPER METHODS ==========
    
    def send_message(self, peer_username: str, message: dict) -> bool:
        """Send message to a peer"""
        if peer_username not in self.peers:
            return False
        
        peer = self.peers[peer_username]
        try:
            data = json.dumps(message).encode('utf-8')
            peer.socket.sendall(data)
            return True
        except Exception as e:
            logger.error(f"Failed to send to {peer_username}: {e}")
            self.remove_peer(peer_username)
            return False
    
    def remove_peer(self, peer_username: str):
        """Remove a peer connection"""
        if peer_username in self.peers:
            peer = self.peers[peer_username]
            if peer.socket:
                try:
                    peer.socket.close()
                except:
                    pass
            del self.peers[peer_username]
            
            if peer_username in self.listener_threads:
                del self.listener_threads[peer_username]
            
            if self.current_chat == peer_username:
                self.current_chat = None
            
            print(f"{Fore.YELLOW}⚠️  Disconnected from {peer_username}{Style.RESET_ALL}")


def main():
    """Main function to run the P2P client"""
    import argparse
    
    parser = argparse.ArgumentParser(description='P2P Chat Client')
    parser.add_argument('--username', required=True, help='Your username')
    parser.add_argument('--ip', default='127.0.0.1', help='Your IP address')
    parser.add_argument('--port', type=int, default=5000, help='Your port')
    parser.add_argument('--stun', default='http://localhost:8000', help='STUN server URL')
    
    args = parser.parse_args()
    
    try:
        client = P2PClient(args.username, args.ip, args.port)
        client.cmdloop()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Client terminated by user{Style.RESET_ALL}")
    except Exception as e:
        logger.error(f"Client error: {e}")
        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")


if __name__ == "__main__":
    main()