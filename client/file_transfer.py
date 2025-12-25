import os
import json
import hashlib
import logging
from typing import BinaryIO, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class FileTransfer:
    @staticmethod
    def prepare_file_info(file_path: str) -> Optional[dict]:
        """Prepare file metadata for transfer"""
        try:
            path = Path(file_path)
            if not path.exists():
                logger.error(f"File not found: {file_path}")
                return None
            
            # Calculate file hash
            file_hash = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    file_hash.update(chunk)
            
            return {
                "type": "file_info",
                "filename": path.name,
                "size": path.stat().st_size,
                "hash": file_hash.hexdigest(),
                "extension": path.suffix,
                "timestamp": os.path.getmtime(file_path)
            }
        except Exception as e:
            logger.error(f"Error preparing file info: {e}")
            return None
    
    @staticmethod
    def send_file(file_path: str, send_func, chunk_size: int = 8192) -> bool:
        """Send file in chunks using provided send function"""
        try:
            file_info = FileTransfer.prepare_file_info(file_path)
            if not file_info:
                return False
            
            # Send file info first
            if not send_func(file_info):
                logger.error("Failed to send file info")
                return False
            
            logger.info(f"📤 Sending file: {file_info['filename']} ({file_info['size']} bytes)")
            
            # Send file data in chunks
            with open(file_path, 'rb') as f:
                bytes_sent = 0
                chunk_id = 0
                
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    
                    chunk_data = {
                        "type": "file_chunk",
                        "chunk_id": chunk_id,
                        "data": chunk.hex(),  # Convert to hex for JSON
                        "total_chunks": (file_info['size'] + chunk_size - 1) // chunk_size
                    }
                    
                    if not send_func(chunk_data):
                        logger.error(f"Failed to send chunk {chunk_id}")
                        return False
                    
                    bytes_sent += len(chunk)
                    chunk_id += 1
                    
                    # Progress indicator
                    if chunk_id % 50 == 0:
                        progress = (bytes_sent / file_info['size']) * 100
                        logger.info(f"Progress: {progress:.1f}%")
                
                # Send completion message
                completion = {
                    "type": "file_complete",
                    "filename": file_info['filename'],
                    "hash": file_info['hash']
                }
                send_func(completion)
                
            logger.info(f"✅ File sent successfully: {file_info['filename']}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending file: {e}")
            return False
    
    @staticmethod
    def receive_file(file_info: dict, receive_func, save_path: str = "./received") -> Optional[str]:
        """Receive file and save it"""
        try:
            os.makedirs(save_path, exist_ok=True)
            file_path = os.path.join(save_path, file_info['filename'])
            
            logger.info(f"📥 Receiving file: {file_info['filename']}")
            
            with open(file_path, 'wb') as f:
                total_chunks = file_info.get('total_chunks', 0)
                
                for chunk_id in range(total_chunks):
                    # Get chunk data
                    chunk_data = receive_func()
                    if not chunk_data or chunk_data.get('type') != 'file_chunk':
                        logger.error(f"Missing chunk {chunk_id}")
                        return None
                    
                    # Convert from hex back to bytes
                    data_bytes = bytes.fromhex(chunk_data['data'])
                    f.write(data_bytes)
                    
                    # Progress indicator
                    if chunk_id % 50 == 0:
                        progress = ((chunk_id + 1) / total_chunks) * 100
                        logger.info(f"Progress: {progress:.1f}%")
            
            # Verify file hash
            received_hash = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    received_hash.update(chunk)
            
            if received_hash.hexdigest() != file_info.get('hash'):
                logger.error("File hash mismatch!")
                os.remove(file_path)
                return None
            
            logger.info(f"✅ File received successfully: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error receiving file: {e}")
            return None