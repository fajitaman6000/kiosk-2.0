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
import subprocess


class KioskApp:
    def __init__(self):
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
        
    def toggle_fullscreen(self):
        """Development helper to toggle fullscreen"""
        is_fullscreen = self.root.attributes('-fullscreen')
        self.root.attributes('-fullscreen', not is_fullscreen)
        if is_fullscreen:
            self.root.config(cursor="")
        else:
            self.root.config(cursor="none")

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
            
        elif msg['type'] == 'video_command' and msg['computer_name'] == self.computer_name:
            self.play_video(msg['video_type'], msg['minutes'])
                
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
        
        video_file = video_dir / f"{video_type}.mp4"
        print(f"Looking for video file: {video_file.absolute()}")

        if not video_file.exists():
            print(f"video: {video_type} not found")
            self.root.deiconify()  # Restore UI if video not found
            return

        game_video = video_dir / "game.mp4"

        try:# VLC arguments for both test and full playback
            vlc_args = [
                vlc_exe,
                '--fullscreen',
                '--no-repeat',
                '--no-loop',
                '--play-and-exit',
                '--no-video-deco',        # No window decoration
                '--no-embedded-video',    # Don't embed in a window
                '--no-video-title-show',  # No title
                '--no-spu',              # No subtitles
                '--no-osd',              # No on-screen display
                '--no-interact',         # No interaction
                str(video_file.absolute())
            ]

            # Play the selected video
            print(f"Playing first video: {video_file}")
            self.current_video_process = subprocess.Popen(
                vlc_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Wait for first video with timeout
            try:
                self.current_video_process.wait(timeout=300)  # 5 minute timeout
            except subprocess.TimeoutExpired:
                self.current_video_process.terminate()

            # If not "game intro only" and game video exists, play game video
            if video_type != 'game' and game_video.exists():
                vlc_args[-1] = str(game_video.absolute())  # Replace video path
                print(f"Playing game video: {game_video}")
                self.current_video_process = subprocess.Popen(
                    vlc_args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                try:
                    self.current_video_process.wait(timeout=300)
                except subprocess.TimeoutExpired:
                    self.current_video_process.terminate()

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