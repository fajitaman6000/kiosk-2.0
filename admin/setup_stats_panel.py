import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import os
from saved_hints_panel import SavedHintsPanel
import json
import io
import base64
import math # Added for volume meter update
import pyaudio # Added for getting default device info
import numpy as np # Added for volume calculation in popup

def setup_stats_panel(interface_builder, computer_name):
    """Setup the stats panel interface"""
    # Clear existing widgets
    for widget in interface_builder.stats_frame.winfo_children():
        widget.destroy()

    # Main container with grid layout
    stats_container = tk.Frame(interface_builder.stats_frame)
    stats_container.pack(fill='both', expand=True, padx=0, pady=0, side='top', anchor='nw')

    # Left side panel for stats and controls
    left_panel = tk.Frame(stats_container, width=350)  # Reduced from ~500px default
    left_panel = tk.Frame(stats_container)
    left_panel.pack(side='left', fill='y', padx=(0, 10))

    # Stats frame for hints
    stats_frame = tk.Frame(left_panel)
    stats_frame.pack(fill='x', pady=(0, 0))

    # Create a frame for hints and reset button
    hints_frame = tk.Frame(stats_frame)
    hints_frame.pack(fill='x')

    # Timer controls section
    timer_frame = tk.LabelFrame(left_panel, text="Timer and Intros", fg='black', font=('Arial', 9, 'bold'), labelanchor='nw')
    timer_frame.pack(fill='x', pady=1)

     # Timer and video controls combined
    control_buttons_frame = tk.Frame(timer_frame)
    control_buttons_frame.pack(fill='x', pady=1)

    # Current time display
    interface_builder.stats_elements['current_time'] = tk.Label(
        control_buttons_frame,
        text="45:00",
        font=('Arial', 19, 'bold'),
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

        video_playing_icon = Image.open(os.path.join(icon_dir, "video_playing.png"))
        video_playing_icon = video_playing_icon.resize((24, 24), Image.Resampling.LANCZOS)
        video_playing_icon = ImageTk.PhotoImage(video_playing_icon)

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

    # Music button frame
    music_button_frame = tk.Frame(control_buttons_frame)

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
    timer_button.pack(side='right', padx=(1, 1))
    interface_builder.stats_elements['timer_button'] = timer_button

   # Video frame with icon button and dropdown
    video_frame = tk.Frame(control_buttons_frame)

    try:
        skip_icon = Image.open(os.path.join(icon_dir, "skip.png"))
        skip_icon = skip_icon.resize((24, 24), Image.Resampling.LANCZOS)
        skip_icon = ImageTk.PhotoImage(skip_icon)
    except Exception as e:
        print(f"[stats panel]Error loading skip icon: {e}")
        skip_icon = None

    # Video frame with icon button, dropdown and skip button
    video_frame = tk.Frame(control_buttons_frame)

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
    # Store the actual PhotoImage objects (or None) as attributes on the button.
    # This ensures hasattr() will work correctly in the update logic.
    video_btn.video_icon_obj = video_icon
    video_btn.video_playing_icon_obj = video_playing_icon
    
    video_btn.pack(side='left', padx=(5,0))
    interface_builder.stats_elements['video_button'] = video_btn # Ensure this key is 'video_button'

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
    video_dropdown.pack(side='left', padx=(3,10))

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
    skip_btn.pack(side='left', padx=(0,10))      # Uncomment to show skip button

    # PACK THE FRAMES IN THE NEW ORDER
    video_frame.pack(side='left', padx=(0,2))
    button_frame.pack(side='right', padx=(7,2))
    music_button_frame.pack(side='right', padx=(0,3))

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
    hint_frame = tk.LabelFrame(left_panel, text="Manual Hint", fg='black', font=('Arial', 9, 'bold'), labelanchor='nw')
    hint_frame.pack(fill='x', pady=(3,3))

    # Create a frame for image selection and preview (Attach Image) at the top
    image_frame = ttk.LabelFrame(hint_frame, text="Attach Image", labelanchor='n')
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

    interface_builder.stats_elements['prop_back_btn'] = tk.Button(
        prop_control_buttons,
        text="Back",
        command=interface_builder.show_manual_hint,
        cursor="hand2",
        bg="#f7a1a1"
    )

    interface_builder.stats_elements['open_browser_btn'] = ttk.Button(
        interface_builder.stats_elements['prop_control_buttons'],  # Parent is the same frame
        text="Browse Images",
        command=interface_builder.open_full_image_browser  # Calls new method on AdminInterfaceBuilder
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
    interface_builder.stats_elements['msg_entry'].pack(fill='x', pady=3, padx=5)

    interface_builder.stats_elements['hint_buttons_frame'] = tk.Frame(hint_frame)
    interface_builder.stats_elements['hint_buttons_frame'].pack(pady=5)

    interface_builder.stats_elements['send_btn'] = tk.Button(
        interface_builder.stats_elements['hint_buttons_frame'],
        text="Send",
        command=lambda: interface_builder.send_hint(computer_name),
        cursor="hand2",
        bg="lightblue",  # Add background color
        #fg="darkblue"    # Add text color
    )
    interface_builder.stats_elements['send_btn'].pack(side='left', padx=5, pady=(5))

    interface_builder.stats_elements['save_btn'] = tk.Button(
        interface_builder.stats_elements['hint_buttons_frame'],
        text="Save",
        command=interface_builder.save_manual_hint,
        cursor="hand2",
        bg="#f7dfa1"
    )
    #interface_builder.stats_elements['save_btn'].pack(side='left', padx=5)                       #Uncomment to bring back save button

    interface_builder.stats_elements['clear_btn'] = tk.Button(
        interface_builder.stats_elements['hint_buttons_frame'],
        text="Clear",
        command=interface_builder.clear_manual_hint,
        cursor="hand2",
        bg="#f7a1a1"
    )
    interface_builder.stats_elements['clear_btn'].pack(side='left', padx=5, pady=(5))

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
        side='right',     # Ensure it stays on right
        fill='both',        # Fill vertical space
        expand=True,     # Allow expansion to fill space
        padx=(0, 0),
        pady=(9, 0)
    )
    right_panel.pack_propagate(False)  # Prevent panel from shrinking

    # --- ADD IMAGE DISPLAY FRAME HERE ---
    #  Wrap stats_below_video and image_display_frame in a container
    stats_and_image_container = tk.Frame(right_panel, borderwidth=1, relief='solid') # For border)
    stats_and_image_container.pack(side='top', anchor='ne', pady=1)  # Pack container at the top


    stats_below_video = tk.Frame(
        stats_and_image_container  # Parent is now the container
        #bg='systemButtonFace'
    )
    stats_below_video.pack(side='left', anchor='ne', fill='both', padx=6, expand=False) # Pack to the LEFT inside the container, FILL and EXPAND


    image_display_frame = tk.Frame(
        stats_and_image_container,  # Parent is now the container
        bg='black',  # Black background when empty
        width=112*1.65,   #  9:16 aspect ratio, scaled down (e.g., 112.5 x 200)
        height=200*1.65  #  Adjust as needed, maintaining 9:16
    )
    image_display_frame.pack(
        side='right',  # Pack to the RIGHT inside the container
        anchor='ne',    # Anchor to the north-east (top-right relative to container)
        pady=(0,0), # Some vertical padding
        padx=(1,0),

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

    # Add check screen button OVER the image display frame
    check_screen_btn = tk.Button(
        image_display_frame, # Parent is the image frame
        text="Check Screen",
        command=lambda cn=computer_name: interface_builder.app.network_handler.send_request_screenshot_command(cn, True),
        cursor="hand2",
        # Consider making the button smaller or using an icon
        bg="lightblue",
        fg="black"
    )
    # Place the button in the top-right corner of the image frame
    check_screen_btn.place(relx=1.0, rely=0.0, anchor='ne', x=-5, y=5)

    # --- Create a container for video and controls, anchored below stats/image ---
    video_controls_container = tk.Frame(
        right_panel,
        bg=right_panel.cget('bg'), # Match parent background
        bd=1,
        relief='solid'
    )
    video_controls_container.pack(
        side='top',  # Changed from 'top' to 'bottom' to place it below stats
        anchor='ne',    # Maintain top-right anchor
        expand=False,
        fill='none',
        pady=(13, 0)
    )
    # -------------------------------------------------------------------

    # Control frame for camera and audio buttons
    # Place this BEFORE the video frame code to ensure it appears above
    control_frame = tk.Frame(
        video_controls_container, # *** PARENT IS NOW video_controls_container ***
        bg='systemButtonFace',
        height=32  # Fixed height
    )
    control_frame.pack(
        side='bottom',      # Pack at top of the container
        fill='x',        # Fill horizontal space of the container
        pady=0,          # Vertical padding
        anchor='se',      # Anchor contents to top-right within the container
        #before=video_frame # No longer needed, packing order handles this
    )
    control_frame.pack_propagate(False)  # Prevent height collapse

    # Video feed panel
    video_frame = tk.Frame(
        video_controls_container, # *** PARENT IS NOW video_controls_container ***
        bg='black',
        width=300,      # Reduced from 500
        height=225      # Reduced from 375
    )
    video_frame.pack(
        side='top',      # Pack below controls within the container
        expand=False,   # Don't expand
        pady=0,         # Slight vertical padding
        anchor='ne'      # Anchor to top-right within the container
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

    # Determine initial state of speak_btn
    initial_speak_btn_image = enable_mic_icon
    initial_speak_btn_text = "Enable Microphone"
    initial_speak_btn_state = 'disabled' # Default to disabled

    is_audio_active = interface_builder.audio_active.get(computer_name, False)
    is_aib_speaking = interface_builder.speaking.get(computer_name, False)

    if is_audio_active:
        initial_speak_btn_state = 'normal'
        if is_aib_speaking:
            # Audio is active AND interface_builder thinks it's speaking
            # Check if audio_client also thinks it's speaking (more robust)
            ac = interface_builder.audio_clients.get(computer_name)
            if ac and ac.speaking: # ac.speaking is AudioClient's internal flag
                initial_speak_btn_image = disable_mic_icon
                initial_speak_btn_text = "Disable Microphone"
            else:
                # Discrepancy or AC not speaking, ensure AIB flag is corrected
                if ac: # if ac exists but not speaking
                    interface_builder.speaking[computer_name] = False
                # Keep button as "Enable Microphone"
                initial_speak_btn_image = enable_mic_icon
                initial_speak_btn_text = "Enable Microphone"
        else:
            # Audio is active but not speaking
            initial_speak_btn_image = enable_mic_icon
            initial_speak_btn_text = "Enable Microphone"
    else:
        # Audio is not active, button should be disabled and show "Enable Microphone"
        initial_speak_btn_state = 'disabled'
        initial_speak_btn_image = enable_mic_icon
        initial_speak_btn_text = "Enable Microphone"


    speak_btn = tk.Button(
        control_frame,
        image=initial_speak_btn_image if initial_speak_btn_image else None,
        text="" if initial_speak_btn_image else initial_speak_btn_text,
        command=lambda: interface_builder.toggle_speaking(computer_name),
        state=initial_speak_btn_state,
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


    # --- START: Microphone Device Selector Button ---
    mic_control_frame = tk.Frame(control_frame, bg='systemButtonFace')
    mic_control_frame.pack(side='left', padx=(10, 5))

    # Button to open device selection popup
    mic_select_button = tk.Button(
        mic_control_frame,
        text="Mic: Default", # Initial text, will be updated
        font=('Arial', 8),
        command=lambda cn=computer_name: show_audio_device_popup(interface_builder, cn),
        cursor="hand2",
        width=18, # Adjust width as needed
        anchor='w' # Align text left
    )
    mic_select_button.pack(side='top', pady=(0,0)) # Add some top padding
    interface_builder.stats_elements['mic_select_button'] = mic_select_button # Store reference
    # --- END: Microphone Device Selector Button ---

    # Store buttons in stats_elements
    interface_builder.stats_elements['camera_btn'] = camera_btn
    interface_builder.stats_elements['listen_btn'] = listen_btn
    interface_builder.stats_elements['speak_btn'] = speak_btn

    # ===========================================
    # Video Solutions Section
    # ===========================================
    video_solutions_frame = tk.LabelFrame(left_panel, text="Video Solutions (Work in progress, videos not recorded yet!)", fg='black', font=('Arial', 9, 'bold'), labelanchor='nw')
    video_solutions_frame.pack(fill='x', pady=3)

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
    # Create a horizontal container for hint info and other controls
    bottom_controls_container = tk.Frame(left_panel)
    bottom_controls_container.pack(fill='x', pady=10, side='bottom', anchor='sw')

    # Frame for hint info (left side)
    hint_info_frame = tk.Frame(bottom_controls_container)
    hint_info_frame.pack(side='left', fill='y', padx=10, anchor='sw')

    # Frame for other controls (right side)
    other_controls_frame = tk.Frame(bottom_controls_container, borderwidth=1, relief='solid')
    other_controls_frame.pack(side='right', fill='y', anchor='se')
    interface_builder.stats_elements['other_controls_frame'] = other_controls_frame

    # Use a canvas + frame for scrollable area
    hint_scroll_canvas = tk.Canvas(hint_info_frame, width=140, height=300, highlightthickness=0)
    hint_scroll_canvas.pack(side='left', expand=False, padx=2, pady=0)
    hint_scrollbar = ttk.Scrollbar(hint_info_frame, orient='vertical', command=hint_scroll_canvas.yview)
    #hint_scrollbar.pack(side='right', fill='y')
    hint_scroll_canvas.configure(yscrollcommand=hint_scrollbar.set)
    # Create a frame inside the canvas
    hint_scroll_frame = tk.Frame(hint_scroll_canvas)
    hint_scroll_frame_id = hint_scroll_canvas.create_window((0, 0), window=hint_scroll_frame, anchor='nw')
    # Update scrollregion when contents change
    def _on_hint_frame_configure(event):
        hint_scroll_canvas.configure(scrollregion=hint_scroll_canvas.bbox('all'))
    hint_scroll_frame.bind('<Configure>', _on_hint_frame_configure)
    # Limit max height
    def _on_canvas_configure(event):
        hint_scroll_canvas.itemconfig(hint_scroll_frame_id, width=event.width)
    hint_scroll_canvas.bind('<Configure>', _on_canvas_configure)

    # Add labels for currently displayed hint text and image to the scrollable frame
    interface_builder.stats_elements['current_hint_text_label'] = tk.Label(
        hint_scroll_frame,
        text="",
        font=('Arial', 9, 'italic'),
        fg='#333333',
        anchor='w',
        justify='left',
        wraplength=100,
        #height=5  # About 2 lines tall
    )
    interface_builder.stats_elements['current_hint_text_label'].pack(fill='x', padx=8, pady=(2,0), anchor='w')

    interface_builder.stats_elements['current_hint_image_label'] = tk.Label(
        hint_scroll_frame,
        text="",
        font=('Arial', 9, 'italic'),
        fg='#333333',
        anchor='w',
        justify='left',
        wraplength=200,
        #height=1  # About 1 line tall
    )
    interface_builder.stats_elements['current_hint_image_label'].pack(fill='x', padx=8, pady=(0,4), anchor='w')

    # Common button width for all buttons in this section
    button_width = 20

    # Add clear hints button
    clear_hints_btn = tk.Button(
        other_controls_frame,
        text="Clear Hints",
        command=lambda: interface_builder.clear_kiosk_hints(computer_name),
        cursor="hand2",
        width=button_width,
        bg='#ff8c4a',
        fg='white'
    )
    clear_hints_btn.pack(side='top', pady=6, padx=20)

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
        other_controls_frame,
        text="Play Hint Sound ",
        image=hint_sound_icon if hint_sound_icon else None,
        compound=tk.RIGHT,
        command=lambda: interface_builder.play_hint_sound(computer_name),
        cursor="hand2",
        width=button_width + 120
    )
    if hint_sound_icon:
        play_sound_btn.image = hint_sound_icon
    play_sound_btn.pack(side='top', pady=6)

    # Add offer assistance button with icon
    offer_assistance_btn = tk.Button(
        other_controls_frame,
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
        cursor="hand2",
        width=button_width + 120
    )
    if assistance_icon:
        offer_assistance_btn.image = assistance_icon
    offer_assistance_btn.pack(side='top', pady=6)

    # Add reset button with confirmation behavior (Restoring this block)
    reset_btn = tk.Button(
        other_controls_frame,
        text="Reset Kiosk",
        bg='#7897bf',
        fg='white',
        cursor="hand2",
        width=button_width
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
                
                # Clear auto-reset countdown in dropdown if present
                if computer_name in interface_builder.connected_kiosks and 'dropdown' in interface_builder.connected_kiosks[computer_name]:
                    dropdown = interface_builder.connected_kiosks[computer_name]['dropdown']
                    dropdown.set('')

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
    reset_btn.pack(side='top', pady=6)

    # Sound controls container 
    sound_container = tk.Frame(other_controls_frame)
    sound_container.pack(fill='x', pady=5)

    # --- Music Volume Controls ---
    music_volume_frame = tk.Frame(sound_container)
    music_volume_frame.pack(pady=2)
    
    interface_builder.stats_elements['music_volume_label'] = tk.Label(
        music_volume_frame,
        text="Music Volume: -/10", # Initial text
        font=('Arial', 9)
    )
    interface_builder.stats_elements['music_volume_label'].pack(side='left', padx=(0, 5))

    music_vol_down_btn = tk.Button(
        music_volume_frame, text="ᐁ", font=('Arial', 8), width=2,
        command=lambda cn=computer_name: interface_builder.change_music_volume(cn, -1),
        cursor="hand2"
    )
    music_vol_down_btn.pack(side='left')
    
    music_vol_up_btn = tk.Button(
        music_volume_frame, text="ᐃ", font=('Arial', 8), width=2,
        command=lambda cn=computer_name: interface_builder.change_music_volume(cn, 1),
        cursor="hand2"
    )
    music_vol_up_btn.pack(side='left', padx=(2,0))
    
    # --- Hint Volume Controls ---
    hint_volume_frame = tk.Frame(sound_container)
    hint_volume_frame.pack(pady=2)

    interface_builder.stats_elements['hint_volume_label'] = tk.Label(
        hint_volume_frame,
        text="Hint Volume: -/10", # Initial text
        font=('Arial', 9)
    )
    interface_builder.stats_elements['hint_volume_label'].pack(side='left', padx=(0, 5))

    hint_vol_down_btn = tk.Button(
        hint_volume_frame, text="ᐁ", font=('Arial', 8), width=2,
        command=lambda cn=computer_name: interface_builder.change_hint_volume(cn, -1),
        cursor="hand2"
    )
    hint_vol_down_btn.pack(side='left')

    hint_vol_up_btn = tk.Button(
        hint_volume_frame, text="ᐃ", font=('Arial', 8), width=2,
        command=lambda cn=computer_name: interface_builder.change_hint_volume(cn, 1),
        cursor="hand2"
    )
    hint_vol_up_btn.pack(side='left', padx=(2,0))

    # Add "Issue Warning:" label (existing)
    tk.Label(
        sound_container,
        text="Issue Warning:",
        anchor='e'
    ).pack(side='top', pady=(10,2)) # Added more top padding to separate from volume controls

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
        width=button_width
    )
    warning_dropdown.pack(side='top', pady=2)

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

    # Create frame for vertical layout with a darker grey background
    stats_vertical_frame = tk.Frame(
        stats_below_video,
        #bg='#E0E0E0',  # Slightly darker grey
        padx=2,
        pady=0,
        #borderwidth=1,
        #relief='solid' # For border
    )
    stats_vertical_frame.pack(side='left', padx=(0,2), pady=0, fill='x', expand=True, anchor='e')  # Crucial: fill='x' here, and expand = True

    stats_panel_ypadding = 18

    # Time to Completion (TTC) label
    interface_builder.stats_elements['ttc_label'] = tk.Label(
        stats_vertical_frame,
        text="Escape Time:\n--:--",
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
        text=f"Hints Requested:\n{current_hints}",
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
        text=f"Hints Received:\n{current_hints_received}",
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

    # --- Set Initial Device Label (on the button) --- 
    initial_audio_client = interface_builder.audio_clients.get(computer_name)
    # Get the button reference
    mic_button = interface_builder.stats_elements.get('mic_select_button') 

    if mic_button: # Ensure the button widget exists
        current_device_name = "Error"
        selected_index = None
        try:
            if initial_audio_client:
                # Client exists, use its info
                devices = initial_audio_client.get_input_devices() # This also sets default if None
                selected_index = initial_audio_client.selected_input_device_index
                current_device_name = "Default" # Fallback
                if devices and selected_index is not None:
                    for dev in devices:
                        if dev['index'] == selected_index:
                            current_device_name = dev['name']
                            break
            else:
                # Client doesn't exist, get system default (best effort)
                temp_audio = None
                try:
                    temp_audio = pyaudio.PyAudio()
                    default_info = temp_audio.get_default_input_device_info()
                    selected_index = default_info['index']
                    current_device_name = default_info['name']
                    # Store this as the preference if no client exists yet
                    interface_builder.preferred_audio_device_index[computer_name] = selected_index
                except Exception as e:
                    print(f"[stats panel] Could not get default audio device info: {e}")
                    current_device_name = "Default (Unknown)"
                finally:
                    if temp_audio:
                        temp_audio.terminate()

            # Limit display name length
            max_len = 15
            display_name = (current_device_name[:max_len] + '...') if len(current_device_name) > max_len else current_device_name
            # Update the button text
            mic_button.config(text=f"Mic: {display_name}", width=100)
            mic_button.pack(side='right', padx=(50,0), anchor='e')

        except Exception as e:
            print(f"[stats panel] Error setting initial mic label for {computer_name}: {e}")
            # Update the button text on error
            mic_button.config(text=f"Mic: Error") 
    # -------------------------------------------------


# --- START: Helper functions for volume meter and device selection ---

def update_volume_meter(interface_builder, computer_name):
     # THIS FUNCTION IS NO LONGER USED (Volume meter moved to popup)
     pass

def show_audio_device_popup(interface_builder, computer_name):
    """Shows a popup to select the audio input device with live volume preview."""
    # Use the dictionary to get the correct network audio client (if it exists)
    network_audio_client = interface_builder.audio_clients.get(computer_name)
    temp_audio_instance = None
    popup_stream = None
    popup_after_id = None
    devices = []
    selected_device_index_at_start = None
    can_set_device_directly = network_audio_client is not None

    # --- Audio parameters for popup preview ---
    CHUNK = 1024
    FORMAT = pyaudio.paFloat32
    CHANNELS = 1
    RATE = 44100
    # -----------------------------------------

    # --- Function to calculate volume (mirrors AudioClient._calculate_volume) ---
    # We define it here to avoid dependency loops if AudioClient needs setup_stats_panel
    def _calculate_popup_volume(data):
        try:
            audio_data = np.frombuffer(data, dtype=np.float32)
            rms = np.sqrt(np.mean(audio_data**2))
            if rms > 0:
                scaled_rms = rms * 8 # Sensitivity adjustment (matches AudioClient)
                db_volume = 20 * math.log10(scaled_rms + 1e-9)
                min_db = -40 # Sensitivity adjustment (matches AudioClient)
                max_db = 0
                normalized_volume = max(0.0, min(1.0, (db_volume - min_db) / (max_db - min_db)))
            else:
                normalized_volume = 0.0
            return normalized_volume
        except Exception as vol_e:
            print(f"[stats panel popup]Error calculating volume: {vol_e}")
            return 0.0
    # ----------------------------------------------------------------------

    try:
        # Need a PyAudio instance regardless to list devices and potentially open stream
        temp_audio_instance = pyaudio.PyAudio()

        # Get device list
        for i in range(temp_audio_instance.get_device_count()):
            dev_info = temp_audio_instance.get_device_info_by_index(i)
            if dev_info['maxInputChannels'] > 0:
                devices.append({'index': i, 'name': dev_info['name']})

        if not devices:
             raise Exception("No input audio devices found on the system.")

        # Determine initially selected device index
        if network_audio_client:
            selected_device_index_at_start = network_audio_client.selected_input_device_index
        else:
            selected_device_index_at_start = interface_builder.preferred_audio_device_index.get(computer_name)

        if selected_device_index_at_start is None:
            try:
                default_info = temp_audio_instance.get_default_input_device_info()
                selected_device_index_at_start = default_info['index']
            except Exception:
                print("[stats panel] Could not get default device index.")
                selected_device_index_at_start = devices[0]['index'] # Fallback

    except Exception as e:
        print(f"[stats panel] Error initializing popup/getting devices: {e}")
        tk.messagebox.showerror("Error", f"Could not retrieve audio devices.\nError: {e}", parent=interface_builder.app.root)
        if temp_audio_instance:
            temp_audio_instance.terminate()
        return

    # --- Create Popup Window --- 
    popup = tk.Toplevel(interface_builder.app.root)
    popup.title(f"Select Mic & Preview - {computer_name}")
    popup.geometry("450x400") # Wider and taller for volume meter
    popup.transient(interface_builder.app.root)
    popup.grab_set()

    tk.Label(popup, text="Select an input device (Live Preview):", font=('Arial', 10)).pack(pady=(10,2))

    listbox = tk.Listbox(popup, exportselection=False, width=60, height=8)
    listbox.pack(pady=5, padx=10)

    # --- Volume Meter --- 
    volume_label = tk.Label(popup, text="Volume:")
    volume_label.pack(pady=(5,0))
    volume_meter_popup = ttk.Progressbar(
        popup,
        orient='horizontal',
        length=300, # Longer bar
        mode='determinate',
        style="popup.green.Horizontal.TProgressbar" # Different style name
    )
    volume_meter_popup.pack(pady=(2, 10))
    # Apply custom style for green progress bar
    style_popup = ttk.Style()
    style_popup.configure("popup.green.Horizontal.TProgressbar", troughcolor='grey', background='green')
    # -------------------

    current_selection_list_index = -1

    for i, device in enumerate(devices):
        max_len_list = 50
        device_name = device['name']
        display_name_list = (device_name[:max_len_list] + '...') if len(device_name) > max_len_list else device_name
        listbox_entry = f"{display_name_list} (Index: {device['index']})"
        listbox.insert(tk.END, listbox_entry)

        if device['index'] == selected_device_index_at_start:
            listbox.itemconfig(i, {'bg':'lightblue'})
            listbox.selection_set(i)
            listbox.see(i)
            current_selection_list_index = i

    # --- Live Preview Functions --- 
    preview_state = {'stream': None, 'after_id': None, 'device_index': None}

    def stop_preview_stream():
        nonlocal preview_state
        if preview_state['after_id']:
            popup.after_cancel(preview_state['after_id'])
            preview_state['after_id'] = None
        if preview_state['stream']:
            try:
                if preview_state['stream'].is_active():
                     preview_state['stream'].stop_stream()
                preview_state['stream'].close()
                print(f"[stats panel popup] Closed preview stream for index {preview_state['device_index']}")
            except Exception as e:
                print(f"[stats panel popup] Error stopping preview stream: {e}")
            preview_state['stream'] = None
        if volume_meter_popup:
             volume_meter_popup['value'] = 0

    def update_popup_volume_meter():
        nonlocal preview_state
        if preview_state['stream'] and preview_state['stream'].is_active() and volume_meter_popup.winfo_exists():
            try:
                data = preview_state['stream'].read(CHUNK, exception_on_overflow=False)
                volume = _calculate_popup_volume(data)
                volume_meter_popup['value'] = volume * 100
                # Schedule next update only if stream is still supposed to be active
                if preview_state['stream'] and preview_state['stream'].is_active():
                    preview_state['after_id'] = popup.after(50, update_popup_volume_meter) # Faster update for preview
                else:
                     volume_meter_popup['value'] = 0
            except Exception as e:
                 print(f"[stats panel popup] Error reading/updating volume: {e}")
                 volume_meter_popup['value'] = 0
                 stop_preview_stream() # Stop on error
        else:
             if volume_meter_popup.winfo_exists():
                 volume_meter_popup['value'] = 0
             # Ensure loop doesn't restart if stream died
             if preview_state['after_id']:
                 popup.after_cancel(preview_state['after_id'])
                 preview_state['after_id'] = None
             preview_state['stream'] = None # Mark stream as dead

    def start_preview_stream(device_index):
        nonlocal preview_state, temp_audio_instance
        stop_preview_stream() # Stop previous one first

        if device_index is None:
             print("[stats panel popup] No device index to start preview stream.")
             return

        print(f"[stats panel popup] Starting preview stream for device index: {device_index}")
        try:
            # Ensure PyAudio instance exists
            if not temp_audio_instance:
                 temp_audio_instance = pyaudio.PyAudio()

            preview_state['stream'] = temp_audio_instance.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
                input_device_index=device_index
            )
            preview_state['device_index'] = device_index
            preview_state['stream'].start_stream()
            update_popup_volume_meter() # Start the update loop
        except Exception as e:
            print(f"[stats panel popup] Failed to start preview stream for index {device_index}: {e}")
            tk.messagebox.showwarning("Preview Error", f"Could not start audio preview for the selected device.\nError: {e}", parent=popup)
            stop_preview_stream()

    def on_listbox_select(event):
        selected_indices = listbox.curselection()
        if selected_indices:
            selected_list_index = selected_indices[0]
            selected_device_info = devices[selected_list_index]
            selected_device_index_from_popup = selected_device_info['index']
            if selected_device_index_from_popup != preview_state['device_index']:
                 start_preview_stream(selected_device_index_from_popup)

    listbox.bind('<<ListboxSelect>>', on_listbox_select)
    # --------------------------

    def on_ok():
        nonlocal network_audio_client # Allow modification
        stop_preview_stream() # Stop preview before applying changes

        selected_indices = listbox.curselection()
        if selected_indices:
            selected_list_index = selected_indices[0]
            selected_device_info = devices[selected_list_index]
            selected_device_index_from_popup = selected_device_info['index']
            selected_device_name = selected_device_info['name']

            print(f"[stats panel] OK selected device: {selected_device_name} (Index: {selected_device_index_from_popup})")

            max_len = 15
            display_name_label = (selected_device_name[:max_len] + '...') if len(selected_device_name) > max_len else selected_device_name
            # Get the button reference to update its text
            mic_button_to_update = interface_builder.stats_elements.get('mic_select_button') 

            if can_set_device_directly:
                if selected_device_index_from_popup != network_audio_client.selected_input_device_index:
                    try:
                        network_audio_client.set_input_device(selected_device_index_from_popup)
                        # Update the button text
                        if mic_button_to_update: 
                             mic_button_to_update.config(text=f"Mic: {display_name_label}")
                        print(f"[stats panel] Mic device for {computer_name} set to index {selected_device_index_from_popup}")
                    except Exception as e:
                        print(f"[stats panel] Error setting device for {computer_name}: {e}")
                        tk.messagebox.showerror("Error", f"Failed to set audio device.\nError: {e}", parent=popup)
                        start_preview_stream(selected_device_index_from_popup) # Restart preview on error
                        return
                else:
                    print(f"[stats panel] No change in device selection for {computer_name}.")
            else:
                print(f"[stats panel] Storing preferred device index {selected_device_index_from_popup} for {computer_name}")
                interface_builder.preferred_audio_device_index[computer_name] = selected_device_index_from_popup
                 # Update the button text even if storing preference
                if mic_button_to_update: 
                     mic_button_to_update.config(text=f"Mic: {display_name_label}")

            close_popup()
        else:
            tk.messagebox.showwarning("Selection Required", "Please select a device.", parent=popup)
            # Restart preview with original selection if nothing chosen
            start_preview_stream(selected_device_index_at_start)

    def on_cancel():
        close_popup()

    def close_popup():
        nonlocal temp_audio_instance
        stop_preview_stream()
        if temp_audio_instance:
             try:
                 temp_audio_instance.terminate()
                 print("[stats panel popup] Terminated temporary PyAudio instance.")
             except Exception as e:
                  print(f"[stats panel popup] Error terminating PyAudio: {e}")
             temp_audio_instance = None
        popup.destroy()

    # Handle window close button
    popup.protocol("WM_DELETE_WINDOW", close_popup)

    # --- Buttons --- 
    button_frame = tk.Frame(popup)
    button_frame.pack(pady=10)
    ok_button = tk.Button(button_frame, text="OK", width=10, command=on_ok)
    ok_button.pack(side='left', padx=5)
    cancel_button = tk.Button(button_frame, text="Cancel", width=10, command=on_cancel)
    cancel_button.pack(side='left', padx=5)
    # ---------------

    # Select the initial device in the listbox
    if current_selection_list_index != -1:
        listbox.selection_set(current_selection_list_index)
        listbox.activate(current_selection_list_index)
        # Start initial preview
        start_preview_stream(selected_device_index_at_start)
    else:
        print("[stats panel popup] No initial device selected in listbox.")

    popup.wait_window()


# --- END: Helper functions --- 