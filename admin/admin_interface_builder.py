import tkinter as tk
from tkinter import ttk
import time
from video_client import VideoClient
import cv2 # type: ignore
from PIL import Image, ImageTk
import threading

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
        for widget in self.stats_frame.winfo_children():
            widget.destroy()
        
        # Main container with grid layout
        stats_container = tk.Frame(self.stats_frame)
        stats_container.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Left side panel for stats and controls
        left_panel = tk.Frame(stats_container)
        left_panel.pack(side='left', fill='y', padx=(0, 10))
        
        # Stats label for hints
        stats_frame = tk.Frame(left_panel)
        stats_frame.pack(fill='x', pady=(0, 10))
        
        self.stats_elements['hints_label'] = tk.Label(stats_frame, justify='left')
        self.stats_elements['hints_label'].pack(anchor='w')

        # Timer controls
        timer_frame = tk.LabelFrame(left_panel, text="Room Controls", bg='black', fg='white')
        timer_frame.pack(fill='x', pady=5)

        # Current time display
        self.stats_elements['current_time'] = tk.Label(
            timer_frame,
            text="60:00",
            font=('Arial', 24, 'bold'),
            fg='white',
            bg='black',
            highlightbackground='white',
            highlightthickness=1,
            padx=10,
            pady=5
        )
        self.stats_elements['current_time'].pack(pady=5)

        timer_controls = tk.Frame(timer_frame, bg='black')
        timer_controls.pack(fill='x', padx=5, pady=5)

        # Timer and video controls combined
        control_buttons_frame = tk.Frame(timer_controls, bg='black')
        control_buttons_frame.pack(fill='x', pady=5)
        
        button_frame = tk.Frame(control_buttons_frame, bg='black')
        button_frame.pack(side='left', padx=5)
        
        self.stats_elements['timer_button'] = tk.Button(
            button_frame,
            text="Start Room",
            command=lambda: self.toggle_timer(computer_name)
        )
        self.stats_elements['timer_button'].pack(side='left', padx=5)

        # Video options with swapped order
        video_frame = tk.Frame(control_buttons_frame, bg='black')
        video_frame.pack(side='left', padx=5)
        
        tk.Button(
            video_frame,
            text="Start Room with Video",
            command=lambda: self.play_video(computer_name)
        ).pack(side='left', padx=30)
        
        video_options = ['Intro', 'Late', 'Recent Player', 'Game Intro Only']
        self.stats_elements['video_type'] = tk.StringVar(value=video_options[0])
        
        video_dropdown = ttk.Combobox(
            video_frame,
            textvariable=self.stats_elements['video_type'],
            values=video_options,
            state='readonly',
            width=10
        )
        video_dropdown.pack(side='left', padx=5)

        # Time setting controls
        time_set_frame = tk.Frame(timer_controls, bg='black')
        time_set_frame.pack(fill='x', pady=5)

        self.stats_elements['time_entry'] = tk.Entry(time_set_frame, width=3)
        self.stats_elements['time_entry'].pack(side='left', padx=5)
        tk.Label(time_set_frame, text="min", fg='white', bg='black').pack(side='left')

        tk.Button(
            time_set_frame,
            text="Set Time",
            command=lambda: self.set_timer(computer_name)
        ).pack(side='left', padx=5)

        # Hint controls
        hint_frame = tk.LabelFrame(left_panel, text="Hint Controls")
        hint_frame.pack(fill='x', pady=10)
        
        self.stats_elements['msg_entry'] = tk.Entry(hint_frame, width=40)
        self.stats_elements['msg_entry'].pack(fill='x', pady=5, padx=5)
        
        self.stats_elements['send_btn'] = tk.Button(
            hint_frame, 
            text="Send",
            command=lambda: self.send_hint(computer_name)
        )
        self.stats_elements['send_btn'].pack(pady=5)

        # Right side panel for video
        right_panel = tk.Frame(stats_container)
        right_panel.pack(side='right', fill='both', expand=True, padx=(10, 0))
        
        # Video feed panel with fixed size
        video_frame = tk.Frame(right_panel, bg='black', width=320, height=240)
        video_frame.pack(expand=True, pady=5)
        video_frame.pack_propagate(False)
        
        self.stats_elements['video_label'] = tk.Label(video_frame, bg='black')
        self.stats_elements['video_label'].pack(fill='both', expand=True)
        
        # Camera controls directly below video feed
        camera_frame = tk.Frame(right_panel)
        camera_frame.pack(pady=5)
        
        self.stats_elements['camera_btn'] = tk.Button(
            camera_frame, 
            text="Start Camera",
            command=lambda: self.toggle_camera(computer_name)
        )
        self.stats_elements['camera_btn'].pack()
        
        # Store the computer name for video updates
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
        is_running = self.stats_elements['timer_button'].cget('text') == "Stop Room"
        new_text = "Start Room" if is_running else "Stop Room"
        self.stats_elements['timer_button'].config(text=new_text)
        
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
        
        self.connected_kiosks[computer_name] = {
            'frame': frame,
            'help_label': help_label,
            'dropdown': dropdown,
            'assign_btn': assign_btn,
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
        if computer_name in self.app.kiosk_tracker.kiosk_stats:
            stats = self.app.kiosk_tracker.kiosk_stats[computer_name]
            
            self.stats_elements['hints_label'].config(
                text=f"Hints requested: {stats.get('total_hints', 0)}"
            )
            
            # Update timer display
            timer_time = stats.get('timer_time', 3600)
            timer_minutes = int(timer_time // 60)
            timer_seconds = int(timer_time % 60)
            if 'current_time' in self.stats_elements:
                self.stats_elements['current_time'].config(
                    text=f"{timer_minutes:02d}:{timer_seconds:02d}"
                )
            
            # Update timer button state
            if 'timer_button' in self.stats_elements:
                is_running = stats.get('timer_running', False)
                self.stats_elements['timer_button'].config(
                    text="Stop Room" if is_running else "Start Room"
                )
            
            if computer_name in self.app.kiosk_tracker.kiosk_assignments:
                self.stats_elements['send_btn'].config(state='normal')
            else:
                self.stats_elements['send_btn'].config(state='disabled')

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