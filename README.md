# 🚀 Computer Networks Project - P2P Chat System

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-green)
![Docker](https://img.shields.io/badge/docker-compose-blue)

A complete peer-to-peer (P2P) chat system featuring:
- Peer registration and management via STUN server
- Direct TCP communication between peers
- Real-time messaging
- File transfer capabilities
- Modern web interface
- Full Docker containerization

## ✨ Features

### 🔗 Core P2P Features
- **STUN Server**: Peer discovery and NAT traversal
- **Direct TCP Connections**: Peer-to-peer communication without intermediaries
- **Real-time Messaging**: Instant message delivery
- **File Transfer**: Share files directly between peers
- **Multiple Client Types**: Web interface and CLI clients

### 🌐 Web Interface
- **Modern UI**: Bootstrap 5 with responsive design
- **WebSocket Communication**: Real-time updates
- **File Preview**: Image thumbnails and file type indicators
- **Activity Logs**: Comprehensive connection and message history
- **Peer Management**: Visual peer discovery and connection status

### 🐳 Containerization
- **Docker Compose**: Single-command deployment
- **Multi-container Architecture**: Isolated services
- **Volume Persistence**: File storage across sessions
- **Health Monitoring**: Automatic service health checks
- **Network Isolation**: Custom bridge network configuration

## 🏗️ Architecture

```
project/
│
├── server/              # STUN Server (FastAPI + Redis)
│   ├── main.py         # FastAPI application
│   ├── Dockerfile      # Container configuration
│   └── requirements.txt # Python dependencies
│
├── client/             # CLI P2P Client
│   ├── main.py         # Main client application
│   ├── network.py      # Network layer
│   ├── tcp_handler.py  # TCP connection handler
│   ├── file_transfer.py # File transfer utilities
│   └── Dockerfile      # Container configuration
│
└── web/                # Web Interface
    └── backend/        # Flask WebSocket Backend
        ├── app.py      # Flask + Socket.IO application
        ├── static/     # Frontend assets
        │   ├── css/style.css
        │   └── js/app.js
        ├── templates/  # HTML templates
        │   └── index.html
        ├── Dockerfile  # Container configuration
        └── requirements.txt # Python dependencies
```

## 🚀 Quick Start

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- Git

### Installation & Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/mohamadrezaMH/P2P-Chat-System
   cd P2P-Chat-System
   ```

2. **Start all services**
   ```bash
   docker-compose up -d
   ```

3. **Access the services**
   - **Web Interface**: http://localhost:8080
   - **STUN Server API**: http://localhost:8000
   - **CLI Clients**: 
     ```bash
     docker attach p2p-peer-1
     docker attach p2p-peer-2
     ```

## 📖 Usage Guide

### Web Interface
1. Open http://localhost:8080 in your browser
2. Register with a username and port
3. Discover available peers in the "Available Peers" section
4. Connect to a peer by clicking "Connect"
5. Select a peer from the dropdown to start chatting
6. Use the file button to send files

### CLI Clients
Two CLI peers are automatically started:
- **Peer 1**: Username: `cli-user1`, Port: `5000`
- **Peer 2**: Username: `cli-user2`, Port: `5001`

Available commands in CLI:
- `list` - List available peers
- `connect <username>` - Connect to a peer
- `send <message>` - Send a message
- `file <filename>` - Send a file
- `help` - Show all commands
- `exit` - Disconnect and exit

### API Endpoints
**STUN Server (Port 8000):**
- `GET /peers` - List all registered peers
- `POST /register` - Register a new peer
- `GET /peerinfo/{username}` - Get peer information

**Web Backend (Port 8080):**
- `GET /` - Web interface
- `GET /api/health` - Health check
- `WebSocket /socket.io` - Real-time communication

## 🔧 Development

### Local Development Setup

1. **Backend Development**
   ```bash
   cd web/backend
   pip install -r requirements.txt
   python app.py
   ```

2. **Frontend Development**
   - Edit files in `web/backend/static/` and `web/backend/templates/`
   - The Flask development server will auto-reload on changes

3. **STUN Server Development**
   ```bash
   cd server
   pip install -r requirements.txt
   python main.py
   ```

### Building Custom Images
```bash
# Build specific service
docker-compose build web-app
docker-compose build stun-server
docker-compose build peer1

# Rebuild all services
docker-compose build --no-cache
```

## 🌐 Network Configuration

### Container Network
```
Subnet: 172.20.0.0/16
Services:
- stun-server: 172.20.0.2
- web-app: 172.20.0.3
- peer1: 172.20.0.4
- peer2: 172.20.0.5
```

### Port Mapping
- **8080**: Web interface (HTTP/WebSocket)
- **8000**: STUN server (HTTP)
- **5000**: CLI Peer 1 (TCP)
- **5001**: CLI Peer 2 (TCP)

## 📊 Monitoring

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web-app
docker-compose logs -f stun-server
docker-compose logs -f peer1
```

### Health Status
```bash
# Check container status
docker-compose ps

# Health check endpoints
curl http://localhost:8000/health
curl http://localhost:8080/api/health
```

## 🐛 Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   # Find process using port
   sudo lsof -i :8080
   # Kill process
   sudo kill -9 <PID>
   ```

2. **Docker containers won't start**
   ```bash
   # Clean everything
   docker-compose down -v
   docker system prune -a
   # Rebuild
   docker-compose up --build
   ```

3. **WebSocket connection issues**
   - Check browser console for errors
   - Verify Docker logs for backend errors
   - Ensure no firewall blocking WebSocket connections

4. **File transfer not working**
   - Check file size (limit: 10MB)
   - Verify both users are connected
   - Check Docker volume permissions

### Debug Mode
```bash
# Start with debug output
docker-compose up --build --force-recreate
```

## 🧪 Testing

### Manual Testing Scenarios
1. **Web-to-Web Communication**
   - Open two browser tabs
   - Register different users
   - Connect and exchange messages/files

2. **CLI-to-CLI Communication**
   - Use `list` command to see peers
   - Connect using `connect <username>`
   - Send messages and files

3. **Cross-interface Communication**
   - Web user connects to CLI user
   - Message exchange between different interfaces

### Network Testing
```bash
# Test STUN server
curl http://localhost:8000/peers

# Test web backend
curl http://localhost:8080/api/health
```

## 📚 Technical Details

### Protocols Used
- **STUN**: Session Traversal Utilities for NAT
- **TCP**: Reliable peer-to-peer connections
- **WebSocket**: Real-time web communication
- **HTTP REST**: Server APIs

### Data Flow
1. Peer registers with STUN server
2. Other peers discover via STUN server
3. Direct TCP connection established
4. Messages/files sent directly between peers
5. Web interface uses WebSocket for real-time updates

### Security Considerations
- **CORS**: Configured for web interface
- **Input Validation**: Sanitized user inputs
- **File Limits**: 10MB file size restriction
- **Session Management**: WebSocket session tracking

## 🤝 Contributing

This is an educational project for the Computer Networks course at Amirkabir University of Technology. For educational purposes, contributions can be made by:

1. Forking the repository
2. Creating a feature branch
3. Making changes
4. Submitting a pull request

## 📄 License

This project was created for educational purposes as part of the Computer Networks course at Amirkabir University of Technology, Fall 2025.

**Disclaimer**: This project is for educational use only. The creators are not responsible for any misuse of this software.

## 👥 Developers & Credits

**Course**: Computer Networks  
**Semester**: Fall 2025 
**University**: Amirkabir University of Technology (Tehran Polytechnic)  
**Department**:  mathematic and Computer science

### Project Team
- Mohammadreza Mohammadi
- Instructor: Dr.Mohammad Hassan Shirali shahreza
- Head TA: Parsa Alikhani

## 🔮 Future Enhancements

Potential improvements for future versions:
- [ ] End-to-end encryption
- [ ] Video/voice chat support
- [ ] Group messaging
- [ ] Message history persistence
- [ ] Mobile application
- [ ] Advanced NAT traversal techniques
- [ ] Load balancing for STUN server
- [ ] OAuth authentication

## 📞 Support

For issues related to this educational project:
1. Check the troubleshooting section
2. Review Docker logs
3. Consult course materials
4. Contact teaching assistants

---

**⭐ If you find this project useful for learning about P2P networks, please consider starring the repository!**

*Last Updated: January 2025*
