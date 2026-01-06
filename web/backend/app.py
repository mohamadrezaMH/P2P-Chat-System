"""
P2P Web Backend - Flask Application with WebSocket Support
This backend bridges the web interface with the P2P core.
"""

import json
import logging
import threading
import time
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import requests
import subprocess
import sys
import os

# Add parent directory to path to import P2P core
sys.path.append('../../client')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

print(f"BASE_DIR: {BASE_DIR}")
print(f"TEMPLATE_DIR: {TEMPLATE_DIR}")
print(f"STATIC_DIR: {STATIC_DIR}")

app = Flask(__name__, 
            template_folder=TEMPLATE_DIR,
            static_folder=STATIC_DIR,
            static_url_path='/static')

CORS(app, resources={r"/*": {"origins": "*"}})
app.config['SECRET_KEY'] = 'p2p-secret-key-2024'
app.config['DEBUG'] = True

# تنظیمات اضافی برای WebSocket
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='eventlet',
    ping_timeout=60,
    ping_interval=25,
    logger=True,
    engineio_logger=True,  # فعال کردن لاگ‌های EngineIO
    always_connect=True
)

# Configure logging
logging.basicConfig(level=logging.DEBUG) 
logger = logging.getLogger(__name__)

# Configuration
STUN_SERVER_URL = os.getenv('STUN_SERVER_URL', 'http://stun-server:8000')
P2P_CORE_PATH = '../../client/main.py'

class P2PWebBridge:
    """Bridge between web interface and P2P core"""
    
    def __init__(self):
        self.active_users = {}  # username -> socket_id
        self.user_peers = {}    # username -> list of connected peers
        self.p2p_processes = {} # username -> subprocess
        
    def register_user(self, username, port, socket_id):
        """Register a new user in the system"""
        if username in self.active_users:
            return False
        
        self.active_users[username] = socket_id
        self.user_peers[username] = []
        
        # Register with STUN server
        try:
            response = requests.post(
                f"{STUN_SERVER_URL}/register",
                json={
                    "username": username,
                    "ip_address": "web-user",  # Special identifier for web users
                    "port": port
                },
                timeout=5
            )
            
            if response.status_code == 201:
                logger.info(f"Web user '{username}' registered with STUN")
                return True
            else:
                logger.error(f"STUN registration failed: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error registering with STUN: {e}")
            return False
    
    def get_available_peers(self, exclude_user=None):
        """Get list of all available peers from STUN server"""
        try:
            response = requests.get(f"{STUN_SERVER_URL}/peers", timeout=5)
            if response.status_code == 200:
                data = response.json()
                peers = data.get('peers', [])
                
                # Filter out web users and exclude specific user
                filtered_peers = []
                for peer in peers:
                    if peer != exclude_user and peer not in self.active_users:
                        # Get peer info
                        info_response = requests.get(
                            f"{STUN_SERVER_URL}/peerinfo/{peer}",
                            timeout=5
                        )
                        if info_response.status_code == 200:
                            peer_info = info_response.json()
                            filtered_peers.append({
                                'username': peer,
                                'ip_address': peer_info.get('ip_address'),
                                'port': peer_info.get('port'),
                                'type': 'cli'  # CLI peer
                            })
                
                # Add web users (except excluded)
                for username, socket_id in self.active_users.items():
                    if username != exclude_user:
                        filtered_peers.append({
                            'username': username,
                            'ip_address': 'web-interface',
                            'port': 'N/A',
                            'type': 'web'  # Web peer
                        })
                
                return filtered_peers
            return []
        except Exception as e:
            logger.error(f"Error getting peers: {e}")
            return []
    
    def connect_to_peer(self, username, target_username):
        """Connect a web user to another peer"""
        if username not in self.active_users:
            return False, "User not registered"
        
        # For web-to-web connections, we just track them
        if target_username in self.active_users:
            if target_username not in self.user_peers[username]:
                self.user_peers[username].append(target_username)
            if username not in self.user_peers[target_username]:
                self.user_peers[target_username].append(username)
            
            # Notify both users
            socketio.emit('peer_connected', {
                'peer': target_username,
                'type': 'web'
            }, room=self.active_users[username])
            
            socketio.emit('peer_connected', {
                'peer': username,
                'type': 'web'
            }, room=self.active_users[target_username])
            
            return True, "Connected to web user"
        
        # For web-to-CLI connections, we need to handle differently
        # This would require actually connecting via TCP
        return False, "CLI connections not yet implemented"
    
    def disconnect_user(self, username):
        """Remove a user from the system"""
        if username in self.active_users:
            socket_id = self.active_users[username]
            
            # Notify connected peers
            for peer in self.user_peers.get(username, []):
                if peer in self.active_users:
                    socketio.emit('peer_disconnected', {
                        'peer': username
                    }, room=self.active_users[peer])
            
            # Cleanup
            if username in self.user_peers:
                del self.user_peers[username]
            del self.active_users[username]
            
            # Unregister from STUN (optional)
            try:
                requests.delete(f"{STUN_SERVER_URL}/unregister/{username}", timeout=2)
            except:
                pass
            
            return True
        return False
    
    def send_message(self, from_user, to_user, message):
        """Send message from one user to another"""
        if from_user not in self.active_users:
            return False, "Sender not found"
        
        # Web-to-web message
        if to_user in self.active_users:
            socketio.emit('message_received', {
                'from': from_user,
                'message': message,
                'timestamp': time.time()
            }, room=self.active_users[to_user])
            return True, "Message sent"
        
        # Web-to-CLI message (would need TCP connection)
        return False, "CLI messaging not implemented"
    
    def send_file(self, from_user, to_user, filename, file_data):
        """Send file from one user to another"""
        logger.debug(f"Sending file from {from_user} to {to_user}: {filename} ({len(file_data)} bytes base64)")
        
        if from_user not in self.active_users:
            logger.error(f"Sender {from_user} not found")
            return False, "Sender not found"
        
        # Web-to-web file transfer
        if to_user in self.active_users:
            # ایجاد یک ID یکتا برای فایل
            file_id = f"file_{int(time.time())}_{filename}"
            
            # ذخیره موقت فایل در memory (یا می‌توانید در فایل سیستم ذخیره کنید)
            socketio.emit('file_received', {
                'from': from_user,
                'filename': filename,
                'data': file_data,  # base64 encoded
                'file_id': file_id,
                'timestamp': time.time(),
                'size': len(file_data)
            }, room=self.active_users[to_user])
            
            logger.info(f"✅ File sent from {from_user} to {to_user}: {filename}")
            return True, "File sent"
        
        # Web-to-CLI file transfer (برای آینده)
        logger.warning(f"Cannot send file to CLI user {to_user}")
        return False, "CLI file transfer not implemented"

