import tkinter as tk
from tkinter import ttk, filedialog
import time
from video_client import VideoClient
from audio_client import AudioClient
from classic_audio_hints import ClassicAudioHints
from setup_stats_panel import setup_stats_panel
import cv2 # type: ignore
from PIL import Image, ImageTk
from pathlib import Path
import threading
import os
import json
import io
import base64


class AdminInterfaceBuilder:
    def __init__(self, app):
        self.app = app
        self.connected_kiosks = {}
        self.selected_kiosk = None
        self.stats_elements = {
            'time_label': None,
            'hints_label': None,
            'msg_entry': None,
            'send_btn': None,
            'camera_btn': None
        }
        self.video_client = VideoClient()
        self.audio_client = AudioClient()  # Initialize audio client
        self.setup_ui()
        
        # Start timer update loop using app's root
        self.app.root.after(1000, self.update_timer_display)

    ROOM_COLORS = {
        4: "#006400",  # Zombie - dark green
        2: "#FF1493",  # Morning After - dark pink 
        1: "#8B0000",  # Casino - dark red
        6: "#377d94",  # Atlantis - light blue
        7: "#FF8C00",  # Time Machine - orange
        3: "#9240a8",  # Wizard - dark teal
        5: "#808080",  # Haunted - grey
    }
        
    def setup_ui(self):
        # Create left panel that spans full height
        self.left_panel = tk.Frame(
            self.app.root,
            bg='SystemButtonFace',  # Use system default background color
            width=220  # Fixed width for left panel
        )
        self.left_panel.pack(
            side='left',     # Place on left side
            fill='y',        # Fill vertical space
            expand=False,    # Don't expand horizontally
            padx=5,          # Add padding from window edge
            pady=5           # Add padding from top/bottom
        )
        
        # Prevent the panel from shrinking below requested width
        self.left_panel.pack_propagate(False)
        
        # Create main container for existing content (kiosks and stats)
        self.main_container = tk.Frame(self.app.root)
        self.main_container.pack(
            side='left',      # Place to right of left panel
            fill='both',      # Fill remaining space
            expand=True,      # Expand to fill space
            padx=10,
            pady=5
        )
        
        # Create existing frames within main container
        left_frame = tk.Frame(self.main_container)
        left_frame.pack(side='left', fill='both', expand=True, padx=5)
        
        self.kiosk_frame = tk.LabelFrame(left_frame, text="Online Kiosk Computers", padx=10, pady=5)
        self.kiosk_frame.pack(fill='both', expand=True)
        
        self.stats_frame = tk.LabelFrame(left_frame, text="No Room Selected", padx=10, pady=5)
        self.stats_frame.pack(fill='both', expand=True, pady=10)

    def setup_audio_hints(self):
        """Set up the Classic Audio Hints panel"""
        print("\n=== AUDIO HINTS SETUP START ===")
        
        def on_room_change(room_name):
            print(f"\n=== ROOM CHANGE CALLBACK ===")
            print(f"Audio hints room change called for: {room_name}")
            print(f"Selected kiosk: {self.selected_kiosk}")
            print(f"Has assignments: {self.selected_kiosk in self.app.kiosk_tracker.kiosk_assignments}")
            
            if self.selected_kiosk and self.selected_kiosk in self.app.kiosk_tracker.kiosk_assignments:
                room_num = self.app.kiosk_tracker.kiosk_assignments[self.selected_kiosk]
                print(f"Room number: {room_num}")
                room_dirs = {
                    6: "atlantis",
                    1: "casino",
                    5: "haunted",
                    2: "MA",
                    7: "time",
                    3: "wizard",
                    4: "zombie"
                }
                if room_num in room_dirs:
                    print(f"Mapped to directory: {room_dirs[room_num]}")
                    self.audio_hints.update_room(room_dirs[room_num])
            print("=== ROOM CHANGE CALLBACK END ===\n")
        
        # Create ClassicAudioHints instance
        print("Creating new ClassicAudioHints instance...")
        self.audio_hints = ClassicAudioHints(self.stats_frame, on_room_change)
        print("=== AUDIO HINTS SETUP END ===\n")

    def setup_stats_panel(self, computer_name):
        # use helper function setup_stats_panel.py
        setup_stats_panel(self, computer_name)

    def select_image(self):
        """Handle image selection for hints"""
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            try:
                # Open and resize image for preview
                image = Image.open(file_path)
                
                # Calculate resize dimensions (max 200px width/height)
                ratio = min(200/image.width, 200/image.height)
                new_size = (int(image.width * ratio), int(image.height * ratio))
                
                # Resize image and convert to PhotoImage
                image = image.resize(new_size, Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(image)
                
                # Update preview
                self.stats_elements['image_preview'].configure(image=photo)
                self.stats_elements['image_preview'].image = photo
                
                # Store original image data
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                self.current_hint_image = base64.b64encode(buffer.getvalue()).decode()
                
                # Enable send button even if no text
                if self.stats_elements['send_btn']:
                    self.stats_elements['send_btn'].config(state='normal')
                    
            except Exception as e:
                print(f"Error loading image: {e}")
                self.current_hint_image = None

    def reset_kiosk(self, computer_name):
        """Reset all kiosk stats and state"""
        if computer_name not in self.app.kiosk_tracker.kiosk_stats:
            return
            
        # Reset hints count locally
        self.app.kiosk_tracker.kiosk_stats[computer_name]['total_hints'] = 0
        
        # Reset and stop timer
        self.app.network_handler.send_timer_command(computer_name, "set", 45)
        self.app.network_handler.send_timer_command(computer_name, "stop")
        
        # Clear any pending help requests
        if computer_name in self.app.kiosk_tracker.help_requested:
            self.app.kiosk_tracker.help_requested.remove(computer_name)
            if computer_name in self.connected_kiosks:
                self.connected_kiosks[computer_name]['help_label'].config(text="")
        
        # Send reset message through network handler
        self.app.network_handler.socket.sendto(
            json.dumps({
                'type': 'reset_kiosk',
                'computer_name': computer_name
            }).encode(),
            ('255.255.255.255', 12346)
        )
        
        # Force immediate UI update
        self.update_stats_display(computer_name)

    def play_video(self, computer_name):
        video_type = self.stats_elements['video_type'].get().lower().split()[0]
        # Get time from timer entry, default to 45 if empty or invalid
        try:
            minutes = int(self.stats_elements['time_entry'].get())
        except (ValueError, AttributeError):
            minutes = 45
            
        self.app.network_handler.send_video_command(computer_name, video_type, minutes)

    def toggle_timer(self, computer_name):
        if 'timer_button' not in self.stats_elements:
            return
            
        timer_button = self.stats_elements['timer_button']
        is_running = timer_button.cget('text') == "Stop Room"
        
        # Switch icons before sending command
        if hasattr(timer_button, 'play_icon') and hasattr(timer_button, 'stop_icon'):
            if is_running:
                timer_button.config(
                    image=timer_button.play_icon,
                    text="Start Room"
                )
            else:
                timer_button.config(
                    image=timer_button.stop_icon,
                    text="Stop Room"
                )
        else:
            # Fallback to text-only if icons aren't available
            timer_button.config(text="Start Room" if is_running else "Stop Room")
        
        command = "stop" if is_running else "start"
        self.app.network_handler.send_timer_command(computer_name, command)

    def set_timer(self, computer_name):
        try:
            minutes = int(self.stats_elements['time_entry'].get())
            if 0 <= minutes <= 99:  # Validate input range
                self.app.network_handler.send_timer_command(computer_name, "set", minutes)
        except ValueError:
            pass  # Invalid input handling

    def add_timer_time(self, computer_name):
        """Add specified minutes to current timer without affecting running state"""
        try:
            minutes_to_add = int(self.stats_elements['time_entry'].get())
            if 0 <= minutes_to_add <= 99:  # Validate input range
                # Get current time from stats
                if computer_name in self.app.kiosk_tracker.kiosk_stats:
                    stats = self.app.kiosk_tracker.kiosk_stats[computer_name]
                    current_seconds = stats.get('timer_time', 0)
                    # Add new time in seconds (convert minutes to seconds)
                    new_seconds = current_seconds + (minutes_to_add * 60)
                    # Convert total seconds back to minutes for the command
                    new_minutes = new_seconds / 60
                    # Send set command with new total time, keeping decimal precision
                    self.app.network_handler.send_timer_command(computer_name, "set", new_minutes)
        except ValueError:
            pass  # Invalid input handling

    def update_timer_display(self):
        if self.selected_kiosk and self.selected_kiosk in self.app.kiosk_tracker.kiosk_stats:
            stats = self.app.kiosk_tracker.kiosk_stats[self.selected_kiosk]
            timer_time = stats.get('timer_time', 2700)
            timer_minutes = int(timer_time // 60)
            timer_seconds = int(timer_time % 60)
            if 'current_time' in self.stats_elements and self.stats_elements['current_time']:
                self.stats_elements['current_time'].config(
                    text=f"{timer_minutes:02d}:{timer_seconds:02d}"
                )
        
        self.app.root.after(1000, self.update_timer_display)

    def toggle_camera(self, computer_name):
        """Toggle camera feed from kiosk"""
        if getattr(self, 'camera_active', False):
            # Stop camera
            self.video_client.disconnect()
            self.camera_active = False
            if hasattr(self.stats_elements['camera_btn'], 'camera_icon'):
                self.stats_elements['camera_btn'].config(
                    image=self.stats_elements['camera_btn'].camera_icon,
                    text="Start Camera"
                )
            else:
                self.stats_elements['camera_btn'].config(text="Start Camera")
            if 'video_label' in self.stats_elements:
                self.stats_elements['video_label'].config(image='')
        else:
            # Start camera
            self.stats_elements['camera_btn'].config(text="Connecting...")
            
            def connect():
                if self.video_client.connect(computer_name):
                    self.camera_active = True
                    if hasattr(self.stats_elements['camera_btn'], 'stop_camera_icon'):
                        self.stats_elements['camera_btn'].config(
                            image=self.stats_elements['camera_btn'].stop_camera_icon,
                            text="Stop Camera"
                        )
                    else:
                        self.stats_elements['camera_btn'].config(text="Stop Camera")
                    self.update_video_feed()
                else:
                    if hasattr(self.stats_elements['camera_btn'], 'camera_icon'):
                        self.stats_elements['camera_btn'].config(
                            image=self.stats_elements['camera_btn'].camera_icon,
                            text="Start Camera"
                        )
                    else:
                        self.stats_elements['camera_btn'].config(text="Start Camera")
                    if 'video_label' in self.stats_elements:
                        self.stats_elements['video_label'].config(
                            text="Camera connection failed",
                            fg='red'
                        )
            
            threading.Thread(target=connect, daemon=True).start()

    def update_video_feed(self):
        if getattr(self, 'camera_active', False) and 'video_label' in self.stats_elements:
            try:
                frame = self.video_client.get_frame()
                if frame is not None:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame = cv2.resize(frame, (500, 375))
                    img = Image.fromarray(frame)
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.stats_elements['video_label'].imgtk = imgtk
                    self.stats_elements['video_label'].config(image=imgtk)
            except Exception as e:
                print(f"Error updating video feed: {e}")
                
        if self.camera_active:
            self.app.root.after(30, self.update_video_feed)

    def remove_kiosk(self, computer_name):
        # Stop camera if it was active for this kiosk
        if getattr(self, 'camera_active', False) and \
           self.stats_elements.get('current_computer') == computer_name:
            self.toggle_camera(computer_name)
        
        # Rest of your existing remove_kiosk code...
        if computer_name in self.connected_kiosks:
            self.connected_kiosks[computer_name]['frame'].destroy()
            del self.connected_kiosks[computer_name]
            
            if computer_name in self.app.kiosk_tracker.kiosk_assignments:
                del self.app.kiosk_tracker.kiosk_assignments[computer_name]
            if computer_name in self.app.kiosk_tracker.kiosk_stats:
                del self.app.kiosk_tracker.kiosk_stats[computer_name]
            if computer_name in self.app.kiosk_tracker.assigned_rooms:
                del self.app.kiosk_tracker.assigned_rooms[computer_name]
            if computer_name in self.app.kiosk_tracker.help_requested:
                self.app.kiosk_tracker.help_requested.remove(computer_name)
            
            if self.selected_kiosk == computer_name:
                self.selected_kiosk = None
                self.stats_frame.configure(text="No Room Selected")
                for widget in self.stats_frame.winfo_children():
                    widget.destroy()
                self.stats_elements = {key: None for key in self.stats_elements}

    def update_stats_timer(self):
        if self.selected_kiosk and self.selected_kiosk in self.app.kiosk_tracker.kiosk_stats:
            self.update_stats_display(self.selected_kiosk)
        self.app.root.after(1000, self.update_stats_timer)

    def add_kiosk_to_ui(self, computer_name):
        """Add or update a kiosk in the UI with room-specific colors"""
        current_time = time.time()
        
        if computer_name in self.connected_kiosks:
            self.connected_kiosks[computer_name]['last_seen'] = current_time
            return
            
        frame = tk.Frame(self.kiosk_frame)
        frame.pack(fill='x', pady=2)
        
        if computer_name in self.app.kiosk_tracker.kiosk_assignments:
            room_num = self.app.kiosk_tracker.kiosk_assignments[computer_name]
            room_name = self.app.rooms[room_num]
            
            # Get room color from mapping, default to black if not found
            room_color = self.ROOM_COLORS.get(room_num, "black")
            
            name_label = tk.Label(frame, 
                text=room_name,
                font=('Arial', 12, 'bold'),
                fg=room_color)  # Apply room-specific color
            name_label.pack(side='left', padx=5)
            #computer_label = tk.Label(frame,
                #text=f"({computer_name})",
                #font=('Arial', 12, 'italic'))
            #computer_label.pack(side='left')
        else:
            name_label = tk.Label(frame, 
                text="Unassigned",
                font=('Arial', 12, 'bold'))
            name_label.pack(side='left', padx=5)
            #computer_label = tk.Label(frame,
                #text=f"({computer_name})",
                #font=('Arial', 12, 'italic'))
            #computer_label.pack(side='left')
        
        def click_handler(cn=computer_name):
            self.select_kiosk(cn)
        
        frame.bind('<Button-1>', lambda e: click_handler())
        name_label.bind('<Button-1>', lambda e: click_handler())
        #computer_label.bind('<Button-1>', lambda e: click_handler())
        
        room_var = tk.StringVar()
        dropdown = ttk.Combobox(frame, textvariable=room_var, 
            values=list(self.app.rooms.values()), state='readonly')
        dropdown.pack(side='left', padx=5)
        
        # Add handler for dropdown selection
        def on_room_select(event):
            if not room_var.get():
                return
            selected_room = next(num for num, name in self.app.rooms.items() 
                            if name == room_var.get())
            self.app.kiosk_tracker.assign_kiosk_to_room(computer_name, selected_room)
            dropdown.set('')
            name_label.config(
                text=self.app.rooms[selected_room],
                fg=self.ROOM_COLORS.get(selected_room, "black")  # Update color on assignment
            )
        
        # Bind the handler to the dropdown selection event
        dropdown.bind('<<ComboboxSelected>>', on_room_select)
        
        help_label = tk.Label(frame, text="", font=('Arial', 14, 'bold'), fg='red')
        help_label.pack(side='left', padx=5)
        
        # Add reboot button with padding to prevent accidental clicks
        reboot_btn = tk.Button(
            frame, 
            text="Reboot Kiosk",
            command=lambda: self.app.network_handler.send_reboot_signal(computer_name),
            bg='#FF6B6B',  # Light red background
            fg='white'
        )
        reboot_btn.pack(side='left', padx=(20, 5))  # Extra left padding
        
        self.connected_kiosks[computer_name] = {
            'frame': frame,
            'help_label': help_label,
            'dropdown': dropdown,
            'reboot_btn': reboot_btn,
            'last_seen': current_time,
            'name_label': name_label,
            #'computer_label': computer_label  # Restored computer_label reference
        }
        
        if computer_name == self.selected_kiosk:
            self.select_kiosk(computer_name)

    def update_kiosk_display(self, computer_name):
        """Update kiosk display including room-specific colors"""
        if computer_name in self.connected_kiosks:
            if computer_name in self.app.kiosk_tracker.kiosk_assignments:
                room_num = self.app.kiosk_tracker.kiosk_assignments[computer_name]
                self.connected_kiosks[computer_name]['name_label'].config(
                    text=self.app.rooms[room_num],
                    fg=self.ROOM_COLORS.get(room_num, "black")  # Apply room color
                )
                
                if computer_name == self.selected_kiosk:
                    self.stats_frame.configure(
                        text=f"{self.app.rooms[room_num]} ({computer_name})"
                    )
                    if self.stats_elements['send_btn']:
                        self.stats_elements['send_btn'].config(state='normal')

    def mark_help_requested(self, computer_name):
        if computer_name in self.connected_kiosks:
            self.connected_kiosks[computer_name]['help_label'].config(
                text="HINT REQUESTED",
                fg='red',
                font=('Arial', 14, 'bold')
            )

    def remove_kiosk(self, computer_name):
        if computer_name in self.connected_kiosks:
            self.connected_kiosks[computer_name]['frame'].destroy()
            del self.connected_kiosks[computer_name]
            
            if computer_name in self.app.kiosk_tracker.kiosk_assignments:
                del self.app.kiosk_tracker.kiosk_assignments[computer_name]
            if computer_name in self.app.kiosk_tracker.kiosk_stats:
                del self.app.kiosk_tracker.kiosk_stats[computer_name]
            if computer_name in self.app.kiosk_tracker.assigned_rooms:
                del self.app.kiosk_tracker.assigned_rooms[computer_name]
            if computer_name in self.app.kiosk_tracker.help_requested:
                self.app.kiosk_tracker.help_requested.remove(computer_name)
            
            if self.selected_kiosk == computer_name:
                self.selected_kiosk = None
                self.stats_frame.configure(text="No Room Selected")
                for widget in self.stats_frame.winfo_children():
                    widget.destroy()
                self.stats_elements = {key: None for key in self.stats_elements}

    def select_kiosk(self, computer_name):
        """Handle selection of a kiosk and setup of its interface"""
        try:
            print(f"\n=== KIOSK SELECTION START: {computer_name} ===")
            
            # Clean up existing audio/video streams before switching
            if hasattr(self, 'camera_active') and self.camera_active:
                self.video_client.disconnect()
                self.camera_active = False
                if 'camera_btn' in self.stats_elements:
                    self.stats_elements['camera_btn'].config(text="Start Camera")
                if 'video_label' in self.stats_elements:
                    self.stats_elements['video_label'].config(image='')
                    
            if hasattr(self, 'audio_active') and self.audio_active:
                if hasattr(self, 'speaking') and self.speaking:
                    self.audio_client.stop_speaking()
                    self.speaking = False
                    if 'speak_btn' in self.stats_elements:
                        self.stats_elements['speak_btn'].config(text="Enable Microphone")
                self.audio_client.disconnect()
                self.audio_active = False
                if 'listen_btn' in self.stats_elements:
                    self.stats_elements['listen_btn'].config(text="Start Listening")
                if 'speak_btn' in self.stats_elements:
                    self.stats_elements['speak_btn'].config(state='disabled')
            
            # Setup stats panel and audio hints first
            self.setup_stats_panel(computer_name)
            
            self.selected_kiosk = computer_name
            
            if computer_name in self.app.kiosk_tracker.kiosk_assignments:
                room_num = self.app.kiosk_tracker.kiosk_assignments[computer_name]
                room_name = self.app.rooms[room_num]
                title = f"{room_name} ({computer_name})"
                print(f"Room assigned: {room_name} (#{room_num})")
                
                # Get room color from mapping, default to black if not found
                room_color = self.ROOM_COLORS.get(room_num, "black")
                
                # Configure title with room-specific color
                self.stats_frame.configure(
                    text=title,
                    font=('Arial', 10, 'bold'),
                    fg=room_color  # Add color to match room color scheme
                )
                
                # Map room number to directory name for audio hints
                print("\n=== AUDIO HINTS UPDATE START ===")
                room_dirs = {
                    6: "atlantis",
                    1: "casino",
                    5: "haunted",
                    2: "MA",
                    7: "time",
                    3: "wizard",
                    4: "zombie"
                }
                
                print(f"Current working directory: {os.getcwd()}")
                if room_num in room_dirs:
                    room_dir = room_dirs[room_num]
                    print(f"Selected room directory: {room_dir}")
                    audio_path = os.path.join("audio_hints", room_dir)
                    print(f"Audio path relative to working dir: {audio_path}")
                    print(f"Full audio path: {os.path.abspath(audio_path)}")
                    print(f"Path exists: {os.path.exists(audio_path)}")
                    if os.path.exists(audio_path):
                        print(f"Directory contents: {os.listdir(audio_path)}")
                    
                    if hasattr(self, 'audio_hints'):
                        print("Audio hints object exists, updating room")
                        self.audio_hints.update_room(room_dir)
                    else:
                        print("WARNING: No audio_hints object found!")
                print("=== AUDIO HINTS UPDATE END ===\n")
            else:
                title = f"Unassigned ({computer_name})"
                print("No room assigned")
                self.stats_frame.configure(
                    text=title,
                    font=('Arial', 10, 'bold'),
                    fg='black'  # Default color for unassigned
                )
            
            if hasattr(self, 'saved_hints'):
                print("Updating saved hints for room")
                if room_num:
                    self.saved_hints.update_room(room_num)
                else:
                    self.saved_hints.clear_preview()
            
            
            # Update highlighting
            for cn, data in self.connected_kiosks.items():
                if cn == computer_name:
                    data['frame'].configure(bg='lightblue')
                    for widget in data['frame'].winfo_children():
                        if isinstance(widget, tk.Button):
                            if widget == data['reboot_btn']:
                                widget.configure(bg='#FF6B6B', fg='white')  # Keep reboot button red
                            elif widget == data['assign_btn']:
                                widget.configure(bg='#90EE90', fg='black')  # Light green for assign button
                        elif not isinstance(widget, ttk.Combobox):
                            widget.configure(bg='lightblue')
                else:
                    data['frame'].configure(bg='SystemButtonFace')
                    for widget in data['frame'].winfo_children():
                        if isinstance(widget, tk.Button):
                            if widget == data['reboot_btn']:
                                widget.configure(bg='#FF6B6B', fg='white')  # Keep reboot button red
                            elif widget == data['assign_btn']:
                                widget.configure(bg='#90EE90', fg='black')  # Light green for assign button
                        elif not isinstance(widget, ttk.Combobox):
                            widget.configure(bg='SystemButtonFace')
            
            self.update_stats_display(computer_name)
            
            # Notify PropControl about room change (with safety check)
            if hasattr(self.app, 'prop_control') and self.app.prop_control:
                if computer_name in self.app.kiosk_tracker.kiosk_assignments:
                    room_num = self.app.kiosk_tracker.kiosk_assignments[computer_name]
                    print(f"Notifying prop control about room change to {room_num}")
                    self.app.root.after(100, lambda: self.app.prop_control.connect_to_room(room_num))
                else:
                    print("No room assignment, skipping prop control notification")
                    
            print(f"=== KIOSK SELECTION END: {computer_name} ===\n")
            
        except Exception as e:
            print(f"Error in select_kiosk: {e}")
            
    def update_stats_display(self, computer_name):
        try:
            if computer_name not in self.app.kiosk_tracker.kiosk_stats:
                return
                
            stats = self.app.kiosk_tracker.kiosk_stats[computer_name]
            
            # Only proceed if we have valid UI elements
            if not self.stats_elements:
                print("Stats elements not initialized yet")
                return
                
            # Update hints label if it exists
            if self.stats_elements.get('hints_label'):
                total_hints = stats.get('total_hints', 0)
                self.stats_elements['hints_label'].config(
                    text=f"Hints requested: {total_hints}"
                )
            
            # Update timer display
            timer_time = stats.get('timer_time', 3600)
            timer_minutes = int(timer_time // 60)
            timer_seconds = int(timer_time % 60)
            if self.stats_elements.get('current_time'):
                self.stats_elements['current_time'].config(
                    text=f"{timer_minutes:02d}:{timer_seconds:02d}"
                )
            
            # Update timer button state and icon
            timer_button = self.stats_elements.get('timer_button')
            if timer_button and timer_button.winfo_exists():
                is_running = stats.get('timer_running', False)
                
                if hasattr(timer_button, 'stop_icon') and hasattr(timer_button, 'play_icon'):
                    try:
                        # Update icon based on current timer state
                        if is_running and timer_button.cget('text') != "Stop Room":
                            timer_button.config(
                                image=timer_button.stop_icon,
                                text="Stop Room"
                            )
                        elif not is_running and timer_button.cget('text') != "Start Room":
                            timer_button.config(
                                image=timer_button.play_icon,
                                text="Start Room"
                            )
                    except tk.TclError:
                        print("Timer button was destroyed")
                        return
                else:
                    try:
                        # Fallback to text-only if icons aren't available
                        if is_running and timer_button.cget('text') != "Stop Room":
                            timer_button.config(text="Stop Room")
                        elif not is_running and timer_button.cget('text') != "Start Room":
                            timer_button.config(text="Start Room")
                    except tk.TclError:
                        print("Timer button was destroyed")
                        return
            
            if computer_name in self.app.kiosk_tracker.kiosk_assignments:
                if self.stats_elements.get('send_btn'):
                    self.stats_elements['send_btn'].config(state='normal')
            else:
                if self.stats_elements.get('send_btn'):
                    self.stats_elements['send_btn'].config(state='disabled')
        except Exception as e:
            print(f"Error updating stats display: {e}")

    def send_hint(self, computer_name, hint_data=None):
        """
        Send a hint to the selected kiosk.
        
        Args:
            computer_name: Name of the target computer
            hint_data: Optional dict containing hint data. If None, uses manual entry fields.
        """
        # Validate kiosk assignment
        if not computer_name in self.app.kiosk_tracker.kiosk_assignments:
            return
                
        if hint_data is None:
            # Using manual entry
            message_text = self.stats_elements['msg_entry'].get('1.0', 'end-1c') if self.stats_elements['msg_entry'] else ""
            if not message_text and not self.current_hint_image:
                return
                
            hint_data = {
                'text': message_text,
                'image': self.current_hint_image
            }
        
        # Get room number
        room_number = self.app.kiosk_tracker.kiosk_assignments[computer_name]
        
        # Send the hint
        self.app.network_handler.send_hint(room_number, hint_data)
        
        # Clear any pending help requests
        if computer_name in self.app.kiosk_tracker.help_requested:
            self.app.kiosk_tracker.help_requested.remove(computer_name)
            if computer_name in self.connected_kiosks:
                self.connected_kiosks[computer_name]['help_label'].config(text="")
        
        # Clear ALL hint entry fields regardless of which method was used
        if self.stats_elements['msg_entry']:
            self.stats_elements['msg_entry'].delete('1.0', 'end')
        
        if self.stats_elements['image_preview']:
            self.stats_elements['image_preview'].configure(image='')
            self.stats_elements['image_preview'].image = None
        self.current_hint_image = None
        
        if self.stats_elements['send_btn']:
            self.stats_elements['send_btn'].config(state='disabled')
            
        # Also clear saved hints preview if it exists
        if hasattr(self, 'saved_hints'):
            self.saved_hints.clear_preview()

    def save_manual_hint(self):
        """Save the current manual hint to saved_hints.json"""
        if not hasattr(self, 'selected_kiosk') or not self.selected_kiosk:
            return
            
        if self.selected_kiosk not in self.app.kiosk_tracker.kiosk_assignments:
            return
            
        # Get hint text
        message_text = self.stats_elements['msg_entry'].get('1.0', 'end-1c') if self.stats_elements['msg_entry'] else ""
        if not message_text and not self.current_hint_image:
            return
            
        # Get room number
        room_number = self.app.kiosk_tracker.kiosk_assignments[self.selected_kiosk]
        room_str = str(room_number)
        
        # Show dialog to get prop name and hint name
        dialog = tk.Toplevel(self.app.root)
        dialog.title("Save Hint")
        dialog.transient(self.app.root)
        dialog.grab_set()
        
        # Center dialog
        dialog_width = 300
        dialog_height = 150
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        
        # Map room number to config key
        room_map = {
            3: "wizard",
            1: "casino_ma",
            2: "casino_ma",
            5: "haunted",
            4: "zombie",
            6: "atlantis",
            7: "time_machine"
        }
        room_key = room_map.get(room_number)
        
        # Load available props for this room from mapping file
        try:
            with open("prop_name_mapping.json", 'r') as f:
                prop_mappings = json.load(f)
                
            # Get props for this room and sort by order
            room_props = prop_mappings.get(room_key, {}).get('mappings', {})
            props_with_order = [(prop, info.get('display', prop) or prop, info.get('order', 999))
                            for prop, info in room_props.items()]
            sorted_props = sorted(props_with_order, key=lambda x: (x[2], x[1]))
            available_props = [(display, internal) for internal, display, _ in sorted_props]
        except Exception as e:
            print(f"Error loading prop mappings: {e}")
            available_props = []
        
        if not available_props:
            tk.messagebox.showerror("Error", "No props available for this room")
            dialog.destroy()
            return
        
        # Add form fields with dropdown for props
        tk.Label(dialog, text="Select Prop:").pack(pady=(10,0))
        prop_var = tk.StringVar(dialog)
        prop_dropdown = ttk.Combobox(dialog, 
            textvariable=prop_var,
            values=[display for display, _ in available_props],
            state='readonly',
            width=30
        )
        prop_dropdown.pack(pady=(0,10))
        
        tk.Label(dialog, text="Hint Name:").pack()
        hint_entry = tk.Entry(dialog, width=35)
        hint_entry.pack(pady=(0,10))
        
        def save_hint():
            display_name = prop_var.get()
            # Find internal prop name from selection
            prop_name = next((internal for disp, internal in available_props if disp == display_name), None)
            hint_name = hint_entry.get().strip()
            
            if not prop_name or not hint_name:
                return
                
            # Load existing hints
            hints_file = Path("saved_hints.json")
            try:
                if hints_file.exists() and hints_file.stat().st_size > 0:
                    with open(hints_file, 'r') as f:
                        try:
                            data = json.load(f)
                        except json.JSONDecodeError:
                            # If JSON is invalid, start fresh
                            data = {"rooms": {}}
                else:
                    # If file doesn't exist or is empty, start fresh
                    data = {"rooms": {}}
            except Exception as e:
                print(f"Error loading hints file: {e}")
                data = {"rooms": {}}
            
            # Ensure room structure exists
            if 'rooms' not in data:
                data['rooms'] = {}
            if room_str not in data['rooms']:
                data['rooms'][room_str] = {"hints": {}}
            elif 'hints' not in data['rooms'][room_str]:
                data['rooms'][room_str]['hints'] = {}
                
            # Generate unique ID for hint
            base_id = f"{prop_name.lower().replace(' ', '_')}_hint"
            hint_id = base_id
            counter = 1
            while hint_id in data['rooms'][room_str]['hints']:
                hint_id = f"{base_id}_{counter}"
                counter += 1
                
            # Save image if present
            image_filename = None
            if self.current_hint_image:
                # Create directory if needed
                Path("saved_hint_images").mkdir(exist_ok=True)
                
                # Generate image filename
                image_filename = f"{hint_id}.png"
                image_path = Path("saved_hint_images") / image_filename
                
                # Save image
                image_data = base64.b64decode(self.current_hint_image)
                with open(image_path, 'wb') as f:
                    f.write(image_data)
                    
            # Add hint to data
            data['rooms'][room_str]['hints'][hint_id] = {
                "prop": prop_name,  # Save internal prop name
                "name": hint_name,
                "text": message_text,
                "image": image_filename
            }
            
            # Save updated hints file
            try:
                with open(hints_file, 'w') as f:
                    json.dump(data, f, indent=4)
            except Exception as e:
                print(f"Error saving hints file: {e}")
                tk.messagebox.showerror("Error", "Failed to save hint")
                return
                
            # Close dialog and clear form
            dialog.destroy()
            self.clear_manual_hint()
            
            # Refresh saved hints panel if it exists
            if hasattr(self, 'saved_hints'):
                self.saved_hints.load_hints()
                self.saved_hints.update_room(room_number)
        
        tk.Button(dialog, text="Save", command=save_hint).pack(pady=10)

    def clear_manual_hint(self):
        """Clear the manual hint entry fields"""
        if self.stats_elements['msg_entry']:
            self.stats_elements['msg_entry'].delete('1.0', 'end')
        
        if self.stats_elements['image_preview']:
            self.stats_elements['image_preview'].configure(image='')
            self.stats_elements['image_preview'].image = None
        self.current_hint_image = None
        
        if self.stats_elements['send_btn']:
            self.stats_elements['send_btn'].config(state='disabled')

    def toggle_audio(self, computer_name):
        """Toggle audio listening from kiosk"""
        if not hasattr(self, 'audio_client'):
            self.audio_client = AudioClient()
            
        if getattr(self, 'audio_active', False):
            try:
                # Stop audio
                self.audio_client.disconnect()
                self.audio_active = False
                if hasattr(self.stats_elements['listen_btn'], 'listen_icon'):
                    self.stats_elements['listen_btn'].config(
                        image=self.stats_elements['listen_btn'].listen_icon,
                        text="Start Listening"
                    )
                else:
                    self.stats_elements['listen_btn'].config(text="Start Listening")
                self.stats_elements['speak_btn'].config(state='disabled')
            except Exception as e:
                print(f"Error stopping audio: {e}")
        else:
            # Start audio
            self.stats_elements['listen_btn'].config(text="Connecting...")
            
            def connect():
                try:
                    if self.audio_client.connect(computer_name):
                        self.audio_active = True
                        if hasattr(self.stats_elements['listen_btn'], 'stop_listening_icon'):
                            self.stats_elements['listen_btn'].config(
                                image=self.stats_elements['listen_btn'].stop_listening_icon,
                                text="Stop Listening"
                            )
                        else:
                            self.stats_elements['listen_btn'].config(text="Stop Listening")
                        self.stats_elements['speak_btn'].config(state='normal')
                    else:
                        if hasattr(self.stats_elements['listen_btn'], 'listen_icon'):
                            self.stats_elements['listen_btn'].config(
                                image=self.stats_elements['listen_btn'].listen_icon,
                                text="Start Listening"
                            )
                        else:
                            self.stats_elements['listen_btn'].config(text="Start Listening")
                        self.stats_elements['speak_btn'].config(state='disabled')
                except Exception as e:
                    print(f"Error connecting audio: {e}")
                    if hasattr(self.stats_elements['listen_btn'], 'listen_icon'):
                        self.stats_elements['listen_btn'].config(
                            image=self.stats_elements['listen_btn'].listen_icon,
                            text="Start Listening"
                        )
                    else:
                        self.stats_elements['listen_btn'].config(text="Start Listening")
                    self.stats_elements['speak_btn'].config(state='disabled')
            
            threading.Thread(target=connect, daemon=True).start()

    def toggle_speaking(self, computer_name):
        """Toggle microphone for speaking to kiosk"""
        if not self.audio_active:
            return
            
        if getattr(self, 'speaking', False):
            try:
                # Stop speaking
                self.audio_client.stop_speaking()
                self.speaking = False
                # Reset background color of the entire interface
                self.app.root.configure(bg='systemButtonFace')
                for frame in [self.main_container, self.kiosk_frame, self.stats_frame]:
                    frame.configure(bg='systemButtonFace')
                # Reset button appearance
                if hasattr(self.stats_elements['speak_btn'], 'enable_mic_icon'):
                    self.stats_elements['speak_btn'].config(
                        image=self.stats_elements['speak_btn'].enable_mic_icon,
                        text="Enable Microphone",
                        bg='systemButtonFace',
                        activebackground='systemButtonFace'
                    )
                else:
                    self.stats_elements['speak_btn'].config(
                        text="Enable Microphone",
                        bg='systemButtonFace',
                        activebackground='systemButtonFace'
                    )
            except Exception as e:
                print(f"Error stopping microphone: {e}")
        else:
            # Start speaking
            try:
                if self.audio_client.start_speaking():
                    self.speaking = True
                    # Set red background for the entire interface
                    self.app.root.configure(bg='#ffcccc')  # Light red
                    for frame in [self.main_container, self.kiosk_frame, self.stats_frame]:
                        frame.configure(bg='#ffcccc')
                    # Update button appearance
                    if hasattr(self.stats_elements['speak_btn'], 'disable_mic_icon'):
                        self.stats_elements['speak_btn'].config(
                            image=self.stats_elements['speak_btn'].disable_mic_icon,
                            text="Disable Microphone",
                            bg='#ffcccc',
                            activebackground='#ffcccc'
                        )
                    else:
                        self.stats_elements['speak_btn'].config(
                            text="Disable Microphone",
                            bg='#ffcccc',
                            activebackground='#ffcccc'
                        )
                else:
                    if hasattr(self.stats_elements['speak_btn'], 'enable_mic_icon'):
                        self.stats_elements['speak_btn'].config(
                            image=self.stats_elements['speak_btn'].enable_mic_icon,
                            text="Enable Microphone"
                        )
                    else:
                        self.stats_elements['speak_btn'].config(text="Enable Microphone")
            except Exception as e:
                print(f"Error enabling microphone: {e}")