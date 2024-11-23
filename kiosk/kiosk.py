# kiosk.py
import tkinter as tk
import socket
import time
import sys
import os
from networking import KioskNetwork
from ui import KioskUI
from config import ROOM_CONFIG
from video_server import VideoServer

class KioskApp:
    def __init__(self):
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        
        self.root = tk.Tk()
        self.computer_name = socket.gethostname()
        self.root.title(f"Kiosk: {self.computer_name}")
        
        self.assigned_room = None
        self.hints_requested = 0
        self.start_time = None
        
        # Initialize network first since timer needs it
        self.network = KioskNetwork(self.computer_name, self)
        
        # Add video server
        self.video_server = VideoServer()
        print("Starting video server...")
        self.video_server.start()
        
        # Create timer
        from kiosk_timer import KioskTimer
        self.timer = KioskTimer(self.root, self.network)
        
        self.ui = KioskUI(self.root, self.computer_name, ROOM_CONFIG, self)
        
        self.ui.setup_waiting_screen()
        self.network.start_threads()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def get_stats(self):
        return {
            'computer_name': self.computer_name,
            'room': self.assigned_room,
            'total_hints': self.hints_requested,
            'timer_time': self.timer.time_remaining,
            'timer_running': self.timer.is_running
        }
        
    def handle_message(self, msg):
        if msg['type'] == 'room_assignment' and msg['computer_name'] == self.computer_name:
            self.assigned_room = msg['room']
            self.start_time = time.time()
            self.ui.hint_cooldown = False
            self.ui.current_hint = None
            self.ui.clear_all_labels()
            self.root.after(0, lambda: self.ui.setup_room_interface(msg['room']))
            
        elif msg['type'] == 'hint' and self.assigned_room:
            if msg.get('room') == self.assigned_room:
                self.root.after(0, lambda t=msg['text']: self.show_hint(t))
                
        elif msg['type'] == 'timer_command' and msg['computer_name'] == self.computer_name:
            minutes = msg.get('minutes')
            self.timer.handle_command(msg['command'], minutes)
                
    def request_help(self):
        if not self.ui.hint_cooldown:
            self.hints_requested += 1
            if self.ui.help_button:
                self.ui.help_button.destroy()
                self.ui.help_button = None
                
            if self.ui.request_pending_label is None:
                self.ui.request_pending_label = tk.Label(
                    self.root,
                    text="Hint requested",
                    fg='yellow', bg='black',
                    font=('Arial', 24)
                )
                self.ui.request_pending_label.pack(pady=10)
            
            self.network.send_message({
                'type': 'help_request',
                **self.get_stats()
            })
            
    def show_hint(self, text):
        self.ui.show_hint(text)
        self.ui.start_cooldown()
        
    def on_closing(self):
        print("Shutting down kiosk...")
        self.network.shutdown()
        self.video_server.stop()  # Add this line
        self.root.destroy()
        sys.exit(0)
        
    def run(self):
        self.root.mainloop()

if __name__ == '__main__':
    app = KioskApp()
    app.run()