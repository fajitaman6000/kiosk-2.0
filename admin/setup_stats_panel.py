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

    # Add reset button next to hints label with confirmation behavior
    reset_btn = tk.Button(
        hints_frame,
        text="Reset Kiosk",
        bg='#7897bf',
        fg='white',
        padx=10,
        justify='left',
        cursor="hand2"
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

            # CANCEL AUTO-RESET TIMER
            if computer_name in interface_builder.auto_reset_timer_ids:
                interface_builder.app.root.after_cancel(interface_builder.auto_reset_timer_ids[computer_name])
                del interface_builder.auto_reset_timer_ids[computer_name]
            if 'auto_reset_label' in interface_builder.stats_elements and interface_builder.stats_elements['auto_reset_label']:
                 interface_builder.stats_elements['auto_reset_label'].config(text=" ")


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

    # ADD AUTO-RESET TIMER LABEL
    interface_builder.stats_elements['auto_reset_label'] = tk.Label(
        hints_frame,
        text=" "
    )
    interface_builder.stats_elements['auto_reset_label'].pack(side='left', padx=5)

    # Timer controls section
    timer_frame = tk.LabelFrame(left_panel, text="Timer and Intros", fg='black')
    timer_frame.pack(fill='x', pady=1)

     # Timer and video controls combined
    control_buttons_frame = tk.Frame(timer_frame)
    control_buttons_frame.pack(fill='x', pady=1)

    # Current time display
    interface_builder.stats_elements['current_time'] = tk.Label(
        control_buttons_frame,
        text="45:00",
        font=('Arial', 20, 'bold'),
        fg='black',
        highlightbackground='black',
        highlightthickness=1,
        padx=7,
        pady=3,
    )
    interface_builder.stats_elements['current_time'].pack(side='left', padx=5)

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

        music_on_icon = Image.open(os.path.join(icon_dir, "music_on.png"))
        music_on_icon = music_on_icon.resize((24, 24), Image.Resampling.LANCZOS)
        music_on_icon = ImageTk.PhotoImage(music_on_icon)

        music_off_icon = Image.open(os.path.join(icon_dir, "music_off.png"))
        music_off_icon = music_off_icon.resize((24, 24), Image.Resampling.LANCZOS)
        music_off_icon = ImageTk.PhotoImage(music_off_icon)
    except Exception as e:
        print(f"[stats panel]Error loading icons: {e}")
        play_icon = stop_icon = video_icon = clock_icon = music_on_icon = music_off_icon = None

    # Timer button frame
    button_frame = tk.Frame(control_buttons_frame)
    button_frame.pack(side='left', padx=5)

    # Music button frame
    music_button_frame = tk.Frame(control_buttons_frame)
    music_button_frame.pack(side='left', padx=5)

    # Create music toggle button with icon
    music_btn = tk.Button(
        music_button_frame,
        image=music_off_icon if music_off_icon else None,
        text="" if music_off_icon else "Toggle Music",
        command=lambda: interface_builder.toggle_music(computer_name),
        width=24,
        height=24,
        bd=0,
        highlightthickness=0,
        #bg='black',
        #activebackground='black',
        cursor="hand2"
    )

    # Store both icons with the button for later use
    if music_on_icon and music_off_icon:
        music_btn.music_on_icon = music_on_icon
        music_btn.music_off_icon = music_off_icon

    music_btn.pack(side='left', padx=(1, 1))
    interface_builder.stats_elements['music_button'] = music_btn

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
        #activebackground='black',
        cursor="hand2"
    )
    # Store both icons with the button for later use
    if play_icon and stop_icon:
        timer_button.play_icon = play_icon
        timer_button.stop_icon = stop_icon
    timer_button.pack(side='left', padx=(1, 1))
    interface_builder.stats_elements['timer_button'] = timer_button

   # Video frame with icon button and dropdown
    video_frame = tk.Frame(control_buttons_frame)
    video_frame.pack(side='left', padx=(0,2))

    try:
        skip_icon = Image.open(os.path.join(icon_dir, "skip.png"))
        skip_icon = skip_icon.resize((24, 24), Image.Resampling.LANCZOS)
        skip_icon = ImageTk.PhotoImage(skip_icon)
    except Exception as e:
        print(f"[stats panel]Error loading skip icon: {e}")
        skip_icon = None

    # Video frame with icon button, dropdown and skip button
    video_frame = tk.Frame(control_buttons_frame)
    video_frame.pack(side='left', padx=(0,2))

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
        cursor="hand2"
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
        highlightthickness=0,
        cursor="hand2"
    )
    if skip_icon:
        skip_btn.image = skip_icon
    skip_btn.pack(side='left', padx=(30,0))


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
        highlightthickness=0,
        cursor="hand2"
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
        print(f"[stats panel]Error loading plus icon: {e}")
        plus_icon = None

    add_time_btn = tk.Button(
        time_set_frame,
        image=plus_icon if plus_icon else None,
        text="" if plus_icon else "Add Time",
        command=lambda: interface_builder.add_timer_time(computer_name),
        width=24,
        height=24,
        bd=0,
        highlightthickness=0,
        cursor="hand2"
    )
    if plus_icon:
        add_time_btn.image = plus_icon
    add_time_btn.pack(side='left', padx=5)

    # Reduce time button (uses minus icon if available)
    try:
        minus_icon = Image.open(os.path.join(icon_dir, "minus.png"))
        minus_icon = minus_icon.resize((24, 24), Image.Resampling.LANCZOS)
        minus_icon = ImageTk.PhotoImage(minus_icon)
    except Exception as e:
        print(f"[stats panel]Error loading minus icon: {e}")
        minus_icon = None

    reduce_time_btn = tk.Button(
        time_set_frame,
        image=minus_icon if minus_icon else None,
        text="" if minus_icon else "Reduce Time",
        command=lambda: interface_builder.reduce_timer_time(computer_name),  # Call reduce_timer_time
        width=24,
        height=24,
        bd=0,
        highlightthickness=0,
        cursor="hand2"
    )
    if minus_icon:
        reduce_time_btn.image = minus_icon
    reduce_time_btn.pack(side='left', padx=5)  # Place to the right of add_time_btn

    # Add auto-start toggle on the same row, aligned to the right
    interface_builder.stats_elements['auto_start_check'] = tk.Button(
        time_set_frame,
        text="[  ] Auto-Start",
        font=('Arial', 10),
        bd=0,
        highlightthickness=0,
        command=lambda: interface_builder.toggle_auto_start(computer_name),
        anchor='e',
        fg='black',
        bg='systemButtonFace',
        activebackground='systemButtonFace',
        cursor="hand2"
    )
    interface_builder.stats_elements['auto_start_check'].pack(side='right', padx=10)


    # Hint controls
    hint_frame = tk.LabelFrame(left_panel, text="Manual Hint")
    hint_frame.pack(fill='x', pady=10)

    # Create a frame for image selection and preview (Attach Image) at the top
    image_frame = ttk.LabelFrame(hint_frame, text="Attach Image")
    image_frame.pack(fill='x', pady=5, padx=5, expand=True)

    # Create prop selection frame
    interface_builder.stats_elements['img_prop_frame'] = ttk.Frame(image_frame)
    interface_builder.stats_elements['img_prop_frame'].pack(fill='x', expand=True)

    # Setup audio hints first to ensure we have room context
    interface_builder.setup_audio_hints()

    # Create image prop dropdown instead of button
    interface_builder.img_prop_var = tk.StringVar()
    interface_builder.stats_elements['image_btn'] = ttk.Combobox(
        interface_builder.stats_elements['img_prop_frame'],
        textvariable=interface_builder.img_prop_var,
        state="readonly",
        width=30
    )
    interface_builder.stats_elements['image_btn'].pack(pady=5)
    interface_builder.stats_elements['image_btn'].bind("<<ComboboxSelected>>", interface_builder.on_image_prop_select)

    # Add back button to prop selection frame (initially hidden)
    prop_control_buttons = ttk.Frame(interface_builder.stats_elements['img_prop_frame'])
    interface_builder.stats_elements['prop_control_buttons'] = prop_control_buttons  # Store reference

    interface_builder.stats_elements['prop_back_btn'] = ttk.Button(
        prop_control_buttons,
        text="Back",
        command=interface_builder.show_manual_hint,
        cursor="hand2"
    )

    interface_builder.stats_elements['prop_attach_btn'] = ttk.Button(
        prop_control_buttons,
        text="Attach",
        command=interface_builder.attach_image,
        cursor="hand2"
    )

    # Add listbox for image files (initially hidden)
    interface_builder.stats_elements['image_listbox'] = tk.Listbox(
        interface_builder.stats_elements['img_prop_frame'],
        height=4,
        width=40,
        selectmode=tk.SINGLE,
        exportselection=False,
        bg="white",
        fg="black"
    )
    interface_builder.stats_elements['image_listbox'].bind('<<ListboxSelect>>', interface_builder.on_image_file_select)

    # Create control frame (initially hidden)
    interface_builder.stats_elements['img_control_frame'] = ttk.Frame(image_frame)
    # Add image preview label in control frame
    interface_builder.stats_elements['image_preview'] = ttk.Label(interface_builder.stats_elements['img_control_frame'])
    interface_builder.stats_elements['image_preview'].pack(pady=5)

    # Add attached image label (initially hidden)
    interface_builder.stats_elements['attached_image_label'] = ttk.Label(
        image_frame,
        font=("Arial", 10)
    )

    # Now add the manual hint text box and buttons below the Attach Image section
    interface_builder.stats_elements['msg_entry'] = tk.Text(
        hint_frame,
        width=30,  # Width in characters
        height=4,  # Height in lines
        wrap=tk.WORD  # Word wrapping
    )
    interface_builder.stats_elements['msg_entry'].pack(fill='x', pady=8, padx=5)

    interface_builder.stats_elements['hint_buttons_frame'] = tk.Frame(hint_frame)
    interface_builder.stats_elements['hint_buttons_frame'].pack(pady=5)

    interface_builder.stats_elements['send_btn'] = tk.Button(
        interface_builder.stats_elements['hint_buttons_frame'],
        text="Send",
        command=lambda: interface_builder.send_hint(computer_name),
        cursor="hand2"
    )
    interface_builder.stats_elements['send_btn'].pack(side='left', padx=5)

    interface_builder.stats_elements['save_btn'] = tk.Button(
        interface_builder.stats_elements['hint_buttons_frame'],
        text="Save",
        command=interface_builder.save_manual_hint,
        cursor="hand2"
    )
    interface_builder.stats_elements['save_btn'].pack(side='left', padx=5)

    interface_builder.stats_elements['clear_btn'] = tk.Button(
        interface_builder.stats_elements['hint_buttons_frame'],
        text="Clear",
        command=interface_builder.clear_manual_hint,
        cursor="hand2"
    )
    interface_builder.stats_elements['clear_btn'].pack(side='left', padx=5)

    # Set the base directory for image hints
    interface_builder.image_root = os.path.join(os.path.dirname(__file__), "sync_directory", "hint_image_files")

    # Store the currently selected image
    interface_builder.current_hint_image = None

    # Update the dropdown with available props
    interface_builder.update_image_props()

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
        print(f"[stats panel]Error loading video/audio control icons: {e}")
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
        activebackground='systemButtonFace',  # Match system background when clicked
        cursor="hand2"
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
        activebackground='systemButtonFace',
        cursor="hand2"
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
        activebackground='systemButtonFace',
        cursor="hand2"
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
        print(f"[stats panel]Error loading prop mappings: {e}")
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
        state='normal' if props_list else 'disabled',
        cursor="hand2"
    )
    play_solution_btn.pack(side='left')

    # Add callback for prop selection
    def on_prop_select(prop_name):
        """Handle prop selection from PropControl click"""
        # Safety check - ensure dropdown still exists
        dropdown = interface_builder.stats_elements.get('props_dropdown')
        if not dropdown:
            print("[stats panel]Warning: Dropdown no longer exists")
            return

        # Get current values
        current_values = dropdown.cget('values')
        if not current_values:
            print("[stats panel]Warning: No values in dropdown")
            return

        # Find matching prop in dropdown
        for prop_item in current_values:
            if f"({prop_name})" in prop_item:
                try:
                    dropdown.set(prop_item)
                    #print(f"[stats panel]Successfully set dropdown to: {prop_item}")
                    break
                except Exception as e:
                    print(f"[stats panel]Error setting dropdown value: {e}")

    # Register for prop selection notifications
    if hasattr(interface_builder.app.prop_control, 'add_prop_select_callback'):
        interface_builder.app.prop_control.add_prop_select_callback(on_prop_select)

    # ===========================================
    # SECTION: Other Controls
    # ===========================================
    other_controls_frame = tk.LabelFrame(left_panel, text="Other Controls")
    other_controls_frame.pack(fill='x', pady=10)

    # Container for the FIRST row of horizontal buttons
    button_container_row1 = tk.Frame(other_controls_frame)
    button_container_row1.pack(fill='x', padx=5, pady=(5, 0)) # Pad bottom 0

    # Add clear hints button
    clear_hints_btn = tk.Button(
        button_container_row1, # Parent is now row 1
        text="Clear Hints",
        command=lambda: interface_builder.clear_kiosk_hints(computer_name),
        cursor="hand2"
    )
    clear_hints_btn.pack(side='left', padx=5)

    # Load hint sound and assistance icons
    try:
        hint_sound_icon = Image.open(os.path.join(icon_dir, "activate.png"))
        hint_sound_icon = hint_sound_icon.resize((10, 20), Image.Resampling.LANCZOS)
        hint_sound_icon = ImageTk.PhotoImage(hint_sound_icon)

        assistance_icon = Image.open(os.path.join(icon_dir, "assistance_requested.png"))
        assistance_icon = assistance_icon.resize((15, 15), Image.Resampling.LANCZOS)
        assistance_icon = ImageTk.PhotoImage(assistance_icon)
    except Exception as e:
        print(f"[stats panel]Error loading hint sound/assistance icons: {e}")
        hint_sound_icon = assistance_icon = None

    # Add play sound button with icon
    play_sound_btn = tk.Button(
        button_container_row1, # Parent is now row 1
        text="Play Hint Sound ",
        image=hint_sound_icon if hint_sound_icon else None,
        compound=tk.RIGHT,
        command=lambda: interface_builder.play_hint_sound(computer_name),
        cursor="hand2"
    )
    if hint_sound_icon:
        play_sound_btn.image = hint_sound_icon
    play_sound_btn.pack(side='left', padx=5)

    # Add offer assistance button with icon
    offer_assistance_btn = tk.Button(
        button_container_row1, # Parent is now row 1
        text="Offer Assistance ",
        image=assistance_icon if assistance_icon else None,
        compound=tk.RIGHT,
        command=lambda: interface_builder.app.network_handler.socket.sendto(
            json.dumps({
                'type': 'offer_assistance',
                'computer_name': computer_name
            }).encode(),
            ('255.255.255.255', 12346)
        ),
        cursor="hand2"
    )
    if assistance_icon:
        offer_assistance_btn.image = assistance_icon
    offer_assistance_btn.pack(side='left', padx=5)

    # --- START: ADD CHECK SCREEN BUTTON CONTAINER (ROW 2) ---
    # Create container for the SECOND row (just Check Screen button)
    button_container_row2 = tk.Frame(other_controls_frame)
    button_container_row2.pack(fill='x', padx=5, pady=(2, 5)) # Adjust padding

    # Add check screen button
    check_screen_btn = tk.Button(
        button_container_row2, # Parent is now row 2
        text="Check Screen",
        # command=lambda: interface_builder.check_kiosk_screen(computer_name), # Future function
        cursor="hand2"
    )
    check_screen_btn.pack(side='left', padx=0, pady=(10,0)) # Pack left, remove side padding if needed
    # --- END: ADD CHECK SCREEN BUTTON CONTAINER (ROW 2) ---

    # Sound controls container (Now packed below the second button row)
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
        "No drinks on props": "drinks_props.mp3",
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

    # --- ADD IMAGE DISPLAY FRAME HERE ---
    #  Wrap stats_below_video and image_display_frame in a container
    stats_and_image_container = tk.Frame(right_panel)
    stats_and_image_container.pack(side='left', anchor='nw', pady=3)  # Pack container at the top


    stats_below_video = tk.Frame(
        stats_and_image_container,  # Parent is now the container
        bg='systemButtonFace'
    )
    stats_below_video.pack(side='left', anchor='n', fill='x', pady=3, expand=True) # Pack to the LEFT inside the container, FILL and EXPAND


    image_display_frame = tk.Frame(
        stats_and_image_container,  # Parent is now the container
        bg='black',  # Black background when empty
        width=112*1.65,   #  9:16 aspect ratio, scaled down (e.g., 112.5 x 200)
        height=200*1.65  #  Adjust as needed, maintaining 9:16
    )
    image_display_frame.pack(
        side='right',  # Pack to the RIGHT inside the container
        anchor='e',    # Anchor to the north-east (top-right relative to container)
        pady=(2,0), # Some vertical padding
        padx=(2,0),

    )
    image_display_frame.pack_propagate(False)  # Prevent frame from shrinking

    # Image display label (initially empty)
    interface_builder.stats_elements['image_display_label'] = tk.Label(
        image_display_frame,
        bg='black'
    )
    interface_builder.stats_elements['image_display_label'].pack(
        fill='both',
        expand=True
    )


    # Create frame for vertical layout with a darker grey background
    stats_vertical_frame = tk.Frame(
        stats_below_video,
        bg='#E0E0E0',  # Slightly darker grey
        padx=5,
        pady=0,
        borderwidth=1,
        relief='solid' # For border
    )
    stats_vertical_frame.pack(side='left', padx=0, pady=1, fill='x', expand=True)  # Crucial: fill='x' here, and expand = True

    stats_panel_ypadding = 14

    # Time to Completion (TTC) label
    interface_builder.stats_elements['ttc_label'] = tk.Label(
        stats_vertical_frame,
        text="TTC:\n--:--",
        font=('Arial', 7, 'bold'),
        fg='black',
        bg='#E0E0E0',
        anchor='w', # Anchor text to left
        justify='left'
    )
    interface_builder.stats_elements['ttc_label'].pack(side='top', pady=stats_panel_ypadding, fill='x') # Fill 'x'

    # Get current hints count from tracker
    current_hints = 0
    if computer_name in interface_builder.app.kiosk_tracker.kiosk_stats:
        current_hints = interface_builder.app.kiosk_tracker.kiosk_stats[computer_name].get('total_hints', 0)

    # Hints requested label
    interface_builder.stats_elements['hints_label_below'] = tk.Label(
        stats_vertical_frame,
        text=f"Hints requested:\n{current_hints}",
        font=('Arial', 7, 'bold'),
        fg='black',
        bg='#E0E0E0',
        anchor='w', # Anchor text to left
        justify='left'
    )
    interface_builder.stats_elements['hints_label_below'].pack(side='top', pady=stats_panel_ypadding, fill='x') # Fill 'x'

    # Hints received label
    current_hints_received = 0
    if computer_name in interface_builder.app.kiosk_tracker.kiosk_stats:
        current_hints_received = interface_builder.app.kiosk_tracker.kiosk_stats[computer_name].get('hints_received', 0)

    interface_builder.stats_elements['hints_received_label'] = tk.Label(
        stats_vertical_frame,
        text=f"Hints received:\n{current_hints_received}",
        font=('Arial', 7, 'bold'),
        fg='black',
        bg='#E0E0E0',
        anchor='w', # Anchor text to left
        justify='left'
    )
    interface_builder.stats_elements['hints_received_label'].pack(side='top', pady=stats_panel_ypadding, fill='x') # Fill 'x'

    # Add "Time Since Last Progress" label:
    interface_builder.stats_elements['last_progress_label'] = tk.Label(
        stats_vertical_frame,
        text="Last Progress:\nN/A",  # Keep the newline for now
        font=('Arial', 7, 'bold'),
        fg='black',
        bg='#E0E0E0',
        anchor='w',
        justify='left'
    )
    interface_builder.stats_elements['last_progress_label'].pack(side='top', pady=stats_panel_ypadding, fill='x')

    # Last prop finished label
    interface_builder.stats_elements['last_prop_label'] = tk.Label(
        stats_vertical_frame,
        text="Last Prop Finished:\nN/A",  # Keep the newline for now
        font=('Arial', 7, 'bold'),
        fg='black',
        bg='#E0E0E0',
        anchor='w',
        justify='left'
    )
    interface_builder.stats_elements['last_prop_label'].pack(side='top', pady=stats_panel_ypadding, fill='x')

    # Screen Touches label
    #current_touches = 0
    #if computer_name in interface_builder.app.kiosk_tracker.kiosk_stats:
        #current_touches = interface_builder.app.kiosk_tracker.kiosk_stats[computer_name].get('times_touched_screen', 0)
        
    #interface_builder.stats_elements['touches_label'] = tk.Label(
        #stats_vertical_frame,
        #text=f"Screen touches: {current_touches}",
        #font=('Arial', 10, 'bold'),
        #fg='black',
        #bg='#E0E0E0',
        #anchor='w' # Anchor text to left
    #c)

    #interface_builder.stats_elements['touches_label'].pack(side='top', pady=2, fill='x') # Fill 'x'