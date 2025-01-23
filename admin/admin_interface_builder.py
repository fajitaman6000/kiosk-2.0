import tkinter as tk
from tkinter import ttk, filedialog
import time
from video_client import VideoClient
from audio_client import AudioClient
from classic_audio_hints import ClassicAudioHints
from setup_stats_panel import setup_stats_panel
from hint_functions import save_manual_hint, clear_manual_hint, send_hint
from admin_audio_manager import AdminAudioManager
import cv2 # type: ignore
from PIL import Image, ImageTk
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
        
        # Create frames within main container
        left_frame = tk.Frame(self.main_container)
        left_frame.pack(side='left', fill='both', expand=True, padx=5)
        
        # Create a horizontal container for kiosk frame and hints button
        kiosk_container = tk.Frame(left_frame)
        kiosk_container.pack(fill='both', expand=True)
        
        # Create kiosk frame on the left side of container
        self.kiosk_frame = tk.LabelFrame(kiosk_container, text="Online Kiosk Computers", padx=10, pady=5)
        self.kiosk_frame.pack(side='left', fill='both', expand=True)
        
        # Load all required icons
        icon_dir = os.path.join("admin_icons")
        try:
            settings_icon = Image.open(os.path.join(icon_dir, "settings.png"))
            settings_icon = settings_icon.resize((24, 24), Image.Resampling.LANCZOS)
            settings_icon = ImageTk.PhotoImage(settings_icon)
        except Exception as e:
            print(f"[interface builder]Error loading icons: {e}")
            settings_icon = None

        # Create small frame for hints button on the right side of container
        hints_button_frame = tk.Frame(kiosk_container)
        hints_button_frame.pack(side='left', anchor='n', padx=5)  # Anchor to top
        
        # Add Hints Library button in its own frame - small and square
        hints_library_btn = tk.Button(
            hints_button_frame,
            text="Hint\nManager",
            command=lambda: self.show_hints_library(),
            bg='#C6AE66',
            fg='white',
            font=('Arial', 9),
            width=6,         # Set fixed width in text units
            height=2         # Set fixed height in text units
        )
        hints_library_btn.pack(anchor='n')  # Anchor to top of its frame
        
        # Create stats frame below the kiosk container
        self.stats_frame = tk.LabelFrame(left_frame, text="No Room Selected", padx=10, pady=5)
        self.stats_frame.pack(fill='both', expand=True, pady=10)

    def show_hints_library(self):
        """Show the Hints Library interface"""
        if not hasattr(self, 'hint_manager'):
            from hints_library import HintManager
            self.hint_manager = HintManager(self.app, self)
        self.hint_manager.show_hint_manager()

    def setup_audio_hints(self):
        """Set up the Classic Audio Hints panel"""
        #print("[interface builder]\n=== AUDIO HINTS SETUP START ===")
        
        def on_room_change(room_name):
            print(f"[interface builder]\n=== ROOM CHANGE CALLBACK ===")
            print(f"[interface builder]Audio hints room change called for: {room_name}")
            print(f"[interface builder]Selected kiosk: {self.selected_kiosk}")
            print(f"[interface builder]Has assignments: {self.selected_kiosk in self.app.kiosk_tracker.kiosk_assignments}")
            
            if self.selected_kiosk and self.selected_kiosk in self.app.kiosk_tracker.kiosk_assignments:
                room_num = self.app.kiosk_tracker.kiosk_assignments[self.selected_kiosk]
                print(f"[interface builder]Room number: {room_num}")
                room_dirs = {
                    6: "atlantis",
                    1: "casino",
                    5: "haunted",
                    2: "ma",
                    7: "time",
                    3: "wizard",
                    4: "zombie"
                }
                if room_num in room_dirs:
                    print(f"[interface builder]Mapped to directory: {room_dirs[room_num]}")
                    self.audio_hints.update_room(room_dirs[room_num])
            print("[interface builder]=== ROOM CHANGE CALLBACK END ===\n")
        
        # Create ClassicAudioHints instance
        #print("[interface builder]Creating new ClassicAudioHints instance...")
        self.audio_hints = ClassicAudioHints(self.stats_frame, on_room_change)
        #print("[interface builder]=== AUDIO HINTS SETUP END ===\n")

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
                print(f"[interface builder]Error loading image: {e}")
                self.current_hint_image = None

    def play_hint_sound(self, computer_name, sound_name='hint_received.mp3'):
        """
        Sends a command to play a sound on the specified kiosk
        Uses the app's network handler to broadcast the message
        
        Args:
            computer_name (str): The target kiosk
            sound_name (str): The sound file to play, defaults to hint_received.mp3
        """
        self.app.network_handler.socket.sendto(
            json.dumps({
                'type': 'play_sound',
                'computer_name': computer_name,
                'sound_name': sound_name
            }).encode(),
            ('255.255.255.255', 12346)
        )

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

    def toggle_music(self, computer_name):
        """Sends a command to toggle music playback on the specified kiosk."""
        # Send toggle music command through network handler
        self.app.network_handler.socket.sendto(
            json.dumps({
                'type': 'toggle_music_command',
                'computer_name': computer_name
            }).encode(),
            ('255.255.255.255', 12346)
        )

        # Assume music will be toggled on the kiosk - update icon immediately
        # (The actual state will be confirmed and corrected by the next broadcast message)
        if 'music_button' in self.stats_elements and self.stats_elements['music_button']:
            music_button = self.stats_elements['music_button']
            if hasattr(music_button, 'music_on_icon') and hasattr(music_button, 'music_off_icon'):
                try:
                    if music_button.cget('image') == str(music_button.music_off_icon):
                        music_button.config(
                            image=music_button.music_on_icon
                        )
                    else:
                        music_button.config(
                            image=music_button.music_off_icon
                        )
                except tk.TclError:
                    print("[interface builder]Music button was destroyed")

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

    def reduce_timer_time(self, computer_name):
        """Reduce specified minutes from current timer without affecting running state"""
        try:
            minutes_to_reduce = int(self.stats_elements['time_entry'].get())
            if 0 <= minutes_to_reduce <= 99:  # Validate input range
                # Get current time from stats
                if computer_name in self.app.kiosk_tracker.kiosk_stats:
                    stats = self.app.kiosk_tracker.kiosk_stats[computer_name]
                    current_seconds = stats.get('timer_time', 0)
                    
                    # Calculate new time in seconds (convert minutes to seconds)
                    new_seconds = current_seconds - (minutes_to_reduce * 60)
                    
                    # Prevent negative time
                    if new_seconds < 0:
                        new_seconds = 0
                    
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
            if 'ttc_label' in self.stats_elements and self.stats_elements['ttc_label']:
                minutes_remaining = int(45 - (timer_time / 60))
                seconds_remaining = int(timer_time % 60)
                
                if seconds_remaining > 0:
                    ttc_minutes = minutes_remaining
                    ttc_seconds = 60- seconds_remaining
                else:
                    ttc_minutes = minutes_remaining
                    ttc_seconds = 0

                ttc_text = f"TTC: {ttc_minutes:02d}:{ttc_seconds:02d}"
                self.stats_elements['ttc_label'].config(text=ttc_text)
        
        for computer_name, kiosk_data in self.connected_kiosks.items():
            if computer_name in self.app.kiosk_tracker.kiosk_stats:
                stats = self.app.kiosk_tracker.kiosk_stats[computer_name]
                is_running = stats.get('timer_running', False)
                
                if is_running:
                    timer_time = stats.get('timer_time', 2700)
                    timer_minutes = int(timer_time // 60)
                    timer_seconds = int(timer_time % 60)
                    display_text = f"{timer_minutes:02d}:{timer_seconds:02d}"
                else:
                    display_text = "- - : - -"
                    
                kiosk_data['timer_label'].config(text=display_text)
                
        if self.selected_kiosk and self.selected_kiosk in self.app.kiosk_tracker.kiosk_assignments:
            room_number = self.app.kiosk_tracker.kiosk_assignments[self.selected_kiosk]
            if hasattr(self.app, 'prop_control') and self.app.prop_control:
                if room_number in self.app.prop_control.last_progress_times:
                    self.update_last_progress_time_display(room_number)
        
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
                print(f"[interface builder]Error updating video feed: {e}")
                
        if self.camera_active:
            self.app.root.after(30, self.update_video_feed)

    def skip_video(self, computer_name):
        """Skip any currently playing videos on the specified kiosk"""
        # Send stop video command to kiosk
        self.app.network_handler.socket.sendto(
            json.dumps({
                'type': 'stop_video_command',
                'computer_name': computer_name
            }).encode(),
            ('255.255.255.255', 12346)
        )

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
        frame.configure(relief='flat', borderwidth=0, highlightthickness=0)
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
        else:
            name_label = tk.Label(frame, 
                text="Unassigned",
                font=('Arial', 12, 'bold'))
            name_label.pack(side='left', padx=5)
        
        def click_handler(cn=computer_name):
            self.select_kiosk(cn)
        
        frame.bind('<Button-1>', lambda e: click_handler())
        name_label.bind('<Button-1>', lambda e: click_handler())
        
        room_var = tk.StringVar()
        dropdown = ttk.Combobox(frame, textvariable=room_var, 
            values=list(self.app.rooms.values()), state='readonly')
        dropdown.pack(side='left', padx=5)
        
        def on_room_select(event):
            if not room_var.get():
                return
            selected_room = next(num for num, name in self.app.rooms.items() 
                            if name == room_var.get())
            self.app.kiosk_tracker.assign_kiosk_to_room(computer_name, selected_room)
            dropdown.set('')
            name_label.config(
                text=self.app.rooms[selected_room],
                fg=self.ROOM_COLORS.get(selected_room, "black")
            )
        
        dropdown.bind('<<ComboboxSelected>>', on_room_select)
        
        help_label = tk.Label(frame, text="", font=('Arial', 14, 'bold'), fg='red')
        help_label.pack(side='left', padx=5)
        
        reboot_btn = tk.Button(
            frame, 
            text="Reboot Kiosk",
            bg='#FF6B6B',
            fg='white'
        )
        
        # Track confirmation state
        reboot_btn.confirmation_pending = False
        reboot_btn.after_id = None
        
        def reset_reboot_button(btn=reboot_btn):
            """Reset the button to its original state"""
            btn.confirmation_pending = False
            btn.config(text="Reboot Kiosk")
            btn.after_id = None
            
        def handle_reboot_click():
            """Handle reboot button clicks with confirmation"""
            if reboot_btn.confirmation_pending:
                # Second click - perform reboot
                self.app.network_handler.send_reboot_signal(computer_name)
                reset_reboot_button()
            else:
                # First click - show confirmation
                reboot_btn.confirmation_pending = True
                reboot_btn.config(text="Confirm")
                
                # Cancel any existing timer
                if reboot_btn.after_id:
                    reboot_btn.after_cancel(reboot_btn.after_id)
                    
                # Set timer to reset button after 2 seconds
                reboot_btn.after_id = reboot_btn.after(2000, lambda: reset_reboot_button()) # Changed to lambda

        reboot_btn.config(command=handle_reboot_click)
        reboot_btn.pack(side='left', padx=(20, 5))

        # Add mini timer label at the end
        timer_label = tk.Label(frame,
            text="--:--",
            font=('Arial', 10, 'bold'),
            width=6)
        timer_label.pack(side='right', padx=5)
        
        self.connected_kiosks[computer_name] = {
            'frame': frame,
            'help_label': help_label,
            'dropdown': dropdown,
            'reboot_btn': reboot_btn,
            'last_seen': current_time,
            'name_label': name_label,
            'timer_label': timer_label  # Store timer label reference
        }
        
        # Check if the hint requested flag was set
        if computer_name in self.app.kiosk_tracker.kiosk_stats:
            stats = self.app.kiosk_tracker.kiosk_stats[computer_name]
            # Use .get() for safe access
            self.mark_help_requested(computer_name)
        else:
            print(f"[interface builder][AdminInterface] add_kiosk_to_ui: No kiosk stats from {computer_name}")
        
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
        """Mark a kiosk as requesting help and play notification sound"""
        if computer_name in self.connected_kiosks:
            if computer_name in self.app.kiosk_tracker.kiosk_stats:
                stats = self.app.kiosk_tracker.kiosk_stats[computer_name]
                if stats.get('hint_requested', False):
                    print(f"[interface builder][AdminInterface] mark_help_requested: Showing HINT REQUESTED for {computer_name}")
                    self.connected_kiosks[computer_name]['help_label'].config(
                        text="HINT REQUESTED",
                        fg='red',
                        font=('Arial', 14, 'bold')
                    )
                    self.audio_manager = AdminAudioManager()
                    self.audio_manager.play_sound("hint_notification")
                else:
                    print(f"[interface builder][AdminInterface] mark_help_requested: Clearing HINT REQUESTED for {computer_name} from state")
                    self.connected_kiosks[computer_name]['help_label'].config(
                         text="",
                         fg='red',
                         font=('Arial', 14, 'bold')
                    )
            else:
                print(f"[interface builder][AdminInterface] mark_help_requested: Ignoring help request - no kiosk stats found for {computer_name}")

        else:
            print(f"[interface builder][AdminInterface] mark_help_requested: Ignoring help request - kiosk {computer_name} not in connected kioskl list")
            
    def remove_kiosk(self, computer_name):
        # Stop camera if it was active for this kiosk
        if getattr(self, 'camera_active', False) and \
           self.stats_elements.get('current_computer') == computer_name:
            self.toggle_camera(computer_name)
        
        # Rest of your existing remove_kiosk code...
        if computer_name in self.connected_kiosks:
            print(f"[interface builder][AdminInterface] remove_kiosk: Removing kiosk {computer_name} from UI")
            self.connected_kiosks[computer_name]['frame'].destroy()
            del self.connected_kiosks[computer_name]
            
            if computer_name in self.app.kiosk_tracker.kiosk_assignments:
                del self.app.kiosk_tracker.kiosk_assignments[computer_name]
            if computer_name in self.app.kiosk_tracker.kiosk_stats:
                del self.app.kiosk_tracker.kiosk_stats[computer_name]
            if computer_name in self.app.kiosk_tracker.assigned_rooms:
                del self.app.kiosk_tracker.assigned_rooms[computer_name]
            
            if self.selected_kiosk == computer_name:
                self.selected_kiosk = None
                self.stats_frame.configure(text="No Room Selected")
                for widget in self.stats_frame.winfo_children():
                    widget.destroy()
                self.stats_elements = {key: None for key in self.stats_elements}

    def select_kiosk(self, computer_name):
        """Handle selection of a kiosk and setup of its interface"""
        try:
            #print(f"[interface builder]\n=== KIOSK SELECTION START: {computer_name} ===")
            
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
                print(f"[interface builder]Room assigned: {room_name} (#{room_num})")
                
                # Get room color from mapping, default to black if not found
                room_color = self.ROOM_COLORS.get(room_num, "black")
                
                # Configure title with room-specific color
                self.stats_frame.configure(
                    text=title,
                    font=('Arial', 10, 'bold'),
                    fg=room_color  # Add color to match room color scheme
                )
                
                # Map room number to directory name for audio hints
                #print("[interface builder]\n=== AUDIO HINTS UPDATE START ===")
                room_dirs = {
                    6: "atlantis",
                    1: "casino",
                    5: "haunted",
                    2: "ma",
                    7: "time",
                    3: "wizard",
                    4: "zombie"
                }
                
                print(f"[interface builder]Current working directory: {os.getcwd()}")
                if room_num in room_dirs:
                    room_dir = room_dirs[room_num]
                    print(f"[interface builder]Selected room directory: {room_dir}")
                    audio_path = os.path.join("audio_hints", room_dir)
                    print(f"[interface builder]Audio path relative to working dir: {audio_path}")
                    print(f"[interface builder]Full audio path: {os.path.abspath(audio_path)}")
                    print(f"[interface builder]Path exists: {os.path.exists(audio_path)}")
                    #if os.path.exists(audio_path):
                       # print(f"[interface builder]Directory contents: {os.listdir(audio_path)}")
                    
                    if hasattr(self, 'audio_hints'):
                        print("[interface builder]Audio hints object exists, updating room")
                        self.audio_hints.update_room(room_dir)
                    else:
                        print("[interface builder]WARNING: No audio_hints object found!")
                #print("[interface builder]=== AUDIO HINTS UPDATE END ===\n")
            else:
                title = f"Unassigned ({computer_name})"
                print("[interface builder]No room assigned")
                self.stats_frame.configure(
                    text=title,
                    font=('Arial', 10, 'bold'),
                    fg='black'  # Default color for unassigned
                )
            
            if hasattr(self, 'saved_hints'):
                #print("[interface builder]Updating saved hints for room")
                if room_num:
                    self.saved_hints.update_room(room_num)
                else:
                    self.saved_hints.clear_preview()
            
            # Update highlighting with dotted border
            for cn, data in self.connected_kiosks.items():
                if cn == computer_name:
                    # Create dotted border effect
                    data['frame'].configure(
                        relief='solid',  # Solid relief creates border base
                        borderwidth=0,   # Border thickness
                        highlightthickness=0,  # Additional highlight border
                        highlightbackground='#363636',  # Color of dotted border
                        highlightcolor='#363636'  # Color when focused
                    )
                    # Create dotted border effect using character spacing
                    border_pattern = '. ' * 20  # Alternating dot and space
                    data['frame'].configure(bd=2, relief='solid')
                    # Keep button colors consistent
                    for widget in data['frame'].winfo_children():
                        if isinstance(widget, tk.Button):
                            if widget == data['reboot_btn']:
                                widget.configure(bg='#FF6B6B', fg='white')  # Keep reboot button red
                            elif widget == data['assign_btn']:
                                widget.configure(bg='#90EE90', fg='black')  # Light green for assign button
                else:
                    # Remove highlighting for unselected kiosks
                    data['frame'].configure(
                        relief='flat',
                        borderwidth=0,
                        highlightthickness=0
                    )
                    # Keep button colors consistent for unselected kiosks
                    for widget in data['frame'].winfo_children():
                        if isinstance(widget, tk.Button):
                            if widget == data['reboot_btn']:
                                widget.configure(bg='#FF6B6B', fg='white')  # Keep reboot button red
                            elif widget == data['assign_btn']:
                                widget.configure(bg='#90EE90', fg='black')  # Light green for assign button
            
            self.update_stats_display(computer_name)
            
            # Notify PropControl about room change (with safety check)
            if hasattr(self.app, 'prop_control') and self.app.prop_control:
                if computer_name in self.app.kiosk_tracker.kiosk_assignments:
                    room_num = self.app.kiosk_tracker.kiosk_assignments[computer_name]
                    print(f"[interface builder]Notifying prop control about room change to {room_num}")
                    self.app.root.after(100, lambda: self.app.prop_control.connect_to_room(room_num))
                else:
                    print("[interface builder]No room assignment, skipping prop control notification")
                    
            #print(f"[interface builder]=== KIOSK SELECTION END: {computer_name} ===\n")
            
        except Exception as e:
            print(f"[interface builder]Error in select_kiosk: {e}")
            
    def update_stats_display(self, computer_name):
        if computer_name not in self.app.kiosk_tracker.kiosk_stats:
            return

        stats = self.app.kiosk_tracker.kiosk_stats[computer_name]

        if not self.stats_elements:
            return

        if self.stats_elements.get('hints_label_below'):
            total_hints = stats.get('total_hints', 0)
            self.stats_elements['hints_label_below'].config(
                text=f"Hints requested: {total_hints}"
            )
            
        if self.stats_elements.get('hints_received_label'):
            hints_received = stats.get('hints_received', 0)
            self.stats_elements['hints_received_label'].config(
                text=f"Hints received: {hints_received}"
            )

        # Music button state update
        music_button = self.stats_elements.get('music_button')
        if music_button and music_button.winfo_exists():
            music_playing = stats.get('music_playing', False)
            #print(f"[DEBUG] Raw stats music_playing value: {music_playing}")  # Add this debug line

            if hasattr(music_button, 'music_on_icon') and hasattr(music_button, 'music_off_icon'):
                try:
                    current_image = music_button.cget('image')
                    #print(f"[DEBUG] music_playing: {music_playing}, current_image: {current_image}, on_icon: {music_button.music_on_icon}, off_icon: {music_button.music_off_icon}")
                    
                    if music_playing and str(current_image) != str(music_button.music_on_icon):
                        music_button.config(
                            image=music_button.music_on_icon
                        )
                    elif not music_playing and str(current_image) != str(music_button.music_off_icon):
                        music_button.config(
                            image=music_button.music_off_icon
                        )
                except tk.TclError:
                    print("[interface builder]Music button was destroyed")
                    return

        timer_time = stats.get('timer_time', 3600)
        timer_minutes = int(timer_time // 60)
        timer_seconds = int(timer_time % 60)
        if self.stats_elements.get('current_time'):
            self.stats_elements['current_time'].config(
                text=f"{timer_minutes:02d}:{timer_seconds:02d}"
            )

        timer_button = self.stats_elements.get('timer_button')
        if timer_button and timer_button.winfo_exists():
            is_running = stats.get('timer_running', False)

            if hasattr(timer_button, 'stop_icon') and hasattr(timer_button, 'play_icon'):
                try:
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
                    print("[interface builder]Timer button was destroyed")
                    return
            else:
                try:
                    if is_running and timer_button.cget('text') != "Stop Room":
                        timer_button.config(text="Stop Room")
                    elif not is_running and timer_button.cget('text') != "Start Room":
                        timer_button.config(text="Start Room")
                except tk.TclError:
                    print("[interface builder]Timer button was destroyed")
                    return
        
        if computer_name in self.app.kiosk_tracker.kiosk_assignments:
            if self.stats_elements.get('send_btn'):
                self.stats_elements['send_btn'].config(state='normal')
        else:
            if self.stats_elements.get('send_btn'):
                self.stats_elements['send_btn'].config(state='disabled')
        
        current_hint_request = stats.get('hint_requested', False)
        if not hasattr(self, '_last_hint_request_states'):
            self._last_hint_request_states = {}

        last_hint_request = self._last_hint_request_states.get(computer_name)
        
        if last_hint_request != current_hint_request:
            self.mark_help_requested(computer_name)
            self._last_hint_request_states[computer_name] = current_hint_request
        
        if self.app.prop_control and self.selected_kiosk in self.app.kiosk_tracker.kiosk_assignments:
            room_number = self.app.kiosk_tracker.kiosk_assignments[self.selected_kiosk]
            
            if room_number in self.app.prop_control.last_progress_times:
                self.update_last_progress_time_display(room_number)
        else:
            self.stats_elements['last_progress_label'].config(text="Last Progress: N/A")

    def update_last_progress_time_display(self, room_number):
        if room_number in self.app.prop_control.last_progress_times:
            last_progress_time = self.app.prop_control.last_progress_times[room_number]
            time_diff = time.time() - last_progress_time
            
            minutes = int(time_diff // 60)
            seconds = int(time_diff % 60)
            
            if minutes == 0 and seconds == 0:
                time_string = "Just now"
            elif minutes == 0:
                time_string = f"{seconds} seconds ago"
            elif seconds == 0:
                time_string = f"{minutes} minutes ago"
            else:
                time_string = f"{minutes} minutes {seconds} seconds ago"
            
            self.stats_elements['last_progress_label'].config(text=f"Last Progress: {time_string}")

    def save_manual_hint(self):
        # Wrapper for the extracted save_manual_hint function
        save_manual_hint(self)

    def clear_manual_hint(self):
        # Wrapper for the extracted clear_manual_hint function
        clear_manual_hint(self)

    def clear_kiosk_hints(self, computer_name):
        """Send command to clear hints on specified kiosk"""
        if computer_name in self.app.kiosk_tracker.kiosk_stats:
            self.app.network_handler.socket.sendto(
                json.dumps({
                    'type': 'clear_hints',
                    'computer_name': computer_name
                }).encode(),
                ('255.255.255.255', 12346)
            )

    def send_hint(self, computer_name, hint_data=None):
        # Wrapper for the extracted send_hint function
        send_hint(self, computer_name, hint_data)

    def play_solution_video(self, computer_name):
        """Play a solution video for the selected prop"""
        if not self.stats_elements['solution_prop'].get():
            return
            
        # Extract the display name from the dropdown value
        # Format is "Display Name (original_name)"
        display_name = self.stats_elements['solution_prop'].get().split('(')[0].strip()
        
        # Convert display name to lowercase and replace spaces with underscores
        video_filename = display_name.lower().replace(' ', '_')
        
        # Get the room folder name based on room number
        room_folders = {
            3: "wizard",
            1: "casino",
            2: "ma",
            5: "haunted",
            4: "zombie",
            6: "atlantis",
            7: "time"
        }
        
        room_num = self.app.kiosk_tracker.kiosk_assignments.get(computer_name)
        if room_num and room_num in room_folders:
            room_folder = room_folders[room_num]
            
            # Clear help request status if it exists
            if computer_name in self.app.kiosk_tracker.help_requested:
                self.app.kiosk_tracker.help_requested.remove(computer_name)
                if computer_name in self.connected_kiosks:
                    self.connected_kiosks[computer_name]['help_label'].config(text="")
            
            # Send video command to kiosk
            self.app.network_handler.socket.sendto(
                json.dumps({
                    'type': 'solution_video',
                    'computer_name': computer_name,
                    'room_folder': room_folder,
                    'video_filename': video_filename
                }).encode(),
                ('255.255.255.255', 12346)
            )

    def cleanup(self):
        """Clean up resources before closing"""
        if hasattr(self, 'audio_manager'):
            self.audio_manager.cleanup()

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
                print(f"[interface builder]Error stopping audio: {e}")
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
                    print(f"[interface builder]Error connecting audio: {e}")
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
                print(f"[interface builder]Error stopping microphone: {e}")
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
                print(f"[interface builder]Error enabling microphone: {e}")