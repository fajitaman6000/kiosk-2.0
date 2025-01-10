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
    _initialized = False
    
    @classmethod
    def init(cls, tkinter_root=None):
        """Initialize Qt application and base window"""
        if not cls._app:
            cls._app = QApplication(sys.argv)
            
        # Store Tkinter window handle
        if tkinter_root:
            cls._parent_hwnd = tkinter_root.winfo_id()
            
        # Create single persistent window if not already created
        if not cls._window:
            cls._window = QWidget()
            cls._window.setAttribute(Qt.WA_TranslucentBackground)
            cls._window.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool |
                Qt.WindowDoesNotAcceptFocus
            )
            
            # Set window to be an active window without focus
            cls._window.setAttribute(Qt.WA_ShowWithoutActivating)
            
            # Set the Qt window as child of Tkinter window
            if cls._parent_hwnd:
                win32gui.SetParent(int(cls._window.winId()), cls._parent_hwnd)
                style = win32gui.GetWindowLong(int(cls._window.winId()), win32con.GWL_EXSTYLE)
                win32gui.SetWindowLong(
                    int(cls._window.winId()),
                    win32con.GWL_EXSTYLE,
                    style | win32con.WS_EX_NOACTIVATE
                )
            
            # Create scene and view for cooldown text
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
            
            # Create text item for cooldown
            cls._text_item = QGraphicsTextItem()
            cls._text_item.setDefaultTextColor(Qt.yellow)
            font = QFont('Arial', 24)
            cls._text_item.setFont(font)
            cls._scene.addItem(cls._text_item)
            
        cls._initialized = True
    
    @classmethod
    def show_hint_cooldown(cls, seconds):
        """Show cooldown message with proper rotation"""
        if not cls._initialized or not cls._window:
            return
            
        width = 100
        height = 1079
        
        cls._window.setGeometry(510, 0, width, height)
        cls._view.setGeometry(0, 0, width, height)
        cls._scene.setSceneRect(QRectF(0, 0, width, height))
        
        message = f"Please wait {seconds} seconds until requesting the next hint."
        cls._text_item.setHtml(
            f'<div style="background-color: rgba(0, 0, 0, 180); padding: 20px;">{message}</div>'
        )
        
        cls._text_item.setTransform(QTransform())
        cls._text_item.setRotation(90)
        
        text_width = cls._text_item.boundingRect().width()
        text_height = cls._text_item.boundingRect().height()
        cls._text_item.setPos(
            (width + text_height) / 2,
            (height - text_width) / 2
        )
        
        cls._window.show()
        cls._window.raise_()
    
    @classmethod
    def init_timer(cls):
        """Initialize timer display components"""
        if not cls._initialized:
            print("Warning: Attempting to init_timer before base initialization")
            return
            
        if not hasattr(cls, '_timer'):
            cls._timer = TimerDisplay()
            
            # Create a separate window for the timer
            cls._timer_window = QWidget(cls._window)  # Make it a child of main window
            cls._timer_window.setAttribute(Qt.WA_TranslucentBackground)
            cls._timer_window.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool |
                Qt.WindowDoesNotAcceptFocus
            )
            cls._timer_window.setAttribute(Qt.WA_ShowWithoutActivating)
            
            # Set up timer scene and view
            cls._timer.scene = QGraphicsScene()
            cls._timer_view = QGraphicsView(cls._timer.scene, cls._timer_window)
            cls._timer_view.setStyleSheet("""
                QGraphicsView {
                    background: transparent;
                    border: none;
                }
            """)
            cls._timer_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._timer_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._timer_view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
            
            # Set up timer components
            cls._timer.bg_image_item = cls._timer.scene.addPixmap(QPixmap())
            cls._timer.text_item = QGraphicsTextItem()
            cls._timer.text_item.setDefaultTextColor(Qt.white)
            font = QFont('Arial', 70)
            font.setWeight(75)
            cls._timer.text_item.setFont(font)
            cls._timer.scene.addItem(cls._timer.text_item)
            
            # Set up timer window dimensions and position
            width = 270
            height = 530
            cls._timer_view.setGeometry(0, 0, width, height)
            cls._timer.scene.setSceneRect(QRectF(0, 0, width, height))
            
            # Position the timer window
            cls._timer_window.setGeometry(
                510 + (610 - 510) - 182,
                int((1079 - height) / 2),
                width,
                height
            )
            
            # Apply rotation to text
            cls._timer.text_item.setTransform(QTransform())
            cls._timer.text_item.setRotation(90)

            if cls._parent_hwnd:
                style = win32gui.GetWindowLong(int(cls._timer_window.winId()), win32con.GWL_EXSTYLE)
                win32gui.SetWindowLong(
                    int(cls._timer_window.winId()),
                    win32con.GWL_EXSTYLE,
                    style | win32con.WS_EX_NOACTIVATE
                )

    @classmethod
    def update_timer_display(cls, time_str):
        """Update the timer display with the given time string"""
        print("attempting to load timer")
        if not hasattr(cls, '_timer') or not cls._timer.text_item:
            return
            
        cls._timer.text_item.setHtml(f'<div>{time_str}</div>')
        cls._timer.text_item.setPos(135, 265)
        cls._timer_window.show()
        cls._timer_window.raise_()

    @classmethod
    def load_timer_background(cls, room_number):
        """Load the timer background for the specified room"""
        print("attempting to load timer bg")
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
        """Hide all overlay windows"""
        if cls._window:
            cls._window.hide()
        if hasattr(cls, '_timer_window'):
            cls._timer_window.hide()