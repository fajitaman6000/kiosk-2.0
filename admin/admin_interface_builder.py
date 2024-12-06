import tkinter as tk
from tkinter import ttk
import time
from video_client import VideoClient
from audio_client import AudioClient
import cv2 # type: ignore
from PIL import Image, ImageTk
import threading
import os


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
        self.setup_ui()
        
        # Start timer update loop using app's root
        self.app.root.after(1000, self.update_timer_display)
        
    def setup_ui(self):
        self.main_container = tk.Frame(self.app.root)
        self.main_container.pack(fill='both', expand=True, padx=10, pady=5)
        
        left_frame = tk.Frame(self.main_container)
        left_frame.pack(side='left', fill='both', expand=True, padx=5)
        
        self.kiosk_frame = tk.LabelFrame(left_frame, text="Online Kiosk Computers", padx=10, pady=5)
        self.kiosk_frame.pack(fill='both', expand=True)
        
        self.stats_frame = tk.LabelFrame(left_frame, text="No Room Selected", padx=10, pady=5)
        self.stats_frame.pack(fill='both', expand=True, pady=10)

    def setup_stats_panel(self, computer_name):
        # Clear existing widgets
        for widget in self.stats_frame.winfo_children():
            widget.destroy()
        
        # Main container with grid layout
        stats_container = tk.Frame(self.stats_frame)
        stats_container.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Left side panel for stats and controls
        left_panel = tk.Frame(stats_container)
        left_panel.pack(side='left', fill='y', padx=(0, 10))
        
        # Stats frame for hints
        stats_frame = tk.Frame(left_panel)
        stats_frame.pack(fill='x', pady=(0, 10))
        
        self.stats_elements['hints_label'] = tk.Label(stats_frame, justify='left')
        self.stats_elements['hints_label'].pack(anchor='w')

        # Timer controls section
        timer_frame = tk.LabelFrame(left_panel, text="Room Controls", bg='black', fg='white')
        timer_frame.pack(fill='x', pady=5)

        # Current time display
        self.stats_elements['current_time'] = tk.Label(
            timer_frame,
            text="45:00",
            font=('Arial', 20, 'bold'),
            fg='white',
            bg='black',
            highlightbackground='white',
            highlightthickness=1,
            padx=10,
            pady=5
        )
        self.stats_elements['current_time'].pack(pady=5)

        # Timer and video controls combined
        control_buttons_frame = tk.Frame(timer_frame, bg='black')
        control_buttons_frame.pack(fill='x', pady=5)
        
        # Load all required icons
        icon_dir = os.path.join("admin_icons")
        try:
            play_icon = Image.open(os.path.join(icon_dir, "play.png"))
            play_icon = play_icon.resize((24, 24), Image.Resampling.LANCZOS)
            play_icon = ImageTk.PhotoImage(play_icon)
            
            stop_icon = Image.open(os.path.join(icon_dir, "stop.png"))
            stop_icon = stop_icon.resize((24, 24), Image.Resampling.LANCZOS)
            stop_icon = ImageTk.PhotoImage(stop_icon)
            
            video_icon = Image.open(os.path.join(icon_dir, "video.png"))
            video_icon = video_icon.resize((24, 24), Image.Resampling.LANCZOS)
            video_icon = ImageTk.PhotoImage(video_icon)
            
            clock_icon = Image.open(os.path.join(icon_dir, "clock.png"))
            clock_icon = clock_icon.resize((24, 24), Image.Resampling.LANCZOS)
            clock_icon = ImageTk.PhotoImage(clock_icon)
        except Exception as e:
            print(f"Error loading icons: {e}")
            play_icon = stop_icon = video_icon = clock_icon = None
        
        # Timer button frame
        button_frame = tk.Frame(control_buttons_frame, bg='black')
        button_frame.pack(side='left', padx=5)
        
        # Create start/stop room button with icon
        timer_button = tk.Button(
            button_frame,
            image=play_icon if play_icon else None,
            text="" if play_icon else "Start Room",
            command=lambda: self.toggle_timer(computer_name),
            width=24,
            height=24,
            bd=0,
            highlightthickness=0,
            bg='black',
            activebackground='black'
        )
        # Store both icons with the button for later use
        if play_icon and stop_icon:
            timer_button.play_icon = play_icon
            timer_button.stop_icon = stop_icon
        timer_button.pack(side='left', padx=(5, 20))  # Increased right padding
        self.stats_elements['timer_button'] = timer_button

        # Video frame with icon button and dropdown
        video_frame = tk.Frame(control_buttons_frame, bg='black')
        video_frame.pack(side='left', padx=5)
        
        # Video button with icon
        video_btn = tk.Button(
            video_frame,
            image=video_icon if video_icon else None,
            text="" if video_icon else "Start Room with Video",
            command=lambda: self.play_video(computer_name),
            width=24,
            height=24,
            bd=0,
            highlightthickness=0,
            bg='black',
            activebackground='black'
        )
        if video_icon:
            video_btn.image = video_icon
        video_btn.pack(side='left', padx=2)
        
        # Video options dropdown
        video_options = ['Intro', 'Late', 'Recent Player', 'Game']
        self.stats_elements['video_type'] = tk.StringVar(value=video_options[0])
        video_dropdown = ttk.Combobox(
            video_frame,
            textvariable=self.stats_elements['video_type'],
            values=video_options,
            state='readonly',
            width=10
        )
        video_dropdown.pack(side='left', padx=2)

        # Time setting controls
        time_set_frame = tk.Frame(timer_frame, bg='black')
        time_set_frame.pack(fill='x', pady=5)

        self.stats_elements['time_entry'] = tk.Entry(time_set_frame, width=3)
        self.stats_elements['time_entry'].pack(side='left', padx=5)
        tk.Label(time_set_frame, text="min", fg='white', bg='black').pack(side='left')

        # Set time button with icon
        set_time_btn = tk.Button(
            time_set_frame,
            image=clock_icon if clock_icon else None,
            text="" if clock_icon else "Set Time",
            command=lambda: self.set_timer(computer_name),
            width=24,
            height=24,
            bd=0,
            highlightthickness=0,
            bg='black',
            activebackground='black'
        )
        if clock_icon:
            set_time_btn.image = clock_icon
        set_time_btn.pack(side='left', padx=5)

        # Hint controls
        hint_frame = tk.LabelFrame(left_panel, text="Hint Controls")
        hint_frame.pack(fill='x', pady=10)
        
        self.stats_elements['msg_entry'] = tk.Entry(hint_frame, width=10)
        self.stats_elements['msg_entry'].pack(fill='x', pady=5, padx=5)
        
        self.stats_elements['send_btn'] = tk.Button(
            hint_frame, 
            text="Send",
            command=lambda: self.send_hint(computer_name)
        )
        self.stats_elements['send_btn'].pack(pady=5)

        # Right side panel for video and audio
        right_panel = tk.Frame(stats_container)
        right_panel.pack(side='right', fill='both', expand=True, padx=(10, 0))
        
        # Video feed panel with fixed size
        video_frame = tk.Frame(right_panel, bg='black', width=320, height=240)
        video_frame.pack(expand=True, pady=1)
        video_frame.pack_propagate(False)
        
        self.stats_elements['video_label'] = tk.Label(video_frame, bg='black')
        self.stats_elements['video_label'].pack(fill='both', expand=True)
        
        # Control frame for camera and audio buttons
        control_frame = tk.Frame(right_panel)
        control_frame.pack(pady=1)
        
        # Camera controls
        self.stats_elements['camera_btn'] = tk.Button(
            control_frame, 
            text="Start Camera",
            command=lambda: self.toggle_camera(computer_name)
        )
        self.stats_elements['camera_btn'].pack(side='left', padx=5)

        # Audio controls
        self.stats_elements['listen_btn'] = tk.Button(
            control_frame,
            text="Start Listening",
            command=lambda: self.toggle_audio(computer_name)
        )
        self.stats_elements['listen_btn'].pack(side='left', padx=5)
        
        self.stats_elements['speak_btn'] = tk.Button(
            control_frame,
            text="Enable Microphone",
            command=lambda: self.toggle_speaking(computer_name),
            state='disabled'  # Initially disabled until listening is active
        )
        self.stats_elements['speak_btn'].pack(side='left', padx=5)
        
        # Store the computer name for video/audio updates
        self.stats_elements['current_computer'] = computer_name

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

    def update_timer_display(self):
        if self.selected_kiosk and self.selected_kiosk in self.app.kiosk_tracker.kiosk_stats:
            stats = self.app.kiosk_tracker.kiosk_stats[self.selected_kiosk]
            timer_time = stats.get('timer_time', 3600)
            timer_minutes = int(timer_time // 60)
            timer_seconds = int(timer_time % 60)
            if 'current_time' in self.stats_elements and self.stats_elements['current_time']:
                self.stats_elements['current_time'].config(
                    text=f"{timer_minutes:02d}:{timer_seconds:02d}"
                )
        
        self.app.root.after(1000, self.update_timer_display)

    def toggle_camera(self, computer_name):
        if getattr(self, 'camera_active', False):
            # Stop camera
            self.video_client.disconnect()
            self.camera_active = False
            self.stats_elements['camera_btn'].config(text="Start Camera")
            if 'video_label' in self.stats_elements:
                self.stats_elements['video_label'].config(image='')
        else:
            # Start camera
            self.stats_elements['camera_btn'].config(text="Connecting...")
            
            def connect():
                if self.video_client.connect(computer_name):
                    self.camera_active = True
                    self.stats_elements['camera_btn'].config(text="Stop Camera")
                    self.update_video_feed()
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
                    frame = cv2.resize(frame, (320, 240))
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
        current_time = time.time()
        
        if computer_name in self.connected_kiosks:
            self.connected_kiosks[computer_name]['last_seen'] = current_time
            return
            
        frame = tk.Frame(self.kiosk_frame)
        frame.pack(fill='x', pady=2)
        
        if computer_name in self.app.kiosk_tracker.kiosk_assignments:
            room_num = self.app.kiosk_tracker.kiosk_assignments[computer_name]
            room_name = self.app.rooms[room_num]
            name_label = tk.Label(frame, 
                text=room_name,
                font=('Arial', 12, 'bold'))
            name_label.pack(side='left', padx=5)
            computer_label = tk.Label(frame,
                text=f"({computer_name})",
                font=('Arial', 12, 'italic'))
            computer_label.pack(side='left')
        else:
            name_label = tk.Label(frame, 
                text="Unassigned",
                font=('Arial', 12, 'bold'))
            name_label.pack(side='left', padx=5)
            computer_label = tk.Label(frame,
                text=f"({computer_name})",
                font=('Arial', 12, 'italic'))
            computer_label.pack(side='left')
        
        def click_handler(cn=computer_name):
            self.select_kiosk(cn)
        
        frame.bind('<Button-1>', lambda e: click_handler())
        name_label.bind('<Button-1>', lambda e: click_handler())
        computer_label.bind('<Button-1>', lambda e: click_handler())
        
        room_var = tk.StringVar()
        dropdown = ttk.Combobox(frame, textvariable=room_var, 
            values=list(self.app.rooms.values()), state='readonly')
        dropdown.pack(side='left', padx=5)
        
        help_label = tk.Label(frame, text="", font=('Arial', 14, 'bold'), fg='red')
        help_label.pack(side='left', padx=5)
        
        def assign_room():
            if not room_var.get():
                return
            selected_room = next(num for num, name in self.app.rooms.items() 
                            if name == room_var.get())
            self.app.kiosk_tracker.assign_kiosk_to_room(computer_name, selected_room)
            dropdown.set('')
            name_label.config(text=self.app.rooms[selected_room])
        
        assign_btn = tk.Button(frame, text="Assign Room", command=assign_room)
        assign_btn.pack(side='left', padx=5)
        
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
            'assign_btn': assign_btn,
            'reboot_btn': reboot_btn,
            'last_seen': current_time,
            'name_label': name_label,
            'computer_label': computer_label
        }
        
        if computer_name == self.selected_kiosk:
            self.select_kiosk(computer_name)

    def update_kiosk_display(self, computer_name):
        if computer_name in self.connected_kiosks:
            if computer_name in self.app.kiosk_tracker.kiosk_assignments:
                room_num = self.app.kiosk_tracker.kiosk_assignments[computer_name]
                self.connected_kiosks[computer_name]['name_label'].config(
                    text=self.app.rooms[room_num]
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
        try:
            print(f"\nSelecting kiosk: {computer_name}")
            
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
            
            self.selected_kiosk = computer_name
            
            if computer_name in self.app.kiosk_tracker.kiosk_assignments:
                room_num = self.app.kiosk_tracker.kiosk_assignments[computer_name]
                room_name = self.app.rooms[room_num]
                title = f"{room_name} ({computer_name})"
                print(f"Room assigned: {room_name} (#{room_num})")
            else:
                title = f"Unassigned ({computer_name})"
                print("No room assigned")
            self.stats_frame.configure(text=title)
            
            # Update highlighting
            for cn, data in self.connected_kiosks.items():
                if cn == computer_name:
                    data['frame'].configure(bg='lightblue')
                    for widget in data['frame'].winfo_children():
                        if not isinstance(widget, ttk.Combobox):
                            widget.configure(bg='lightblue')
                else:
                    data['frame'].configure(bg='SystemButtonFace')
                    for widget in data['frame'].winfo_children():
                        if not isinstance(widget, ttk.Combobox):
                            widget.configure(bg='SystemButtonFace')
            
            self.setup_stats_panel(computer_name)
            self.update_stats_display(computer_name)
            
            # Notify PropControl about room change (with safety check)
            if hasattr(self.app, 'prop_control') and self.app.prop_control:
                if computer_name in self.app.kiosk_tracker.kiosk_assignments:
                    room_num = self.app.kiosk_tracker.kiosk_assignments[computer_name]
                    print(f"Notifying prop control about room change to {room_num}")
                    self.app.root.after(100, lambda: self.app.prop_control.connect_to_room(room_num))
                else:
                    print("No room assignment, skipping prop control notification")
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
                self.stats_elements['hints_label'].config(
                    text=f"Hints requested: {stats.get('total_hints', 0)}"
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

    def send_hint(self, computer_name):
        if not self.stats_elements['msg_entry'] or not computer_name in self.app.kiosk_tracker.kiosk_assignments:
            return
            
        message_text = self.stats_elements['msg_entry'].get()
        if not message_text:
            return
            
        room_number = self.app.kiosk_tracker.kiosk_assignments[computer_name]
        self.app.network_handler.send_hint(room_number, message_text)
        
        if computer_name in self.app.kiosk_tracker.help_requested:
            self.app.kiosk_tracker.help_requested.remove(computer_name)
            if computer_name in self.connected_kiosks:
                self.connected_kiosks[computer_name]['help_label'].config(text="")
        
        self.stats_elements['msg_entry'].delete(0, 'end')

    def toggle_audio(self, computer_name):
        """Toggle audio listening from kiosk"""
        if getattr(self, 'audio_active', False):
            try:
                # Stop audio
                self.audio_client.disconnect()
                self.audio_active = False
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
                        self.stats_elements['listen_btn'].config(text="Stop Listening")
                        self.stats_elements['speak_btn'].config(state='normal')
                    else:
                        self.stats_elements['listen_btn'].config(text="Start Listening")
                        self.stats_elements['speak_btn'].config(state='disabled')
                except Exception as e:
                    print(f"Error connecting audio: {e}")
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
                self.stats_elements['speak_btn'].config(text="Enable Microphone")
            except Exception as e:
                print(f"Error stopping microphone: {e}")
        else:
            # Start speaking
            try:
                if self.audio_client.start_speaking():
                    self.speaking = True
                    self.stats_elements['speak_btn'].config(text="Disable Microphone")
                else:
                    self.stats_elements['speak_btn'].config(text="Enable Microphone")
            except Exception as e:
                print(f"Error enabling microphone: {e}")