import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, UnidentifiedImageError, ImageOps
import os
import math

# --- Constants ---
CROP_SIZE = 1200  # Target output size in pixels
CANVAS_BG = "#2B2B2B"
FRAME_COLOR = "red"
FRAME_THICKNESS = 2
# Define the VISUAL size of the red box on the canvas (adjust as needed)
# Option 1: Percentage of the smaller canvas dimension
FRAME_VISUAL_SIZE_FACTOR = 0.75
# Option 2: Fixed pixel size (uncomment to use instead)
# FRAME_VISUAL_PIXELS = 500
INITIAL_CANVAS_WIDTH = 800
INITIAL_CANVAS_HEIGHT = 700
ZOOM_STEP = 1.1
MIN_ZOOM = 0.01 # Prevent zooming out too far

class ImageCropperApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Python Image Cropper - Fixed Box PNG (1200x1200)")
        self.master.geometry(f"{INITIAL_CANVAS_WIDTH+50}x{INITIAL_CANVAS_HEIGHT+110}")

        # --- State Variables ---
        self.original_image = None
        self.display_image = None
        self.tk_image = None
        self.canvas_image_id = None
        self.scale_factor = 1.0 # Image scale (canvas px / original px)
        self.image_offset_x = 0 # Image top-left on canvas
        self.image_offset_y = 0
        self.last_drag_x = 0
        self.last_drag_y = 0
        self.image_queue = []
        self.current_image_index = -1
        self.current_filepath = None

        # --- GUI Elements ---
        # Top Frame
        self.top_frame = tk.Frame(master)
        self.top_frame.pack(pady=5, fill=tk.X)
        self.btn_load = tk.Button(self.top_frame, text="Load Image(s)", command=self.load_images)
        self.btn_load.pack(side=tk.LEFT, padx=5)
        self.status_label = tk.Label(self.top_frame, text="No images loaded.", anchor='w')
        self.status_label.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

        # Control Frame
        self.control_frame = tk.Frame(master)
        self.control_frame.pack(pady=5)
        self.btn_rotate = tk.Button(self.control_frame, text="Rotate 90° CW", command=self.rotate_image, state=tk.DISABLED)
        self.btn_rotate.pack(side=tk.LEFT, padx=5)
        self.btn_save = tk.Button(self.control_frame, text="Crop & Save as PNG (Overwrite)", command=self.save_crop_overwrite, state=tk.DISABLED)
        self.btn_save.pack(side=tk.LEFT, padx=5)
        self.btn_skip = tk.Button(self.control_frame, text="Skip ->", command=self.skip_image, state=tk.DISABLED)
        self.btn_skip.pack(side=tk.LEFT, padx=5)
        self.btn_reset = tk.Button(self.control_frame, text="Reset View", command=self.reset_view, state=tk.DISABLED)
        self.btn_reset.pack(side=tk.LEFT, padx=5)

        # Canvas
        self.canvas = tk.Canvas(master, bg=CANVAS_BG, width=INITIAL_CANVAS_WIDTH, height=INITIAL_CANVAS_HEIGHT, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.crop_frame_id = None # ID of the red box rectangle

        # --- Bindings ---
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag_image)
        self.canvas.bind("<MouseWheel>", self.zoom_image) # Windows/Mac
        self.canvas.bind("<Button-4>", self.zoom_image)    # Linux Scroll Up
        self.canvas.bind("<Button-5>", self.zoom_image)    # Linux Scroll Down
        self.master.bind("<Configure>", self.on_window_resize) # Re-center frame on resize

        # --- Initial Setup ---
        # Draw the initial frame (it will be centered once window size is known)
        self.master.after_idle(self.center_crop_frame)
        self.update_button_states()

    # ========================================================================
    # Canvas, FIXED Frame, and Visual Updates
    # ========================================================================
    def get_canvas_center(self):
        self.canvas.update_idletasks()
        return self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2

    def center_crop_frame(self):
        """Draws or moves the FIXED visual crop frame to the center."""
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        cx = canvas_w / 2
        cy = canvas_h / 2

        # Calculate the fixed visual size for the frame on the canvas
        try:
             # Use percentage factor if defined
             frame_visual_size = min(canvas_w, canvas_h) * FRAME_VISUAL_SIZE_FACTOR
        except NameError:
             # Fallback to fixed pixel size if factor is commented out
              try:
                  frame_visual_size = FRAME_VISUAL_PIXELS
              except NameError:
                   # Default fallback if neither constant is defined
                   frame_visual_size = min(canvas_w, canvas_h) * 0.75
                   print("Warning: Using default frame size factor.")

        half_size = frame_visual_size / 2
        x1 = cx - half_size
        y1 = cy - half_size
        x2 = cx + half_size
        y2 = cy + half_size

        if self.crop_frame_id:
            # Move existing frame
            self.canvas.coords(self.crop_frame_id, x1, y1, x2, y2)
        else:
            # Create the frame
            self.crop_frame_id = self.canvas.create_rectangle(
                x1, y1, x2, y2,
                outline=FRAME_COLOR, width=FRAME_THICKNESS, tags="crop_frame"
            )

        # Keep frame on top
        self.canvas.tag_raise("crop_frame")

    def on_window_resize(self, event=None):
        """Handles window resize: Re-centers the fixed crop frame."""
        # Schedule the centering after Tkinter has processed the resize
        if event is None or event.widget == self.master or event.widget == self.canvas:
            self.master.after_idle(self.center_crop_frame)

    def update_display(self):
        """Updates the image displayed on the canvas based on scale and offset."""
        # This function DOES NOT change the frame, only the image underneath
        if not self.original_image:
            if self.canvas_image_id:
                self.canvas.delete(self.canvas_image_id)
            self.canvas_image_id = None
            self.tk_image = None
            return

        try:
            img_w, img_h = self.original_image.size
            new_width = max(1, int(img_w * self.scale_factor))
            new_height = max(1, int(img_h * self.scale_factor))

            resample_filter = Image.Resampling.LANCZOS if self.scale_factor >= 1.0 else Image.Resampling.BICUBIC
            self.display_image = self.original_image.resize((new_width, new_height), resample_filter)
            self.tk_image = ImageTk.PhotoImage(self.display_image)

            if self.canvas_image_id:
                self.canvas.itemconfig(self.canvas_image_id, image=self.tk_image)
                self.canvas.coords(self.canvas_image_id, self.image_offset_x, self.image_offset_y)
            else:
                self.canvas_image_id = self.canvas.create_image(
                    self.image_offset_x, self.image_offset_y,
                    anchor=tk.NW, image=self.tk_image, tags="image"
                )
            # Ensure image is below frame
            self.canvas.tag_lower(self.canvas_image_id, "crop_frame")

        except Exception as e:
            print(f"Error updating display: {e}")

    # ========================================================================
    # Image Loading and Queue Management (Unchanged from previous correct version)
    # ========================================================================
    def load_images(self):
        filepaths = filedialog.askopenfilenames(parent=self.master, title="Select Image(s)", filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.gif *.tiff"), ("All Files", "*.*")])
        if not filepaths: return
        self.image_queue = list(filepaths)
        self.current_image_index = -1
        self.load_next_image()

    def load_next_image(self):
        self.current_image_index += 1
        self.clear_canvas()
        if 0 <= self.current_image_index < len(self.image_queue):
            self.current_filepath = self.image_queue[self.current_image_index]
            try:
                self._load_image_from_path(self.current_filepath)
                self.reset_view() # Fit image, reset scale/offset
            except (FileNotFoundError, UnidentifiedImageError, MemoryError, ValueError, Exception) as e: # Catch ValueError too
                 error_type = "Memory Error" if isinstance(e, MemoryError) else "Error Loading Image"
                 msg = f"Could not load image:\n{self.current_filepath}\n\nError: {e}\n\nSkipping this image."
                 print(f"ERROR: {msg}")
                 messagebox.showerror(error_type, msg, parent=self.master)
                 self._handle_load_error_skip()
                 return # Skip rest of the function for this failed load
            else: # Only update UI if load succeeded
                self.update_button_states()
                self.update_status_label()
        else: # End of queue
            self._finalize_queue()
            self.update_button_states() # Ensure buttons are disabled
            self.update_status_label()

    def _handle_load_error_skip(self):
         # Safely remove the problematic file from the queue
        if 0 <= self.current_image_index < len(self.image_queue):
            if self.image_queue[self.current_image_index] == self.current_filepath:
                del self.image_queue[self.current_image_index]
                self.current_image_index -= 1 # Adjust index
            else: print("Warning: Mismatch during error handling skip.")
        self.load_next_image() # Try next

    def _finalize_queue(self):
        self.original_image = None
        self.current_filepath = None
        self.image_queue = []
        self.current_image_index = -1
        self.clear_canvas()
        self.status_label.config(text="Queue finished.")
        if self.master.winfo_exists(): # Check if window still exists before showing popup
             messagebox.showinfo("Queue Finished", "All images processed.", parent=self.master)

    def _load_image_from_path(self, filepath):
        img = Image.open(filepath)
        try: img = ImageOps.exif_transpose(img)
        except Exception: pass # Ignore if EXIF fails
        try: self.original_image = img.convert('RGBA')
        except Exception:
            try: self.original_image = img.convert('RGB')
            except Exception as final_err: raise ValueError(f"Cannot convert {filepath} to RGBA/RGB: {final_err}") from final_err
        if not hasattr(self.original_image, 'filename'): self.original_image.filename = filepath

    def clear_canvas(self):
        if self.canvas_image_id: self.canvas.delete(self.canvas_image_id)
        self.canvas_image_id = None
        self.tk_image = None
        self.original_image = None
        self.display_image = None
        self.scale_factor = 1.0
        self.image_offset_x = 0
        self.image_offset_y = 0

    def skip_image(self):
        if not self.image_queue or self.current_image_index < 0 or not self.current_filepath: return
        skipped_path = self.current_filepath
        print(f"Skipping: {skipped_path}")
        if 0 <= self.current_image_index < len(self.image_queue):
             if self.image_queue[self.current_image_index] == skipped_path:
                  del self.image_queue[self.current_image_index]; self.current_image_index -= 1
             else: print(f"Warning: Queue inconsistency during skip. Expected {skipped_path}")
        self.load_next_image()

    # ========================================================================
    # Image Manipulation (Rotate, Reset, Drag, Zoom) (Unchanged)
    # ========================================================================
    def rotate_image(self):
        if not self.original_image: return
        try:
            self.original_image = self.original_image.rotate(-90, expand=True, resample=Image.Resampling.BICUBIC)
            self.reset_view()
        except Exception as e: messagebox.showerror("Rotation Error", f"Could not rotate image:\n{e}", parent=self.master)

    def reset_view(self):
        if not self.original_image: self.update_display(); return
        img_w, img_h = self.original_image.size
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if img_w <= 0 or img_h <= 0 or canvas_w <= 0 or canvas_h <= 0: self.scale_factor = 1.0
        else: scale_w = canvas_w / img_w; scale_h = canvas_h / img_h; self.scale_factor = min(scale_w, scale_h, 1.0) # Fit, max 1:1
        disp_w = int(img_w * self.scale_factor); disp_h = int(img_h * self.scale_factor)
        self.image_offset_x = (canvas_w - disp_w) / 2; self.image_offset_y = (canvas_h - disp_h) / 2
        self.update_display()

    def start_drag(self, event): self.last_drag_x = event.x; self.last_drag_y = event.y

    def drag_image(self, event):
        if not self.canvas_image_id: return
        dx = event.x - self.last_drag_x; dy = event.y - self.last_drag_y
        self.image_offset_x += dx; self.image_offset_y += dy
        self.canvas.move(self.canvas_image_id, dx, dy)
        self.last_drag_x = event.x; self.last_drag_y = event.y

    def zoom_image(self, event):
        if not self.original_image: return
        zoom_direction = 0
        if hasattr(event, 'delta') and event.delta != 0 : # Windows/Mac
            zoom_direction = 1 if event.delta > 0 else -1
        elif hasattr(event, 'num'): # Linux
             if event.num == 4: zoom_direction = 1
             elif event.num == 5: zoom_direction = -1
        if zoom_direction == 0: return

        zoom_multiplier = ZOOM_STEP if zoom_direction > 0 else 1 / ZOOM_STEP
        prospective_scale = self.scale_factor * zoom_multiplier
        new_scale = max(MIN_ZOOM, prospective_scale)
        if new_scale == self.scale_factor: return

        mouse_x, mouse_y = event.x, event.y
        try:
            img_coord_x = (mouse_x - self.image_offset_x) / self.scale_factor
            img_coord_y = (mouse_y - self.image_offset_y) / self.scale_factor
        except ZeroDivisionError: return # Should be prevented by MIN_ZOOM

        self.image_offset_x = mouse_x - (img_coord_x * new_scale)
        self.image_offset_y = mouse_y - (img_coord_y * new_scale)
        self.scale_factor = new_scale
        self.update_display()

    # ========================================================================
    # Saving (MODIFIED FOR FIXED BOX)
    # ========================================================================
    def save_crop_overwrite(self):
        """Calculates crop based on FIXED frame, crops original,
           RESIZES crop to CROP_SIZE, saves as PNG (overwriting path)."""
        if not self.original_image or not self.current_filepath:
            messagebox.showwarning("No Image", "No image loaded.", parent=self.master); return
        if not self.crop_frame_id:
            messagebox.showerror("Error", "Crop frame not found.", parent=self.master); return

        # --- Get FIXED Frame Coordinates on CANVAS ---
        try:
            frame_coords = self.canvas.coords(self.crop_frame_id)
            if not frame_coords or len(frame_coords) != 4: raise ValueError("Invalid frame coords")
            frame_canvas_x1, frame_canvas_y1, frame_canvas_x2, frame_canvas_y2 = frame_coords
        except Exception as e:
            messagebox.showerror("Error", f"Could not get crop frame coords: {e}", parent=self.master); return

        # --- Translate Canvas Frame Coords to ORIGINAL Image Coords ---
        if self.scale_factor <= 0: # Prevent division by zero
             messagebox.showerror("Error", "Invalid image scale factor.", parent=self.master); return
        pixels_per_canvas_pixel = 1.0 / self.scale_factor

        # Top-left corner on original image
        original_x1 = (frame_canvas_x1 - self.image_offset_x) * pixels_per_canvas_pixel
        original_y1 = (frame_canvas_y1 - self.image_offset_y) * pixels_per_canvas_pixel
        # Bottom-right corner on original image
        original_x2 = (frame_canvas_x2 - self.image_offset_x) * pixels_per_canvas_pixel
        original_y2 = (frame_canvas_y2 - self.image_offset_y) * pixels_per_canvas_pixel

        # Define the crop box for PIL (using integers)
        # Use floor/ceil to ensure the box includes edge pixels fully covered by the frame
        crop_box = (
            math.floor(original_x1),
            math.floor(original_y1),
            math.ceil(original_x2),
            math.ceil(original_y2)
        )

        # --- Confirmation ---
        confirm = messagebox.askyesno("Confirm Overwrite as PNG", f"Save content inside red box as {CROP_SIZE}x{CROP_SIZE} PNG?\n\nThis will OVERWRITE:\n{self.current_filepath}\n\n(Saving PNG data to non-PNG files can cause issues).", parent=self.master)
        if not confirm: return

        # --- Perform Crop, Resize, Save ---
        try:
            # 1. Crop the *original* image
            source_image = self.original_image # Assumed RGBA
            if source_image.mode != 'RGBA': source_image = source_image.convert('RGBA')
            cropped_image = source_image.crop(crop_box)

            if cropped_image.width <= 0 or cropped_image.height <= 0:
                 messagebox.showerror("Crop Error", "Crop area is outside image or has zero size.", parent=self.master); return

            # 2. Resize the cropped image to the EXACT target size
            final_image = cropped_image.resize((CROP_SIZE, CROP_SIZE), Image.Resampling.LANCZOS)

            # 3. Save as PNG
            final_image.save(self.current_filepath, format='PNG', optimize=True)
            print(f"Saved: {self.current_filepath}")

            # --- Advance Queue ---
            if 0 <= self.current_image_index < len(self.image_queue):
                if self.image_queue[self.current_image_index] == self.current_filepath:
                    del self.image_queue[self.current_image_index]; self.current_image_index -= 1
                else: print("Warning: Queue inconsistency on save.")
            self.load_next_image()

        except FileNotFoundError:
             messagebox.showerror("Save Error", f"Original file not found:\n{self.current_filepath}", parent=self.master)
             self._handle_load_error_skip() # Treat as load error, remove and skip
        except PermissionError:
             messagebox.showerror("Save Error", f"Permission denied:\n{self.current_filepath}", parent=self.master)
        except SystemError as se:
             messagebox.showerror("Save Error", f"System error during processing (crop boundaries?):\n{self.current_filepath}\n{se}", parent=self.master)
        except Exception as e:
             messagebox.showerror("Save Error", f"Failed to process/save:\n{self.current_filepath}\n{e}", parent=self.master)

    # ========================================================================
    # UI Updates (Button States, Status Label) (Unchanged)
    # ========================================================================
    def update_button_states(self):
        has_image = self.original_image is not None
        can_skip = has_image
        self.btn_save.config(state=tk.NORMAL if has_image else tk.DISABLED)
        self.btn_rotate.config(state=tk.NORMAL if has_image else tk.DISABLED)
        self.btn_reset.config(state=tk.NORMAL if has_image else tk.DISABLED)
        self.btn_skip.config(state=tk.NORMAL if can_skip else tk.DISABLED)

    def update_status_label(self):
        total_remaining = len(self.image_queue)
        if self.current_filepath and self.original_image:
            current_num_in_remaining = self.current_image_index + 1
            filename = os.path.basename(self.current_filepath)
            max_len = 50; filename = filename if len(filename) <= max_len else filename[:max_len-3]+"..."
            self.status_label.config(text=f"Processing {current_num_in_remaining}/{total_remaining}: {filename}")
        elif not self.image_queue and self.current_image_index == -1:
             self.status_label.config(text="No images loaded or queue empty.")
        else: # Between loads or finished
             if total_remaining == 0: self.status_label.config(text="Queue finished.")
             else: self.status_label.config(text="...")


# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = ImageCropperApp(root)
    root.mainloop()