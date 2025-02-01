import json
import os

def create_directories(json_file):
    """
    Creates directories based on the room names and display (new) prop names from a JSON file.

    Args:
        json_file: Path to the JSON file containing prop mappings.
    """

    with open(json_file, 'r') as f:
        data = json.load(f)

    for room, details in data.items():
        room_dir = room
        os.makedirs(room_dir, exist_ok=True)

        for original_prop, prop_details in details['mappings'].items():
            # Use the 'display' name instead of the original prop name
            new_prop_name = prop_details['display']
            prop_dir = os.path.join(room_dir, new_prop_name)
            os.makedirs(prop_dir, exist_ok=True)

# Example usage (this part makes the script runnable directly):
if __name__ == "__main__":
    json_file_path = 'prop_name_mapping.json'

    # Create a dummy prop_name_mapping.json for testing if it doesn't exist
    if not os.path.exists(json_file_path):
        dummy_data = {
            "test_room": {
                "comments": "Test Room Props",
                "mappings": {
                    "Test Prop 1": {
                        "display": "Test Display 1",
                        "order": 1,
                        "finishing_prop": False
                    },
                    "Test Prop 2": {
                        "display": "Test Display 2",
                        "order": 2,
                        "finishing_prop": True
                    }
                }
            }
        }
        with open(json_file_path, 'w') as f:
            json.dump(dummy_data, f, indent=4)

    create_directories(json_file_path)