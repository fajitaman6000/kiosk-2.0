import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame
from PyQt5.QtCore import Qt, QTimer
import signal

class QtKioskApp(QApplication):
    """Main Qt Application class replacing Tkinter root."""
    instance = None  # Class variable to store the single instance
    
    def __init__(self, kiosk_app_instance):
        super().__init__(sys.argv)
        self.kiosk_app_instance = kiosk_app_instance
        QtKioskApp.instance = self  # Store reference to this instance
        
        # Create a proper main window that will appear in taskbar and Alt+Tab
        self.main_window = QWidget()
        self.main_window.setWindowTitle("Escape Room Kiosk")
        
        # Use a layout to properly manage child widgets
        self.layout = QVBoxLayout(self.main_window)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Content area where UI elements will be placed
        self.content_widget = QWidget(self.main_window)
        self.content_widget.setAttribute(Qt.WA_TranslucentBackground, True)
        self.content_widget.setStyleSheet("background: transparent;")
        
        # Create a grid layout for positioning all UI elements
        self.grid_layout = QGridLayout(self.content_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(0)
        
        # Create containers for various UI elements
        # Background container (covers entire area)
        self.background_container = QFrame(self.content_widget)
        self.background_container.setFrameShape(QFrame.NoFrame)
        self.background_container.setStyleSheet("background: transparent;")
        
        # Hint text container (right side)
        self.hint_container = QFrame(self.content_widget)
        self.hint_container.setFrameShape(QFrame.NoFrame)
        self.hint_container.setStyleSheet("background: transparent;")
        
        # Hint request container (center)
        self.hint_request_container = QFrame(self.content_widget)
        self.hint_request_container.setFrameShape(QFrame.NoFrame)
        self.hint_request_container.setStyleSheet("background: transparent;")
        
        # Cooldown container (overlay at the center)
        self.cooldown_container = QFrame(self.content_widget)
        self.cooldown_container.setFrameShape(QFrame.NoFrame)
        self.cooldown_container.setStyleSheet("background: rgba(0, 0, 0, 120);")
        
        # Timer container (top right)
        self.timer_container = QFrame(self.content_widget)
        self.timer_container.setFrameShape(QFrame.NoFrame)
        self.timer_container.setStyleSheet("background: transparent;")
        
        # Help button container (left side)
        self.help_button_container = QFrame(self.content_widget)
        self.help_button_container.setFrameShape(QFrame.NoFrame)
        self.help_button_container.setStyleSheet("background: transparent;")
        
        # Waiting screen container
        self.waiting_container = QFrame(self.content_widget)
        self.waiting_container.setFrameShape(QFrame.NoFrame)
        self.waiting_container.setStyleSheet("background: transparent;")
        
        # View image button container (left side)
        self.view_image_container = QFrame(self.content_widget)
        self.view_image_container.setFrameShape(QFrame.NoFrame)
        self.view_image_container.setStyleSheet("background: transparent;")
        
        # View solution button container (left side)
        self.view_solution_container = QFrame(self.content_widget)
        self.view_solution_container.setFrameShape(QFrame.NoFrame)
        self.view_solution_container.setStyleSheet("background: transparent;")
        
        # Video container (covers entire area)
        self.video_container = QFrame(self.content_widget)
        self.video_container.setFrameShape(QFrame.NoFrame)
        self.video_container.setStyleSheet("background: black;")
        
        # Fullscreen hint container (covers entire area)
        self.fullscreen_hint_container = QFrame(self.content_widget)
        self.fullscreen_hint_container.setFrameShape(QFrame.NoFrame)
        self.fullscreen_hint_container.setStyleSheet("background: black;")
        
        # GM assistance container (center)
        self.gm_assistance_container = QFrame(self.content_widget)
        self.gm_assistance_container.setFrameShape(QFrame.NoFrame)
        self.gm_assistance_container.setStyleSheet("background: transparent;")
        
        # Add all containers to the grid layout
        # Background layer (lowest z-order, spans entire grid)
        self.grid_layout.addWidget(self.background_container, 0, 0, 12, 12)
        
        # UI elements in correct positions
        self.grid_layout.addWidget(self.hint_container, 1, 8, 10, 4)  # Hint on right side
        self.grid_layout.addWidget(self.hint_request_container, 4, 4, 4, 4)  # Hint request in center
        self.grid_layout.addWidget(self.cooldown_container, 4, 3, 4, 6)  # Cooldown in center (larger)
        self.grid_layout.addWidget(self.timer_container, 0, 10, 2, 2)  # Timer top right
        self.grid_layout.addWidget(self.help_button_container, 3, 0, 6, 1)  # Help on left
        self.grid_layout.addWidget(self.view_image_container, 3, 1, 3, 1)  # View image on left
        self.grid_layout.addWidget(self.view_solution_container, 6, 1, 3, 1)  # View solution on left
        
        # Overlays (higher z-order, span entire grid)
        self.grid_layout.addWidget(self.waiting_container, 0, 0, 12, 12)
        self.grid_layout.addWidget(self.video_container, 0, 0, 12, 12)
        self.grid_layout.addWidget(self.fullscreen_hint_container, 0, 0, 12, 12)
        self.grid_layout.addWidget(self.gm_assistance_container, 3, 3, 6, 6)  # Center
        
        # Set z-order manually
        self.background_container.lower()
        self.waiting_container.raise_()
        self.video_container.raise_()
        self.fullscreen_hint_container.raise_()
        self.gm_assistance_container.raise_()
        
        # Hide overlay containers initially
        self.waiting_container.hide()
        self.video_container.hide()
        self.fullscreen_hint_container.hide()
        self.gm_assistance_container.hide()
        self.hint_request_container.hide()
        self.cooldown_container.hide()
        
        # Add content widget to main layout
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
        # Show the main window so it appears in taskbar and Alt+Tab
        self.main_window.show()
        self.main_window.activateWindow()
        self.main_window.raise_()
        exit_code = self.exec_()
        print(f"[Qt Main] Qt event loop finished with exit code: {exit_code}")
        sys.exit(exit_code) 