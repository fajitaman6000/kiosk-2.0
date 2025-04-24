import os
import sys
import time
import datetime
import traceback
from pathlib import Path
import threading

class KioskLogger:
    """
    Logger class to redirect console output to log files.
    Creates timestamped log files in the logs directory.
    """
    def __init__(self, log_dir="logs"):
        # Create logs directory if it doesn't exist
        self.log_dir = Path(log_dir)
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Generate a unique filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_file_path = self.log_dir / f"kiosk_log_{timestamp}.txt"
        
        # Store original stdout and stderr
        self.stdout_original = sys.stdout
        self.stderr_original = sys.stderr
        
        # Open log file
        self.log_file = open(self.log_file_path, 'w', encoding='utf-8')
        
        # Add file lock for thread safety
        self.file_lock = threading.Lock()
        
        # Create stdout and stderr wrappers
        self.stdout_wrapper = self.LogWrapper(self.stdout_original, self.log_file, self.file_lock)
        self.stderr_wrapper = self.LogWrapper(self.stderr_original, self.log_file, self.file_lock, is_error=True)
        
        # Install exception hook to catch unhandled exceptions
        self.original_excepthook = sys.excepthook
        sys.excepthook = self.exception_hook
        
        print(f"[KioskLogger] Logging started. Output will be saved to: {self.log_file_path}")
    
    def start(self):
        """Start logging by redirecting stdout and stderr."""
        sys.stdout = self.stdout_wrapper
        sys.stderr = self.stderr_wrapper
        return self
    
    def stop(self):
        """Stop logging and restore original stdout and stderr."""
        # Restore original streams
        sys.stdout = self.stdout_original
        sys.stderr = self.stderr_original
        
        # Restore original exception hook
        sys.excepthook = self.original_excepthook
        
        # Close log file
        try:
            with self.file_lock:
                self.log_file.flush()
                self.log_file.close()
        except Exception as e:
            print(f"[KioskLogger] Error closing log file: {e}")
        
        print(f"[KioskLogger] Logging stopped. Log file: {self.log_file_path}")
    
    def exception_hook(self, exc_type, exc_value, exc_traceback):
        """Custom exception hook to log unhandled exceptions."""
        try:
            # Write exception info to log file with timestamp
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            
            # Format the exception info
            exception_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            
            # Write each line with timestamp
            with self.file_lock:
                self.log_file.write(f"{timestamp} [UNHANDLED_EXCEPTION] Unhandled exception detected:\n")
                for line in exception_lines:
                    for subline in line.splitlines():
                        if subline.strip():
                            self.log_file.write(f"{timestamp} [UNHANDLED_EXCEPTION] {subline}\n")
                self.log_file.flush()
                
        except Exception as e:
            # If we can't log to the file, at least print to the original stderr
            self.stderr_original.write(f"Error in exception hook: {e}\n")
        
        # Call the original exception hook
        self.original_excepthook(exc_type, exc_value, exc_traceback)
    
    class LogWrapper:
        """Wrapper class for stdout and stderr to capture output to log file."""
        def __init__(self, original_stream, log_file, file_lock, is_error=False):
            self.original_stream = original_stream
            self.log_file = log_file
            self.file_lock = file_lock
            self.is_error = is_error
            self.last_char = '\n'  # Track the last character written
        
        def write(self, message):
            # Always write to original stream first
            self.original_stream.write(message)
            
            # Skip empty messages
            if not message.strip():
                return
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            prefix = "[ERROR] " if self.is_error else ""
            
            with self.file_lock:
                # Ensure each log message starts on a new line if the last character wasn't a newline
                if self.last_char != '\n' and not message.startswith('\n'):
                    self.log_file.write('\n')
                
                # Add timestamp to the start of each line
                lines = message.splitlines(True)  # Keep line endings
                for line in lines:
                    if line.strip():  # Skip empty lines
                        if line.endswith('\n'):
                            self.log_file.write(f"{timestamp} {prefix}{line}")
                            self.last_char = '\n'
                        else:
                            self.log_file.write(f"{timestamp} {prefix}{line}")
                            self.last_char = line[-1] if line else '\n'
                
                self.log_file.flush()
        
        def flush(self):
            self.original_stream.flush()
            with self.file_lock:
                self.log_file.flush()
        
        # Forward other methods to original stream
        def __getattr__(self, attr):
            return getattr(self.original_stream, attr)


def init_logging():
    """Initialize logging and return the logger instance."""
    try:
        return KioskLogger().start()
    except Exception as e:
        print(f"Failed to initialize logging: {e}")
        traceback.print_exc()
        return None


# Helper function to log exceptions
def log_exception(e, context=""):
    """Log an exception with context information."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    # Get the formatted traceback
    tb_text = traceback.format_exc()
    
    # Log the context and exception message
    error_msg = f"{timestamp} [EXCEPTION] {context}: {str(e)}\n"
    
    # Add each line of the traceback with its own timestamp
    for line in tb_text.splitlines():
        if line.strip():
            error_msg += f"{timestamp} [EXCEPTION] {line}\n"
    
    # Write directly to stderr (which will be captured by our logger if active)
    sys.stderr.write(error_msg)
    sys.stderr.flush()


# Function to directly log a message to the log file (useful for background threads)
def log_message(message, level="INFO"):
    """
    Log a message directly to the current log file.
    Useful for background threads or components that don't use stdout/stderr.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    formatted_message = f"{timestamp} [{level}] {message}\n"
    
    # Print to stdout/stderr which will be captured by the logger
    if level in ("ERROR", "EXCEPTION", "CRITICAL"):
        sys.stderr.write(formatted_message)
        sys.stderr.flush()
    else:
        sys.stdout.write(formatted_message)
        sys.stdout.flush() 