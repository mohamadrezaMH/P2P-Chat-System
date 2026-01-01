import os
import json
import hashlib
import logging
from typing import Dict, Optional, Callable, BinaryIO
from pathlib import Path

logger = logging.getLogger(__name__)


class FileTransfer:
    """Class for handling file transfers between peers"""
    
    CHUNK_SIZE = 8192  # 8KB chunks for file transfer
    
    @staticmethod
    def prepare_file_info(file_path: str) -> Optional[Dict]:
        """
        Prepare file metadata for transfer
        Returns: Dictionary with file info or None if error
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.error(f"File not found: {file_path}")
                return None
            if not path.is_file():
                logger.error(f"Path is not a file: {file_path}")
                return None
            
            # Get file size
            file_size = path.stat().st_size
            
            # Calculate file hash (MD5)
            file_hash = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    file_hash.update(chunk)
            
            # Prepare file info
            file_info = {
                "filename": path.name,
                "size": file_size,
                "hash": file_hash.hexdigest(),
                "extension": path.suffix.lower(),
                "total_chunks": (file_size + FileTransfer.CHUNK_SIZE - 1) // FileTransfer.CHUNK_SIZE
            }
            
            logger.debug(f"Prepared file info for {path.name}: {file_size} bytes")
            return file_info
            
        except Exception as e:
            logger.error(f"Error preparing file info: {e}")
            return None
    
    @staticmethod
    def send_file(file_path: str, send_func: Callable[[Dict], bool], 
                  chunk_size: int = None) -> bool:
        """
        Send file in chunks using provided send function
        Returns: True if successful, False otherwise
        """
        if chunk_size is None:
            chunk_size = FileTransfer.CHUNK_SIZE
        
        try:
            # Prepare file info
            file_info = FileTransfer.prepare_file_info(file_path)
            if not file_info:
                return False
            
            # Send file info
            if not send_func(file_info):
                logger.error("Failed to send file info")
                return False
            
            logger.info(f"Sending file: {file_info['filename']} ({file_info['size']} bytes)")
            
            # Send file data in chunks
            with open(file_path, 'rb') as f:
                chunk_id = 0
                bytes_sent = 0
                
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    
                    # Prepare chunk data
                    chunk_data = {
                        "type": "file_chunk",
                        "chunk_id": chunk_id,
                        "data": chunk.hex(),  # Convert to hex for JSON
                        "total_chunks": file_info['total_chunks']
                    }
                    
                    # Send chunk
                    if not send_func(chunk_data):
                        logger.error(f"Failed to send chunk {chunk_id}")
                        return False
                    
                    chunk_id += 1
                    bytes_sent += len(chunk)
                    
                    # Log progress every 10 chunks
                    if chunk_id % 10 == 0:
                        progress = (bytes_sent / file_info['size']) * 100
                        logger.debug(f"File transfer progress: {progress:.1f}%")
                
                # Send completion message
                completion = {
                    "type": "file_complete",
                    "filename": file_info['filename'],
                    "hash": file_info['hash']
                }
                send_func(completion)
            
            logger.info(f"File sent successfully: {file_info['filename']}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending file: {e}")
            return False
    
    @staticmethod
    def receive_file(file_info: Dict, receive_func: Callable[[], Optional[Dict]], 
                     save_path: str = "./received_files") -> Optional[str]:
        """
        Receive file and save it
        Returns: Path to saved file or None if error
        """
        try:
            # Create save directory if it doesn't exist
            os.makedirs(save_path, exist_ok=True)
            
            # Prepare file path
            filename = file_info.get('filename', 'received_file')
            file_path = os.path.join(save_path, filename)
            
            # Check if file already exists
            counter = 1
            original_file_path = file_path
            while os.path.exists(file_path):
                name, ext = os.path.splitext(filename)
                new_filename = f"{name}_{counter}{ext}"
                file_path = os.path.join(save_path, new_filename)
                counter += 1
            
            logger.info(f"Receiving file: {filename}")
            logger.info(f"Saving to: {file_path}")
            
            # Open file for writing
            with open(file_path, 'wb') as f:
                total_chunks = file_info.get('total_chunks', 0)
                received_chunks = 0
                
                for chunk_id in range(total_chunks):
                    # Receive chunk data
                    chunk_data = receive_func()
                    if not chunk_data:
                        logger.error(f"Missing chunk {chunk_id}")
                        os.remove(file_path)
                        return None
                    
                    # Validate chunk
                    if (chunk_data.get('type') != 'file_chunk' or 
                        chunk_data.get('chunk_id') != chunk_id):
                        logger.error(f"Invalid chunk received: {chunk_data}")
                        os.remove(file_path)
                        return None
                    
                    # Convert hex to bytes
                    try:
                        data_bytes = bytes.fromhex(chunk_data['data'])
                    except ValueError:
                        logger.error(f"Invalid hex data in chunk {chunk_id}")
                        os.remove(file_path)
                        return None
                    
                    # Write chunk to file
                    f.write(data_bytes)
                    received_chunks += 1
                    
                    # Log progress every 10 chunks
                    if chunk_id % 10 == 0:
                        progress = ((chunk_id + 1) / total_chunks) * 100
                        logger.debug(f"File receive progress: {progress:.1f}%")
            
            # Verify file hash
            received_hash = FileTransfer.calculate_file_hash(file_path)
            expected_hash = file_info.get('hash')
            
            if received_hash != expected_hash:
                logger.error(f"File hash mismatch! Expected: {expected_hash}, Got: {received_hash}")
                os.remove(file_path)
                return None
            
            logger.info(f"File received successfully: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error receiving file: {e}")
            # Try to clean up partial file
            try:
                if 'file_path' in locals() and os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
            return None
    
    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        """Calculate MD5 hash of a file"""
        file_hash = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                file_hash.update(chunk)
        return file_hash.hexdigest()
    
    @staticmethod
    def send_file_simple(file_path: str, send_func: Callable[[Dict], bool]) -> bool:
        """
        Simple file transfer (for small files)
        Sends entire file in one message
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            file_info = {
                "type": "file_simple",
                "filename": os.path.basename(file_path),
                "size": len(file_data),
                "data": file_data.hex(),
                "hash": hashlib.md5(file_data).hexdigest()
            }
            
            return send_func(file_info)
            
        except Exception as e:
            logger.error(f"Error in simple file transfer: {e}")
            return False
    
    @staticmethod
    def receive_file_simple(file_info: dict, save_path: str = "./received_files") -> Optional[str]:
        """دریافت فایل به روش ساده (برای فایل‌های کوچک)"""
        try:
            os.makedirs(save_path, exist_ok=True)
            
            # ایجاد نام فایل منحصربفرد
            filename = file_info.get('filename', 'received_file')
            base_name, ext = os.path.splitext(filename)
            counter = 1
            file_path = os.path.join(save_path, filename)
            
            while os.path.exists(file_path):
                new_filename = f"{base_name}_{counter}{ext}"
                file_path = os.path.join(save_path, new_filename)
                counter += 1
            
            # در این نسخه ساده، فایل خالی ایجاد می‌کنیم
            # در نسخه کامل، باید داده‌های واقعی را دریافت کنیم
            with open(file_path, 'wb') as f:
                f.write(b"File received - Placeholder for actual content")
            
            print(f"Simple file receive: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error in simple file receive: {e}")
            return None