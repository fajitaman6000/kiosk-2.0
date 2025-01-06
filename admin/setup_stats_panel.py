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
        left_panel = tk.Frame(stats_container, width=350)  # Reduced from ~500px default
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
        
        # Add reset button next to hints label with confirmation behavior
        reset_btn = tk.Button(
            hints_frame,
            text="Reset Kiosk",
            bg='#7897bf',
            fg='white',
            padx=10
        )

        # Track confirmation state
        reset_btn.confirmation_pending = False
        reset_btn.after_id = None

        def reset_reset_button():
            """Reset the button to its original state"""
            reset_btn.confirmation_pending = False
            reset_btn.config(text="Reset Kiosk")
            reset_btn.after_id = None
            
        def handle_reset_click():
            """Handle reset button clicks with confirmation"""
            if reset_btn.confirmation_pending:
                # Second click - perform reset
                interface_builder.reset_kiosk(computer_name)
                reset_reset_button()
            else:
                # First click - show confirmation
                reset_btn.confirmation_pending = True
                reset_btn.config(text="Confirm")
                
                # Cancel any existing timer
                if reset_btn.after_id:
                    reset_btn.after_cancel(reset_btn.after_id)
                    
                # Set timer to reset button after 2 seconds
                reset_btn.after_id = reset_btn.after(2000, reset_reset_button)

        reset_btn.config(command=handle_reset_click)
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
        
        try:
            skip_icon = Image.open(os.path.join(icon_dir, "skip.png"))
            skip_icon = skip_icon.resize((24, 24), Image.Resampling.LANCZOS)
            skip_icon = ImageTk.PhotoImage(skip_icon)
        except Exception as e:
            print(f"Error loading skip icon: {e}")
            skip_icon = None

        # Video frame with icon button, dropdown and skip button
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
            highlightthickness=0
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

        # Add skip button
        skip_btn = tk.Button(
            video_frame,
            image=skip_icon if skip_icon else None,
            text="" if skip_icon else "Skip Video",
            command=lambda: interface_builder.skip_video(computer_name),
            width=24,
            height=24,
            bd=0,
            highlightthickness=0
        )
        if skip_icon:
            skip_btn.image = skip_icon
        skip_btn.pack(side='left', padx=2)


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

        # Right side panel - with adjusted proportions
        right_panel = tk.Frame(
            stats_container,
            width=600,  # Increased to accommodate video better
            bg='systemButtonFace'
        )
        right_panel.pack(
            side='left',     # Ensure it stays on right
            fill='y',        # Fill vertical space
            expand=True,     # Allow expansion to fill space
            padx=(10, 0)     # Padding only on left side
        )
        right_panel.pack_propagate(False)  # Prevent panel from shrinking

        # Video feed panel with reduced size (60% of original)
        video_frame = tk.Frame(
            right_panel,
            bg='black',
            width=300,      # Reduced from 500
            height=225      # Reduced from 375
        )
        video_frame.pack(
            expand=False,   # Don't expand
            pady=1,         # Slight vertical padding
            anchor='n'      # Anchor to top
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

        # ===========================================
        # Video Solutions Section
        # ===========================================
        video_solutions_frame = tk.LabelFrame(left_panel, text="Video Solutions")
        video_solutions_frame.pack(fill='x', pady=10)

        # Container for dropdown and play button
        solutions_container = tk.Frame(video_solutions_frame)
        solutions_container.pack(fill='x', padx=5, pady=5)

        # Load prop mappings
        try:
            with open('prop_name_mapping.json', 'r') as f:
                prop_mappings = json.load(f)
        except Exception as e:
            print(f"Error loading prop mappings: {e}")
            prop_mappings = {}
            
        # Get room-specific props if room is assigned
        props_list = []
        if computer_name in interface_builder.app.kiosk_tracker.kiosk_assignments:
            room_num = interface_builder.app.kiosk_tracker.kiosk_assignments[computer_name]
            room_map = {
                3: "wizard",
                1: "casino",
                2: "ma",
                5: "haunted",
                4: "zombie",
                6: "atlantis",
                7: "time"
            }
            
            if room_num in room_map:
                room_key = room_map[room_num]
                if room_key in prop_mappings:
                    # Sort props by order
                    props = [(k, v) for k, v in prop_mappings[room_key]["mappings"].items()]
                    props.sort(key=lambda x: x[1]["order"])
                    props_list = [f"{p[1]['display']} ({p[0]})" for p in props]

        # IMPORTANT: Initialize the StringVar before creating the dropdown
        interface_builder.stats_elements['solution_prop'] = tk.StringVar()

        # Create dropdown with the initialized StringVar
        interface_builder.stats_elements['props_dropdown'] = ttk.Combobox(
            solutions_container,
            textvariable=interface_builder.stats_elements['solution_prop'],  # Use the initialized StringVar
            values=props_list,
            state='readonly' if props_list else 'disabled',
            width=30
        )
        interface_builder.stats_elements['props_dropdown'].pack(side='left', padx=(0, 5))

        # Add play button
        play_solution_btn = tk.Button(
            solutions_container,
            text="Send Video Solution",
            command=lambda: interface_builder.play_solution_video(computer_name),
            state='normal' if props_list else 'disabled'
        )
        play_solution_btn.pack(side='left')

        # Add callback for prop selection
        def on_prop_select(prop_name):
            """Handle prop selection from PropControl click"""
            # Safety check - ensure dropdown still exists
            dropdown = interface_builder.stats_elements.get('props_dropdown')
            if not dropdown:
                print("Warning: Dropdown no longer exists")
                return
                
            # Get current values
            current_values = dropdown.cget('values')
            if not current_values:
                print("Warning: No values in dropdown")
                return
                
            # Find matching prop in dropdown
            for prop_item in current_values:
                if f"({prop_name})" in prop_item:
                    try:
                        dropdown.set(prop_item)
                        #print(f"Successfully set dropdown to: {prop_item}")
                        break
                    except Exception as e:
                        print(f"Error setting dropdown value: {e}")

        # Register for prop selection notifications
        if hasattr(interface_builder.app.prop_control, 'add_prop_select_callback'):
            interface_builder.app.prop_control.add_prop_select_callback(on_prop_select)

        # ===========================================
        # NEW SECTION: Other Controls
        # ===========================================
        other_controls_frame = tk.LabelFrame(left_panel, text="Other Controls")
        other_controls_frame.pack(fill='x', pady=10)

        # Create container for horizontal button layout
        button_container = tk.Frame(other_controls_frame)
        button_container.pack(fill='x', padx=5, pady=5)
        
        # Add clear hints button
        clear_hints_btn = tk.Button(
            button_container,  # Note: Parent changed to button_container
            text="Clear Hints",
            command=lambda: interface_builder.clear_kiosk_hints(computer_name)
        )
        clear_hints_btn.pack(side='left', padx=5)  # Added side='left'

        # Add play sound button
        play_sound_btn = tk.Button(
            button_container,  # Note: Parent changed to button_container
            text="Play Hint Sound",
            command=lambda: interface_builder.play_hint_sound(computer_name)
        )
        play_sound_btn.pack(side='left', padx=5)  # Added side='left'

        # Sound controls container
        sound_container = tk.Frame(other_controls_frame)
        sound_container.pack(fill='x', padx=5, pady=5)
        
        # Add "Issue Warning:" label
        tk.Label(
            sound_container,
            text="Issue Warning:",
            anchor='e'
        ).pack(side='left', padx=(0, 5))
        
        # Define warning sounds
        warning_sounds = {
            "Be gentle": "be_gentle.mp3",
            "No photos": "no_photos.mp3",
            "Please stop": "please_stop.mp3"
        }
        
        # Create variable for dropdown
        interface_builder.stats_elements['warning_sound'] = tk.StringVar()
        
        # Create and configure dropdown
        warning_dropdown = ttk.Combobox(
            sound_container,
            textvariable=interface_builder.stats_elements['warning_sound'],
            values=list(warning_sounds.keys()),
            state='readonly',
            width=15
        )
        warning_dropdown.pack(side='left')
        
        # Add automatic trigger on selection
        def on_warning_select(event):
            selected = interface_builder.stats_elements['warning_sound'].get()
            if selected:  # Only trigger if something is actually selected
                interface_builder.play_hint_sound(
                    computer_name, 
                    warning_sounds[selected]
                )
                warning_dropdown.set('')  # Reset dropdown after playing
        
        warning_dropdown.bind('<<ComboboxSelected>>', on_warning_select)
        
        # Store the computer name for video/audio updates
        interface_builder.stats_elements['current_computer'] = computer_name