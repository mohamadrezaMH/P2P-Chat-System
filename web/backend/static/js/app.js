/**
 * P2P Web Application - Main JavaScript File
 * Handles WebSocket connection and core functionality
 */

class P2PWebApp {
    constructor() {
        this.socket = null;
        this.username = null;
        this.port = null;
        this.connected = false;
        this.availablePeers = [];
        this.connectedPeers = [];
        this.currentChatPeer = null;
        this.messageCount = 0;
        this.fileCount = 0;
        this.connectionAttempts = 0;
        this.maxConnectionAttempts = 5;
        this.messageClass = null
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.connectWebSocket();
        this.updateUI();
        this.setupConnectionMonitor();
    }
    
    setupConnectionMonitor() {
        setInterval(() => {
            if (this.socket && !this.socket.connected) {
                this.log('Connection lost, attempting to reconnect...', 'warning');
                this.connectWebSocket();
            }
        }, 5000);
    }

    bindEvents() {
        // Registration
        $('#register-btn').click(() => this.register());
        $('#disconnect-btn').click(() => this.disconnect());
        
        // Message input
        $('#message-input').on('input', () => this.updateCharCount());
        $('#message-input').keypress((e) => {
            if (e.which === 13 && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Send button
        $('#send-btn').click(() => this.sendMessage());
        
        // File button
        $('#file-btn').click(() => $('#file-input').click());
        $('#file-input').change((e) => this.handleFileSelect(e));
        
        // Refresh peers
        $('#refresh-peers').click(() => this.refreshPeers());
        
        // Chat selection
        $('#chat-with').change(() => this.selectChatPeer());

        $('#test-connection').click(() => this.testConnection());

    }
    
    connectWebSocket() {
        if (this.connectionAttempts >= this.maxConnectionAttempts) {
            this.showAlert('Error', 'Max connection attempts reached. Please refresh the page.', 'error');
            return;
        }
        
        this.connectionAttempts++;
        
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsHost = window.location.host;
        
        const wsUrl1 = `${wsProtocol}//${wsHost}/socket.io/`;
        const wsUrl2 = `${wsProtocol}//${wsHost}`;
        
        this.log(`Attempting WebSocket connection (attempt ${this.connectionAttempts})...`, 'info');
        
        this.socket = io(wsUrl2, {
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionAttempts: 10,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            timeout: 20000,
            forceNew: true,
            multiplex: false,
            path: '/socket.io/'
        });
        
        // Event Handlers با لاگ
        this.socket.on('connect', () => {
            this.connectionAttempts = 0; // reset attempts
            this.log('✅ WebSocket Connected to server', 'success');
            this.showAlert('Connected', 'Successfully connected to server', 'success');
            this.updateConnectionStatus(true);
            
            this.socket.emit('ping');
        });
        
        this.socket.on('connected', (data) => {
            this.log(`✅ Connection established: ${data.message}`, 'success');
            this.showAlert('Connected', 'WebSocket connection established', 'success');
        });
        
        this.socket.on('status_update', (data) => {
            this.log(`Status: ${data.type} - ${data.message}`, 'info');
        });
        
        this.socket.on('pong', (data) => {
            this.log(`Ping response received`, 'success');
        });
        
        this.socket.on('disconnect', (reason) => {
            this.log(`❌ Disconnected from server: ${reason}`, 'error');
            this.updateConnectionStatus(false);
            this.showAlert('Disconnected', 'Lost connection to server', 'warning');
        });
        
        this.socket.on('connect_error', (error) => {
            this.log(`❌ Connection error: ${error.message}`, 'error');
            this.updateConnectionStatus(false);
            
            if (this.connectionAttempts < this.maxConnectionAttempts) {
                setTimeout(() => {
                    this.log(`Retrying connection... (${this.connectionAttempts}/${this.maxConnectionAttempts})`, 'info');
                    this.connectWebSocket();
                }, 2000);
            }
        });
        
        this.socket.on('registration_result', (data) => {
            this.handleRegistrationResult(data);
        });
        
        this.socket.on('peers_list', (data) => {
            this.handlePeersList(data);
        });
        
        this.socket.on('connection_result', (data) => {
            this.handleConnectionResult(data);
        });
        
        this.socket.on('peer_connected', (data) => {
            this.handlePeerConnected(data);
        });
        
        this.socket.on('peer_disconnected', (data) => {
            this.handlePeerDisconnected(data);
        });
        
        this.socket.on('message_received', (data) => {
            this.handleMessageReceived(data);
        });
        
        this.socket.on('message_sent', (data) => {
            this.handleMessageSent(data);
        });

        this.socket.on('file_received', (data) => {
            this.handleFileReceived(data);
        });

        this.socket.on('file_sent', (data) => {
            this.handleFileSent(data);
        });
    }
    
    testConnection() {
        if (!this.socket) {
            this.showAlert('Error', 'Socket not initialized', 'error');
            return;
        }
        
        this.log(`Testing connection... Socket connected: ${this.socket.connected}`, 'info');
        
        // تست HTTP connection
        fetch('/api/test/connection')
            .then(response => response.json())
            .then(data => {
                this.log(`HTTP Test: ${JSON.stringify(data)}`, 'success');
                this.showAlert('Connection Test', `HTTP: OK, WebSocket: ${this.socket.connected ? 'Connected' : 'Disconnected'}`, 'info');
            })
            .catch(error => {
                this.log(`HTTP Test failed: ${error}`, 'error');
            });
    }
    
    register() {
        const username = $('#username').val().trim();
        const port = $('#port').val();
        
        if (!username) {
            this.showAlert('Error', 'Please enter a username', 'error');
            return;
        }
        
        if (username.length < 3) {
            this.showAlert('Error', 'Username must be at least 3 characters', 'error');
            return;
        }

        this.log(`Registering... Socket status: ${this.socket ? 'exists' : 'null'}, Connected: ${this.socket ? this.socket.connected : 'N/A'}`, 'info');
        
         if (!this.socket) {
            this.showAlert('Error', 'Socket not initialized. Please wait for connection or refresh page.', 'error');
            this.connectWebSocket();
            return;
        }
        
        if (!this.socket.connected) {
            this.showAlert('Error', 'Not connected to server. Attempting to reconnect...', 'error');
            this.connectWebSocket();
            
            setTimeout(() => {
                if (this.socket.connected) {
                    this.register();
                } else {
                    this.showAlert('Error', 'Still not connected. Please check your network.', 'error');
                }
            }, 2000);
            return;
        }
        
        this.username = username;
        this.port = port;

        this.log(`Emitting register event for ${username}...`, 'info');

        this.socket.emit('register', {
            username: username,
            port: port
        });
        
        this.log(`Registering as ${username}...`, 'info');
        $('#register-btn').prop('disabled', true).html('<i class="fas fa-spinner fa-spin me-2"></i>Registering...');
    }
    
    handleRegistrationResult(data) {
        $('#register-btn').prop('disabled', false).html('<i class="fas fa-sign-in-alt me-2"></i>Register & Connect');
        
        if (data.success) {
            this.connected = true;
            this.username = data.username;
            
            // Update UI
            $('#registration-section').addClass('d-none');
            $('#profile-section').removeClass('d-none');
            $('#profile-username').text(this.username);
            $('#profile-port').text(this.port);
            
            $('#chat-with').prop('disabled', false);
            $('#message-input').prop('disabled', false);
            $('#send-btn').prop('disabled', false);
            $('#file-btn').prop('disabled', false);
            $('#file-input').prop('disabled', false);
            
            this.updateUserInfo();
            this.refreshPeers();
            
            this.log(`Successfully registered as ${this.username}`, 'success');
            this.showAlert('Success', `Registered as ${this.username}`, 'success');
        } else {
            this.log('Registration failed', 'error');
            this.showAlert('Error', 'Registration failed. Please try again.', 'error');
        }
    }
    
    disconnect() {
        if (!this.connected) return;
        
        this.socket.emit('disconnect_user', { username: this.username });
        
        this.connected = false;
        this.username = null;
        this.port = null;
        this.connectedPeers = [];
        this.currentChatPeer = null;
        
        // Reset UI
        $('#profile-section').addClass('d-none');
        $('#registration-section').removeClass('d-none');
        
        $('#chat-with').prop('disabled', true).val('');
        $('#message-input').prop('disabled', true).val('');
        $('#send-btn').prop('disabled', true);
        $('#file-btn').prop('disabled', true);
        $('#file-input').prop('disabled', true);
        
        $('#connected-peers').html(`
            <div class="text-center text-muted py-4">
                <i class="fas fa-user-plus fa-2x mb-2"></i>
                <p>Not connected to any peer</p>
            </div>
        `);
        
        this.clearChat();
        this.updateUserInfo();
        
        this.log('Disconnected from P2P network', 'info');
        this.showAlert('Disconnected', 'You have been disconnected', 'info');
    }
    
    refreshPeers() {
        if (!this.connected || !this.username) return;
        
        this.socket.emit('get_peers', { username: this.username });
        this.log('Refreshing peers list...', 'info');
        $('#refresh-peers').prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i>');
    }
    
    handlePeersList(data) {
        $('#refresh-peers').prop('disabled', false).html('<i class="fas fa-sync-alt"></i>');
        this.availablePeers = data.peers || [];
        this.renderPeersList();
        this.updateOnlinePeersCount();
    }
    
    connectToPeer(peerUsername) {
        if (!this.connected || !this.username) return;
        
        this.socket.emit('connect_to_peer', {
            username: this.username,
            target: peerUsername
        });
        
        this.log(`Connecting to ${peerUsername}...`, 'info');
    }
    
    handleConnectionResult(data) {
        if (data.success) {
            if (!this.connectedPeers.includes(data.peer)) {
                this.connectedPeers.push(data.peer);
            }
            
            // Update chat dropdown
            this.updateChatDropdown();
            
            // Update connected peers list
            this.renderConnectedPeers();
            
            this.log(`Connected to ${data.peer}`, 'success');
            this.showAlert('Connected', `Successfully connected to ${data.peer}`, 'success');
        } else {
            this.log(`Failed to connect to ${data.peer}: ${data.message}`, 'error');
            this.showAlert('Connection Failed', data.message, 'error');
        }
    }
    
    handlePeerConnected(data) {
        if (!this.connectedPeers.includes(data.peer)) {
            this.connectedPeers.push(data.peer);
        }
        
        this.updateChatDropdown();
        this.renderConnectedPeers();
        this.updateOnlinePeersCount();
        
        this.log(`${data.peer} connected to you`, 'success');
    }
    
    handlePeerDisconnected(data) {
        const index = this.connectedPeers.indexOf(data.peer);
        if (index > -1) {
            this.connectedPeers.splice(index, 1);
        }
        
        // If current chat peer disconnected, clear chat
        if (this.currentChatPeer === data.peer) {
            this.currentChatPeer = null;
            $('#chat-with').val('');
            this.clearChat();
        }
        
        this.updateChatDropdown();
        this.renderConnectedPeers();
        this.updateOnlinePeersCount();
        
        this.log(`${data.peer} disconnected`, 'info');
    }
    
    selectChatPeer() {
        const selectedPeer = $('#chat-with').val();
        this.currentChatPeer = selectedPeer;
        
        // this.clearChat();
        
        if (selectedPeer) {
            this.addChatMessage('system', `Started chat with ${selectedPeer}`, 'info');
            this.log(`Now chatting with ${selectedPeer}`, 'info');
        }
    }
    
    sendMessage() {
        if (!this.currentChatPeer) {
            this.showAlert('Warning', 'Please select a peer to chat with', 'warning');
            return;
        }
        
        const message = $('#message-input').val().trim();
        if (!message) return;
        
        if (message.length > 500) {
            this.showAlert('Error', 'Message cannot exceed 500 characters', 'error');
            return;
        }
        
        this.socket.emit('send_message', {
            from: this.username,
            to: this.currentChatPeer,
            message: message
        });
        
        // Display message immediately
        this.addChatMessage('outgoing', message);
        this.messageCount++;
        $('#messages-sent').text(this.messageCount);
        
        // Clear input
        $('#message-input').val('');
        this.updateCharCount();
    }
    
    handleMessageReceived(data) {
        this.addChatMessage('incoming', data.message, data.from);
    }
    
    handleMessageSent(data) {
        if (!data.success) {
            this.log(`Failed to send message: ${data.message}`, 'error');
        }
    }
    
    handleFileSelect(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        if (file.size > 10 * 1024 * 1024) { // 10MB limit
            this.showAlert('Error', 'File size cannot exceed 10MB', 'error');
            event.target.value = '';
            return;
        }
        
        this.sendFile(file);
    }
    
    sendFile(file) {
        if (!this.currentChatPeer) {
            this.showAlert('Warning', 'Please select a peer to send file to', 'warning');
            return;
        }
        
        const reader = new FileReader();
        
        reader.onload = (e) => {
            const base64Data = e.target.result.split(',')[1];
            
            this.socket.emit('send_file', {
                from: this.username,
                to: this.currentChatPeer,
                filename: file.name,
                data: base64Data
            });
            
            this.fileCount++;
            $('#files-sent').text(this.fileCount);
            
            this.log(`Sending file: ${file.name} (${this.formatFileSize(file.size)})`, 'info');
            this.showAlert('Sending', `Sending ${file.name}...`, 'info');
        };
        
        reader.readAsDataURL(file);
        $('#file-input').val('');
    }
    
    // UI Helper Methods
    renderPeersList() {
        const $peersList = $('#peers-list');
        
        if (this.availablePeers.length === 0) {
            $peersList.html(`
                <div class="text-center text-muted py-4">
                    <i class="fas fa-users fa-2x mb-2"></i>
                    <p>No peers available</p>
                </div>
            `);
            return;
        }
        
        let html = '';
        this.availablePeers.forEach(peer => {
            const isConnected = this.connectedPeers.includes(peer.username);
            const avatarLetter = peer.username.charAt(0).toUpperCase();
            const peerType = peer.type === 'web' ? 'Web User' : 'CLI Peer';
            
            html += `
                <div class="peer-item ${isConnected ? 'connected' : ''}" data-username="${peer.username}">
                    <div class="peer-avatar">
                        ${avatarLetter}
                    </div>
                    <div class="peer-info">
                        <div class="peer-name">${peer.username}</div>
                        <div class="peer-details">
                            <i class="fas fa-${peer.type === 'web' ? 'globe' : 'terminal'} me-1"></i>
                            ${peerType}
                            <span class="mx-1">•</span>
                            ${peer.ip_address}:${peer.port}
                        </div>
                    </div>
                    <div class="peer-actions">
                        ${isConnected ? 
                            `<span class="badge bg-success">Connected</span>` : 
                            `<button class="btn btn-sm btn-outline-primary connect-peer-btn" 
                                     data-username="${peer.username}">
                                <i class="fas fa-link me-1"></i>Connect
                            </button>`
                        }
                    </div>
                </div>
            `;
        });
        
        $peersList.html(html);
        
        // Bind connect buttons
        $('.connect-peer-btn').click((e) => {
            const username = $(e.currentTarget).data('username');
            this.connectToPeer(username);
        });
    }
    
    renderConnectedPeers() {
        const $connectedPeers = $('#connected-peers');
        
        if (this.connectedPeers.length === 0) {
            $connectedPeers.html(`
                <div class="text-center text-muted py-4">
                    <i class="fas fa-user-plus fa-2x mb-2"></i>
                    <p>Not connected to any peer</p>
                </div>
            `);
            return;
        }
        
        let html = '';
        this.connectedPeers.forEach(peer => {
            const avatarLetter = peer.charAt(0).toUpperCase();
            
            html += `
                <div class="peer-item connected" data-username="${peer}">
                    <div class="peer-avatar">
                        ${avatarLetter}
                    </div>
                    <div class="peer-info">
                        <div class="peer-name">${peer}</div>
                        <div class="peer-details">
                            <i class="fas fa-circle text-success me-1"></i>
                            Online
                        </div>
                    </div>
                    <div class="peer-actions">
                        <button class="btn btn-sm btn-outline-success chat-with-btn" 
                                data-username="${peer}">
                            <i class="fas fa-comment me-1"></i>Chat
                        </button>
                    </div>
                </div>
            `;
        });
        
        $connectedPeers.html(html);
        
        // Bind chat buttons
        $('.chat-with-btn').click((e) => {
            const username = $(e.currentTarget).data('username');
            $('#chat-with').val(username).trigger('change');
        });
    }
    
    updateChatDropdown() {
        const $dropdown = $('#chat-with');
        const currentVal = $dropdown.val();
        
        $dropdown.empty();
        $dropdown.append('<option value="">Select a peer...</option>');
        
        this.connectedPeers.forEach(peer => {
            $dropdown.append(`<option value="${peer}">${peer}</option>`);
        });
        
        // Restore previous selection if still connected
        if (currentVal && this.connectedPeers.includes(currentVal)) {
            $dropdown.val(currentVal);
        }
    }
    
    addChatMessage(type, content, sender = null) {
        const $chat = $('#chat-messages');
        const timestamp = new Date().toLocaleTimeString();
        
        // Remove welcome message if present
        if ($chat.find('.welcome-message').length) {
            $chat.empty();
        }
        
        this.messageClass = type;
        let senderName = type === 'outgoing' ? 'You' : (sender || 'Unknown');
        let avatarLetter = senderName.charAt(0).toUpperCase();
        
        if (type === 'system') {
            this.messageClass = 'system';
            senderName = 'System';
        }
        
        const messageHtml = `
            <div class="message ${this.messageClass}">
                <div class="d-flex align-items-start">
                    <div class="me-2">
                        <div class="avatar-circle-small">
                            ${avatarLetter}
                        </div>
                    </div>
                    <div class="flex-grow-1">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="sender fw-bold">${senderName}</span>
                            <span class="time small text-muted">${timestamp}</span>
                        </div>
                        <div class="message-content">${this.escapeHtml(content)}</div>
                    </div>
                </div>
            </div>
        `;
        
        $chat.append(messageHtml);
        
        // Scroll to bottom
        $chat.scrollTop($chat[0].scrollHeight);
    }
    
    clearChat() {
        $('#chat-messages').html(`
            <div class="welcome-message text-center">
                <i class="fas fa-comments fa-4x text-muted mb-3"></i>
                <h4 class="text-muted">${this.currentChatPeer ? `Chat with ${this.currentChatPeer}` : 'Welcome to P2P Chat!'}</h4>
                <p class="text-muted">${this.currentChatPeer ? 'Start sending messages...' : 'Register and connect to a peer to start chatting'}</p>
            </div>
        `);
    }
    
    updateCharCount() {
        const length = $('#message-input').val().length;
        const $charCount = $('#char-count');
        
        $charCount.text(length);
        
        if (length > 450) {
            $charCount.addClass('warning');
            $charCount.removeClass('danger');
        } else if (length > 490) {
            $charCount.removeClass('warning');
            $charCount.addClass('danger');
        } else {
            $charCount.removeClass('warning danger');
        }
    }
    
    updateConnectionStatus(connected) {
        const $status = $('#connection-status');
        
        if (connected) {
            $status.html(`
                <span class="badge bg-success">
                    <i class="fas fa-plug"></i> Connected
                </span>
            `);
        } else {
            $status.html(`
                <span class="badge bg-secondary">
                    <i class="fas fa-plug"></i> Disconnected
                </span>
            `);
        }
    }
    
    updateUserInfo() {
        const $userInfo = $('#user-info');
        
        if (this.connected && this.username) {
            $userInfo.removeClass('d-none');
            $('#current-username').text(this.username);
        } else {
            $userInfo.addClass('d-none');
        }
    }
    
    updateOnlinePeersCount() {
        $('#online-peers').text(this.availablePeers.length);
    }
    
    updateUI() {
        // Add custom CSS for small avatar
        const style = document.createElement('style');
        style.textContent = `
            .avatar-circle-small {
                width: 32px;
                height: 32px;
                border-radius: 50%;
                background: linear-gradient(135deg, #4361ee, #3a0ca3);
                color: white;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                font-size: 0.9rem;
            }
            
            .message.system {
                background-color: #e9ecef;
                border: 1px solid #dee2e6;
                color: #6c757d;
                text-align: center;
                max-width: 100% !important;
            }
        `;

        const fileStyles = document.createElement('style');
        fileStyles.textContent = `
            .file-preview {
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 10px;
                background-color: #f8f9fa;
                max-width: 300px;
            }
            .file-preview img {
                border-radius: 4px;
                transition: transform 0.2s;
            }
            .file-preview img:hover {
                transform: scale(1.05);
            }
            .file-info {
                font-size: 0.85rem;
            }
        `;
        document.head.appendChild(style);
        document.head.appendChild(fileStyles);
    }
    
    // Utility Methods
    log(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const typeClass = type === 'error' ? 'error' : type === 'success' ? 'success' : 'info';
        
        console.log(`[${timestamp}] ${type.toUpperCase()}: ${message}`);
        
        const logEntry = `
            <div class="log-entry ${typeClass}">
                <small><strong>[${timestamp}]</strong> ${message}</small>
            </div>
        `;
        
        $('#activity-logs').prepend(logEntry);
        
        // Keep only last 50 logs
        const logs = $('#activity-logs').children();
        if (logs.length > 50) {
            logs.last().remove();
        }
    }
    
    showAlert(title, text, icon) {
        Swal.fire({
            title: title,
            text: text,
            icon: icon,
            timer: 3000,
            showConfirmButton: false,
            toast: true,
            position: 'top-end'
        });
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }






    handleFileReceived(data) {
    this.log(`📥 File received from ${data.from}: ${data.filename} (${this.formatBytes(data.size)})`, 'success');
    
    this.addFileMessage(data.from, data.filename, data.data);
    
    this.showAlert('File Received', `${data.filename} from ${data.from}`, 'success');
}


handleFileSent(data) {
    if (data.success) {
        this.log(`✅ File sent to ${data.to}: ${data.filename}`, 'success');
        this.addFileMessage('You', data.filename, 'sent');
    } else {
        this.log(`❌ Failed to send file: ${data.message}`, 'error');
        this.showAlert('File Send Failed', data.message, 'error');
    }
}

addFileMessage(sender, filename, base64Data) {
    const $chat = $('#chat-messages');
    const timestamp = new Date().toLocaleTimeString();
    const avatarLetter = sender.charAt(0).toUpperCase();
    
    const isImage = filename.match(/\.(jpg|jpeg|png|gif|bmp|webp)$/i);
    const isPDF = filename.match(/\.pdf$/i);
    const isText = filename.match(/\.(txt|json|js|html|css|py|java|cpp)$/i);
    
    let fileContent = '';
    
    if (isImage) {
        fileContent = `
            <div class="file-preview">
                <img src="data:image/jpeg;base64,${base64Data}" 
                     alt="${filename}" 
                     class="img-thumbnail" 
                     style="max-width: 200px; max-height: 200px; cursor: pointer;"
                     onclick="window.p2pApp.downloadFile('${filename}', '${base64Data}')">
                <div class="file-info mt-1">
                    <small class="text-muted">${filename}</small>
                </div>
            </div>
        `;
    } else if (isPDF) {
        fileContent = `
            <div class="file-preview">
                <i class="fas fa-file-pdf text-danger fa-3x"></i>
                <div class="file-info mt-1">
                    <small class="text-muted">${filename}</small>
                    <br>
                    <button class="btn btn-sm btn-danger mt-1" 
                            onclick="window.p2pApp.downloadFile('${filename}', '${base64Data}')">
                        <i class="fas fa-download me-1"></i>Download PDF
                    </button>
                </div>
            </div>
        `;
    } else {
        fileContent = `
            <div class="file-preview">
                <i class="fas fa-file fa-3x text-secondary"></i>
                <div class="file-info mt-1">
                    <small class="text-muted">${filename}</small>
                    <br>
                    <button class="btn btn-sm btn-outline-secondary mt-1" 
                            onclick="window.p2pApp.downloadFile('${filename}', '${base64Data}')">
                        <i class="fas fa-download me-1"></i>Download
                    </button>
                    ${isText ? `
                    <button class="btn btn-sm btn-outline-info mt-1" 
                            onclick="window.p2pApp.previewTextFile('${filename}', '${base64Data}')">
                        <i class="fas fa-eye me-1"></i>Preview
                    </button>
                    ` : ''}
                </div>
            </div>
        `;
    }
    
    const messageHtml = `
        <div class="message ${this.messageClass}">
            <div class="d-flex align-items-start">
                <div class="me-2">
                    <div class="avatar-circle-small">
                        ${avatarLetter}
                    </div>
                </div>
                <div class="flex-grow-1">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <span class="sender fw-bold">${sender}</span>
                        <span class="time small text-muted">${timestamp}</span>
                    </div>
                    <div class="message-content">
                        ${fileContent}
                    </div>
                </div>
            </div>
        </div>
    `;
    
    $chat.append(messageHtml);
    $chat.scrollTop($chat[0].scrollHeight);
}

formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

downloadFile(filename, base64Data) {
    const link = document.createElement('a');
    link.href = 'data:application/octet-stream;base64,' + base64Data;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    this.log(`File downloaded: ${filename}`, 'success');
}

previewTextFile(filename, base64Data) {
    try {
        const text = atob(base64Data);
        Swal.fire({
            title: `Preview: ${filename}`,
            html: `<pre style="text-align: left; max-height: 400px; overflow-y: auto;">${this.escapeHtml(text)}</pre>`,
            width: '80%',
            showCloseButton: true,
            showConfirmButton: false
        });
    } catch (e) {
        this.showAlert('Error', 'Cannot preview this file', 'error');
    }
}
}

// Initialize app when page loads
$(document).ready(() => {
    window.p2pApp = new P2PWebApp();
    
    // همچنین می‌توانید یک دکمه تست به HTML اضافه کنید
    $('body').append(`
        <button id="test-connection" style="position: fixed; bottom: 10px; right: 10px; z-index: 1000;" 
                class="btn btn-sm btn-info">
            Test Connection
        </button>
    `);
});