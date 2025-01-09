from PyQt5.QtWidgets import QApplication, QWidget, QLabel
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QTransform, QPainter, QColor, QFont
import sys
import time
import os

class KioskTimer:
    def __init__(self, root, kiosk_app):
        """Initialize the timer with root and kiosk_app reference"""
        # Store references
        self.root = root
        self.kiosk_app = kiosk_app
        
        # Initialize timer state
        self.time_remaining = 60 * 45  # 45 minutes in seconds
        self.is_running = False
        self.last_update = None
        self.current_room = None
        
        # Initialize Qt
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()
            
        # Create main window
        self.window = QWidget()
        self.window.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.window.setAttribute(Qt.WA_TranslucentBackground)
        self.window.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # Set geometry - position on right side
        self.window.setGeometry(
            self.root.winfo_screenwidth() - 270 - 182,  # Match original x position
            (self.root.winfo_screenheight() - 530) // 2,  # Center vertically
            270,  # Original width
            530   # Original height
        )
        
        # Create background label
        self.bg_label = QLabel(self.window)
        self.bg_label.setGeometry(0, 0, 270, 530)
        
        # Create timer label
        self.timer_label = QLabel(self.window)
        self.timer_label.setGeometry(0, 0, 270, 530)
        self.timer_label.setAlignment(Qt.AlignCenter)
        
        # Style timer text
        font = QFont('Arial', 70, QFont.Bold)
        self.timer_label.setFont(font)
        self.timer_label.setStyleSheet('color: white;')
        
        # Set up Qt timer for updates
        self.qt_timer = QTimer()
        self.qt_timer.timeout.connect(self.update_timer)
        self.qt_timer.start(100)  # Update every 100ms
        
        # Define room backgrounds
        self.timer_backgrounds = {
            1: "casino_heist.png",
            2: "morning_after.png",
            3: "wizard_trials.png",
            4: "zombie_outbreak.png",
            5: "haunted_manor.png",
            6: "atlantis_rising.png",
            7: "time_machine.png"
        }
        
        # Show the window
        self.window.show()
        self.window.raise_()
        
    def load_room_background(self, room_number):
        """Load the timer background for the specified room"""
        if room_number == self.current_room:
            return
            
        self.current_room = room_number
        bg_filename = self.timer_backgrounds.get(room_number)
        
        if bg_filename:
            bg_path = os.path.join("timer_backgrounds", bg_filename)
            if os.path.exists(bg_path):
                # Load and scale background
                pixmap = QPixmap(bg_path)
                scaled_pixmap = pixmap.scaled(
                    270, 530,
                    Qt.KeepAspectRatioByExpanding,
                    Qt.SmoothTransformation
                )
                self.bg_label.setPixmap(scaled_pixmap)
                
    def handle_command(self, command, minutes=None):
        """Handle timer commands"""
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
        
    def update_timer(self):
        """Update timer state and check thresholds"""
        try:
            if self.is_running and self.last_update is not None:
                current_time = time.time()
                elapsed = current_time - self.last_update
                old_time = self.time_remaining
                self.time_remaining = max(0, self.time_remaining - elapsed)
                self.last_update = current_time
                
                # Check 42-minute threshold
                old_minutes = old_time / 60
                new_minutes = self.time_remaining / 60
                
                if old_minutes > 42 and new_minutes <= 42:
                    print(f"\nTimer crossed 42-minute threshold (down)")
                    if hasattr(self.kiosk_app, 'ui'):
                        self.root.after(0, self.kiosk_app.ui.create_help_button)
                
                self.update_display()
                
        except Exception as e:
            print(f"Error in update_timer: {e}")
            
    def update_display(self):
        """Update the timer display"""
        try:
            minutes = int(self.time_remaining // 60)
            seconds = int(self.time_remaining % 60)
            time_str = f"{minutes:02d}:{seconds:02d}"
            
            # Create rotated text
            pixmap = QPixmap(270, 530)
            pixmap.fill(Qt.transparent)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Rotate text
            transform = QTransform()
            transform.translate(270/2, 530/2)  # Move to center
            transform.rotate(270)              # Rotate
            painter.setTransform(transform)
            
            # Draw text
            painter.setFont(self.timer_label.font())
            painter.setPen(QColor('white'))
            painter.drawText(
                -530/2, -270/2, 530, 270,
                Qt.AlignCenter,
                time_str
            )
            painter.end()
            
            # Set the rotated text
            self.timer_label.setPixmap(pixmap)
            
            # Ensure window stays on top
            self.window.raise_()
            
        except Exception as e:
            print(f"Error updating display: {e}")
            
    def lift_to_top(self):
        """Ensure timer stays on top"""
        self.window.raise_()