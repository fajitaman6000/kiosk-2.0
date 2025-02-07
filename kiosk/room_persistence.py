import json
import os
from pathlib import Path

class RoomPersistence:
    def __init__(self):
        # Store data locally in the kiosk directory
        self.config_dir = Path(__file__).parent / "data"
        self.config_file = self.config_dir / "room_assignment.json"
        print(f"[room persistence]\nRoom Persistence initialized")
        #print(f"[room persistence]Config directory: {self.config_dir}")
        #print(f"[room persistence]Config file: {self.config_file}")
        self._ensure_config_dir()

    def _ensure_config_dir(self):
        """Create data directory if it doesn't exist"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            #print(f"[room persistence]Config directory created/verified at: {self.config_dir}")
        except Exception as e:
            print(f"[room persistence]Error creating data directory: {e}")

    def save_room_assignment(self, room_number):
        """Save room assignment to persistent storage"""
        try:
            config = {'assigned_room': room_number}
            print(f"[room persistence]\nSaving room assignment: {room_number}")
            print(f"[room persistence]To file: {self.config_file}")
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
            #print("[room persistence]Room assignment saved successfully")
            return True
        except Exception as e:
            print(f"[room persistence]Error saving room assignment: {e}")
            return False

    def load_room_assignment(self):
        """Load room assignment from persistent storage"""
        try:
            if not self.config_file.exists():
                print(f"[room persistence]\nNo saved room assignment found at: {self.config_file}")
                return None
            #print(f"[room persistence]\nLoading room assignment from: {self.config_file}")
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            room = config.get('assigned_room')
            #print(f"[room persistence]Loaded room assignment: {room}")
            return room
        except Exception as e:
            print(f"[room persistence]Error loading room assignment: {e}")
            return None

    def clear_room_assignment(self):
        """Clear saved room assignment"""
        try:
            if self.config_file.exists():
                print(f"[room persistence]\nClearing room assignment: {self.config_file}")
                self.config_file.unlink()
                #print("[room persistence]Room assignment cleared")
            return True
        except Exception as e:
            print(f"[room persistence]Error clearing room assignment: {e}")
            return False