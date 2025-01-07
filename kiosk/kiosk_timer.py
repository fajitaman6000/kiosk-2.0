from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor
from rotated_widget import RotatedWidget
import os
from PIL import Image
import time

class KioskTimer(QWidget):
    """
    PyQt5 implementation of the kiosk timer system.
    This replaces the Tkinter-based timer while maintaining identical functionality.
    
    Key differences from Tkinter version:
    - Uses QTimer instead of after() calls
    - Implements proper Qt parent-child relationships
    - Uses RotatedWidget for display
    - Handles transparency correctly
    """
    
    # Signal emitted when timer crosses thresholds
    threshold_crossed = pyqtSignal(float, float)  # old_minutes, new_minutes
    
    def __init__(self, parent=None):
        """Initialize the timer with parent widget reference"""
        super().__init__(parent)
        
        # State variables (maintained from Tkinter version)
        self.time_remaining = 60 * 45  # Default 45 minutes
        self.is_running = False
        self.last_update = None
        self.current_room = None
        
        # Define room to timer background mapping (same as Tkinter version)
        self.timer_backgrounds = {
            1: "casino_heist.png",
            2: "morning_after.png",
            3: "wizard_trials.png",
            4: "zombie_outbreak.png",
            5: "haunted_manor.png",
            6: "atlantis_rising.png",
            7: "time_machine.png"
        }
        
        # Setup widget properties
        self.setFixedSize(270, 530)  # Match Tkinter dimensions
        
        # Create rotated timer display
        self.timer_display = RotatedWidget(self)
        self.timer_display.setRotatedFont('Arial')
        self.timer_display.setRotatedTextColor('white')
        self.timer_display.setAlignment(Qt.AlignCenter)
        
        # Setup layout
        layout = QVBoxLayout()
        layout.addWidget(self.timer_display)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # Create update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_timer_display)
        self.update_timer.start(100)  # 100ms interval, same as Tkinter
        
        # Initial display update
        self.update_display()
        
    def load_room_background(self, room_number):
        """Load the timer background for the specified room"""
        try:
            if room_number == self.current_room:
                return  # Already loaded
                
            self.current_room = room_number
            bg_filename = self.timer_backgrounds.get(room_number)
            
            if not bg_filename:
                print(f"No timer background defined for room {room_number}")
                return
                
            bg_path = os.path.join("timer_backgrounds", bg_filename)
            print(f"Loading timer background: {bg_path}")
            
            if not os.path.exists(bg_path):
                print(f"Timer background not found: {bg_path}")
                return
                
            # Load and resize the background image
            bg_img = Image.open(bg_path)
            bg_img = bg_img.resize((270, 530))  # Use exact dimensions
            
            # Convert PIL image to QPixmap
            pixmap = QPixmap.fromImage(bg_img.toqimage())
            self.timer_display.setBackgroundImage(pixmap)
            
        except Exception as e:
            print(f"Error loading timer background for room {room_number}: {e}")
            
    def handle_command(self, command, minutes=None):
        """Handle timer commands (start/stop/set)"""
        if command == "start":
            self.is_running = True
            self.last_update = time.time()
            print("Timer started")
            
        elif command == "stop":
            self.is_running = False
            self.last_update = None
            print("Timer stopped")
            
        elif command == "set" and minutes is not None:
            self.time_remaining = minutes * 60
            print(f"Timer set to {minutes} minutes")
            
        self.update_display()
        
    def update_timer_display(self):
        """Updates the timer display and checks for threshold crossings"""
        try:
            if self.is_running and self.last_update is not None:
                current_time = time.time()
                elapsed = current_time - self.last_update
                old_time = self.time_remaining
                self.time_remaining = max(0, self.time_remaining - elapsed)
                self.last_update = current_time
                
                # Check if we crossed any significant thresholds
                old_minutes = old_time / 60
                new_minutes = self.time_remaining / 60
                
                # If we crossed the 42-minute threshold (going down)
                if old_minutes > 42 and new_minutes <= 42:
                    print(f"\nTimer crossed 42-minute threshold (down)")
                    print(f"Old time: {old_minutes:.2f} minutes")
                    print(f"New time: {new_minutes:.2f} minutes")
                    # Emit signal for threshold crossing
                    self.threshold_crossed.emit(old_minutes, new_minutes)
                
                self.update_display()
                
        except Exception as e:
            print(f"Error in timer update: {e}")
            
    def update_display(self):
        """Update the timer display text"""
        try:
            minutes = int(self.time_remaining // 60)
            seconds = int(self.time_remaining % 60)
            display_text = f"{minutes:02d}:{seconds:02d}"
            
            # Update rotated text display
            self.timer_display.setRotatedText(display_text)
            
        except Exception as e:
            print(f"Error updating timer display: {e}")
            
    def raise_to_top(self):
        """Ensure timer stays on top of other widgets"""
        self.raise_()
        
    def paintEvent(self, event):
        """Custom paint event to handle background and ensure proper layering"""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw widget background (black by default)
        painter.fillRect(self.rect(), QColor('black'))