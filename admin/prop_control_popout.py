# prop_control_popout.py
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import os
import time

class PropControlPopout:
    def __init__(self, parent_toplevel, main_prop_control, room_number):
        self.parent_toplevel = parent_toplevel
        self.main_pc = main_prop_control  # Reference to the main PropControl
        self.room_number = room_number
        self.popout_props = {} # prop_id -> { 'frame', 'status_label', 'name_label', 'info' }

        self.setup_ui()
        self.load_icons() # Load icons specific to popout or reuse from main_pc
        self.load_flagged_prop_image() # Load flagged image specific to popout or reuse from main_pc
        self.initialize_popout_props()

    def setup_ui(self):
        self.frame = ttk.Frame(self.parent_toplevel)
        self.frame.pack(fill='both', expand=True)

        # Title for the popout window
        room_name = self.main_pc.ROOM_MAP.get(self.room_number, f"Room {self.room_number}")
        title_label = ttk.Label(self.frame, text=f"Prop Status: {room_name}", font=('Arial', 10, 'bold'))
        #title_label.pack(fill='x', pady=(5, 5))

        self.canvas = tk.Canvas(self.frame)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.props_frame = ttk.Frame(self.canvas)
        self.canvas_frame = self.canvas.create_window((0,0), window=self.props_frame, anchor="nw")

        self.props_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        self.parent_toplevel.title(f"{room_name}")
        self.parent_toplevel.protocol("WM_DELETE_WINDOW", self.on_close)

        # Apply styles from main PropControl, if they are defined
        # This assumes ttk.Style() is shared or styles are applied globally by the main app
        style = ttk.Style()
        # Ensure styles are configured, if not already by the main app
        if 'Circuit.TFrame' not in style.theme_names() and 'Circuit.TFrame' not in style.layout('TFrame'):
             style.configure('Circuit.TFrame', background='#ffe6e6', borderwidth=2, relief='solid')
             style.configure('Circuit.TLabel', background='#ffe6e6', font=('Arial', 8, 'bold'))
             style.configure('Cousin.TFrame', background='#e6ffe6', borderwidth=2, relief='solid')
             style.configure('Cousin.TLabel', background='#e6ffe6', font=('Arial', 8, 'bold'))

    def load_icons(self):
        # Prefer to get icons from main PropControl to avoid re-loading if already loaded
        if hasattr(self.main_pc, 'status_icons') and self.main_pc.status_icons:
            self.status_icons = self.main_pc.status_icons
        else:
            # Fallback: load icons if main_pc hasn't loaded them yet
            try:
                icon_dir = os.path.join("admin_icons")
                self.status_icons = {
                    'not_activated': ImageTk.PhotoImage(
                        Image.open(os.path.join(icon_dir, "not_activated.png")).resize((16, 16), Image.Resampling.LANCZOS)
                    ),
                    'activated': ImageTk.PhotoImage(
                        Image.open(os.path.join(icon_dir, "activated.png")).resize((16, 16), Image.Resampling.LANCZOS)
                    ),
                    'finished': ImageTk.PhotoImage(
                        Image.open(os.path.join(icon_dir, "finished.png")).resize((16, 16), Image.Resampling.LANCZOS)
                    ),
                    'offline': ImageTk.PhotoImage(
                        Image.open(os.path.join(icon_dir, "offline.png")).resize((16, 16), Image.Resampling.LANCZOS)
                    )
                }
            except Exception as e:
                print(f"[prop control popout]Error loading status icons: {e}")
                self.status_icons = None

    def load_flagged_prop_image(self):
        # Prefer to get flagged image from main PropControl
        if hasattr(self.main_pc, 'flagged_prop_image') and self.main_pc.flagged_prop_image:
            self.flagged_prop_image = self.main_pc.flagged_prop_image
        else:
            # Fallback: load if main_pc hasn't loaded it
            try:
                icon_dir = os.path.join("admin_icons")
                self.flagged_prop_image = ImageTk.PhotoImage(
                    Image.open(os.path.join(icon_dir, "flagged_prop.png")).resize((16, 16), Image.Resampling.LANCZOS)
                )
            except Exception as e:
                print(f"[prop control popout] Error loading flagged prop image: {e}")
                self.flagged_prop_image = None

    def initialize_popout_props(self):
        # Populate initial state from main PropControl's all_props for this room
        # Create copies of data to avoid modifying main_pc's internal structures
        if self.room_number in self.main_pc.all_props:
            for prop_id, prop_data in self.main_pc.all_props[self.room_number].items():
                self.update_prop_display(prop_id, prop_data['info'].copy()) # Pass a copy of 'info'
        self.sort_and_repack_props() # Initial sort

    def update_prop_display(self, prop_id, prop_data_info):
        """
        Receives updated prop_data_info from the main PropControl and updates
        the popout's display for that prop.
        """
        # Ensure prop_data_info is a dictionary
        if not isinstance(prop_data_info, dict):
            print(f"[prop control popout]Received invalid prop_data_info for prop {prop_id}: {prop_data_info}")
            return

        mapped_name = self.main_pc.get_mapped_prop_name(prop_data_info.get("strName", ""), self.room_number)
        order = self.main_pc.get_prop_order(prop_data_info.get("strName", ""), self.room_number)

        try:
            if prop_id not in self.popout_props:
                # Create new prop widgets for the popout
                prop_frame = ttk.Frame(self.props_frame)
                prop_frame.pack(fill='x', pady=1) # Initial pack, will be resorted

                # Name label (no buttons)
                name_label = ttk.Label(prop_frame, font=('Arial', 8, 'bold'), text=mapped_name)
                name_label.pack(side='left', padx=5) # Left-aligned for popout

                # Bind hover events for highlighting
                prop_name_for_hover = prop_data_info.get("strName", "")
                if prop_name_for_hover:
                    name_label.bind('<Enter>', lambda e, name=prop_name_for_hover: self.highlight_cousin_props(name, True))
                    name_label.bind('<Leave>', lambda e, name=prop_name_for_hover: self.highlight_cousin_props(name, False))

                # Formatting for finishing/standby props
                if self.main_pc.is_finishing_prop(self.room_number, prop_data_info.get('strName', '')):
                    name_label.config(font=('Arial', 8, 'bold', 'italic', 'underline'))
                    line_label = tk.Frame(prop_frame, height=1, bg="black")
                    line_label.pack(fill='x', padx=(5,0), pady=(0, 2), side='bottom')
                elif self.main_pc.is_standby_prop(self.room_number, prop_data_info.get('strName', '')):
                    name_label.config(font=('Arial', 8, 'italic'))
                else:
                    name_label.config(font=('Arial', 8, 'bold'))

                # Status label (icon)
                status_label = tk.Label(prop_frame)
                status_label.pack(side='right', padx=5) # Right-aligned

                self.popout_props[prop_id] = {
                    'frame': prop_frame,
                    'name_label': name_label,
                    'status_label': status_label,
                    'info': prop_data_info, # Store info directly
                    'order': order
                }
                self.sort_and_repack_props()

            else:
                # Update existing prop info
                prop_entry = self.popout_props[prop_id]
                prop_entry['info'] = prop_data_info
                prop_entry['order'] = order

                if prop_entry['name_label'].winfo_exists():
                    prop_entry['name_label'].config(text=mapped_name)
                    # Update formatting on existing label
                    if self.main_pc.is_finishing_prop(self.room_number, prop_data_info.get('strName', '')):
                        prop_entry['name_label'].config(font=('Arial', 8, 'bold', 'italic', 'underline'))
                    elif self.main_pc.is_standby_prop(self.room_number, prop_data_info.get('strName', '')):
                        prop_entry['name_label'].config(font=('Arial', 8, 'italic'))
                    else:
                        prop_entry['name_label'].config(font=('Arial', 8, 'bold'))

            self._update_prop_status_icon(prop_id)

        except tk.TclError as e:
            print(f"[prop control popout]Widget error updating prop {prop_id}: {e}")
            if prop_id in self.popout_props:
                for key in ['name_label', 'status_label', 'frame']:
                    if key in self.popout_props[prop_id]:
                        # Clean up destroyed widgets references
                        if key == 'frame' and self.popout_props[prop_id][key].winfo_exists():
                            self.popout_props[prop_id][key].destroy()
                        del self.popout_props[prop_id][key]
        except Exception as e:
            print(f"[prop control popout]Error in update_prop_display for prop {prop_id}: {e}")
            import traceback
            traceback.print_exc()


    def _update_prop_status_icon(self, prop_id):
        if prop_id not in self.popout_props:
            return

        prop = self.popout_props[prop_id]
        if 'status_label' not in prop or not prop['status_label'].winfo_exists():
            return

        current_time = time.time()
        main_pc_last_updates = self.main_pc.last_mqtt_updates.get(self.room_number, {})

        is_offline = (self.room_number not in self.main_pc.last_mqtt_updates or
                      prop_id not in main_pc_last_updates or
                      current_time - main_pc_last_updates.get(prop_id, 0) > 3)

        if is_offline:
            icon = self.status_icons['offline']
        else:
            status_text = prop['info']['strStatus']
            if status_text == "Not activated" or status_text == "Not Activated":
                icon = self.status_icons['not_activated']
            elif status_text == "Activated":
                icon = self.status_icons['activated']
            elif status_text == "Finished":
                icon = self.status_icons['finished']
            else:
                icon = self.status_icons['not_activated']

        # Check if prop is flagged (using main PropControl's flag state)
        is_flagged = (self.room_number in self.main_pc.flagged_props and
                      prop_id in self.main_pc.flagged_props[self.room_number] and
                      self.main_pc.flagged_props[self.room_number][prop_id])

        if is_flagged and self.flagged_prop_image:
            composite_image = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
            try:
                background_image = ImageTk.getimage(icon).convert("RGBA")
                flag_image = ImageTk.getimage(self.flagged_prop_image).convert("RGBA")

                composite_image.paste(flag_image, (0, 0), flag_image)
                composite_image.paste(background_image, (0, 0), background_image)
                combined_icon = ImageTk.PhotoImage(composite_image)
                prop['status_label'].config(image=combined_icon)
                prop['status_label'].image = combined_icon
            except Exception as e:
                print(f"[prop control popout]Error creating composite flagged image for prop {prop_id}: {e}")
                prop['status_label'].config(image=icon)
                prop['status_label'].image = icon
        else:
            prop['status_label'].config(image=icon)
            prop['status_label'].image = icon

    def sort_and_repack_props(self):
        if not self.popout_props:
            return

        # Filter out props whose frames no longer exist
        active_props = {
            pid: pdata for pid, pdata in self.popout_props.items()
            if 'frame' in pdata and pdata['frame'].winfo_exists()
        }
        self.popout_props = active_props # Update the main dict

        sorted_props = sorted(
            self.popout_props.items(),
            key=lambda item: self.main_pc.get_prop_order(item[1]['info']['strName'], self.room_number)
        )

        for prop_id, prop_data in sorted_props:
            if 'frame' in prop_data and prop_data['frame'].winfo_exists():
                try:
                    prop_data['frame'].pack_forget()
                    prop_data['frame'].pack(fill='x', pady=1)
                except tk.TclError as e:
                    print(f"[prop control popout]Error repacking prop {prop_id}: Widget destroyed? {e}")
                    # Remove from self.popout_props if frame destroyed unexpectedly
                    if prop_id in self.popout_props:
                        del self.popout_props[prop_id]

    def highlight_cousin_props(self, prop_name, highlight):
        """Highlight or unhighlight props that are cousins (delegates to main_pc for logic)"""
        cousin = self.main_pc.get_prop_cousin(prop_name)
        if not cousin:
             return

        room_key = self.main_pc.ROOM_MAP.get(self.room_number)
        if not room_key or not hasattr(self.main_pc, 'prop_name_mappings') or \
           room_key not in self.main_pc.prop_name_mappings or \
           'mappings' not in self.main_pc.prop_name_mappings[room_key]:
            return

        cousin_props_names = [
            name for name, info in self.main_pc.prop_name_mappings[room_key]['mappings'].items()
            if info.get('cousin') == cousin
        ]

        for prop_id, prop_data in self.popout_props.items():
            if prop_data['info'].get('strName') in cousin_props_names:
                try:
                    prop_frame = prop_data.get('frame')
                    name_label = prop_data.get('name_label')
                    if prop_frame and prop_frame.winfo_exists() and name_label and name_label.winfo_exists():
                        if highlight:
                            prop_frame.configure(style='Cousin.TFrame')
                            name_label.configure(style='Cousin.TLabel')
                        else:
                            prop_frame.configure(style='TFrame') # Reset to default TFrame style
                            name_label.configure(style='TLabel') # Reset to default TLabel style
                except tk.TclError:
                    continue

    def on_frame_configure(self, event=None):
        if self.canvas.winfo_exists() and self.props_frame.winfo_exists():
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            width = self.canvas.winfo_width()
            self.canvas.itemconfig(self.canvas_frame, width=width)

    def on_canvas_configure(self, event):
        if self.canvas.winfo_exists() and self.props_frame.winfo_exists():
            width = event.width
            self.canvas.itemconfig(self.canvas_frame, width=width)

    def on_close(self):
        """Handle the closing of the popout window."""
        self.main_pc.popout_closed(self.room_number) # Notify main PropControl
        self.parent_toplevel.destroy()