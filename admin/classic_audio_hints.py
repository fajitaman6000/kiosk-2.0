import os
import pygame
import tkinter as tk
from tkinter import ttk

class ClassicAudioHints:
    def __init__(self, parent, room_change_callback):
        print("\n=== INITIALIZING CLASSIC AUDIO HINTS ===")  # Debug line
        self.parent = parent
        self.room_change_callback = room_change_callback
        self.current_room = None
        self.current_audio_file = None
        self.audio_root = "audio_hints"
        
        # Initialize pygame mixer for audio playback
        pygame.mixer.init()
        
        # Create main frame with a distinctive border for debugging
        self.frame = ttk.LabelFrame(parent, text="Classic Audio Hints")
        self.frame.pack(fill='x', padx=5, pady=5)
        print("Main frame created and packed")  # Debug line
        
        # Create container for list boxes with light gray background for visibility
        self.list_container = ttk.Frame(self.frame)
        self.list_container.pack(fill='x', padx=5, pady=5)
        print("List container created and packed")  # Debug line
        
        # Create prop listbox with more obvious styling
        self.prop_frame = ttk.Frame(self.list_container)
        self.prop_frame.pack(side='left', fill='both', expand=True)
        prop_label = ttk.Label(self.prop_frame, text="Props:", font=('Arial', 10, 'bold'))
        prop_label.pack(anchor='w')
        self.prop_listbox = tk.Listbox(
            self.prop_frame, 
            height=10,
            selectmode=tk.SINGLE,
            exportselection=False,  # Keep selection visible when switching focus
            bg='white',  # Explicit background color
            fg='black'   # Explicit text color
        )
        self.prop_listbox.pack(fill='both', expand=True)
        self.prop_listbox.bind('<<ListboxSelect>>', self.on_prop_select)
        print("Prop listbox created and packed")  # Debug line
        
        # Create audio file listbox with similar styling
        self.audio_frame = ttk.Frame(self.list_container)
        self.audio_frame.pack(side='left', fill='both', expand=True, padx=(5, 0))
        audio_label = ttk.Label(self.audio_frame, text="Audio Files:", font=('Arial', 10, 'bold'))
        audio_label.pack(anchor='w')
        self.audio_listbox = tk.Listbox(
            self.audio_frame, 
            height=10,
            selectmode=tk.SINGLE,
            exportselection=False,  # Keep selection visible when switching focus
            bg='white',  # Explicit background color
            fg='black'   # Explicit text color
        )
        self.audio_listbox.pack(fill='both', expand=True)
        self.audio_listbox.bind('<<ListboxSelect>>', self.on_audio_select)
        print("Audio listbox created and packed")  # Debug line
        
        # Create control buttons frame (initially hidden)
        self.control_frame = ttk.Frame(self.list_container)
        self.preview_btn = ttk.Button(self.control_frame, text="Preview", command=self.preview_audio)
        self.preview_btn.pack(side='left', padx=5)
        self.send_btn = ttk.Button(self.control_frame, text="Send", command=self.send_audio)
        self.send_btn.pack(side='left', padx=5)
        self.back_btn = ttk.Button(self.control_frame, text="Back", command=self.show_lists)
        self.back_btn.pack(side='left', padx=5)
        print("Control buttons created")  # Debug line
        
        print("=== CLASSIC AUDIO HINTS INITIALIZATION COMPLETE ===\n")  # Debug line

    def update_room(self, room_name):
        """Update the prop list for the selected room with enhanced path checking and logging"""
        print("\n=== AUDIO HINTS UPDATE START ===")
        print(f"Updating room to: {room_name}")
        
        # Store current room and clear existing lists
        self.current_room = room_name
        self.show_lists()
        self.prop_listbox.delete(0, tk.END)
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
                
            # Add props to listbox
            for prop in sorted(props):
                prop_path = os.path.join(room_path, prop)
                print(f"Verifying prop path: {prop_path}")
                print(f"Prop path exists: {os.path.exists(prop_path)}")
                if os.path.exists(prop_path):
                    self.prop_listbox.insert(tk.END, prop)
                    
            print(f"Successfully added {len(props)} props to listbox")
            
        except Exception as e:
            print(f"ERROR reading props: {str(e)}")
            import traceback
            print(traceback.format_exc())
            
        print("=== AUDIO HINTS UPDATE END ===")

    def on_prop_select(self, event):
        """Handle prop selection"""
        self.audio_listbox.delete(0, tk.END)
        selection = self.prop_listbox.curselection()
        
        if not selection:
            return
            
        prop_name = self.prop_listbox.get(selection[0])
        prop_path = os.path.join(self.audio_root, self.current_room, prop_name)
        
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
            
        prop_selection = self.prop_listbox.curselection()
        if not prop_selection:
            return
            
        prop_name = self.prop_listbox.get(prop_selection[0])
        audio_name = self.audio_listbox.get(selection[0])
        
        self.current_audio_file = os.path.join(
            self.audio_root,
            self.current_room,
            prop_name,
            audio_name
        )
        
        # Hide list boxes and show control buttons
        self.show_controls()

    def show_controls(self):
        """Show control buttons and hide list boxes"""
        self.prop_frame.pack_forget()
        self.audio_frame.pack_forget()
        self.control_frame.pack(fill='x', padx=5, pady=5)

    def show_lists(self):
        """Show list boxes and hide control buttons"""
        self.control_frame.pack_forget()
        self.prop_frame.pack(side='left', fill='both', expand=True)
        self.audio_frame.pack(side='left', fill='both', expand=True, padx=(5, 0))
        
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