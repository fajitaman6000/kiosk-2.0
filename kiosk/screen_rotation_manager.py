# screen_rotation_manager.py
import rotatescreen
import sys
import time # Add a small delay if needed for stability after rotation

def rotate_to_preferred_landscape():
    """
    Checks the current primary screen orientation and rotates it
    to landscape (180 degrees) if portrait (90), or landscape (0 degrees)
    if portrait flipped (270). Does nothing if already in a landscape orientation.
    """
    try:
        print("[Screen Rotation] Checking primary display orientation...", flush=True)
        
        # Give the display system a moment to be ready, especially on fast startups
        time.sleep(0.1) 

        screen = rotatescreen.get_primary_display()
        current_orientation = screen.current_orientation
        print(f"[Screen Rotation] Current orientation detected: {current_orientation} degrees.", flush=True)

        if current_orientation == 90: # Portrait
            print("[Screen Rotation] Detected Portrait (90 degrees). Rotating to Landscape (Flipped - 180 degrees)...", flush=True)
            screen.set_landscape_flipped()
            print("[Screen Rotation] Rotation to 180 degrees complete.", flush=True)
            # Add a small delay for the system to apply the rotation
            time.sleep(1) 
        elif current_orientation == 270: # Portrait Flipped
            print("[Screen Rotation] Detected Portrait (Flipped - 270 degrees). Rotating to Landscape (0 degrees)...", flush=True)
            screen.set_landscape()
            print("[Screen Rotation] Rotation to 0 degrees complete.", flush=True)
            # Add a small delay for the system to apply the rotation
            time.sleep(1) 
        elif current_orientation == 0 or current_orientation == 180: # Already Landscape
            print("[Screen Rotation] Already in a Landscape orientation (0 or 180 degrees). No rotation needed.", flush=True)
        else:
             print(f"[Screen Rotation] Unknown orientation: {current_orientation}. No rotation attempted.", flush=True)
             # This might happen if rotatescreen returns an unexpected value

    except rotatescreen.DisplayNotFoundError:
         print("[Screen Rotation] ERROR: No primary display found or rotatescreen failed to detect displays.", flush=True)
         print("[Screen Rotation] Skipping initial screen rotation.", flush=True)
         # This might happen if there are no displays, or on systems where rotatescreen doesn't work.
         # Kiosk should continue attempting to start.
    except Exception as e:
        print(f"[Screen Rotation] An unexpected error occurred during screen rotation: {e}", flush=True)
        print("[Screen Rotation] Skipping initial screen rotation.", flush=True)
        # Catch any other exceptions from rotatescreen and log them.


if __name__ == "__main__":
    # This block allows you to run the script independently for testing
    # It will check and rotate the primary display if needed when run directly.
    rotate_to_preferred_landscape()