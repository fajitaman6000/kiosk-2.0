# rotate_screen.py
import rotatescreen
import time
import sys
import os # Import os for potential console closing trick (Windows specific, not simple)

def rotate_opposite():
    """
    Rotates the primary screen to its defined opposite orientation and exits.
    Defined Opposites:
    0 degrees (Landscape) -> 270 degrees (Portrait Flipped)
    90 degrees (Portrait) -> 180 degrees (Landscape Flipped)
    180 degrees (Landscape Flipped) -> 90 degrees (Portrait)
    270 degrees (Portrait Flipped) -> 0 degrees (Landscape)
    """
    try:
        print("rotate_screen: Starting...", flush=True)
        # Add a small delay to ensure rotatescreen can initialize properly
        # and the system is ready to report/accept rotation changes.
        time.sleep(0.1)

        screen = rotatescreen.get_primary_display()
        current_orientation = screen.current_orientation
        print(f"rotate_screen: Detected current orientation: {current_orientation} degrees.", flush=True)

        target_orientation = None

        # Determine the target opposite orientation
        if current_orientation == 0:
            target_orientation = 270 # Landscape -> Portrait Flipped
            print("rotate_screen: Mapping 0 -> 270 (Portrait Flipped)", flush=True)
        elif current_orientation == 90:
            target_orientation = 180 # Portrait -> Landscape Flipped
            print("rotate_screen: Mapping 90 -> 180 (Landscape Flipped)", flush=True)
        elif current_orientation == 180:
            target_orientation = 90  # Landscape Flipped -> Portrait
            print("rotate_screen: Mapping 180 -> 90 (Portrait)", flush=True)
        elif current_orientation == 270:
            target_orientation = 0  # Portrait Flipped -> Landscape
            print("rotate_screen: Mapping 270 -> 0 (Landscape)", flush=True)
        else:
            print(f"rotate_screen: Warning: Unknown current orientation {current_orientation}.", flush=True)
            print("rotate_screen: No rotation performed.", flush=True)
            return # Exit the function without rotating

        # Perform the rotation
        print(f"rotate_screen: Attempting to rotate to {target_orientation} degrees...", flush=True)
        screen.rotate_to(target_orientation)
        print("rotate_screen: Rotation command sent.", flush=True)

        # Add a delay to allow the operating system to apply the rotation
        # before the script exits. Without this, the script might exit
        # too quickly and the rotation might not complete smoothly or at all.
        time.sleep(1)
        print("rotate_screen: Rotation process complete (after 1s delay).", flush=True)

    except rotatescreen.DisplayNotFoundError:
         print("rotate_screen: ERROR: No primary display found or rotatescreen failed to detect displays.", flush=True)
         print("rotate_screen: Cannot perform rotation.", flush=True)
    except Exception as e:
        print(f"rotate_screen: An unexpected error occurred: {e}", flush=True)
        # You might want to log this exception more formally in a real application

# --- Main execution starts here ---
if __name__ == "__main__":
    rotate_opposite()

    print("rotate_screen: Script finished. Exiting now.", flush=True)

    # --- Attempt to close the console window (Windows specific and not guaranteed) ---
    # Note: Closing the console window that launched the script is tricky
    # from within the script itself in a reliable way.
    # A common method is to launch the script using `pythonw.exe` instead of `python.exe`.
    # If you double-click the .py file on Windows, it usually runs with python.exe
    # in a new console, which stays open after the script finishes.
    # The below is a simple attempt that *might* work in some contexts, but is not robust.
    # A more reliable method requires changing how the script is launched (e.g., using a .bat or .vbs).
    if sys.platform == "win32":
        try:
            # Import required libraries for Windows API calls
            import ctypes
            # Get the console window handle
            kernel32 = ctypes.WinDLL('kernel32')
            user32 = ctypes.WinDLL('user32')
            # Get the console window handle
            hwnd = kernel32.GetConsoleWindow()
            if hwnd:
                # Send a close message to the console window
                # WM_CLOSE = 0x0010
                user32.SendMessageW(hwnd, 0x0010, 0, 0)
                # Note: This sends the CLOSE message, but the console might
                # still remain open if it's waiting for user input or if
                # there are other reasons.
        except Exception as e:
            # This attempt failed, but the script will still exit via sys.exit()
            print(f"rotate_screen: Failed to attempt console close: {e}", flush=True)
    # --- End of console closing attempt ---


    # Terminate the script
    sys.exit(0)