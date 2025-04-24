import os
import sys
import time
import datetime
import traceback
from pathlib import Path

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
        
        # Create stdout and stderr wrappers
        self.stdout_wrapper = self.LogWrapper(self.stdout_original, self.log_file)
        self.stderr_wrapper = self.LogWrapper(self.stderr_original, self.log_file, is_error=True)
        
        print(f"[KioskLogger] Logging started. Output will be saved to: {self.log_file_path}")
    
    def start(self):
        """Start logging by redirecting stdout and stderr."""
        sys.stdout = self.stdout_wrapper
        sys.stderr = self.stderr_wrapper
        return self
    
    def stop(self):
        """Stop logging and restore original stdout and stderr."""
        sys.stdout = self.stdout_original
        sys.stderr = self.stderr_original
        self.log_file.close()
        print(f"[KioskLogger] Logging stopped. Log file: {self.log_file_path}")
    
    class LogWrapper:
        """Wrapper class for stdout and stderr to capture output to log file."""
        def __init__(self, original_stream, log_file, is_error=False):
            self.original_stream = original_stream
            self.log_file = log_file
            self.is_error = is_error
            self.last_char = '\n'  # Track the last character written
        
        def write(self, message):
            # Write to original stream
            self.original_stream.write(message)
            
            # Add timestamp and write to log file
            if message.strip():  # Only log non-empty messages
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                prefix = "[ERROR] " if self.is_error else ""
                
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
    error_msg = f"{timestamp} [EXCEPTION] {context}: {str(e)}\n"
    error_msg += traceback.format_exc()
    
    # Print to stderr (which will be captured by our logger if active)
    sys.stderr.write(error_msg)
    sys.stderr.flush() 