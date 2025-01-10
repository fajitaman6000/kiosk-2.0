from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, 
                              QGraphicsScene, QGraphicsView, QGraphicsTextItem)
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QTransform, QFont, QPainter, QPixmap
from PIL import Image
import sys
import win32gui
import win32con
import os

class TimerDisplay:
    """Handles the visual elements of the timer display"""
    def __init__(self):
        self.scene = None
        self.text_item = None
        self.bg_image_item = None
        self._current_image = None
        
        # Define room to timer background mapping
        self.timer_backgrounds = {
            1: "casino_heist.png",
            2: "morning_after.png",
            3: "wizard_trials.png",
            4: "zombie_outbreak.png",
            5: "haunted_manor.png",
            6: "atlantis_rising.png",
            7: "time_machine.png"
        }


class Overlay:
    _app = None
    _window = None
    _parent_hwnd = None
    
    @classmethod
    def init(cls, tkinter_root=None):
        """Initialize Qt application once"""
        if not cls._app:
            cls._app = QApplication(sys.argv)
            
            # Store Tkinter window handle if provided
            if tkinter_root:
                cls._parent_hwnd = tkinter_root.winfo_id()
            
            # Create single persistent window
            cls._window = QWidget()
            cls._window.setAttribute(Qt.WA_TranslucentBackground)
            cls._window.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool |
                Qt.WindowDoesNotAcceptFocus
            )
            
            # Create graphics scene and view for rotation
            cls._scene = QGraphicsScene()
            cls._view = QGraphicsView(cls._scene, cls._window)
            cls._view.setStyleSheet("""
                QGraphicsView {
                    background: transparent;
                    border: none;
                }
            """)
            cls._view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
            
            # Create text item
            cls._text_item = QGraphicsTextItem()
            cls._text_item.setDefaultTextColor(Qt.yellow)
            font = QFont('Arial', 24)
            cls._text_item.setFont(font)
            cls._scene.addItem(cls._text_item)
            
            # Set window to be an active window without focus
            cls._window.setAttribute(Qt.WA_ShowWithoutActivating)
            
            # Set the Qt window as child of Tkinter window
            if cls._parent_hwnd:
                # Use the win32gui SetParent function instead of SetWindowLong
                win32gui.SetParent(
                    int(cls._window.winId()),
                    cls._parent_hwnd
                )
    
    @classmethod
    def show_hint_cooldown(cls, seconds):
        """Show cooldown message with proper rotation"""
        if not cls._app:
            cls.init()
        
        # Set window and view dimensions
        width = 100   # 610 - 510
        height = 1079
        
        # Position window
        cls._window.setGeometry(510, 0, width, height)
        cls._view.setGeometry(0, 0, width, height)
        
        # Set scene rect to match view
        cls._scene.setSceneRect(QRectF(0, 0, width, height))
        
        # Set up text
        message = f"Please wait {seconds} seconds until requesting the next hint."
        cls._text_item.setHtml(
            f'<div style="background-color: rgba(0, 0, 0, 180); padding: 20px;">{message}</div>'
        )
        
        # Reset and apply rotation transform
        cls._text_item.setTransform(QTransform())
        cls._text_item.setRotation(90)
        
        # Center the text
        text_width = cls._text_item.boundingRect().width()
        text_height = cls._text_item.boundingRect().height()
        cls._text_item.setPos(
            (width + text_height) / 2,
            (height - text_width) / 2
        )
        
        # Show and raise window
        cls._window.show()
        cls._window.raise_()
    
    @classmethod
    def init_timer(cls):
        """Initialize the timer display components"""
        if not cls._app:
            cls.init()
            
        # Create timer instance if it doesn't exist
        if not hasattr(cls, '_timer'):
            cls._timer = TimerDisplay()
            cls._timer.scene = QGraphicsScene()
            cls._timer_view = QGraphicsView(cls._timer.scene, cls._window)
            cls._timer_view.setStyleSheet("""
                QGraphicsView {
                    background: transparent;
                    border: none;
                }
            """)
            cls._timer_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._timer_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._timer_view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
            
            # Set up background placeholder first
            cls._timer.bg_image_item = cls._timer.scene.addPixmap(QPixmap())
            
            # Create timer text and add it after background
            cls._timer.text_item = QGraphicsTextItem()
            cls._timer.text_item.setDefaultTextColor(Qt.white)
            
            # Create font with correct weight parameter (QFont.Bold is 75)
            font = QFont('Arial', 70)
            font.setWeight(75)  # QFont.Bold
            cls._timer.text_item.setFont(font)
            
            # Add text item last so it appears on top
            cls._timer.scene.addItem(cls._timer.text_item)

            
            # Position window
            width = 270
            height = 530
            cls._timer_view.setGeometry(0, 0, width, height)
            cls._timer.scene.setSceneRect(QRectF(0, 0, width, height))
            
            # Position the window on the right side
            cls._window.setGeometry(
                510 + (610 - 510) - 182,  # Right edge with padding
                int((1079 - height) / 2),  # Vertical center
                width,
                height
            )
            
            # Apply rotation to text
            cls._timer.text_item.setTransform(QTransform())
            cls._timer.text_item.setRotation(90)

    @classmethod
    def update_timer_display(cls, time_str):
        """Update the timer display with the given time string"""
        if hasattr(cls, '_timer') and cls._timer.text_item:
            cls._timer.text_item.setHtml(f'<div>{time_str}</div>')
            
            # Center the text
            text_width = cls._timer.text_item.boundingRect().width()
            text_height = cls._timer.text_item.boundingRect().height()
            cls._timer.text_item.setPos(
                135,  # Horizontal center
                265   # Vertical center
            )
            cls._window.show()
            cls._window.raise_()

    @classmethod
    def load_timer_background(cls, room_number):
        """Load the timer background for the specified room"""
        if not hasattr(cls, '_timer'):
            return
            
        try:
            bg_filename = cls._timer.timer_backgrounds.get(room_number)
            if not bg_filename:
                print(f"No timer background defined for room {room_number}")
                return
                
            bg_path = os.path.join("timer_backgrounds", bg_filename)
            if not os.path.exists(bg_path):
                print(f"Timer background not found: {bg_path}")
                return
                
            # Load and resize the background image
            bg_img = Image.open(bg_path)
            bg_img = bg_img.resize((270, 530))
            
            from io import BytesIO
            from PyQt5.QtGui import QImage
            buf = BytesIO()
            bg_img.save(buf, format='PNG')
            qimg = QImage()
            qimg.loadFromData(buf.getvalue())
            pixmap = QPixmap.fromImage(qimg)
            
            # Update the background
            cls._timer.bg_image_item.setPixmap(pixmap)
            cls._timer._current_image = pixmap  # Store reference
            
        except Exception as e:
            print(f"Error loading timer background for room {room_number}: {e}")

    @classmethod
    def hide(cls):
        """Hide the overlay"""
        if cls._window:
            cls._window.hide()