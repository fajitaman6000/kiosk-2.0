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
from audio_server import AudioServer
from pathlib import Path
from room_persistence import RoomPersistence
import subprocess
import traceback


class KioskApp:
    def __init__(self):
        print("\nStarting KioskApp initialization...")
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        
        self.root = tk.Tk()
        self.computer_name = socket.gethostname()
        self.root.title(f"Kiosk: {self.computer_name}")
        
        # Add fullscreen and cursor control
        self.root.attributes('-fullscreen', True)
        self.root.config(cursor="none")  # Hide cursor
        self.root.bind('<Escape>', lambda e: self.toggle_fullscreen())
        
        self.assigned_room = None
        self.hints_requested = 0
        self.start_time = None
        self.current_video_process = None  # Add this line
        
        # Initialize components as before
        self.network = KioskNetwork(self.computer_name, self)
        self.video_server = VideoServer()
        print("Starting video server...")
        self.video_server.start()
        
        from kiosk_timer import KioskTimer
        self.timer = KioskTimer(self.root, self.network)
        
        self.ui = KioskUI(self.root, self.computer_name, ROOM_CONFIG, self)
        self.ui.setup_waiting_screen()
        self.network.start_threads()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.audio_server = AudioServer()
        print("Starting audio server...")
        self.audio_server.start()

        print(f"Computer name: {self.computer_name}")
        print("Creating RoomPersistence...")
        self.room_persistence = RoomPersistence()
        print("Loading saved room...")
        self.assigned_room = self.room_persistence.load_room_assignment()
        print(f"Loaded room assignment: {self.assigned_room}")

        
        # Initialize UI with saved room if available
        if self.assigned_room:
            self.root.after(100, lambda: self.ui.setup_room_interface(self.assigned_room))
        else:
            self.ui.setup_waiting_screen()

    def handle_message(self, msg):
        print(f"\nReceived message: {msg}")
        if msg['type'] == 'room_assignment' and msg['computer_name'] == self.computer_name:
            print(f"Processing room assignment: {msg['room']}")            
            self.assigned_room = msg['room']
            print("Saving room assignment...")
            save_result = self.room_persistence.save_room_assignment(msg['room'])
            print(f"Save result: {save_result}")
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
            
        elif msg['type'] == 'video_command' and msg['computer_name'] == self.computer_name:
            self.play_video(msg['video_type'], msg['minutes'])
            
        elif msg['type'] == 'reset_kiosk' and msg['computer_name'] == self.computer_name:
            # Reset hints count
            self.hints_requested = 0
            
            # Clear UI elements
            self.ui.hint_cooldown = False
            self.ui.current_hint = None
            self.ui.clear_all_labels()
            
            # Restore room interface if assigned
            if self.assigned_room:
                self.ui.setup_room_interface(self.assigned_room)
            
            # Stop any playing videos
            if self.current_video_process:
                self.current_video_process.terminate()
                self.current_video_process = None
                self.root.deiconify()  # Restore UI if hidden

    def toggle_fullscreen(self):
        """Development helper to toggle fullscreen"""
        is_fullscreen = self.root.attributes('-fullscreen')
        self.root.attributes('-fullscreen', not is_fullscreen)
        if is_fullscreen:
            self.root.config(cursor="")
        else:
            self.root.config(cursor="none")

    def get_stats(self):
        stats = {
            'computer_name': self.computer_name,
            'room': self.assigned_room,
            'total_hints': self.hints_requested,
            'timer_time': self.timer.time_remaining,
            'timer_running': self.timer.is_running
        }
        # Only log if stats have changed from last time
        if not hasattr(self, '_last_stats') or self._last_stats != stats:
            print(f"\nStats updated: {stats}")
            self._last_stats = stats.copy()
        return stats
        
    def handle_message(self, msg):
        print(f"\nReceived message: {msg}")
        try:
            if msg['type'] == 'room_assignment' and msg['computer_name'] == self.computer_name:
                print(f"Processing room assignment: {msg['room']}")            
                self.assigned_room = msg['room']
                print("Saving room assignment...")
                save_result = self.room_persistence.save_room_assignment(msg['room'])
                print(f"Save result: {save_result}")
                self.start_time = time.time()
                self.ui.hint_cooldown = False
                self.ui.current_hint = None
                self.ui.clear_all_labels()
                self.root.after(0, lambda: self.ui.setup_room_interface(msg['room']))
                
            elif msg['type'] == 'hint' and self.assigned_room:
                if msg.get('room') == self.assigned_room:
                    print("\nProcessing hint message:")
                    print(f"Has image flag: {msg.get('has_image')}")
                    print(f"Message keys: {msg.keys()}")
                    
                    # Prepare hint data
                    if msg.get('has_image') and 'image' in msg:
                        print("Creating image+text hint data")
                        hint_data = {
                            'text': msg.get('text', ''),
                            'image': msg['image']
                        }
                    else:
                        print("Creating text-only hint")
                        hint_data = msg.get('text', '')
                    
                    print(f"Scheduling hint display with data type: {type(hint_data)}")
                    self.root.after(0, lambda d=hint_data: self.show_hint(d))
                    
            elif msg['type'] == 'timer_command' and msg['computer_name'] == self.computer_name:
                minutes = msg.get('minutes')
                self.timer.handle_command(msg['command'], minutes)
                
            elif msg['type'] == 'video_command' and msg['computer_name'] == self.computer_name:
                self.play_video(msg['video_type'], msg['minutes'])
                
            elif msg['type'] == 'reset_kiosk' and msg['computer_name'] == self.computer_name:
                print("Received reset command - resetting kiosk state")
                self.hints_requested = 0
                self.network.send_message({
                    'type': 'kiosk_announce',
                    'computer_name': self.computer_name,
                    'room': self.assigned_room,
                    'total_hints': 0,
                    'timer_time': self.timer.time_remaining,
                    'timer_running': self.timer.is_running
                })
                
                self.ui.hint_cooldown = False
                self.ui.current_hint = None
                self.ui.clear_all_labels()
                
                if self.assigned_room:
                    self.ui.setup_room_interface(self.assigned_room)
                
                if self.current_video_process:
                    self.current_video_process.terminate()
                    self.current_video_process = None
                    self.root.deiconify()
        
        except Exception as e:
            print("\nCritical error in handle_message:")
            print(f"Error type: {type(e)}")
            print(f"Error message: {str(e)}")
            traceback.print_exc()
                
    def request_help(self):
        if not self.ui.hint_cooldown:
            self.hints_requested += 1
            if self.ui.help_button:
                self.ui.help_button.destroy()
                self.ui.help_button = None
                
            if self.ui.request_pending_label is None:
                self.ui.request_pending_label = tk.Label(
                    self.root,
                    text="Hint Requested, please wait...",
                    fg='yellow', bg='black',
                    font=('Arial', 24)
                )
                # Position the pending request text on the left side
                self.ui.request_pending_label.place(relx=0.2, rely=0.4, anchor='center')
            
            self.network.send_message({
                'type': 'help_request',
                **self.get_stats()
            })
            
    def show_hint(self, text):
        # Clear any pending request status
        if self.ui.request_pending_label:
            self.ui.request_pending_label.destroy()
            self.ui.request_pending_label = None
            
        # Show the hint
        self.ui.show_hint(text)
        
        # Start cooldown timer
        self.ui.start_cooldown()

    def play_video(self, video_type, minutes):
        print(f"\nStarting play_video with type: {video_type}")
        
        # Stop any currently playing video
        if self.current_video_process:
            self.current_video_process.terminate()
            self.current_video_process = None
            
        # Hide the main UI temporarily
        self.root.withdraw()
        
        # Try to find VLC in common installation paths
        vlc_paths = [
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
        ]
        
        vlc_exe = None
        print("Checking VLC paths:")
        for path in vlc_paths:
            print(f"Checking {path}...")
            if os.path.exists(path):
                vlc_exe = path
                print(f"Found VLC at: {path}")
                break
                
        if not vlc_exe:
            print("Error: VLC not found. Please install VLC media player.")
            self.root.deiconify()
            return
            
        # Debug current directory and video path
        print(f"Current working directory: {os.getcwd()}")
        video_dir = Path("videos")
        print(f"Video directory exists: {video_dir.exists()}")
        print(f"Video directory absolute path: {video_dir.absolute()}")
        
        # Define video paths upfront
        video_file = video_dir / f"{video_type}.mp4" if video_type != 'game' else None
        game_video = None
        
        # Get room-specific game video name from config if room is assigned
        if self.assigned_room is not None and self.assigned_room in ROOM_CONFIG['backgrounds']:
            game_video_name = ROOM_CONFIG['backgrounds'][self.assigned_room].replace('.png', '.mp4')
            game_video = video_dir / game_video_name
            print(f"Looking for room-specific game video: {game_video}")
        else:
            print("No room assigned or invalid room number - skipping room-specific game video")

        try:
            # VLC arguments for video playback
            vlc_args = [
                vlc_exe,
                '--fullscreen',
                '--no-repeat',
                '--no-loop',
                '--play-and-exit',
                '--no-video-deco',        
                '--no-embedded-video',    
                '--no-video-title-show',  
                '--no-spu',              
                '--no-osd',              
                '--no-interact',
                '--video-filter=transform{type=270}',
            ]

            # If not "game", play the intro video first
            if video_type != 'game':
                print(f"Looking for intro video file: {video_file.absolute()}")
                if not video_file.exists():
                    print(f"video: {video_type} not found")
                    self.root.deiconify()  # Restore UI if video not found
                    return

                # Play the intro video
                print(f"Playing intro video: {video_file}")
                self.current_video_process = subprocess.Popen(
                    vlc_args + [str(video_file.absolute())],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
                # Wait for intro video with timeout
                try:
                    self.current_video_process.wait(timeout=300)  # 5 minute timeout
                except subprocess.TimeoutExpired:
                    self.current_video_process.terminate()

            # Play room-specific game video if it exists
            if game_video and game_video.exists():
                print(f"Playing room-specific game video: {game_video}")
                self.current_video_process = subprocess.Popen(
                    vlc_args + [str(game_video.absolute())],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                try:
                    self.current_video_process.wait(timeout=300)
                except subprocess.TimeoutExpired:
                    self.current_video_process.terminate()
            else:
                print("Room-specific game video not found")

            print("Videos complete, restoring UI")
            # Restore UI
            self.root.deiconify()  # Restore the main window
            
            # Clear any remnant fullscreen states
            self.root.attributes('-fullscreen', True)  # Re-assert fullscreen
            self.root.config(cursor="")  # Restore cursor
            self.root.update()
            
            # Reset UI completely
            self.ui.hint_cooldown = False  # Reset hint cooldown
            self.ui.clear_all_labels()     # Clear any existing UI elements
            if self.assigned_room:
                self.ui.setup_room_interface(self.assigned_room)
                # Force hint button creation if not in cooldown
                if not self.ui.hint_cooldown:
                    self.ui.create_help_button()
            
            # Set and start timer
            self.timer.handle_command("set", minutes)
            self.timer.handle_command("start")
            
        except Exception as e:
            print(f"Error running VLC: {e}")
            self.root.deiconify()
            return
        
    def on_closing(self):
        print("Shutting down kiosk...")
        if self.current_video_process:
            self.current_video_process.terminate()
        self.network.shutdown()
        self.video_server.stop()
        self.audio_server.stop()
        self.root.destroy()
        sys.exit(0)
        
    def run(self):
        self.root.mainloop()

if __name__ == '__main__':
    app = KioskApp()
    app.run()