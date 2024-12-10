import os
import pygame
import tkinter as tk
from tkinter import ttk

class ClassicAudioHints:
    def __init__(self, parent, room_change_callback):
        print("\n=== INITIALIZING CLASSIC AUDIO HINTS ===")
        self.parent = parent
        self.room_change_callback = room_change_callback
        self.current_room = None
        self.current_audio_file = None
        self.audio_root = "audio_hints"
        
        # Initialize pygame mixer for audio playback
        pygame.mixer.init()
        
        # Create main frame with fixed width
        self.frame = ttk.LabelFrame(parent, text="Classic Audio Hints")
        self.frame.pack(fill='x', padx=5, pady=5)
        
        # Create fixed-width inner container
        self.list_container = ttk.Frame(self.frame)
        self.list_container.pack(padx=5, pady=5)  # Remove fill='x' to prevent expansion
        
        # Create prop dropdown section with fixed width
        self.prop_frame = ttk.Frame(self.list_container)
        self.prop_frame.pack(pady=(0, 5))
        prop_label = ttk.Label(self.prop_frame, text="Select Prop:", font=('Arial', 10, 'bold'))
        prop_label.pack(side='left', padx=(0, 5))
        
        # Create prop dropdown (Combobox)
        self.prop_var = tk.StringVar()
        self.prop_dropdown = ttk.Combobox(
            self.prop_frame,
            textvariable=self.prop_var,
            state='readonly',
            width=30
        )
        self.prop_dropdown.pack(side='left')
        self.prop_dropdown.bind('<<ComboboxSelected>>', self.on_prop_select)
        
        # Create audio file section with fixed width
        self.audio_frame = ttk.Frame(self.list_container)
        self.audio_frame.pack(pady=5)  # Remove fill='x' to prevent expansion
        audio_label = ttk.Label(self.audio_frame, text="Audio Files:", font=('Arial', 10, 'bold'))
        audio_label.pack(anchor='w')
        
        # Fixed-width listbox container
        listbox_container = ttk.Frame(self.audio_frame)
        listbox_container.pack()  # No expansion
        
        self.audio_listbox = tk.Listbox(
            listbox_container, 
            height=6,
            width=40,
            selectmode=tk.SINGLE,
            exportselection=False,
            bg='white',
            fg='black'
        )
        self.audio_listbox.pack()  # No expansion
        self.audio_listbox.bind('<<ListboxSelect>>', self.on_audio_select)
        
        # Create control buttons frame (initially hidden)
        self.control_frame = ttk.Frame(self.list_container)
        
        # Add selected file label
        self.selected_file_label = ttk.Label(self.control_frame, font=('Arial', 10))
        self.selected_file_label.pack(side='left', padx=5)
        
        self.preview_btn = ttk.Button(self.control_frame, text="Preview", command=self.preview_audio)
        self.preview_btn.pack(side='left', padx=5)
        self.send_btn = ttk.Button(self.control_frame, text="Send", command=self.send_audio)
        self.send_btn.pack(side='left', padx=5)
        self.back_btn = ttk.Button(self.control_frame, text="Back", command=self.show_lists)
        self.back_btn.pack(side='left', padx=5)
        
        print("=== CLASSIC AUDIO HINTS INITIALIZATION COMPLETE ===\n")

    def update_room(self, room_name):
        """Update the prop list for the selected room with enhanced path checking and logging"""
        print("\n=== AUDIO HINTS UPDATE START ===")
        print(f"Updating room to: {room_name}")
        
        # Store current room and clear existing lists
        self.current_room = room_name
        self.show_lists()
        self.prop_dropdown['values'] = ()  # Clear dropdown
        self.audio_listbox.delete(0, tk.END)
        
        # Get absolute paths
        working_dir = os.getcwd()
        print(f"Current working directory: {working_dir}")
        
        # Construct and verify audio_hints base path
        audio_base = os.path.join(working_dir, self.audio_root)
        print(f"Audio base path: {audio_base}")
        print(f"Audio base exists: {os.path.exists(audio_base)}")
        
        # Construct and verify room path
        room_path = os.path.join(audio_base, room_name)
        print(f"Room path: {room_path}")
        print(f"Room path exists: {os.path.exists(room_path)}")
        
        if not os.path.exists(room_path):
            print("ERROR: Room path does not exist!")
            print(f"Attempted path: {room_path}")
            print("Directory contents at audio_base:")
            if os.path.exists(audio_base):
                print(os.listdir(audio_base))
            return
            
        # Get and verify props
        try:
            props = [d for d in os.listdir(room_path) 
                    if os.path.isdir(os.path.join(room_path, d))]
            print(f"Found props: {props}")
            
            if not props:
                print("No prop directories found!")
                print(f"Contents of room directory:")
                print(os.listdir(room_path))
                return
                
            # Update dropdown with sorted props
            self.prop_dropdown['values'] = sorted(props)
            print(f"Successfully added {len(props)} props to dropdown")
            
        except Exception as e:
            print(f"ERROR reading props: {str(e)}")
            import traceback
            print(traceback.format_exc())
            
        print("=== AUDIO HINTS UPDATE END ===")
        
    def on_prop_select(self, event):
        """Handle prop selection from dropdown"""
        self.audio_listbox.delete(0, tk.END)
        selected_prop = self.prop_var.get()
        
        if not selected_prop:
            return
            
        prop_path = os.path.join(self.audio_root, self.current_room, selected_prop)
        
        if os.path.exists(prop_path):
            audio_files = [f for f in os.listdir(prop_path) 
                        if f.lower().endswith('.mp3')]
            for audio in sorted(audio_files):
                self.audio_listbox.insert(tk.END, audio)

    def on_audio_select(self, event):
        """Handle audio file selection"""
        selection = self.audio_listbox.curselection()
        if not selection:
            return
            
        audio_name = self.audio_listbox.get(selection[0])
        selected_prop = self.prop_var.get()
        
        if not selected_prop:
            return
            
        self.current_audio_file = os.path.join(
            self.audio_root,
            self.current_room,
            selected_prop,
            audio_name
        )
        
        # Update selected file label
        self.selected_file_label.config(text=f"Selected: {audio_name}")
        
        # Show control buttons
        self.show_controls()

    def show_controls(self):
        """Show control buttons and hide lists"""
        self.prop_frame.pack_forget()
        self.audio_frame.pack_forget()
        self.control_frame.pack(pady=5)

    def show_lists(self):
        """Show dropdown and audio list, hide control buttons"""
        self.control_frame.pack_forget()
        self.prop_frame.pack(pady=(0, 5))
        self.audio_frame.pack(pady=5)
        
        # Clear selected file label
        self.selected_file_label.config(text="")
        
        # Stop any playing audio
        pygame.mixer.music.stop()

    def preview_audio(self):
        """Play the selected audio file"""
        if self.current_audio_file and os.path.exists(self.current_audio_file):
            pygame.mixer.music.load(self.current_audio_file)
            pygame.mixer.music.play()

    def send_audio(self):
        """Send the selected audio hint and return to list view"""
        if self.current_audio_file and os.path.exists(self.current_audio_file):
            print(f"Would send audio hint: {self.current_audio_file}")
            # Here you would implement the actual sending logic
            self.show_lists()

    def cleanup(self):
        """Clean up pygame mixer"""
        pygame.mixer.quit()