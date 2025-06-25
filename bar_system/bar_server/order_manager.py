# bar_server/order_manager.py
import json
import os  # --- NEW --- Need os for os.replace and os.remove
from datetime import datetime, timezone
from PyQt5.QtCore import QObject, pyqtSignal

import config

class OrderManager(QObject):
    order_updated = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.pending_orders = []
        self.completed_orders = []
        self._load_orders()

    def _load_orders(self):
        # We can add more robust loading here if needed, but for now this is fine.
        if not os.path.exists(config.ORDER_LOG_FILE):
            return
        try:
            with open(config.ORDER_LOG_FILE, 'r') as f:
                all_orders = json.load(f)
            self.pending_orders = [o for o in all_orders if o.get('status') == 'Pending']
            self.completed_orders = [o for o in all_orders if o.get('status') == 'Completed']
            print(f"Loaded {len(self.pending_orders)} pending and {len(self.completed_orders)} completed orders.")
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading order history from {config.ORDER_LOG_FILE}: {e}. Starting fresh.")
            # Optional: attempt to load a backup file if one exists
            self.pending_orders = []
            self.completed_orders = []


    # --- MODIFIED --- This method is now atomic and safe from corruption on crash.
    def _save_orders(self):
        """Saves the current order lists to the log file atomically."""
        all_orders = self.pending_orders + self.completed_orders
        temp_file_path = config.ORDER_LOG_FILE + ".tmp"
        
        try:
            with open(temp_file_path, 'w') as f:
                json.dump(all_orders, f, indent=4)
            # Atomically rename the temp file to the final file.
            # This is much safer than writing directly to the original file.
            os.replace(temp_file_path, config.ORDER_LOG_FILE)
        except Exception as e:
            print(f"Error saving to {config.ORDER_LOG_FILE}: {e}")
        finally:
            # Ensure the temp file is cleaned up if it still exists
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    def add_order(self, order_data, item_map):
        order_id = order_data.get("order_id")
        item_id = order_data.get("item_id")
        item_info = item_map.get(item_id)

        if not item_info:
            print(f"Cannot process order {order_id}: Item ID {item_id} not found.")
            return None

        new_order = {
            **order_data,
            "item_name": item_info["name"],
            "item_price": item_info.get("price", 0.0),
            "receiver_hostname": config.SERVER_HOSTNAME,
            "received_timestamp_utc": datetime.now(timezone.utc).isoformat(timespec='seconds'),
            "status": "Pending"
        }
        self.pending_orders.append(new_order)
        self._save_orders()
        self.order_updated.emit()
        print(f"Added new pending order: {order_id}")
        return new_order

    def complete_order(self, order_id):
        order_to_complete = None
        for order in self.pending_orders:
            if order['order_id'] == order_id:
                order_to_complete = order
                break
        
        if order_to_complete:
            self.pending_orders.remove(order_to_complete)
            order_to_complete['status'] = 'Completed'
            order_to_complete['completed_timestamp_utc'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
            self.completed_orders.append(order_to_complete)
            self._save_orders()
            self.order_updated.emit()
            print(f"Completed order: {order_id}")
        else:
            print(f"Could not find pending order to complete with ID: {order_id}")

    def get_pending_orders(self):
        return sorted(self.pending_orders, key=lambda o: o['received_timestamp_utc'])