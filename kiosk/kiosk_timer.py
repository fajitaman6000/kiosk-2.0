from PyQt5.QtWidgets import QWidget, QVBoxLayout, QFrame
from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont
from PIL import Image
import os
import time

class TimerDisplay(QWidget):
    """Custom widget for rotated timer display with background image support"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = "45:00"
        self._background_image = None
        self._background_pixmap = None  # Store reference to prevent GC
        self.setFont(QFont('Arial', 70, QFont.Bold))
        
    def setText(self, text):
        """Update the displayed time text"""
        self._text = text
        self.update()
        
    def setBackgroundImage(self, image_path):
        """Set the timer background, maintaining reference"""
        try:
            if image_path and os.path.exists(image_path):
                # Load with PIL first for consistent resizing
                pil_image = Image.open(image_path)
                pil_image = pil_image.resize((270, 530))
                
                # Convert to QPixmap and store reference
                self._background_pixmap = QPixmap.fromImage(pil_image.toqimage())
                self._background_image = self._background_pixmap
                self.update()
                return True
        except Exception as e:
            print(f"Error loading timer background: {e}")
        return False
        
    def paintEvent(self, event):
        """Custom paint event with rotation and background handling"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Draw background
        if self._background_image and not self._background_image.isNull():
            painter.drawPixmap(self.rect(), self._background_image)
        else:
            painter.fillRect(self.rect(), QColor('black'))
        
        # Setup for rotated text
        painter.setPen(QColor('white'))
        painter.setFont(self.font())
        
        # Calculate text rect for rotation
        text_width = painter.fontMetrics().horizontalAdvance(self._text)
        text_height = painter.fontMetrics().height()
        
        # Create transform for 270-degree rotation
        painter.translate(self.width()/2, self.height()/2)
        painter.rotate(270)
        painter.translate(-text_width/2, text_height/4)
        
        # Draw text
        painter.drawText(0, 0, self._text)

class KioskTimer(QFrame):
    """
    PyQt5 implementation of the kiosk timer system.
    Handles timer display with background images and proper rotation.
    """
    
    # Signal for threshold crossings (e.g., 42-minute mark)
    threshold_crossed = pyqtSignal(float, float)  # old_minutes, new_minutes
    
    def __init__(self, parent=None):
        super().__init__(parent)
        print("Initializing KioskTimer")
        
        # State variables
        self.time_remaining = 60 * 45  # Default 45 minutes
        self.is_running = False
        self.last_update = None
        self.current_room = None
        
        # Room background mapping
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
        self.setFixedSize(270, 530)  # Match original dimensions
        self.setStyleSheet("QFrame { background-color: black; }")
        
        # Create timer display
        self.timer_display = TimerDisplay(self)
        self.timer_display.setFixedSize(270, 530)
        
        # Layout setup
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.timer_display)
        self.setLayout(layout)
        
        # Create update timer
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_timer_display)
        self.update_timer.start(100)  # 100ms interval
        
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
                
            # Load background using TimerDisplay's method
            success = self.timer_display.setBackgroundImage(bg_path)
            if success:
                print(f"Successfully loaded timer background for room {room_number}")
            
        except Exception as e:
            print(f"Error loading timer background: {e}")
            
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
        """Updates the timer and checks for threshold crossings"""
        try:
            if self.is_running and self.last_update is not None:
                current_time = time.time()
                elapsed = current_time - self.last_update
                old_time = self.time_remaining
                self.time_remaining = max(0, self.time_remaining - elapsed)
                self.last_update = current_time
                
                # Check for threshold crossings
                old_minutes = old_time / 60
                new_minutes = self.time_remaining / 60
                
                # Check 42-minute threshold (going down)
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
            
            # Update display
            self.timer_display.setText(display_text)
            
        except Exception as e:
            print(f"Error updating timer display: {e}")
            
    def raise_to_top(self):
        """Ensure timer stays on top of other widgets"""
        super().raise_()
        self.timer_display.raise_()
        
    def paintEvent(self, event):
        """Ensure proper background painting"""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw widget background
        painter.fillRect(self.rect(), QColor('black'))