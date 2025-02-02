import tkinter as tk
from tkinter import ttk
import json
from pathlib import Path
import base64
import os

def save_manual_hint(interface_builder):
    """Save the current manual hint to saved_hints.json"""
    if not hasattr(interface_builder, 'selected_kiosk') or not interface_builder.selected_kiosk:
        return
        
    if interface_builder.selected_kiosk not in interface_builder.app.kiosk_tracker.kiosk_assignments:
        return
        
    # Get hint text
    message_text = interface_builder.stats_elements['msg_entry'].get('1.0', 'end-1c') if interface_builder.stats_elements['msg_entry'] else ""
    if not message_text and not interface_builder.current_hint_image:
        return
        
    # Get room number
    room_number = interface_builder.app.kiosk_tracker.kiosk_assignments[interface_builder.selected_kiosk]
    room_str = str(room_number)
    
    # Show dialog to get prop name and hint name
    dialog = tk.Toplevel(interface_builder.app.root)
    dialog.title("Save Hint")
    dialog.transient(interface_builder.app.root)
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
        1: "casino",
        2: "ma",
        5: "haunted",
        4: "zombie",
        6: "atlantis",
        7: "time"
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
        print(f"[hint functions]Error loading prop mappings: {e}")
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
    prop_dropdown.pack(pady=5)
    
    # Add hint name field
    tk.Label(dialog, text="Hint Name:").pack()
    hint_entry = ttk.Entry(dialog, width=30)
    hint_entry.pack(pady=5)
    
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
            print(f"[hint functions]Error loading hints file: {e}")
            data = {"rooms": {}}
        
        # Ensure room and prop structure exists
        if 'rooms' not in data:
            data['rooms'] = {}
        if room_str not in data['rooms']:
            data['rooms'][room_str] = {}
            
        # Get the display name for the prop from mappings
        prop_info = room_props.get(prop_name, {})
        prop_display_name = prop_info.get('display', prop_name)
        
        # Store hints under the display name of the prop
        if prop_display_name not in data['rooms'][room_str]:
            data['rooms'][room_str][prop_display_name] = {}
            
        # Get image filename if present
        image_filename = None
        if hasattr(interface_builder, 'current_image_file') and interface_builder.current_image_file:
            # Just store the filename since we know the path structure
            image_filename = os.path.basename(interface_builder.current_image_file)
                
        # Add hint to data under the prop's display name
        data['rooms'][room_str][prop_display_name][hint_name] = {
            "text": message_text,
            "image": image_filename  # Just store the filename
        }
        
        # Save updated hints file
        try:
            with open(hints_file, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[hint functions]Error saving hints file: {e}")
            tk.messagebox.showerror("Error", "Failed to save hint")
            return
            
        # Close dialog and clear form
        dialog.destroy()
        clear_manual_hint(interface_builder)
        
        # Refresh saved hints panel if it exists
        if hasattr(interface_builder, 'saved_hints'):
            interface_builder.saved_hints.load_hints()
            interface_builder.saved_hints.update_room(room_number)
    
    tk.Button(dialog, text="Save", command=save_hint).pack(pady=10)

def clear_manual_hint(interface_builder):
    """Clear the manual hint entry fields"""
    if interface_builder.stats_elements['msg_entry']:
        interface_builder.stats_elements['msg_entry'].delete('1.0', 'end')
    
    if interface_builder.stats_elements['image_preview']:
        interface_builder.stats_elements['image_preview'].configure(image='')
        interface_builder.stats_elements['image_preview'].image = None
    interface_builder.current_hint_image = None
    
    # Hide the attached image label
    if 'attached_image_label' in interface_builder.stats_elements:
        interface_builder.stats_elements['attached_image_label'].pack_forget()
    
    if interface_builder.stats_elements['send_btn']:
        interface_builder.stats_elements['send_btn'].config(state='disabled')

def send_hint(interface_builder, computer_name, hint_data=None):
    """
    Send a hint to the selected kiosk.
    
    Args:
        interface_builder: The AdminInterfaceBuilder instance
        computer_name: Name of the target computer
        hint_data: Optional dict containing hint data. If None, uses manual entry fields.
    """
    # Validate kiosk assignment
    if not computer_name in interface_builder.app.kiosk_tracker.kiosk_assignments:
        return
            
    if hint_data is None:
        # Using manual entry
        message_text = interface_builder.stats_elements['msg_entry'].get('1.0', 'end-1c') if interface_builder.stats_elements['msg_entry'] else ""
        if not message_text and not interface_builder.current_hint_image:
            return
            
        hint_data = {
            'text': message_text,
            'image': interface_builder.current_hint_image
        }
    
    # Get room number
    room_number = interface_builder.app.kiosk_tracker.kiosk_assignments[computer_name]
    
    # Send the hint
    interface_builder.app.network_handler.send_hint(room_number, hint_data)
    
    # Clear any pending help requests
    if computer_name in interface_builder.app.kiosk_tracker.help_requested:
        interface_builder.app.kiosk_tracker.help_requested.remove(computer_name)
        if computer_name in interface_builder.connected_kiosks:
            interface_builder.connected_kiosks[computer_name]['help_label'].config(text="")
    
    # Clear ALL hint entry fields regardless of which method was used
    if interface_builder.stats_elements['msg_entry']:
        interface_builder.stats_elements['msg_entry'].delete('1.0', 'end')
    
    if interface_builder.stats_elements['image_preview']:
        interface_builder.stats_elements['image_preview'].configure(image='')
        interface_builder.stats_elements['image_preview'].image = None
    interface_builder.current_hint_image = None
    
    # Hide the attached image label
    if 'attached_image_label' in interface_builder.stats_elements:
        interface_builder.stats_elements['attached_image_label'].pack_forget()
    
    if interface_builder.stats_elements['send_btn']:
        interface_builder.stats_elements['send_btn'].config(state='disabled')
        
    # Reset the image prop dropdown
    if hasattr(interface_builder, 'img_prop_var'):
        interface_builder.img_prop_var.set('')
        
    # Also clear saved hints preview if it exists
    if hasattr(interface_builder, 'saved_hints'):
        interface_builder.saved_hints.clear_preview()