import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import os
from saved_hints_panel import SavedHintsPanel
import json
import io
import base64

def setup_stats_panel(interface_builder, computer_name):
        """Setup the stats panel interface"""
        # Clear existing widgets
        for widget in interface_builder.stats_frame.winfo_children():
            widget.destroy()
        
        # Main container with grid layout
        stats_container = tk.Frame(interface_builder.stats_frame)
        stats_container.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Left side panel for stats and controls
        left_panel = tk.Frame(stats_container)
        left_panel.pack(side='left', fill='y', padx=(0, 10))
        
        # Stats frame for hints
        stats_frame = tk.Frame(left_panel)
        stats_frame.pack(fill='x', pady=(0, 2))
        
        # Create a frame for hints and reset button
        hints_frame = tk.Frame(stats_frame)
        hints_frame.pack(fill='x')
        
        # Get current hints count from tracker
        current_hints = 0
        if computer_name in interface_builder.app.kiosk_tracker.kiosk_stats:
            current_hints = interface_builder.app.kiosk_tracker.kiosk_stats[computer_name].get('total_hints', 0)
        
        # Create the hints label with current count
        interface_builder.stats_elements['hints_label'] = tk.Label(
            hints_frame, 
            text=f"Hints requested: {current_hints}",
            justify='left'
        )
        interface_builder.stats_elements['hints_label'].pack(side='left')
        
        # Add reset button next to hints label
        reset_btn = tk.Button(
            hints_frame,
            text="Reset Kiosk",
            command=lambda: interface_builder.reset_kiosk(computer_name),
            bg='#7897bf',
            fg='white',
            padx=10
        )
        reset_btn.pack(side='left', padx=10)

        # Timer controls section
        timer_frame = tk.LabelFrame(left_panel, text="Room Controls", fg='black')
        timer_frame.pack(fill='x', pady=1)

        # Current time display
        interface_builder.stats_elements['current_time'] = tk.Label(
            timer_frame,
            text="45:00",
            font=('Arial', 20, 'bold'),
            fg='black',
            highlightbackground='black',
            highlightthickness=1,
            padx=10,
            pady=5
        )
        interface_builder.stats_elements['current_time'].pack(pady=5)

        # Timer and video controls combined
        control_buttons_frame = tk.Frame(timer_frame)
        control_buttons_frame.pack(fill='x', pady=1)
        
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
        button_frame = tk.Frame(control_buttons_frame)
        button_frame.pack(side='left', padx=5)
        
        # Create start/stop room button with icon
        timer_button = tk.Button(
            button_frame,
            image=play_icon if play_icon else None,
            text="" if play_icon else "Start Room",
            command=lambda: interface_builder.toggle_timer(computer_name),
            width=24,
            height=24,
            bd=0,
            highlightthickness=0,
            #bg='black',
            #activebackground='black'
        )
        # Store both icons with the button for later use
        if play_icon and stop_icon:
            timer_button.play_icon = play_icon
            timer_button.stop_icon = stop_icon
        timer_button.pack(side='left', padx=(25, 5))
        interface_builder.stats_elements['timer_button'] = timer_button

        # Video frame with icon button and dropdown
        video_frame = tk.Frame(control_buttons_frame)
        video_frame.pack(side='left', padx=(0,25))
        
        # Video button with icon
        video_btn = tk.Button(
            video_frame,
            image=video_icon if video_icon else None,
            text="" if video_icon else "Start Room with Video",
            command=lambda: interface_builder.play_video(computer_name),
            width=24,
            height=24,
            bd=0,
            highlightthickness=0,
            #bg='black',
            #activebackground='black'
        )
        if video_icon:
            video_btn.image = video_icon
        video_btn.pack(side='left', padx=2)
        
        # Video options dropdown
        video_options = ['Intro', 'Late', 'Recent Player', 'Game']
        interface_builder.stats_elements['video_type'] = tk.StringVar(value=video_options[0])
        video_dropdown = ttk.Combobox(
            video_frame,
            textvariable=interface_builder.stats_elements['video_type'],
            values=video_options,
            state='readonly',
            width=10
        )
        video_dropdown.pack(side='left', padx=2)

        # Time setting controls
        time_set_frame = tk.Frame(timer_frame)
        time_set_frame.pack(fill='x', pady=5)

        interface_builder.stats_elements['time_entry'] = tk.Entry(time_set_frame, width=3)
        interface_builder.stats_elements['time_entry'].pack(side='left', padx=5)
        tk.Label(time_set_frame, text="min", fg='black').pack(side='left')

        # Set time button with icon
        set_time_btn = tk.Button(
            time_set_frame,
            image=clock_icon if clock_icon else None,
            text="" if clock_icon else "Set Time",
            command=lambda: interface_builder.set_timer(computer_name),
            width=24,
            height=24,
            bd=0,
            highlightthickness=0
        )
        if clock_icon:
            set_time_btn.image = clock_icon
        set_time_btn.pack(side='left', padx=5)

        # Add time button (uses plus icon if available)
        try:
            plus_icon = Image.open(os.path.join(icon_dir, "plus.png"))
            plus_icon = plus_icon.resize((24, 24), Image.Resampling.LANCZOS)
            plus_icon = ImageTk.PhotoImage(plus_icon)
        except Exception as e:
            print(f"Error loading plus icon: {e}")
            plus_icon = None

        add_time_btn = tk.Button(
            time_set_frame,
            image=plus_icon if plus_icon else None,
            text="" if plus_icon else "Add Time",
            command=lambda: interface_builder.add_timer_time(computer_name),
            width=24,
            height=24,
            bd=0,
            highlightthickness=0
        )
        if plus_icon:
            add_time_btn.image = plus_icon
        add_time_btn.pack(side='left', padx=5)

        # Hint controls
        hint_frame = tk.LabelFrame(left_panel, text="Manual Hint")
        hint_frame.pack(fill='x', pady=10)
        
        # Create Text widget instead of Entry
        interface_builder.stats_elements['msg_entry'] = tk.Text(
            hint_frame, 
            width=30,  # Width in characters
            height=4,  # Height in lines
            wrap=tk.WORD  # Word wrapping
        )
        interface_builder.stats_elements['msg_entry'].pack(fill='x', pady=8, padx=5)
        
         # Create button frame for all hint controls
        hint_buttons_frame = tk.Frame(hint_frame)
        hint_buttons_frame.pack(pady=5)
        
        interface_builder.stats_elements['send_btn'] = tk.Button(
            hint_buttons_frame, 
            text="Send",
            command=lambda: interface_builder.send_hint(computer_name)
        )
        interface_builder.stats_elements['send_btn'].pack(side='left', padx=5)
        
        # Add save button
        save_btn = tk.Button(
            hint_buttons_frame,
            text="Save",
            command=interface_builder.save_manual_hint
        )
        save_btn.pack(side='left', padx=5)
        
        # Add clear button
        clear_btn = tk.Button(
            hint_buttons_frame,
            text="Clear",
            command=interface_builder.clear_manual_hint
        )
        clear_btn.pack(side='left', padx=5)

        # Create a frame for image selection and preview
        image_frame = ttk.LabelFrame(hint_frame, text="Attach Image")
        image_frame.pack(fill='x', pady=5, padx=5)

        # Add image selection button
        interface_builder.stats_elements['image_btn'] = ttk.Button(
            image_frame, 
            text="Choose Image",
            command=lambda: interface_builder.select_image()
        )
        interface_builder.stats_elements['image_btn'].pack(pady=5)

        # Add image preview label
        interface_builder.stats_elements['image_preview'] = ttk.Label(image_frame)
        interface_builder.stats_elements['image_preview'].pack(pady=5)

        # Store the currently selected image
        interface_builder.current_hint_image = None
        interface_builder.setup_audio_hints()

        # Set up Saved Hints panel after audio hints
        saved_hint_callback = lambda hint_data, cn=computer_name: interface_builder.send_hint(cn, hint_data)
        interface_builder.saved_hints = SavedHintsPanel(
            interface_builder.stats_frame,
            saved_hint_callback
        )

        # Right side panel
        right_panel = tk.Frame(
            stats_container,
            width=500,  # Fixed width for entire right panel
            bg='systemButtonFace'
        )
        right_panel.pack(
            side='left',     # Ensure it stays on right
            fill='y',         # Fill vertical space
            expand=False,     # Don't expand horizontally
            padx=(10, 0)      # Padding only on left side
        )
        right_panel.pack_propagate(False)  # Prevent panel from shrinking
        
        # Video feed panel with fixed size
        video_frame = tk.Frame(
            right_panel,
            bg='black',
            width=500,
            height=375
        )
        video_frame.pack(
            expand=False,     # Don't expand
            pady=1,           # Slight vertical padding
            anchor='n'        # Anchor to top
        )
        video_frame.pack_propagate(False)  # Prevent frame from shrinking
        
        # Video display label fills video frame
        interface_builder.stats_elements['video_label'] = tk.Label(
            video_frame,
            bg='black'
        )
        interface_builder.stats_elements['video_label'].pack(
            fill='both',
            expand=True
        )
        
        # Control frame for camera and audio buttons
        # Place this BEFORE the video frame code to ensure it appears above
        control_frame = tk.Frame(
            right_panel,
            bg='systemButtonFace',
            height=32  # Fixed height
        )
        control_frame.pack(
            side='top',      # Pack at top of right panel
            fill='x',        # Fill horizontal space
            pady=0,          # Vertical padding
            anchor='n',      # Anchor to top
            before=video_frame  # Ensure it stays above video frame
        )
        control_frame.pack_propagate(False)  # Prevent height collapse

        # Load additional icons for video/audio controls
        try:
            camera_icon = Image.open(os.path.join(icon_dir, "start_camera.png"))
            camera_icon = camera_icon.resize((24, 24), Image.Resampling.LANCZOS)
            camera_icon = ImageTk.PhotoImage(camera_icon)
            
            stop_camera_icon = Image.open(os.path.join(icon_dir, "stop_camera.png"))
            stop_camera_icon = stop_camera_icon.resize((24, 24), Image.Resampling.LANCZOS)
            stop_camera_icon = ImageTk.PhotoImage(stop_camera_icon)
            
            listen_icon = Image.open(os.path.join(icon_dir, "start_listening.png"))
            listen_icon = listen_icon.resize((24, 24), Image.Resampling.LANCZOS)
            listen_icon = ImageTk.PhotoImage(listen_icon)
            
            stop_listening_icon = Image.open(os.path.join(icon_dir, "stop_listening.png"))
            stop_listening_icon = stop_listening_icon.resize((24, 24), Image.Resampling.LANCZOS)
            stop_listening_icon = ImageTk.PhotoImage(stop_listening_icon)
            
            enable_mic_icon = Image.open(os.path.join(icon_dir, "enable_microphone.png"))
            enable_mic_icon = enable_mic_icon.resize((24, 24), Image.Resampling.LANCZOS)
            enable_mic_icon = ImageTk.PhotoImage(enable_mic_icon)
            
            disable_mic_icon = Image.open(os.path.join(icon_dir, "disable_microphone.png"))
            disable_mic_icon = disable_mic_icon.resize((24, 24), Image.Resampling.LANCZOS)
            disable_mic_icon = ImageTk.PhotoImage(disable_mic_icon)
        except Exception as e:
            print(f"Error loading video/audio control icons: {e}")
            camera_icon = stop_camera_icon = listen_icon = stop_listening_icon = enable_mic_icon = disable_mic_icon = None

        # Camera controls with icon
        camera_btn = tk.Button(
            control_frame,
            image=camera_icon if camera_icon else None,
            text="" if camera_icon else "Start Camera",
            command=lambda: interface_builder.toggle_camera(computer_name),
            width=24,
            height=20,
            bd=0,
            highlightthickness=0,
            bg='systemButtonFace',  # Match system background
            activebackground='systemButtonFace'  # Match system background when clicked
        )
        if camera_icon and stop_camera_icon:
            camera_btn.camera_icon = camera_icon
            camera_btn.stop_camera_icon = stop_camera_icon
        camera_btn.pack(side='left', padx=5)

        # Audio listening controls with icon
        listen_btn = tk.Button(
            control_frame,
            image=listen_icon if listen_icon else None,
            text="" if listen_icon else "Start Listening",
            command=lambda: interface_builder.toggle_audio(computer_name),
            width=24,
            height=24,
            bd=0,
            highlightthickness=0,
            bg='systemButtonFace',
            activebackground='systemButtonFace'
        )
        if listen_icon and stop_listening_icon:
            listen_btn.listen_icon = listen_icon
            listen_btn.stop_listening_icon = stop_listening_icon
        listen_btn.pack(side='left', padx=5)

        # Microphone controls with icon
        speak_btn = tk.Button(
            control_frame,
            image=enable_mic_icon if enable_mic_icon else None,
            text="" if enable_mic_icon else "Enable Microphone",
            command=lambda: interface_builder.toggle_speaking(computer_name),
            state='disabled',
            width=24,
            height=24,
            bd=0,
            highlightthickness=0,
            bg='systemButtonFace',
            activebackground='systemButtonFace'
        )
        if enable_mic_icon and disable_mic_icon:
            speak_btn.enable_mic_icon = enable_mic_icon
            speak_btn.disable_mic_icon = disable_mic_icon
        speak_btn.pack(side='left', padx=5)

        # Store buttons in stats_elements
        interface_builder.stats_elements['camera_btn'] = camera_btn
        interface_builder.stats_elements['listen_btn'] = listen_btn
        interface_builder.stats_elements['speak_btn'] = speak_btn

        # Store the computer name for video/audio updates
        interface_builder.stats_elements['current_computer'] = computer_name