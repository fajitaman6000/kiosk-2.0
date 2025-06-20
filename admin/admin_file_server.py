# admin_file_server.py
import os
from flask import Flask, send_from_directory, request, jsonify, Response
from file_sync_config import ADMIN_SYNC_DIR, ADMIN_SERVER_PORT
import json
import glob
import hashlib
import urllib.parse
from queue import Queue
from threading import Lock
import time

app = Flask(__name__)

# Sync queue and lock
sync_queue = Queue()
active_sync = None
sync_lock = Lock()

# Add at the start of the file, after imports
queue_generation = 0  # Global counter for queue state changes

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_files(path):
    """Serve static files from the sync directory."""
    try:
        # Unquote and normalize the path
        path = urllib.parse.unquote(path)
        normalized_path = path.replace("\\", "/")
        print(f"[admin_file_server][DEBUG] Serving path: {normalized_path}")
        if not normalized_path:
            files = []
            for file in glob.iglob(ADMIN_SYNC_DIR + '/**', recursive=True):
                if os.path.isfile(file):
                    files.append(os.path.relpath(file, ADMIN_SYNC_DIR).replace("\\","/"))
            return "\n".join(files)
        return send_from_directory(ADMIN_SYNC_DIR, normalized_path) # Serve using normalized path
    except Exception as e:
        print(f"[admin_file_server] Error serving file: {e}")
        return jsonify({'error': 'File not found'}), 404

def calculate_file_hash(file_path):
    """Calculate the SHA256 hash of a file."""
    hasher = hashlib.sha256()
    try:
        with open(file_path, 'rb') as file:
            while True:
                chunk = file.read(4096)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        print(f"[admin_file_server] Error calculating hash for {file_path}: {e}")
        return None


@app.route('/sync_info', methods=['GET', 'POST'])
def get_sync_info():
    """Get or update the file list and their hashes for syncing."""
    try:
        if request.method == 'POST':
            # Store the file hashes from admin
            data = request.get_json()
            if not data or 'files' not in data:
                return jsonify({'error': 'Invalid data format'}), 400
                
            # Store hashes in memory (could be moved to a persistent store if needed)
            app.config['CURRENT_FILE_HASHES'] = data['files']
            return jsonify({'message': 'File hashes updated'})
            
        # GET request - return current file hashes
        files = app.config.get('CURRENT_FILE_HASHES', {})
        return jsonify(files)

    except Exception as e:
        print(f"[admin_file_server] Error handling sync info: {e}")
        return jsonify({'error': str(e)}), 500
        
@app.route('/sync', methods=['POST'])
def sync_handler():
    """Handle synchronization requests."""
    try:
        print("[admin_file_server] Received synchronization request")
        
        data = request.get_json()
        if not data:
            print("[admin_file_server] Error: No JSON data received.")
            return jsonify({'error': 'No JSON data received'}), 400
        
        if 'files' not in data or not isinstance(data['files'], dict):
            print(f"[admin_file_server] Error: Incorrect data format received, keys: {data.keys()}")
            return jsonify({'error': 'Incorrect data format received'}), 400
        
        files_to_sync = data['files']
        
        # Handle file management
        for file_path, details in files_to_sync.items():
          if not details.get('type'):
                print(f"[admin_file_server] Error: Missing file type, {details}")
                return jsonify({'error': 'Missing file type'}), 400
          if details.get('type') == 'delete':
              target_path = os.path.join(ADMIN_SYNC_DIR, file_path)
              if os.path.exists(target_path):
                  os.remove(target_path)
              print(f"[admin_file_server] Removed file: {target_path}")
          elif details.get('type') == 'upload':
              if 'data' not in details:
                    print(f"[admin_file_server] Error: No file data found {details}")
                    return jsonify({'error': 'No file data received'}), 400
              target_path = os.path.join(ADMIN_SYNC_DIR, file_path)
              os.makedirs(os.path.dirname(target_path), exist_ok=True)
              with open(target_path, "wb") as file:
                file.write(details['data'].encode('latin1'))
              print(f"[admin_file_server] Uploaded file: {target_path}")
          else:
            print(f"[admin_file_server] Unknown type: {details}")
            return jsonify({'error': 'Unknown type'}), 400
        
        print("[admin_file_server] Sync process complete.")
        return jsonify({'message': 'Synchronization successful'}), 200
    
    except Exception as e:
      print(f"[admin_file_server] An error occured, details: {e}")
      import traceback
      traceback.print_exc()
      return jsonify({'error': str(e)}), 500

