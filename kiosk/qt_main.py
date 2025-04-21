import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
import signal
import os

class QtKioskApp(QApplication):
    """Main Qt Application class replacing Tkinter root."""
    instance = None  # Class variable to store the single instance
    
    def __init__(self, kiosk_app_instance):
        super().__init__(sys.argv)
        self.kiosk_app_instance = kiosk_app_instance
        QtKioskApp.instance = self  # Store reference to this instance
        
        # Create a proper main window that will appear in taskbar and Alt+Tab
        self.main_window = QWidget()
        self.main_window.setWindowTitle("PanIQ Room Kiosk")
        
        # Set window flags to remove window decorations
        self.main_window.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        
        # Set application and window icon
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        if os.path.exists(icon_path):
            print(f"[Qt Main] Setting application icon from: {icon_path}")
            app_icon = QIcon(icon_path)
            self.setWindowIcon(app_icon)
            self.main_window.setWindowIcon(app_icon)
        else:
            print(f"[Qt Main] Warning: Icon file not found at {icon_path}")
        
        # Use a layout to properly manage child widgets
        self.layout = QVBoxLayout(self.main_window)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Content area where UI elements will be placed
        self.content_widget = QWidget(self.main_window)
        self.layout.addWidget(self.content_widget)
        
        # Set a reasonable size for the main window
        screen_size = self.primaryScreen().size()
        self.main_window.setFixedSize(screen_size)
        
        # Make this window accept focus
        self.main_window.setFocusPolicy(Qt.StrongFocus)
        
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
        # Show the main window in fullscreen so it appears in taskbar and Alt+Tab
        self.main_window.showFullScreen()
        self.main_window.activateWindow()
        self.main_window.raise_()
        exit_code = self.exec_()
        print(f"[Qt Main] Qt event loop finished with exit code: {exit_code}")
        sys.exit(exit_code) 