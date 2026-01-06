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
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.connectWebSocket();
        this.updateUI();
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
    }
    
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const wsUrl = `${protocol}//${host}/socket.io`;
        
        this.socket = io(wsUrl, {
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionAttempts: 5,
            reconnectionDelay: 1000
        });
        
        this.socket.on('connect', () => {
            this.log('Connected to server', 'success');
            this.updateConnectionStatus(true);
        });
        
        this.socket.on('disconnect', () => {
            this.log('Disconnected from server', 'error');
            this.updateConnectionStatus(false);
        });
        
        this.socket.on('connected', (data) => {
            this.log('WebSocket connection established', 'success');
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
        
        if (!this.socket || !this.socket.connected) {
            this.showAlert('Error', 'Not connected to server', 'error');
            return;
        }
        
        this.username = username;
        this.port = port;
        
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
        
        this.clearChat();
        
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
        
        let messageClass = type;
        let senderName = type === 'outgoing' ? 'You' : (sender || 'Unknown');
        let avatarLetter = senderName.charAt(0).toUpperCase();
        
        if (type === 'system') {
            messageClass = 'system';
            senderName = 'System';
        }
        
        const messageHtml = `
            <div class="message ${messageClass}">
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
        document.head.appendChild(style);
    }
    
    // Utility Methods
    log(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const typeClass = type === 'error' ? 'error' : type === 'success' ? 'success' : 'info';
        
        const logEntry = `
            <div class="log-entry ${typeClass}">
                <small>${timestamp}: ${message}</small>
            </div>
        `;
        
        $('#activity-logs').prepend(logEntry);
        
        // Keep only last 20 logs
        const logs = $('#activity-logs').children();
        if (logs.length > 20) {
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
}

// Initialize app when page loads
$(document).ready(() => {
    window.p2pApp = new P2PWebApp();
});