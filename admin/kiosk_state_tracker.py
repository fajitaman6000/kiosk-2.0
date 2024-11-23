import time

class KioskStateTracker:
    def __init__(self, app):
        self.app = app
        self.kiosk_assignments = {}  # computer_name -> room_number
        self.kiosk_stats = {}        # computer_name -> stats dict
        self.assigned_rooms = {}     # computer_name -> room_name
        self.help_requested = set()  # set of computer_names
        
    def update_kiosk_stats(self, computer_name, msg):
        self.kiosk_stats[computer_name] = {
            'total_hints': msg.get('total_hints', 0),
            'timer_time': msg.get('timer_time', 3600),
            'timer_running': msg.get('timer_running', False)
        }
        
        # Update UI if this kiosk is selected
        if computer_name == self.app.interface_builder.selected_kiosk:
            self.app.interface_builder.update_stats_display(computer_name)

    def update_timer_state(self, computer_name, time_remaining, is_running):
        if computer_name in self.kiosk_stats:
            self.kiosk_stats[computer_name]['timer_time'] = time_remaining
            self.kiosk_stats[computer_name]['timer_running'] = is_running
            
            # Update UI if this kiosk is selected
            if computer_name == self.app.interface_builder.selected_kiosk:
                self.app.interface_builder.update_stats_display(computer_name)
        
    def add_help_request(self, computer_name):
        self.help_requested.add(computer_name)
        
    def remove_help_request(self, computer_name):
        if computer_name in self.help_requested:
            self.help_requested.remove(computer_name)
            
    def assign_kiosk_to_room(self, computer_name, room_number):
        print(f"Assigning {computer_name} to room {room_number}")
        self.kiosk_assignments[computer_name] = room_number
        self.assigned_rooms[computer_name] = self.app.rooms[room_number]
        
        # Update interface
        if computer_name in self.app.interface_builder.connected_kiosks:
            self.app.interface_builder.update_kiosk_display(computer_name)
        
        # Send network message
        self.app.network_handler.send_room_assignment(computer_name, room_number)
        
    def check_timeouts(self):
        current_time = time.time()
        for computer_name in list(self.app.interface_builder.connected_kiosks.keys()):
            if current_time - self.app.interface_builder.connected_kiosks[computer_name]['last_seen'] > 10:
                self.app.interface_builder.remove_kiosk(computer_name)
        self.app.root.after(5000, self.check_timeouts)
