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
from video_manager import VideoManager
from audio_server import AudioServer
from pathlib import Path
from room_persistence import RoomPersistence
from kiosk_timer import KioskTimer
from audio_manager import AudioManager
import subprocess
import traceback
import pygame


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
        self.time_exceeded_45 = False
        print("Initialized time_exceeded_45 flag to False")
        self.audio_manager = AudioManager()  # Initialize audio manager
        self.video_manager = VideoManager(self.root) # Initialize video manager
        
        # Initialize components as before
        self.network = KioskNetwork(self.computer_name, self)
        self.video_server = VideoServer()
        print("Starting video server...")
        self.video_server.start()
        
        from kiosk_timer import KioskTimer
        self.timer = KioskTimer(self.root, self)  # Pass self instead of self.network
        
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

    def update_help_button_state(self):
        """Check timer and update help button state"""
        current_minutes = self.timer.time_remaining / 60
        print(f"\n=== Timer State Update ===")
        print(f"Current timer: {current_minutes:.2f} minutes")
        print(f"Time exceeded 45 flag: {self.time_exceeded_45}")
        
        # Check if we've exceeded 45 minutes
        if current_minutes > 45 and not self.time_exceeded_45:
            print("Timer has exceeded 45 minutes - setting flag")
            self.time_exceeded_45 = True
        
        # Refresh help button
        self.ui.create_help_button()

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
            #print(f"\nStats updated: {stats}")
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
                print("\nProcessing timer command")
                minutes = msg.get('minutes')
                
                # Update time_exceeded_45 flag if timer is being set above 45
                if minutes is not None:
                    minutes = float(minutes)
                    print(f"Setting timer to {minutes} minutes")
                    if minutes > 45:
                        print("New time exceeds 45 minutes - setting flag")
                        self.time_exceeded_45 = True
                
                # Handle the timer command
                self.timer.handle_command(msg['command'], minutes)
                
                # Update help button state
                self.root.after(100, self.update_help_button_state)
                
            elif msg['type'] == 'video_command' and msg['computer_name'] == self.computer_name:
                self.play_video(msg['video_type'], msg['minutes'])

            elif msg['type'] == 'clear_hints' and msg['computer_name'] == self.computer_name:
                print("\nProcessing clear hints command")
                self.clear_hints()

            elif msg['type'] == 'play_sound' and msg['computer_name'] == self.computer_name:
                print("\nReceived play sound command")
                sound_name = msg.get('sound_name')
                if sound_name:
                    self.audio_manager.play_sound(sound_name)
                    
            elif msg['type'] == 'solution_video' and msg['computer_name'] == self.computer_name:
                print("\nReceived solution video command")
                try:
                    room_folder = msg.get('room_folder')
                    video_filename = msg.get('video_filename')
                    
                    if not room_folder or not video_filename:
                        print("Error: Missing room_folder or video_filename in message")
                        return
                        
                    video_path = os.path.join("video_solutions", room_folder, f"{video_filename}.mp4")
                    print(f"Looking for solution video at: {video_path}")
                    
                    if os.path.exists(video_path):
                        print(f"Setting up solution video interface: {video_path}")
                        
                        # Create hint-style message for video solution
                        hint_data = {
                            'text': 'Video Solution Received',  # This will show in the hint text box
                        }
                        
                        # Show hint first, then show video interface
                        self.show_hint(hint_data)
                        
                        # Show the solution video interface
                        self.ui.show_video_solution(room_folder, video_filename)
                    else:
                        print(f"Error: Solution video not found at {video_path}")
                        
                except Exception as e:
                    print(f"Error processing solution video command: {e}")
                    traceback.print_exc()

            elif msg['type'] == 'reset_kiosk' and msg['computer_name'] == self.computer_name:
                print("\nProcessing kiosk reset")
                
                # First, stop all audio and video playback
                print("Stopping all media playback...")
                
                # Stop video manager (which handles both video and its audio)
                self.video_manager.stop_video()
                
                # Ensure pygame mixer is fully reset
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                    pygame.mixer.stop()  # Stop all sound channels
                
                # Stop any playing audio from audio manager
                #self.audio_manager.stop_sound()
                
                # Kill any remaining video process
                if self.current_video_process:
                    print("Terminating external video process")
                    self.current_video_process.terminate()
                    self.current_video_process = None
                    self.root.deiconify()
                
                # Reset application state
                print("Resetting application state...")
                self.time_exceeded_45 = False
                self.hints_requested = 0
                
                # Reset UI hint-related state
                print("Resetting UI hint state...")
                self.ui.hint_cooldown = False
                self.ui.current_hint = None
                self.ui.stored_image_data = None
                if hasattr(self.ui, 'stored_video_info'):
                    self.ui.stored_video_info = None
                if hasattr(self.ui, 'video_is_playing'):
                    self.ui.video_is_playing = False
                
                # Cancel any existing cooldown timer
                if self.ui.cooldown_after_id:
                    self.root.after_cancel(self.ui.cooldown_after_id)
                    self.ui.cooldown_after_id = None
                
                # Clear all UI elements
                print("Clearing UI elements...")
                self.ui.clear_all_labels()
                
                # Clear specific hint-related elements
                if hasattr(self.ui, 'image_button') and self.ui.image_button:
                    self.ui.image_button.destroy()
                    self.ui.image_button = None
                if hasattr(self.ui, 'video_solution_button') and self.ui.video_solution_button:
                    self.ui.video_solution_button.destroy()
                    self.ui.video_solution_button = None
                if hasattr(self.ui, 'fullscreen_image') and self.ui.fullscreen_image:
                    self.ui.fullscreen_image.destroy()
                    self.ui.fullscreen_image = None
                
                # Clear any pending request status
                if self.ui.status_frame:
                    self.ui.status_frame.delete('all')
                    self.ui.hide_status_frame()
                
                # Restore UI
                if self.assigned_room:
                    print("Restoring room interface")
                    self.ui.setup_room_interface(self.assigned_room)
                
                # Update help button state after reset
                self.root.after(100, self.update_help_button_state)
                
                print("Kiosk reset complete")
        
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
            
        # Play the hint received sound
        self.audio_manager.play_sound("hint_received.mp3")
        
        # Show the hint
        self.ui.show_hint(text)
        
        # Start cooldown timer
        self.ui.start_cooldown()

    def play_video(self, video_type, minutes):
        print(f"\n=== Video Playback Sequence Start ===")
        print(f"Starting play_video with type: {video_type}")
        print(f"Current room assignment: {self.assigned_room}")
        
        # Define video paths upfront
        video_dir = Path("intro_videos")
        video_file = video_dir / f"{video_type}.mp4" if video_type != 'game' else None
        game_video = None
        
        # Get room-specific game video name from config if room is assigned
        if self.assigned_room is not None and self.assigned_room in ROOM_CONFIG['backgrounds']:
            game_video_name = ROOM_CONFIG['backgrounds'][self.assigned_room].replace('.png', '.mp4')
            game_video = video_dir / game_video_name
            print(f"Found room-specific game video path: {game_video}")
            print(f"Game video exists? {game_video.exists() if game_video else False}")

        def finish_video_sequence():
            """Final callback after all videos are complete"""
            print("\n=== Video Sequence Completion ===")
            print("Executing finish_video_sequence callback")
            print(f"Setting timer to {minutes} minutes")
            self.timer.handle_command("set", minutes)
            self.timer.handle_command("start")
            print("Resetting UI state...")
            self.ui.hint_cooldown = False
            self.ui.clear_all_labels()
            if self.assigned_room:
                print(f"Restoring room interface for: {self.assigned_room}")
                self.ui.setup_room_interface(self.assigned_room)
                if not self.ui.hint_cooldown:
                    print("Creating help button")
                    self.ui.create_help_button()
            print("=== Video Sequence Complete ===\n")

        def play_game_video():
            """Helper to play game video if it exists"""
            print("\n=== Starting Game Video Sequence ===")
            print(f"Game video path: {game_video}")
            if game_video and game_video.exists():
                print(f"Starting playback of game video: {game_video}")
                print("Setting up completion callback to finish_video_sequence")
                self.video_manager.play_video(str(game_video), on_complete=finish_video_sequence)
            else:
                print("No valid game video found, proceeding to finish sequence")
                print(f"Game video exists? {game_video.exists() if game_video else False}")
                finish_video_sequence()
            print("=== Game Video Sequence Initiated ===\n")

        # Play video based on type
        if video_type != 'game':
            print("\n=== Starting Intro Video Sequence ===")
            if video_file.exists():
                print(f"Found intro video at: {video_file}")
                print("Setting up completion callback to play_game_video")
                self.video_manager.play_video(str(video_file), on_complete=play_game_video)
            else:
                print(f"Intro video not found at: {video_file}")
                print("Skipping to game video")
                play_game_video()  # Skip to game video if intro doesn't exist
        else:
            print("\n=== Skipping Intro, Playing Game Video ===")
            play_game_video()
        
    def on_closing(self):
        print("Shutting down kiosk...")
        if self.current_video_process:
            self.current_video_process.terminate()
        self.network.shutdown()
        self.video_server.stop()
        self.audio_server.stop()
        self.root.destroy()
        sys.exit(0)

    def clear_hints(self):
        """Clear all visible hints without resetting other kiosk state"""
        print("\nClearing visible hints...")
        
        # Reset UI hint-related state
        self.ui.hint_cooldown = False
        self.ui.current_hint = None
        self.ui.stored_image_data = None
        
        # Cancel any existing cooldown timer
        if self.ui.cooldown_after_id:
            self.root.after_cancel(self.ui.cooldown_after_id)
            self.ui.cooldown_after_id = None
        
        # Clear UI elements related to hints
        self.ui.clear_all_labels()
        
        # Clear specific hint-related elements
        if hasattr(self.ui, 'image_button') and self.ui.image_button:
            self.ui.image_button.destroy()
            self.ui.image_button = None
        if hasattr(self.ui, 'video_solution_button') and self.ui.video_solution_button:
            self.ui.video_solution_button.destroy()
            self.ui.video_solution_button = None
        if hasattr(self.ui, 'fullscreen_image') and self.ui.fullscreen_image:
            self.ui.fullscreen_image.destroy()
            self.ui.fullscreen_image = None
        
        # Clear any pending request status
        if self.ui.status_frame:
            self.ui.status_frame.delete('all')
            self.ui.hide_status_frame()
            
        # Update help button state
        self.root.after(100, self.update_help_button_state)
        
        print("Hint clearing complete")

    def run(self):
        self.root.mainloop()

if __name__ == '__main__':
    app = KioskApp()
    app.run()