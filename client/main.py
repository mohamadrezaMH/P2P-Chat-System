import sys
import os
import json
import logging
import threading
import time
import cmd
from typing import Optional, List, Dict
from colorama import init, Fore, Style

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.network import STUNClient
from client.tcp_handler import TCPServer, TCPClient, PeerConnection
from client.file_transfer import FileTransfer

# Initialize colorama for colored output
init(autoreset=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format=f'{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - {Fore.GREEN}%(name)s{Style.RESET_ALL} - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('p2p_client.log')
    ]
)
logger = logging.getLogger(__name__)

class P2PClient(cmd.Cmd):
    intro = f"""
{Fore.YELLOW}═══════════════════════════════════════════════{Style.RESET_ALL}
{Fore.CYAN}      P2P Chat Client v1.0{Style.RESET_ALL}
{Fore.YELLOW}═══════════════════════════════════════════════{Style.RESET_ALL}
Type {Fore.GREEN}help{Style.RESET_ALL} or {Fore.GREEN}?{Style.RESET_ALL} to list commands.
    """
    prompt = f'{Fore.BLUE}P2P>{Style.RESET_ALL} '
    
    def __init__(self, username: str, ip: str = "127.0.0.1", port: int = 5000):
        super().__init__()
        self.username = username
        self.ip = ip
        self.port = port
        
        # Network components
        self.stun_client = STUNClient()
        self.tcp_server = None
        self.active_connections: Dict[str, PeerConnection] = {}
        self.current_chat: Optional[str] = None
        
        # For file transfer
        self.file_receiver = None
        
        # Start the client
        self.start_client()
    
    def start_client(self):
        """Initialize and start the P2P client"""
        # Register with STUN server
        if not self.stun_client.register(self.username, self.ip, self.port):
            logger.error("Failed to register with STUN server. Exiting.")
            sys.exit(1)
        
        # Start TCP server
        self.tcp_server = TCPServer(
            host=self.ip,
            port=self.port,
            on_message=self.handle_message,
            on_connection=self.handle_new_connection
        )
        self.tcp_server.start()
        
        logger.info(f"✅ P2P Client started for '{self.username}' at {self.ip}:{self.port}")
        print(f"{Fore.GREEN}✓ Registered as '{self.username}'{Style.RESET_ALL}")
    
    def handle_message(self, message: dict, sender: str):
        """Handle incoming messages"""
        msg_type = message.get('type', 'text')
        
        if msg_type == 'text':
            content = message.get('content', '')
            print(f"\n{Fore.YELLOW}[{sender}]{Style.RESET_ALL}: {content}")
            if self.prompt:
                print(f"{self.prompt}", end='', flush=True)
        
        elif msg_type == 'file_info':
            print(f"\n{Fore.CYAN}📁 File incoming from {sender}:{Style.RESET_ALL}")
            print(f"   Name: {message.get('filename')}")
            print(f"   Size: {message.get('size')} bytes")
            print(f"   Type: {message.get('extension')}")
            accept = input(f"{Fore.YELLOW}Accept file? (y/n): {Style.RESET_ALL}").lower()
            
            if accept == 'y':
                self.tcp_server.send_to_peer(sender, {"type": "file_accept"})
                # Start receiving file
                threading.Thread(
                    target=self.receive_file,
                    args=(message, sender),
                    daemon=True
                ).start()
            else:
                self.tcp_server.send_to_peer(sender, {"type": "file_reject"})
    
    def handle_new_connection(self, peer: PeerConnection):
        """Handle new incoming connection"""
        print(f"\n{Fore.GREEN}🔗 New connection from {peer.username}{Style.RESET_ALL}")
        self.active_connections[peer.username] = peer
        
        # If not chatting with anyone, ask if we want to chat
        if not self.current_chat:
            choice = input(f"Start chatting with {peer.username}? (y/n): ").lower()
            if choice == 'y':
                self.current_chat = peer.username
                print(f"{Fore.GREEN}Now chatting with {peer.username}{Style.RESET_ALL}")
    
    # ========== COMMAND METHODS ==========
    
    def do_list(self, arg):
        """List all available peers: list"""
        peers = self.stun_client.get_peers()
        
        print(f"\n{Fore.CYAN}📋 Available Peers ({len(peers)}):{Style.RESET_ALL}")
        for i, peer in enumerate(peers, 1):
            if peer != self.username:
                info = self.stun_client.get_peer_info(peer)
                if info:
                    status = f"{Fore.GREEN}● Online{Style.RESET_ALL}" if peer in self.active_connections else f"{Fore.RED}○ Offline{Style.RESET_ALL}"
                    print(f"  {i}. {peer} - {info['ip_address']}:{info['port']} {status}")
    
    def do_connect(self, arg):
        """Connect to a peer: connect <username>"""
        if not arg:
            print(f"{Fore.RED}Usage: connect <username>{Style.RESET_ALL}")
            return
        
        if arg == self.username:
            print(f"{Fore.RED}Cannot connect to yourself!{Style.RESET_ALL}")
            return
        
        # Get peer info
        info = self.stun_client.get_peer_info(arg)
        if not info:
            print(f"{Fore.RED}Peer '{arg}' not found{Style.RESET_ALL}")
            return
        
        # Connect via TCP
        client = TCPClient()
        if client.connect(info['ip_address'], info['port'], self.username):
            print(f"{Fore.GREEN}Connected to {arg}{Style.RESET_ALL}")
            self.current_chat = arg
            
            # Start listening for messages in background
            threading.Thread(
                target=self.listen_to_peer,
                args=(client, arg),
                daemon=True
            ).start()
        else:
            print(f"{Fore.RED}Failed to connect to {arg}{Style.RESET_ALL}")
    
    def do_chat(self, arg):
        """Start chatting with a peer: chat <username>"""
        if not arg:
            print(f"{Fore.RED}Usage: chat <username>{Style.RESET_ALL}")
            return
        
        if arg not in self.active_connections:
            print(f"{Fore.RED}Not connected to {arg}. Use 'connect' first.{Style.RESET_ALL}")
            return
        
        self.current_chat = arg
        print(f"{Fore.GREEN}Now chatting with {arg}{Style.RESET_ALL}")
        print(f"Type {Fore.YELLOW}/exit{Style.RESET_ALL} to end chat\n")
        
        # Simple chat loop
        while True:
            try:
                message = input(f"{Fore.BLUE}You to {arg}>{Style.RESET_ALL} ")
                
                if message.lower() == '/exit':
                    break
                elif message.lower().startswith('/file '):
                    # File transfer command
                    filename = message[6:].strip()
                    self.send_file(filename, arg)
                else:
                    # Send text message
                    msg_data = {
                        "type": "text",
                        "content": message,
                        "sender": self.username,
                        "timestamp": time.time()
                    }
                    
                    if not self.tcp_server.send_to_peer(arg, msg_data):
                        print(f"{Fore.RED}Failed to send message{Style.RESET_ALL}")
                        break
                        
            except KeyboardInterrupt:
                break
        
        self.current_chat = None
    
    def do_send(self, arg):
        """Send message to current chat: send <message>"""
        if not self.current_chat:
            print(f"{Fore.RED}No active chat. Use 'chat <username>' first.{Style.RESET_ALL}")
            return
        
        msg_data = {
            "type": "text",
            "content": arg,
            "sender": self.username,
            "timestamp": time.time()
        }
        
        if self.tcp_server.send_to_peer(self.current_chat, msg_data):
            print(f"{Fore.GREEN}Message sent{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}Failed to send message{Style.RESET_ALL}")
    
    def do_file(self, arg):
        """Send file to current chat: file <filename>"""
        if not self.current_chat:
            print(f"{Fore.RED}No active chat. Use 'chat <username>' first.{Style.RESET_ALL}")
            return
        
        if not arg:
            print(f"{Fore.RED}Usage: file <filename>{Style.RESET_ALL}")
            return
        
        self.send_file(arg, self.current_chat)
    
    def do_status(self, arg):
        """Show current status: status"""
        print(f"\n{Fore.CYAN}📊 Current Status:{Style.RESET_ALL}")
        print(f"  Username: {self.username}")
        print(f"  Address: {self.ip}:{self.port}")
        print(f"  Active connections: {len(self.active_connections)}")
        print(f"  Current chat: {self.current_chat or 'None'}")
        
        if self.active_connections:
            print(f"\n{Fore.CYAN}Connected peers:{Style.RESET_ALL}")
            for peer in self.active_connections.keys():
                print(f"  • {peer}")
    
    def do_exit(self, arg):
        """Exit the client: exit"""
        print(f"{Fore.YELLOW}Shutting down...{Style.RESET_ALL}")
        if self.tcp_server:
            self.tcp_server.stop()
        return True
    
    # ========== HELPER METHODS ==========
    
    def listen_to_peer(self, client: TCPClient, username: str):
        """Listen for messages from a connected peer"""
        while client.connected:
            message = client.receive(timeout=1)
            if message:
                self.handle_message(message, username)
            time.sleep(0.1)
    
    def send_file(self, filepath: str, receiver: str):
        """Send file to another peer"""
        if not os.path.exists(filepath):
            print(f"{Fore.RED}File not found: {filepath}{Style.RESET_ALL}")
            return
        
        print(f"{Fore.CYAN}Sending file: {filepath}{Style.RESET_ALL}")
        
        def send_wrapper(message):
            return self.tcp_server.send_to_peer(receiver, message)
        
        if FileTransfer.send_file(filepath, send_wrapper):
            print(f"{Fore.GREEN}File sent successfully!{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}File transfer failed{Style.RESET_ALL}")
    
    def receive_file(self, file_info: dict, sender: str):
        """Receive file from another peer"""
        # This would be implemented to handle file chunks
        print(f"{Fore.CYAN}Starting file receive...{Style.RESET_ALL}")
        # Implementation depends on your chunking strategy

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='P2P Chat Client')
    parser.add_argument('--username', required=True, help='Your username')
    parser.add_argument('--ip', default='127.0.0.1', help='Your IP address')
    parser.add_argument('--port', type=int, default=5000, help='Your port')
    parser.add_argument('--stun', default='http://localhost:8000', help='STUN server URL')
    
    args = parser.parse_args()
    
    # Set STUN URL
    if hasattr(args, 'stun'):
        import client.network
        client.network.STUNClient.base_url = args.stun
    
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