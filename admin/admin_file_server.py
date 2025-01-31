# admin_file_server.py
import os
from flask import Flask, send_from_directory, request, jsonify
from file_sync_config import ADMIN_SYNC_DIR, ADMIN_SERVER_PORT
import json
import glob
import hashlib

app = Flask(__name__)


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_files(path):
    """Serve static files from the sync directory."""
    try:
        if not path:
            files = []
            for file in glob.iglob(ADMIN_SYNC_DIR + '/**', recursive=True):
                if os.path.isfile(file):
                    files.append(os.path.relpath(file, ADMIN_SYNC_DIR))
            return "\n".join(files)
        return send_from_directory(ADMIN_SYNC_DIR, path)
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


@app.route('/sync_info', methods=['GET'])
def get_sync_info():
    """Get the file list and their hashes for syncing."""
    try:
        files = {}
        for root, _, filenames in os.walk(ADMIN_SYNC_DIR):
            for filename in filenames:
                file_path = os.path.relpath(os.path.join(root, filename), ADMIN_SYNC_DIR)
                full_path = os.path.join(ADMIN_SYNC_DIR, file_path)
                files[file_path] = calculate_file_hash(full_path)
        
        return jsonify(files)

    except Exception as e:
        print(f"[admin_file_server] Error providing sync info: {e}")
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=ADMIN_SERVER_PORT, debug=True)