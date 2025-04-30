print("[qt_main] Beginning imports...", flush=True)
print("[qt_main] Importing sys...", flush=True)
import sys
print("[qt_main] Imported sys.", flush=True)
print("[qt_main] Importing PyQt5.QtWidgets...", flush=True)
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
print("[qt_main] Imported PyQt5.QtWidgets.", flush=True)
print("[qt_main] Importing PyQt5.QtCore...", flush=True)
from PyQt5.QtCore import Qt, QTimer
print("[qt_main] Imported PyQt5.QtCore.", flush=True)
print("[qt_main] Importing PyQt5.QtGui...", flush=True)
from PyQt5.QtGui import QIcon
print("[qt_main] Imported PyQt5.QtGui.", flush=True)
print("[qt_main] Importing signal...", flush=True)
import signal
print("[qt_main] Imported signal.", flush=True)
print("[qt_main] Importing os...", flush=True)
import os
print("[qt_main] Imported os.", flush=True)
print("[qt_main] Ending imports.", flush=True)

class QtKioskApp(QApplication):
    """Main Qt Application class replacing Tkinter root."""
    instance = None  # Class variable to store the single instance
    
    def __init__(self, kiosk_app_instance):
        print("[qt_main] Initializing QtKioskApp (QApplication)...", flush=True)
        super().__init__(sys.argv)
        self.kiosk_app_instance = kiosk_app_instance
        QtKioskApp.instance = self  # Store reference to this instance
        print("[qt_main] QApplication initialized.", flush=True)
        
        # Create a proper main window that will appear in taskbar and Alt+Tab
        print("[qt_main] Creating main window...", flush=True)
        self.main_window = QWidget()
        self.main_window.setWindowTitle("PanIQ Room Kiosk")
        
        # Set window flags to remove window decorations
        self.main_window.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        print("[qt_main] Main window created.", flush=True)
        
        # Set application and window icon
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        if os.path.exists(icon_path):
            print(f"[Qt Main] Setting application icon from: {icon_path}", flush=True)
            app_icon = QIcon(icon_path)
            self.setWindowIcon(app_icon)
            self.main_window.setWindowIcon(app_icon)
        else:
            print(f"[Qt Main] Warning: Icon file not found at {icon_path}", flush=True)
        
        # Use a layout to properly manage child widgets
        print("[qt_main] Setting up main window layout...", flush=True)
        self.layout = QVBoxLayout(self.main_window)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Content area where UI elements will be placed
        self.content_widget = QWidget(self.main_window)
        self.layout.addWidget(self.content_widget)
        print("[qt_main] Main window layout configured.", flush=True)
        
        # Set a reasonable size for the main window
        screen_size = self.primaryScreen().size()
        self.main_window.setFixedSize(screen_size)
        
        # Make this window accept focus
        self.main_window.setFocusPolicy(Qt.StrongFocus)
        
        print("[Qt Main] QtKioskApp initialized.", flush=True)

        # Graceful shutdown handling for Ctrl+C
        print("[qt_main] Setting up signal handler...", flush=True)
        signal.signal(signal.SIGINT, self.signal_handler)
        # Use a QTimer to periodically check for the signal, as signal handlers
        # might not work reliably with Qt's event loop on all platforms/situations.
        print("[qt_main] Creating signal check timer...", flush=True)
        self._signal_timer = QTimer()
        self._signal_timer.setInterval(100) # Check every 100ms
        self._signal_timer.timeout.connect(lambda: None) # Dummy connect to allow timer processing
        self._signal_timer.start()
        print("[qt_main] Signal handler and timer set up.", flush=True)

    def signal_handler(self, sig, frame):
        print('\n[Qt Main] SIGINT received, initiating shutdown...', flush=True)
        self.kiosk_app_instance.on_closing() # Call the KioskApp's cleanup
        self.quit()

    def run(self):
        print("[Qt Main] Starting Qt event loop...", flush=True)
        # Show the main window in fullscreen so it appears in taskbar and Alt+Tab
        print("[qt_main] Showing main window in fullscreen...", flush=True)
        self.main_window.showFullScreen()
        self.main_window.activateWindow()
        self.main_window.raise_()
        print("[qt_main] Entering Qt event loop...", flush=True)
        exit_code = self.exec_()
        print(f"[Qt Main] Qt event loop finished with exit code: {exit_code}", flush=True)
        sys.exit(exit_code) 