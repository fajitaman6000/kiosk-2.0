import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
import signal

class QtKioskApp(QApplication):
    """Main Qt Application class replacing Tkinter root."""
    instance = None  # Class variable to store the single instance
    
    def __init__(self, kiosk_app_instance):
        super().__init__(sys.argv)
        self.kiosk_app_instance = kiosk_app_instance
        QtKioskApp.instance = self  # Store reference to this instance
        
        # Create a proper main application window that will show in the taskbar
        self.main_window = QWidget()
        self.main_window.setWindowTitle("Escape Room Kiosk")
        
        # Make the main window completely transparent but keep its presence in the taskbar
        self.main_window.setAttribute(Qt.WA_TranslucentBackground, True)
        self.main_window.setStyleSheet("background-color: transparent;")
        
        # Size it to full screen
        screen_rect = self.desktop().screenGeometry()
        self.main_window.setGeometry(0, 0, screen_rect.width(), screen_rect.height())
        
        # Remove border but keep it in the taskbar (unlike Qt.Tool)
        self.main_window.setWindowFlags(self.main_window.windowFlags() & ~Qt.FramelessWindowHint)
        
        # Show the main window so it appears in taskbar
        self.main_window.show()
        
        print("[Qt Main] QtKioskApp initialized with transparent main window.")

        # Graceful shutdown handling for Ctrl+C
        signal.signal(signal.SIGINT, self.signal_handler)
        # Use a QTimer to periodically check for the signal
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
        # Ensure the main window is visible and maximized
        self.main_window.show()
        self.main_window.showMaximized()
        exit_code = self.exec_()
        print(f"[Qt Main] Qt event loop finished with exit code: {exit_code}")
        sys.exit(exit_code) 