# Initialize bridge
p2p_bridge = P2PWebBridge()


# app = Flask(__name__, 
#             template_folder='../frontend',
#             static_folder='../frontend')
# Web Routes
@app.route('/')
def index():
    """Serve the main page"""
    logger.debug("Serving index.html")
    return render_template('index.html')

@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'P2P Web Backend',
        'timestamp': time.time(),
        'active_users': len(p2p_bridge.active_users)
    })
    



@app.route('/api/test/connection')
def test_connection():
    """Test connection endpoint"""
    return jsonify({
        'websocket_available': True,
        'stun_server': STUN_SERVER_URL,
        'active_users': list(p2p_bridge.active_users.keys())
    })

# WebSocket Events
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"✅ WebSocket Client connected: {request.sid}")
    emit('connected', {
        'sid': request.sid,
        'message': 'Connection established'
    })
    
    # همچنین می‌توانیم status update بفرستیم
    emit('status_update', {
        'type': 'connection',
        'status': 'connected',
        'message': 'WebSocket connection established'
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"❌ WebSocket Client disconnected: {request.sid}")
    
    # Find and cleanup user
    for username, sid in p2p_bridge.active_users.items():
        if sid == request.sid:
            p2p_bridge.disconnect_user(username)
            logger.info(f"Cleaned up user: {username}")
            break

@socketio.on('register')
def handle_register(data):
    """Handle user registration via WebSocket"""
    logger.info(f"📝 Registration request received: {data}")
    username = data.get('username')
    port = data.get('port', 6000)
    
    if not username:
        logger.error("No username provided in registration")
        emit('registration_result', {
            'success': False,
            'error': 'Username required'
        })
        return
    
    success = p2p_bridge.register_user(username, port, request.sid)
    
    logger.info(f"Registration result for {username}: {success}")
    emit('registration_result', {
        'success': success,
        'username': username if success else None,
        'message': 'Registration successful' if success else 'Registration failed'
    })

@socketio.on('get_peers')
def handle_get_peers(data):
    """Handle request for peers list"""
    username = data.get('username')
    logger.debug(f"Getting peers for user: {username}")
    peers = p2p_bridge.get_available_peers(exclude_user=username)
    
    emit('peers_list', {
        'peers': peers,
        'count': len(peers)
    })

@socketio.on('connect_to_peer')
def handle_connect_to_peer(data):
    """Handle connection request to a peer"""
    username = data.get('username')
    target = data.get('target')
    logger.info(f"Connection request: {username} -> {target}")
    
    success, message = p2p_bridge.connect_to_peer(username, target)
    
    emit('connection_result', {
        'success': success,
        'message': message,
        'peer': target
    })

@socketio.on('send_message')
def handle_send_message(data):
    """Handle sending a message"""
    from_user = data.get('from')
    to_user = data.get('to')
    message = data.get('message')
    logger.info(f"Message from {from_user} to {to_user}: {message[:50]}...")
    
    success, msg = p2p_bridge.send_message(from_user, to_user, message)
    
    emit('message_sent', {
        'success': success,
        'message': msg,
        'to': to_user,
        'original_message': message[:100]  # برای لاگ
    })

@socketio.on('ping')
def handle_ping():
    """Handle ping for connection testing"""
    emit('pong', {'timestamp': time.time()})
    
    
    
@socketio.on('send_file')
def handle_send_file(data):
    """Handle sending a file"""
    from_user = data.get('from')
    to_user = data.get('to')
    filename = data.get('filename')
    file_data = data.get('data')  # base64 encoded
    
    if not all([from_user, to_user, filename, file_data]):
        logger.error(f"Missing parameters in file send: {data}")
        emit('file_sent', {
            'success': False,
            'message': 'Missing parameters'
        })
        return
    
    logger.info(f"📁 File from {from_user} to {to_user}: {filename} ({len(file_data) if file_data else 0} bytes)")
    
    success, msg = p2p_bridge.send_file(from_user, to_user, filename, file_data)
    
    emit('file_sent', {
        'success': success,
        'message': msg,
        'to': to_user,
        'filename': filename,
        'file_id': f"file_{int(time.time())}_{filename}"
    })
    


if __name__ == '__main__':
    logger.info("🚀 Starting P2P Web Backend with enhanced logging...")
    logger.info(f"STUN Server URL: {STUN_SERVER_URL}")
    
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=8080, 
        debug=True,  # در production به False تغییر دهید
        log_output=True
    )
    


