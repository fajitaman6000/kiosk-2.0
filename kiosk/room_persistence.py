print("[room persistence] Beginning imports ...", flush=True)
print("[room persistence] Importing json...", flush=True)
import json
print("[room persistence] Imported json.", flush=True)
print("[room persistence] Importing os...", flush=True)
import os
print("[room persistence] Imported os.", flush=True)
print("[room persistence] Importing Path from pathlib...", flush=True)
from pathlib import Path
print("[room persistence] Imported Path from pathlib.", flush=True)
print("[room persistence] Ending imports ...", flush=True)

class RoomPersistence:
    def __init__(self):
        print("[room persistence] Initializing RoomPersistence...", flush=True)
        # Store data locally in the kiosk directory
        self.config_dir = Path(__file__).parent / "data"
        self.config_file = self.config_dir / "room_assignment.json"
        print(f"[room persistence] Room Persistence initialized", flush=True)
        #print(f"[room persistence]Config directory: {self.config_dir}")
        #print(f"[room persistence]Config file: {self.config_file}")
        self._ensure_config_dir()
        print(f"[room persistence] RoomPersistence initialization complete.", flush=True)

    def _ensure_config_dir(self):
        """Create data directory if it doesn't exist"""
        try:
            print(f"[room persistence] Creating/verifying config directory: {self.config_dir}", flush=True)
            self.config_dir.mkdir(parents=True, exist_ok=True)
            print(f"[room persistence] Config directory created/verified.", flush=True)
            #print(f"[room persistence]Config directory created/verified at: {self.config_dir}")
        except Exception as e:
            print(f"[room persistence] Error creating data directory: {e}", flush=True)

    def save_room_assignment(self, room_number):
        """Save room assignment to persistent storage"""
        try:
            config = {'assigned_room': room_number}
            print(f"[room persistence] Saving room assignment: {room_number}", flush=True)
            print(f"[room persistence] To file: {self.config_file}", flush=True)
            print(f"[room persistence] Opening file for writing...", flush=True)
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
            print("[room persistence] Room assignment saved successfully", flush=True)
            return True
        except Exception as e:
            print(f"[room persistence] Error saving room assignment: {e}", flush=True)
            return False

    def load_room_assignment(self):
        """Load room assignment from persistent storage"""
        try:
            if not self.config_file.exists():
                print(f"[room persistence] No saved room assignment found at: {self.config_file}", flush=True)
                return None
            print(f"[room persistence] Loading room assignment from: {self.config_file}", flush=True)
            print(f"[room persistence] Opening file for reading...", flush=True)
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            room = config.get('assigned_room')
            print(f"[room persistence] Loaded room assignment: {room}", flush=True)
            return room
        except Exception as e:
            print(f"[room persistence] Error loading room assignment: {e}", flush=True)
            return None

    def clear_room_assignment(self):
        """Clear saved room assignment"""
        try:
            if self.config_file.exists():
                print(f"[room persistence] Clearing room assignment: {self.config_file}", flush=True)
                self.config_file.unlink()
                print("[room persistence] Room assignment cleared", flush=True)
            return True
        except Exception as e:
            print(f"[room persistence] Error clearing room assignment: {e}", flush=True)
            return False