from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, 
                              QGraphicsScene, QGraphicsView, QGraphicsTextItem)
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QTransform, QFont, QPainter
import sys
import win32gui
import win32con


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
    def hide(cls):
        """Hide the overlay"""
        if cls._window:
            cls._window.hide()