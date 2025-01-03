import json
import os
from pathlib import Path

class RoomPersistence:
    def __init__(self):
        self.config_dir = Path(os.path.expanduser("~")) / ".kiosk"
        self.config_file = self.config_dir / "room_assignment.json"
        print(f"\nRoom Persistence initialized")
        #print(f"Config directory: {self.config_dir}")
        #print(f"Config file: {self.config_file}")
        self._ensure_config_dir()

    def _ensure_config_dir(self):
        """Create config directory if it doesn't exist"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            #print(f"Config directory created/verified at: {self.config_dir}")
        except Exception as e:
            print(f"Error creating config directory: {e}")

    def save_room_assignment(self, room_number):
        """Save room assignment to persistent storage"""
        try:
            config = {'assigned_room': room_number}
            print(f"\nSaving room assignment: {room_number}")
            print(f"To file: {self.config_file}")
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
            #print("Room assignment saved successfully")
            return True
        except Exception as e:
            print(f"Error saving room assignment: {e}")
            return False

    def load_room_assignment(self):
        """Load room assignment from persistent storage"""
        try:
            if not self.config_file.exists():
                print(f"\nNo saved room assignment found at: {self.config_file}")
                return None
            #print(f"\nLoading room assignment from: {self.config_file}")
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            room = config.get('assigned_room')
            #print(f"Loaded room assignment: {room}")
            return room
        except Exception as e:
            print(f"Error loading room assignment: {e}")
            return None

    def clear_room_assignment(self):
        """Clear saved room assignment"""
        try:
            if self.config_file.exists():
                print(f"\nClearing room assignment: {self.config_file}")
                self.config_file.unlink()
                #print("Room assignment cleared")
            return True
        except Exception as e:
            print(f"Error clearing room assignment: {e}")
            return False