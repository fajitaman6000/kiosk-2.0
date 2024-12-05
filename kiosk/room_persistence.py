import json
import os
from pathlib import Path

class RoomPersistence:
    def __init__(self):
        self.config_dir = Path(os.path.expanduser("~")) / ".kiosk"
        self.config_file = self.config_dir / "room_assignment.json"
        self._ensure_config_dir()

    def _ensure_config_dir(self):
        """Create config directory if it doesn't exist"""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def save_room_assignment(self, room_number):
        """Save room assignment to persistent storage"""
        try:
            config = {'assigned_room': room_number}
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
            return True
        except Exception as e:
            print(f"Error saving room assignment: {e}")
            return False

    def load_room_assignment(self):
        """Load room assignment from persistent storage"""
        try:
            if not self.config_file.exists():
                return None
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            return config.get('assigned_room')
        except Exception as e:
            print(f"Error loading room assignment: {e}")
            return None

    def clear_room_assignment(self):
        """Clear saved room assignment"""
        try:
            if self.config_file.exists():
                self.config_file.unlink()
            return True
        except Exception as e:
            print(f"Error clearing room assignment: {e}")
            return False