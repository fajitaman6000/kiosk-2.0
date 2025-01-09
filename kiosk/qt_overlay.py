from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, 
                              QGraphicsScene, QGraphicsView, QGraphicsTextItem)
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QTransform, QFont, QPainter, QImage, QPixmap
import sys
import win32gui
import win32con
import os

class Overlay:
    _app = None
    _window = None
    _parent_hwnd = None
    _timer_window = None
    
    @classmethod
    def init(cls, tkinter_root=None):
        """Initialize Qt application once"""
        if not cls._app:
            cls._app = QApplication(sys.argv)
            
            # Store Tkinter window handle if provided
            if tkinter_root:
                cls._parent_hwnd = tkinter_root.winfo_id()
            
            # Create single persistent window for cooldown
            cls._window = QWidget()
            cls._window.setAttribute(Qt.WA_TranslucentBackground)
            cls._window.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool |
                Qt.WindowDoesNotAcceptFocus
            )
            
            # Create graphics scene and view for cooldown
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
            
            # Create timer window and its components
            cls._timer_window = QWidget()
            cls._timer_window.setAttribute(Qt.WA_TranslucentBackground)
            cls._timer_window.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool |
                Qt.WindowDoesNotAcceptFocus
            )
            
            # Create timer scene and view
            cls._timer_scene = QGraphicsScene()
            cls._timer_view = QGraphicsView(cls._timer_scene, cls._timer_window)
            cls._timer_view.setStyleSheet("""
                QGraphicsView {
                    background: transparent;
                    border: none;
                }
            """)
            cls._timer_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._timer_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._timer_view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
            
            # Create timer text item
            cls._timer_text = QGraphicsTextItem()
            cls._timer_text.setDefaultTextColor(Qt.white)
            timer_font = QFont('Arial', 70, QFont.Bold)
            cls._timer_text.setFont(timer_font)
            cls._timer_scene.addItem(cls._timer_text)
            
            # Create background image item for timer
            cls._timer_bg = cls._timer_scene.addPixmap(QPixmap())
            
            # Set windows to be active without focus
            cls._window.setAttribute(Qt.WA_ShowWithoutActivating)
            cls._timer_window.setAttribute(Qt.WA_ShowWithoutActivating)
            
            # Set the Qt windows as children of Tkinter window
            if cls._parent_hwnd:
                win32gui.SetParent(int(cls._window.winId()), cls._parent_hwnd)
                win32gui.SetParent(int(cls._timer_window.winId()), cls._parent_hwnd)
    
    @classmethod
    def show_cooldown(cls, seconds):
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
    def show_timer(cls, time_str, room_number=None):
        """Show timer display with optional background"""
        if not cls._app:
            cls.init()
            
        # Set timer window dimensions
        width = 270     # Match original timer frame width
        height = 530    # Match original timer frame height
        
        # Position timer window (matching original placement)
        cls._timer_window.setGeometry(
            -182,    # Matches original x position
            (1079 // 2) - (height // 2),  # Center vertically
            width,
            height
        )
        
        # Configure view
        cls._timer_view.setGeometry(0, 0, width, height)
        cls._timer_scene.setSceneRect(QRectF(0, 0, width, height))
        
        # Load room-specific background if provided
        if room_number is not None:
            bg_filename = {
                1: "casino_heist.png",
                2: "morning_after.png",
                3: "wizard_trials.png",
                4: "zombie_outbreak.png",
                5: "haunted_manor.png",
                6: "atlantis_rising.png",
                7: "time_machine.png"
            }.get(room_number)
            
            if bg_filename:
                bg_path = os.path.join("timer_backgrounds", bg_filename)
                if os.path.exists(bg_path):
                    bg_image = QImage(bg_path)
                    bg_pixmap = QPixmap.fromImage(bg_image).scaled(
                        width,
                        height,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    cls._timer_bg.setPixmap(bg_pixmap)
                    cls._timer_bg.setPos(0, 0)
        
        # Set up timer text
        cls._timer_text.setPlainText(time_str)
        
        # Reset and apply rotation transform
        cls._timer_text.setTransform(QTransform())
        cls._timer_text.setRotation(270)
        
        # Center the text
        text_width = cls._timer_text.boundingRect().width()
        text_height = cls._timer_text.boundingRect().height()
        cls._timer_text.setPos(
            width // 2 + text_height // 2,
            height // 2 + text_width // 2
        )
        
        # Show and raise window
        cls._timer_window.show()
        cls._timer_window.raise_()
    
    @classmethod
    def hide_timer(cls):
        """Hide the timer overlay"""
        if cls._timer_window:
            cls._timer_window.hide()
    
    @classmethod
    def hide(cls):
        """Hide the cooldown overlay"""
        if cls._window:
            cls._window.hide()