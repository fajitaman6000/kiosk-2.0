import sys
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QTimer
import signal

class QtKioskApp(QApplication):
    """Main Qt Application class replacing Tkinter root."""
    instance = None  # Class variable to store the single instance
    
    def __init__(self, kiosk_app_instance):
        super().__init__(sys.argv)
        self.kiosk_app_instance = kiosk_app_instance
        QtKioskApp.instance = self  # Store reference to this instance
        
        # Create a simple, invisible main window
        # This helps manage application lifetime and potentially other top-level interactions
        # if needed later, without being the primary visible interface.
        self.main_window = QWidget()
        # Optional: Make it truly invisible and non-interactive if desired
        # self.main_window.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        # self.main_window.setAttribute(Qt.WA_TranslucentBackground)
        # self.main_window.setFixedSize(1, 1)
        # self.main_window.move(-10, -10) # Move offscreen

        print("[Qt Main] QtKioskApp initialized.")

        # Graceful shutdown handling for Ctrl+C
        signal.signal(signal.SIGINT, self.signal_handler)
        # Use a QTimer to periodically check for the signal, as signal handlers
        # might not work reliably with Qt's event loop on all platforms/situations.
        self._signal_timer = QTimer()
        self._signal_timer.setInterval(100) # Check every 100ms
        self._signal_timer.timeout.connect(lambda: None) # Dummy connect to allow timer processing
        self._signal_timer.start()

    def signal_handler(self, sig, frame):
        print('\n[Qt Main] SIGINT received, initiating shutdown...')
        self.kiosk_app_instance.on_closing() # Call the KioskApp's cleanup
        self.quit()

    def run(self):
        print("[Qt Main] Starting Qt event loop...")
        # Optional: Show the invisible main window if you haven't hidden it aggressively
        # self.main_window.show()
        exit_code = self.exec_()
        print(f"[Qt Main] Qt event loop finished with exit code: {exit_code}")
        sys.exit(exit_code) 