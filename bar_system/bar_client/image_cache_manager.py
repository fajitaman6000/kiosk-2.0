# Client/image_cache_manager.py
import os
import json
import base64
import config

class ImageCacheManager:
    def __init__(self, network_client):
        self.network_client = network_client
        self.manifest = {}
        self._load_manifest()

        if not os.path.exists(config.IMAGE_CACHE_DIR):
            os.makedirs(config.IMAGE_CACHE_DIR)

    def _load_manifest(self):
        """Loads the JSON file that tracks hashes of cached images."""
        try:
            if os.path.exists(config.CACHE_MANIFEST_FILE):
                with open(config.CACHE_MANIFEST_FILE, 'r') as f:
                    self.manifest = json.load(f)
        except (IOError, json.JSONDecodeError):
            self.manifest = {}

    def _save_manifest(self):
        """Saves the current cache manifest to a file."""
        with open(config.CACHE_MANIFEST_FILE, 'w') as f:
            json.dump(self.manifest, f, indent=4)

    def check_and_request_image(self, item_data):
        """
        Checks if an image is cached and up-to-date.
        If not, sends a request to the server to download it.
        Returns the local path to the image.
        """
        filename = item_data.get("image_file")
        server_hash = item_data.get("image_hash")

        if not filename or not server_hash:
            return None # No image for this item

        local_path = os.path.join(config.IMAGE_CACHE_DIR, filename)
        local_hash = self.manifest.get(filename)

        if os.path.exists(local_path) and local_hash == server_hash:
            # Image is cached and up-to-date
            return local_path
        else:
            # Image is missing or outdated, request it
            print(f"Requesting image download for: {filename}")
            self.network_client.send_message("REQUEST_IMAGE", {"filename": filename})
            return None # No path available until it's downloaded

    def save_image_from_server(self, payload):
        """Decodes and saves an image received from the server."""
        filename = payload.get("filename")
        server_hash = payload.get("hash")
        b64_data = payload.get("data")

        if not all([filename, server_hash, b64_data]):
            print("Error: Incomplete image data received from server.")
            return None

        try:
            image_data = base64.b64decode(b64_data)
            local_path = os.path.join(config.IMAGE_CACHE_DIR, filename)
            with open(local_path, 'wb') as f:
                f.write(image_data)

            # Update manifest and save
            self.manifest[filename] = server_hash
            self._save_manifest()
            print(f"Successfully cached image: {filename}")
            return local_path

        except Exception as e:
            print(f"Error saving cached image {filename}: {e}")
            return None