@app.route('/sync_status', methods=['GET'])
def get_sync_status():
    """Get current sync queue status."""
    try:
        kiosk_id = request.args.get('kiosk_id')
        if not kiosk_id:
            return jsonify({'error': 'No kiosk ID provided'}), 400
            
        with sync_lock:
            if active_sync == kiosk_id:
                return jsonify({
                    'status': 'active',
                    'generation': queue_generation
                })
                
            queue_items = list(sync_queue.queue)
            if kiosk_id in queue_items:
                position = queue_items.index(kiosk_id) + 1
                return jsonify({
                    'status': 'queued',
                    'position': position,
                    'generation': queue_generation
                })
                
            return jsonify({
                'status': 'not_queued',
                'generation': queue_generation
            })
    except Exception as e:
        print(f"[admin_file_server] Error getting sync status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/request_sync', methods=['POST'])
def request_sync():
    """Request to be added to sync queue."""
    try:
        data = request.get_json()
        if not data or 'kiosk_id' not in data:
            return jsonify({'error': 'No kiosk ID provided'}), 400
            
        kiosk_id = data['kiosk_id']
        
        with sync_lock:
            # If already active, just confirm it
            if active_sync == kiosk_id:
                return jsonify({
                    'status': 'active',
                    'generation': queue_generation
                })
                
            # If already in queue, return position
            if kiosk_id in sync_queue.queue:
                position = list(sync_queue.queue).index(kiosk_id) + 1
                return jsonify({
                    'status': 'queued',
                    'position': position,
                    'generation': queue_generation
                })
            
            # Add to queue if not already present
            sync_queue.put(kiosk_id)
            update_sync_activity(kiosk_id)
            position = list(sync_queue.queue).index(kiosk_id) + 1
            print(f"[admin_file_server] Added {kiosk_id} to sync queue at position {position}")
            
            return jsonify({
                'status': 'queued',
                'position': position,
                'generation': queue_generation
            })
    except Exception as e:
        print(f"[admin_file_server] Error requesting sync: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/request_files', methods=['POST'])
def request_files():
    """Handle requests for specific files."""
    try:
        data = request.get_json()
        if not data or 'kiosk_id' not in data or 'files' not in data:
            return jsonify({'error': 'Invalid request format'}), 400
            
        kiosk_id = data['kiosk_id']
        requested_files = data['files']
        info_only = data.get('info_only', False)
        
        # Check if this kiosk is currently active
        if active_sync != kiosk_id:
            return jsonify({'error': 'Not your turn to sync'}), 403
            
        response_data = {}
        total_size = 0
        MAX_BATCH_SIZE = 50 * 1024 * 1024  # 50MB batch size limit
        
        for file_path in requested_files:
            full_path = os.path.join(ADMIN_SYNC_DIR, file_path)
            if os.path.exists(full_path):
                file_size = os.path.getsize(full_path)
                
                # If adding this file would exceed batch size, send current batch
                if total_size + file_size > MAX_BATCH_SIZE and response_data:
                    return jsonify({
                        'files': response_data,
                        'status': 'partial',
                        'remaining_files': requested_files[requested_files.index(file_path):]
                    })
                
                if info_only:
                    response_data[file_path] = {
                        'size': file_size
                    }
                else:
                    # Read and add file to current batch
                    with open(full_path, 'rb') as f:
                        file_data = f.read()
                        response_data[file_path] = {
                            'data': file_data.decode('latin1'),
                            'size': file_size
                        }
                total_size += file_size
                print(f"[admin_file_server] Added {file_path} ({file_size} bytes) to response")
                    
        return jsonify({
            'files': response_data,
            'status': 'complete'
        })
    except Exception as e:
        print(f"[admin_file_server] Error serving requested files: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/finish_sync', methods=['POST'])
def finish_sync():
    """Mark sync as complete for a kiosk."""
    try:
        data = request.get_json()
        if not data or 'kiosk_id' not in data:
            return jsonify({'error': 'No kiosk ID provided'}), 400
            
        kiosk_id = data['kiosk_id']
        
        global active_sync, queue_generation
        with sync_lock:
            if active_sync == kiosk_id:
                active_sync = None
                queue_generation += 1  # Increment generation on queue state change
                if not sync_queue.empty():
                    active_sync = sync_queue.get()
                    
        return jsonify({'message': 'Sync completed', 'generation': queue_generation})
    except Exception as e:
        print(f"[admin_file_server] Error finishing sync: {e}")
        return jsonify({'error': str(e)}), 500

def process_next_sync():
    """Process next kiosk in sync queue."""
    global active_sync, queue_generation
    with sync_lock:
        if active_sync is None and not sync_queue.empty():
            active_sync = sync_queue.get()
            queue_generation += 1  # Increment generation when activating new sync
            print(f"[admin_file_server] Now syncing with {active_sync}")
            # Clear activity timestamp when becoming active
            if 'last_sync_activity' in app.config and active_sync in app.config['last_sync_activity']:
                del app.config['last_sync_activity'][active_sync]

# Add background thread to process queue
def queue_processor():
    while True:
        process_next_sync()
        time.sleep(1)

from threading import Thread
queue_thread = Thread(target=queue_processor, daemon=True)
queue_thread.start()

@app.route('/download_file', methods=['POST'])
def download_file():
    """Stream a file in chunks for large file downloads."""
    try:
        data = request.get_json()
        if not data or 'file_path' not in data or 'kiosk_id' not in data:
            return jsonify({'error': 'Invalid request data'}), 400

        file_path = data['file_path'].replace('\\', '/')
        full_path = os.path.join(ADMIN_SYNC_DIR, file_path)
        
        if not os.path.exists(full_path):
            return jsonify({'error': 'File not found'}), 404

        # Handle range requests for resume capability
        range_header = request.headers.get('Range', None)
        file_size = os.path.getsize(full_path)
        chunk_size = 1 * 1024 * 1024  # 1MB chunks to match client

        if range_header:
            try:
                bytes_range = range_header.replace('bytes=', '').split('-')
                start_byte = int(bytes_range[0])
                end_byte = file_size - 1
            except:
                return jsonify({'error': 'Invalid range header'}), 400
        else:
            start_byte = 0
            end_byte = file_size - 1

        # Create response headers
        headers = {
            'Content-Type': 'application/octet-stream',
            'Accept-Ranges': 'bytes',
            'Content-Length': str(end_byte - start_byte + 1),
            'Content-Range': f'bytes {start_byte}-{end_byte}/{file_size}',
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }

        def generate():
            try:
                with open(full_path, 'rb', buffering=chunk_size) as file:
                    file.seek(start_byte)
                    remaining = end_byte - start_byte + 1
                    while remaining:
                        # Read smaller chunks and add small delay to prevent overwhelming system
                        chunk = file.read(min(chunk_size, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        time.sleep(0.01)  # Small delay between chunks
                        yield chunk
            except Exception as e:
                print(f"[admin_file_server] Error during file streaming: {e}")
                raise

        return Response(
            generate(),
            206 if range_header else 200,
            headers=headers,
            direct_passthrough=True
        )

    except Exception as e:
        print(f"[admin_file_server] Error streaming file: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# Add timeout handling for active syncs
def check_sync_timeout():
    """Check for timed out syncs and clear them."""
    global active_sync
    while True:
        try:
            with sync_lock:
                if active_sync:
                    # If a sync has been active for more than 5 minutes, clear it
                    last_activity = app.config.get('last_sync_activity', {}).get(active_sync)
                    if last_activity and time.time() - last_activity > 300:  # 5 minutes
                        print(f"[admin_file_server] Sync timed out for {active_sync}")
                        active_sync = None
                        if not sync_queue.empty():
                            active_sync = sync_queue.get()
            time.sleep(10)  # Check every 10 seconds
        except Exception as e:
            print(f"[admin_file_server] Error in sync timeout checker: {e}")
            time.sleep(10)

# Start the timeout checker thread
timeout_thread = Thread(target=check_sync_timeout, daemon=True)
timeout_thread.start()

# Update activity timestamp whenever a kiosk makes a request
def update_sync_activity(kiosk_id):
    """Update the last activity timestamp for a kiosk."""
    if 'last_sync_activity' not in app.config:
        app.config['last_sync_activity'] = {}
    app.config['last_sync_activity'][kiosk_id] = time.time()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=ADMIN_SERVER_PORT, debug=True)