# @app.route('/api/register', methods=['POST'])
# def api_register():
#     """API endpoint for user registration"""
#     data = request.json
#     username = data.get('username')
#     port = data.get('port', 6000)
    
#     if not username:
#         return jsonify({'success': False, 'error': 'Username required'}), 400
    
#     success = p2p_bridge.register_user(username, port, request.sid)
    
#     if success:
#         return jsonify({
#             'success': True,
#             'username': username,
#             'message': 'Registered successfully'
#         })
#     else:
#         return jsonify({
#             'success': False,
#             'error': 'Registration failed'
#         }), 500

# @app.route('/api/peers')
# def api_peers():
#     """Get list of available peers"""
#     username = request.args.get('username')
#     peers = p2p_bridge.get_available_peers(exclude_user=username)
#     return jsonify({'peers': peers})

# @app.route('/api/connect', methods=['POST'])
# def api_connect():
#     """Connect to a peer"""
#     data = request.json
#     username = data.get('username')
#     target = data.get('target')
    
#     if not username or not target:
#         return jsonify({'success': False, 'error': 'Missing parameters'}), 400
    
#     success, message = p2p_bridge.connect_to_peer(username, target)
    
#     return jsonify({
#         'success': success,
#         'message': message,
#         'peer': target
#     })

# @app.route('/api/send', methods=['POST'])
# def api_send():
#     """Send a message"""
#     data = request.json
#     from_user = data.get('from')
#     to_user = data.get('to')
#     message = data.get('message')
    
#     if not all([from_user, to_user, message]):
#         return jsonify({'success': False, 'error': 'Missing parameters'}), 400
    
#     success, msg = p2p_bridge.send_message(from_user, to_user, message)
    
#     return jsonify({
#         'success': success,
#         'message': msg
#     })

# # WebSocket Events
# @socketio.on('connect')
# def handle_connect():
#     """Handle client connection"""
#     logger.info(f"Client connected: {request.sid}")
#     emit('connected', {'sid': request.sid})

# @socketio.on('disconnect')
# def handle_disconnect():
#     """Handle client disconnection"""
#     logger.info(f"Client disconnected: {request.sid}")
    
#     # Find and cleanup user
#     for username, sid in p2p_bridge.active_users.items():
#         if sid == request.sid:
#             p2p_bridge.disconnect_user(username)
#             break

# @socketio.on('register')
# def handle_register(data):
#     """Handle user registration via WebSocket"""
#     username = data.get('username')
#     port = data.get('port', 6000)
    
#     success = p2p_bridge.register_user(username, port, request.sid)
    
#     emit('registration_result', {
#         'success': success,
#         'username': username if success else None
#     })

# @socketio.on('get_peers')
# def handle_get_peers(data):
#     """Handle request for peers list"""
#     username = data.get('username')
#     peers = p2p_bridge.get_available_peers(exclude_user=username)
    
#     emit('peers_list', {
#         'peers': peers
#     })

# @socketio.on('connect_to_peer')
# def handle_connect_to_peer(data):
#     """Handle connection request to a peer"""
#     username = data.get('username')
#     target = data.get('target')
    
#     success, message = p2p_bridge.connect_to_peer(username, target)
    
#     emit('connection_result', {
#         'success': success,
#         'message': message,
#         'peer': target
#     })

# @socketio.on('send_message')
# def handle_send_message(data):
#     """Handle sending a message"""
#     from_user = data.get('from')
#     to_user = data.get('to')
#     message = data.get('message')
    
#     success, msg = p2p_bridge.send_message(from_user, to_user, message)
    
#     emit('message_sent', {
#         'success': success,
#         'message': msg,
#         'to': to_user
#     })

# if __name__ == '__main__':
#     logger.info("Starting P2P Web Backend...")
#     socketio.run(app, host='0.0.0.0', port=8080, debug=True)