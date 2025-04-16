print("[qt init] Beginning imports ...")
from PyQt5.QtCore import Qt, QRectF, QThread, pyqtSignal, QMetaObject, Q_ARG, Qt, QPointF, pyqtSlot, QBuffer, QIODevice, QObject, QTimer
from PyQt5.QtGui import QTransform, QFont, QPainter, QPixmap, QImage, QPen, QBrush, QColor
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QGraphicsScene, QGraphicsView, QGraphicsTextItem, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsItem
from PIL import Image
import sys
import win32gui
import win32con
import os
import io
import traceback
import numpy as np # Needed for type hints / checks potentially
from config import ROOM_CONFIG
import cv2
import base64
from qt_classes import ClickableHintView, ClickableVideoView, TimerThread, TimerDisplay, HelpButtonThread, HintTextThread, HintRequestTextThread, VideoFrameItem
print("[qt init] Ending imports ...")


def init_fullscreen_hint(cls):
    """Initialize fullscreen hint display components."""
    if cls._fullscreen_hint_initialized:
        return

    print("[qt init] Initializing fullscreen hint components...")
    
    # Get the main window and content widget
    from qt_main import QtKioskApp
    main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
    content_widget = QtKioskApp.instance.content_widget if QtKioskApp.instance else None
    
    if not content_widget:
        print("[qt init] Error: No content widget available for fullscreen hint")
        if main_window:
            content_widget = main_window  # Fallback to main window
        else:
            return  # Can't proceed without parent
    
    try:
        # Create window as child of content widget
        cls._fullscreen_hint_window = QWidget(content_widget)
        cls._fullscreen_hint_window.setStyleSheet("background-color: black;") # Black background
        
        # Make it fill the entire parent
        cls._fullscreen_hint_window.setGeometry(0, 0, content_widget.width(), content_widget.height())

        # Create scene and view using the new clickable view
        cls._fullscreen_hint_scene = QGraphicsScene(cls._fullscreen_hint_window)
        cls._fullscreen_hint_view = ClickableHintView(cls._fullscreen_hint_scene, cls._fullscreen_hint_window) # Use ClickableHintView
        cls._fullscreen_hint_view.setStyleSheet("background: transparent; border: none;")
        cls._fullscreen_hint_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._fullscreen_hint_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # --- FIX: Call setRenderHint separately for each flag ---
        cls._fullscreen_hint_view.setRenderHint(QPainter.Antialiasing, True)
        cls._fullscreen_hint_view.setRenderHint(QPainter.SmoothPixmapTransform, True)
        # --- END FIX ---

        cls._fullscreen_hint_view.setCacheMode(QGraphicsView.CacheNone)
        cls._fullscreen_hint_view.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate) # Usually better for static images

        # Create and add pixmap item
        cls._fullscreen_hint_pixmap_item = QGraphicsPixmapItem()
        cls._fullscreen_hint_scene.addItem(cls._fullscreen_hint_pixmap_item)

        # Make view fill the parent
        cls._fullscreen_hint_view.setGeometry(0, 0, content_widget.width(), content_widget.height())
        cls._fullscreen_hint_scene.setSceneRect(0, 0, content_widget.width(), content_widget.height())
        
        # Hide initially
        cls._fullscreen_hint_window.hide()

        cls._fullscreen_hint_initialized = True
        print("[qt init] Fullscreen hint components initialized.")

    except Exception as e:
        print(f"[qt init] Error initializing fullscreen hint display: {e}")
        traceback.print_exc()
        cls._fullscreen_hint_initialized = False



def init_view_image_button(cls):
    """Initialize the 'View Image Hint' button components."""
    if cls._view_image_button_initialized:
        return
    print("[qt init] Initializing View Image Hint button components...")
    
    # Get the main window if available
    from qt_main import QtKioskApp
    main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
    
    if not main_window:
        print("[qt init] Warning: No main window available for View Image button")
        parent = cls._window
    else:
        parent = main_window
        
    try:
        cls._view_image_button = {
            'window': QWidget(parent), # Parent to main window
            'scene': QGraphicsScene(),
            'view': None,
            'rect': None,
            'text_item': None
        }

        # Window setup
        win = cls._view_image_button['window']
        win.setAttribute(Qt.WA_TranslucentBackground)
        
        # Use simpler window flags - avoid WindowStaysOnTopHint and Tool
        win.setWindowFlags(Qt.FramelessWindowHint)

        # Scene setup (already created)
        scene = cls._view_image_button['scene']

        # View setup (Using ClickableHintView for click signal)
        view = ClickableHintView(scene, win) # Reusing ClickableHintView
        view.setStyleSheet("background: transparent; border: none;")
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        cls._view_image_button['view'] = view

        # Button dimensions (from ui.py)
        button_width = 100
        button_height = 300

        # Rectangle (background)
        rect = QGraphicsRectItem(0, 0, button_width, button_height)
        rect.setBrush(QBrush(QColor(0, 0, 255, 200))) # Blue, semi-transparent
        rect.setPen(QPen(Qt.NoPen)) # No border
        scene.addItem(rect)
        cls._view_image_button['rect'] = rect

        # Inside _init_view_image_button (and similar for _init_view_solution_button)

        text_item = QGraphicsTextItem("VIEW IMAGE HINT")
        text_item.setDefaultTextColor(Qt.white)
        text_item.setFont(QFont('Arial', 24))
        scene.addItem(text_item)
        cls._view_image_button['text_item'] = text_item

        # 1. Calculate centers
        button_center_x = button_width / 2
        button_center_y = button_height / 2
        text_rect = text_item.boundingRect()
        text_center_x = text_rect.width() / 2
        text_center_y = text_rect.height() / 2

        # 2. Position the item's top-left so its center is at the button's center
        initial_pos_x = button_center_x - text_center_x
        initial_pos_y = button_center_y - text_center_y
        text_item.setPos(initial_pos_x, initial_pos_y)

        # 3. Set transform origin to the item's local center
        text_item.setTransformOriginPoint(text_center_x, text_center_y)

        # 4. Rotate
        text_item.setRotation(90)


        # Set geometry for view and scene rect
        view.setGeometry(0, 0, button_width, button_height)
        scene.setSceneRect(0, 0, button_width, button_height)

        cls._view_image_button_initialized = True
        print("[qt init] View Image Hint button initialized.")
    except Exception as e:
        print(f"[qt init] Error initializing View Image Hint button: {e}")
        traceback.print_exc()
        cls._view_image_button_initialized = False


def init_view_solution_button(cls):
    """Initialize the 'View Solution' button components."""
    if cls._view_solution_button_initialized:
        return
    print("[qt init] Initializing View Solution button components...")
    
    # Get the main window if available
    from qt_main import QtKioskApp
    main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
    
    if not main_window:
        print("[qt init] Warning: No main window available for View Solution button")
        parent = cls._window
    else:
        parent = main_window
        
    try:
        cls._view_solution_button = {
            'window': QWidget(parent), # Parent to main window
            'scene': QGraphicsScene(),
            'view': None,
            'rect': None,
            'text_item': None
        }

        # Window setup
        win = cls._view_solution_button['window']
        win.setAttribute(Qt.WA_TranslucentBackground)
        
        # Use simpler window flags - avoid WindowStaysOnTopHint and Tool
        win.setWindowFlags(Qt.FramelessWindowHint)

        # Scene setup (already created)
        scene = cls._view_solution_button['scene']

        # View setup (Using ClickableHintView for click signal)
        view = ClickableHintView(scene, win) # Reusing ClickableHintView
        view.setStyleSheet("background: transparent; border: none;")
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        cls._view_solution_button['view'] = view

        # Button dimensions (from ui.py)
        button_width = 100
        button_height = 400 # Note: Taller than image button

        # Rectangle (background)
        rect = QGraphicsRectItem(0, 0, button_width, button_height)
        rect.setBrush(QBrush(QColor(0, 0, 255, 200))) # Blue, semi-transparent
        rect.setPen(QPen(Qt.NoPen)) # No border
        scene.addItem(rect)
        cls._view_solution_button['rect'] = rect

        # Text Item
        text_item = QGraphicsTextItem("VIEW SOLUTION")
        text_item.setDefaultTextColor(Qt.white)
        text_item.setFont(QFont('Arial', 24))
        scene.addItem(text_item)
        cls._view_solution_button['text_item'] = text_item

        # 1. Calculate centers
        button_center_x = button_width / 2
        button_center_y = button_height / 2
        text_rect = text_item.boundingRect()
        text_center_x = text_rect.width() / 2
        text_center_y = text_rect.height() / 2

        # 2. Position the item's top-left so its center is at the button's center
        initial_pos_x = button_center_x - text_center_x
        initial_pos_y = button_center_y - text_center_y
        text_item.setPos(initial_pos_x, initial_pos_y)

        # 3. Set transform origin to the item's local center
        text_item.setTransformOriginPoint(text_center_x, text_center_y)

        # 4. Rotate
        text_item.setRotation(90)

        # Set geometry for view and scene rect
        view.setGeometry(0, 0, button_width, button_height)
        scene.setSceneRect(0, 0, button_width, button_height)

        cls._view_solution_button_initialized = True
        print("[qt init] View Solution button initialized.")
    except Exception as e:
        print(f"[qt init] Error initializing View Solution button: {e}")
        traceback.print_exc()
        cls._view_solution_button_initialized = False


def init_video_display(cls):
    """Initialize video display components (window, scene, view, item)."""
    if cls._video_is_initialized:
        return # Already initialized

    print("[qt init] Initializing video display components...")
    
    # Get the main window and content widget
    from qt_main import QtKioskApp
    main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
    content_widget = QtKioskApp.instance.content_widget if QtKioskApp.instance else None
    
    if not content_widget:
        print("[qt init] Error: No content widget available for video display")
        if main_window:
            content_widget = main_window  # Fallback to main window
        else:
            return  # Can't proceed without parent
    
    try:
        # Create video window as a child of content widget to ensure proper z-order
        cls._video_window = QWidget(content_widget)
        cls._video_window.setStyleSheet("background-color: black;") # Explicit black background
        
        # Video should be visible above background but below UI elements
        cls._video_window.setGeometry(0, 0, content_widget.width(), content_widget.height())
        
        # Create scene and view
        cls._video_scene = QGraphicsScene(cls._video_window)
        cls._video_view = ClickableVideoView(cls._video_scene, cls._video_window) # Use custom view
        cls._video_view.setStyleSheet("background: transparent; border: none;") # View transparent, window black
        cls._video_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._video_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._video_view.setRenderHint(QPainter.Antialiasing, False)
        cls._video_view.setCacheMode(QGraphicsView.CacheNone)
        cls._video_view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

        # Use the custom VideoFrameItem
        cls._video_frame_item = VideoFrameItem() # Use the new custom item
        cls._video_scene.addItem(cls._video_frame_item)

        # Full screen setup
        screen_geometry = QApplication.desktop().screenGeometry()
        width = screen_geometry.width()
        height = screen_geometry.height()

        cls._video_window.setGeometry(0, 0, width, height)
        cls._video_view.setGeometry(0, 0, width, height)
        cls._video_scene.setSceneRect(0, 0, width, height)
        cls._video_frame_item.setPos(0, 0) # Place item at top-left
        
        # Hide initially
        cls._video_window.hide()

        cls._video_is_initialized = True
        print("[qt init] Video display components initialized.")

    except Exception as e:
        print(f"[qt init] Error initializing video display: {e}")
        traceback.print_exc()
        cls._video_is_initialized = False


def init_hint_text_overlay(cls):
    """Initialize hint text overlay components."""
    # Get the main window and content widget
    from qt_main import QtKioskApp
    main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
    content_widget = QtKioskApp.instance.content_widget if QtKioskApp.instance else None
    
    if not content_widget:
        print("[qt init] Warning: No content widget available for hint text overlay")
        if main_window:
            parent = main_window
        else:
            parent = cls._window
    else:
        parent = content_widget
    
    if not hasattr(cls, '_hint_text') or not cls._hint_text:
        cls._hint_text = {
            'window': None,
            'scene': None,
            'view': None,
            'text_item': None,
            'bg_image_item': None,
            'current_background': None
        }

    # Create hint window if needed - CRITICAL: Create at the correct dimensions immediately
    if not cls._hint_text['window']:
        width = 588  # Default width for hint window
        height = 951  # Default height for hint window
        
        # Parent to content widget to ensure proper z-ordering
        cls._hint_text['window'] = QWidget(parent)
        
        # Critical: Set fixed geometry immediately at creation time
        cls._hint_text['window'].setGeometry(850, 80, width, height)
        
        # Make sure it's transparent
        cls._hint_text['window'].setAttribute(Qt.WA_TranslucentBackground, True)

    # Create scene and view if needed
    if not cls._hint_text['scene']:
        cls._hint_text['scene'] = QGraphicsScene()
    if not cls._hint_text['view']:
        cls._hint_text['view'] = QGraphicsView(cls._hint_text['scene'], cls._hint_text['window'])
        # Critical: Use explicit transparent background
        cls._hint_text['view'].viewport().setAutoFillBackground(False)
        cls._hint_text['view'].setStyleSheet("""
            QGraphicsView {
                background: transparent;
                border: none;
            }
        """)
        cls._hint_text['view'].setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._hint_text['view'].setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._hint_text['view'].setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        
        # Fill the window exactly
        width = cls._hint_text['window'].width()
        height = cls._hint_text['window'].height()
        cls._hint_text['view'].setGeometry(0, 0, width, height)
        cls._hint_text['scene'].setSceneRect(0, 0, width, height)

    # Create text item if needed
    if not cls._hint_text['text_item']:
        cls._hint_text['text_item'] = QGraphicsTextItem()
        cls._hint_text['text_item'].setDefaultTextColor(Qt.white)
        font = QFont('Arial', 22)
        cls._hint_text['text_item'].setFont(font)
        cls._hint_text['scene'].addItem(cls._hint_text['text_item'])

    # Set up background image for the hint text (not the main background)
    if not cls._hint_text['bg_image_item']:
        cls._hint_text['bg_image_item'] = cls._hint_text['scene'].addPixmap(QPixmap())
        cls._hint_text['bg_image_item'].setZValue(-1) # Set the image to the background layer


def init_hint_request_text_overlay(cls):
    """Initialize hint request text overlay components."""
    # Get the main window and content widget
    from qt_main import QtKioskApp
    main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
    content_widget = QtKioskApp.instance.content_widget if QtKioskApp.instance else None
    
    if not content_widget:
        print("[qt init] Warning: No content widget available for hint request text overlay")
        if main_window:
            parent = main_window
        else:
            parent = cls._window
    else:
        parent = content_widget
    
    if not hasattr(cls, '_hint_request_text') or not cls._hint_request_text:
        cls._hint_request_text = {
            'window': None,
            'scene': None,
            'view': None,
            'text_item': None,
            'bg_image_item': None,
            'current_background': None
        }

    # Create hint window if needed
    if not cls._hint_request_text['window']:
        # Define size and position
        width = 100  # Default width for hint request window
        height = 1079  # Default height for hint request window
        
        # Parent to content widget to ensure proper z-ordering
        cls._hint_request_text['window'] = QWidget(parent)
        
        # Critical: Set fixed geometry immediately at creation
        cls._hint_request_text['window'].setGeometry(510, 0, width, height)
        
        # Ensure transparency
        cls._hint_request_text['window'].setAttribute(Qt.WA_TranslucentBackground, True)

    # Create scene and view if needed
    if not cls._hint_request_text['scene']:
        cls._hint_request_text['scene'] = QGraphicsScene()
    if not cls._hint_request_text['view']:
        cls._hint_request_text['view'] = QGraphicsView(cls._hint_request_text['scene'], cls._hint_request_text['window'])
        
        # Critical: Explicitly disable auto-fill background
        cls._hint_request_text['view'].viewport().setAutoFillBackground(False)
        cls._hint_request_text['view'].setStyleSheet("""
            QGraphicsView {
                background: transparent;
                border: none;
            }
        """)
        cls._hint_request_text['view'].setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._hint_request_text['view'].setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._hint_request_text['view'].setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        
        # Fill the window exactly
        width = cls._hint_request_text['window'].width()
        height = cls._hint_request_text['window'].height()
        cls._hint_request_text['view'].setGeometry(0, 0, width, height)
        cls._hint_request_text['scene'].setSceneRect(0, 0, width, height)

    # Create text item if needed
    if not cls._hint_request_text['text_item']:
        cls._hint_request_text['text_item'] = QGraphicsTextItem()
        cls._hint_request_text['text_item'].setDefaultTextColor(Qt.yellow)
        font = QFont('Arial', 24)
        cls._hint_request_text['text_item'].setFont(font)
        cls._hint_request_text['scene'].addItem(cls._hint_request_text['text_item'])


def init_gm_assistance_overlay(cls):
    """Initialize game master assistance overlay components."""
    print("[qt init] Initializing GM assistance overlay...")
    print(f"[qt init] Has kiosk_app: {hasattr(cls, 'kiosk_app')}")
    if hasattr(cls, 'kiosk_app') and cls._kiosk_app is not None:
        print(f"[qt init] Using kiosk_app with computer_name: {cls._kiosk_app.computer_name}")
    else:
        print("[qt init] No kiosk_app available")
        
    if not hasattr(cls, '_gm_assistance_overlay') or not cls._gm_assistance_overlay:
        cls._gm_assistance_overlay = {
            'window': QWidget(cls._window),
            'scene': QGraphicsScene(),
            'view': None,
            'text_item': None,
            'yes_button': None,
            'no_button': None,
            'yes_rect': None,
            'no_rect': None
        }

        # Set up window properties
        cls._gm_assistance_overlay['window'].setAttribute(Qt.WA_TranslucentBackground)
        cls._gm_assistance_overlay['window'].setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowDoesNotAcceptFocus
        )
        cls._gm_assistance_overlay['window'].setAttribute(Qt.WA_ShowWithoutActivating)

        # Set up view
        cls._gm_assistance_overlay['view'] = QGraphicsView(
            cls._gm_assistance_overlay['scene'],
            cls._gm_assistance_overlay['window']
        )
        cls._gm_assistance_overlay['view'].setStyleSheet("""
            QGraphicsView {
                background: rgba(0, 0, 0, 180);
                border: 2px solid white;
                border-radius: 10px;
            }
        """)
        cls._gm_assistance_overlay['view'].setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._gm_assistance_overlay['view'].setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._gm_assistance_overlay['view'].setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        # Create and set up text item with centered text
        cls._gm_assistance_overlay['text_item'] = QGraphicsTextItem()
        cls._gm_assistance_overlay['text_item'].setDefaultTextColor(Qt.white)
        font = QFont('Arial', 24)
        cls._gm_assistance_overlay['text_item'].setFont(font)
        
        # Set text with proper centering - using table for guaranteed centering
        cls._gm_assistance_overlay['text_item'].setHtml(
            '<div style="width: 500px;">'
            '<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">'
            'Your game master offered<br>'
            'in-room assistance'
            '</td></tr></table>'
            '</div>'
        )
        cls._gm_assistance_overlay['scene'].addItem(cls._gm_assistance_overlay['text_item'])

        # Create button backgrounds (rectangles)
        yes_rect = QGraphicsRectItem(0, 0, 200, 60)  # Larger fixed size for buttons
        yes_rect.setBrush(QBrush(QColor(0, 128, 0, 204)))  # Semi-transparent green
        yes_rect.setPen(QPen(Qt.white))
        cls._gm_assistance_overlay['yes_rect'] = yes_rect
        cls._gm_assistance_overlay['scene'].addItem(yes_rect)

        no_rect = QGraphicsRectItem(0, 0, 200, 60)  # Larger fixed size for buttons
        no_rect.setBrush(QBrush(QColor(255, 0, 0, 204)))  # Semi-transparent red
        no_rect.setPen(QPen(Qt.white))
        cls._gm_assistance_overlay['no_rect'] = no_rect
        cls._gm_assistance_overlay['scene'].addItem(no_rect)

        # Create Yes button text
        yes_button = QGraphicsTextItem("Yes")
        yes_button.setDefaultTextColor(Qt.white)
        yes_button.setFont(QFont('Arial', 20))
        cls._gm_assistance_overlay['yes_button'] = yes_button
        cls._gm_assistance_overlay['scene'].addItem(yes_button)

        # Create No button text
        no_button = QGraphicsTextItem("No")
        no_button.setDefaultTextColor(Qt.white)
        no_button.setFont(QFont('Arial', 20))
        cls._gm_assistance_overlay['no_button'] = no_button
        cls._gm_assistance_overlay['scene'].addItem(no_button)

        # For a sideways window:
        window_width = 400
        window_height = 600

        # Position the window in the center of the screen
        screen_width = 1920  # Standard screen width
        screen_height = 1080  # Standard screen height
        x_pos = (screen_width - window_width) // 2  # Center horizontally
        y_pos = (screen_height - window_height) // 2  # Center vertically

        # Set window and view geometry
        cls._gm_assistance_overlay['window'].setGeometry(x_pos, y_pos, window_width, window_height)
        cls._gm_assistance_overlay['view'].setGeometry(0, 0, window_width, window_height)
        cls._gm_assistance_overlay['scene'].setSceneRect(0, 0, window_width, window_height)

        # First rotate all items
        cls._gm_assistance_overlay['text_item'].setRotation(90)
        yes_button.setRotation(90)
        no_button.setRotation(90)
        yes_rect.setRotation(90)
        no_rect.setRotation(90)

        # Get the rotated bounding rectangle for text
        text_rect = cls._gm_assistance_overlay['text_item'].boundingRect()
        text_width = text_rect.width()
        text_height = text_rect.height()

        # Calculate center position for rotated text
        x_center = (window_width - text_height) / 2 + 140
        y_center = (window_height + text_width) / 2

        # Position text in center, accounting for rotation pivot point
        cls._gm_assistance_overlay['text_item'].setPos(x_center, y_center - text_width)

        # Position buttons vertically (will appear to the left of text when rotated)
        button_spacing = 270  # Space between buttons
        button_width = 170  # Width of button rectangles
        button_height = 60  # Height of button rectangles
        
        # Base position for buttons (to the left of text when rotated)
        base_x = x_center - 150  # Distance from text
        base_y = y_center - text_width/2 + 30  # Moved base position down by 100 pixels

        # Position Yes button and its background (stays at original position)
        cls._gm_assistance_overlay['yes_rect'].setPos(base_x, base_y)

        # Center Yes text in button - calculate center of the button rectangle
        yes_text_width = cls._gm_assistance_overlay['yes_button'].boundingRect().width()
        yes_text_height = cls._gm_assistance_overlay['yes_button'].boundingRect().height()
        # Calculate the center point of the button rectangle
        yes_rect_center_x = base_x + button_height/2
        yes_rect_center_y = base_y + button_width/2
        # Position text at center point, accounting for text dimensions
        cls._gm_assistance_overlay['yes_button'].setPos(
            yes_rect_center_x - yes_text_height/2,
            yes_rect_center_y - yes_text_width/2
        )

        # Position No button and its background (moved up significantly)
        cls._gm_assistance_overlay['no_rect'].setPos(base_x, base_y - button_spacing)
        
        # Center No text in button - using same centering logic
        no_text_width = cls._gm_assistance_overlay['no_button'].boundingRect().width()
        no_text_height = cls._gm_assistance_overlay['no_button'].boundingRect().height()
        # Calculate the center point of the button rectangle
        no_rect_center_x = base_x + button_height/2
        no_rect_center_y = (base_y - button_spacing) + button_width/2
        # Position text at center point, accounting for text dimensions
        cls._gm_assistance_overlay['no_button'].setPos(
            no_rect_center_x - no_text_height/2,
            no_rect_center_y - no_text_width/2
        )

        # Add click handling to the view
        class GMAssistanceView(QGraphicsView):
            def mousePressEvent(self, event):
                scene_pos = self.mapToScene(event.pos())
                items = self.scene().items(scene_pos)
                for item in items:
                    if item == cls._gm_assistance_overlay['yes_rect'] or item == cls._gm_assistance_overlay['yes_button']:
                        print("[qt init] Yes button clicked - GM assistance accepted")
                        # Send message to admin using the kiosk app's network
                        if hasattr(cls, 'kiosk_app') and cls._kiosk_app is not None:
                            print(f"[qt init] Found kiosk_app with computer_name: {cls._kiosk_app.computer_name}")
                            try:
                                cls._kiosk_app.network.send_message({
                                    'type': 'gm_assistance_accepted',
                                    'computer_name': cls._kiosk_app.computer_name
                                })
                                print("[qt init] Message sent successfully")
                            except Exception as e:
                                print(f"[qt init] Error sending message: {e}")
                                traceback.print_exc()
                        else:
                            print("[qt init] Error: kiosk_app not found or is None")
                            print(f"[qt init] Has kiosk_app attribute: {hasattr(cls, 'kiosk_app')}")
                            if hasattr(cls, 'kiosk_app'):
                                print(f"[qt init] kiosk_app value: {cls._kiosk_app}")
                        # Hide the overlay after accepting
                        cls.hide_gm_assistance()
                        break
                    elif item == cls._gm_assistance_overlay['no_rect'] or item == cls._gm_assistance_overlay['no_button']:
                        print("[qt init] Player clicked \"No\" - In-room assistance declined")
                        # Hide the overlay after declining
                        cls.hide_gm_assistance()
                        break
                super().mousePressEvent(event)

        # Replace the view with our custom view
        old_view = cls._gm_assistance_overlay['view']
        cls._gm_assistance_overlay['view'] = GMAssistanceView(
            cls._gm_assistance_overlay['scene'],
            cls._gm_assistance_overlay['window']
        )
        cls._gm_assistance_overlay['view'].setStyleSheet(old_view.styleSheet())
        cls._gm_assistance_overlay['view'].setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._gm_assistance_overlay['view'].setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._gm_assistance_overlay['view'].setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        cls._gm_assistance_overlay['view'].setGeometry(0, 0, window_width, window_height)
        old_view.deleteLater()

        # Show the window immediately
        #cls._gm_assistance_overlay['window'].show()
        #cls._gm_assistance_overlay['view'].show()
        #cls._gm_assistance_overlay['window'].raise_()

    

def init_timer(cls):
    """Initialize the timer display components"""
    if not cls._initialized:
        print("[qt init]Warning: Attempting to init_timer before base initialization")
        return
    
    # Get the main window if available
    from qt_main import QtKioskApp
    main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
    
    if not main_window:
        print("[qt init] Warning: No main window available for timer")
        parent = cls._window
    else:
        parent = main_window
            
    if not hasattr(cls, '_timer'):
        print("[qt init]Initializing timer components...")
        cls._timer = TimerDisplay()
            
        # Create a separate window for the timer, parented to main window
        cls._timer_window = QWidget(parent)
        cls._timer_window.setAttribute(Qt.WA_TranslucentBackground)
        
        # Use simpler window flags - no WindowStaysOnTopHint or Tool
        cls._timer_window.setWindowFlags(Qt.FramelessWindowHint)
            
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
            
        # Set up background image first
        print("[qt init]Setting up background placeholder...")
        cls._timer.bg_image_item = cls._timer.scene.addPixmap(QPixmap())
        
        # Create timer text and add it after background
        print("[qt init]Setting up timer text...")
        cls._timer.text_item = QGraphicsTextItem()
        cls._timer.text_item.setDefaultTextColor(Qt.white)
        font = QFont('Arial', 120)
        font.setWeight(75)
        cls._timer.text_item.setFont(font)
        cls._timer.scene.addItem(cls._timer.text_item)
            
        # Set up timer window dimensions and position
        width = 500
        height = 750
        cls._timer_view.setGeometry(0, 0, width, height)
        cls._timer.scene.setSceneRect(QRectF(0, 0, width, height))
            
        # Position the timer window
        cls._timer_window.setGeometry(
            1400,
            170,
            width,
            height
        )
            
        # Apply rotation to text
        cls._timer.text_item.setTransform(QTransform())
        cls._timer.text_item.setRotation(90)
            
        print("[qt init]Timer initialization complete")



def init_help_button(cls):
    if not cls._initialized:
        print("[qt init]Warning: Attempting to init_help_button before base initialization")
        return
    
    # Get the main window if available
    from qt_main import QtKioskApp
    main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
    
    if not main_window:
        print("[qt init] Warning: No main window available for help button")
        parent = cls._window
    else:
        parent = main_window

    if not hasattr(cls, '_button'):
        print("[qt init]Initializing help button components...")
        cls._button = {}

        # Create a separate window for the button, parented to main window
        cls._button_window = QWidget(parent)
        cls._button_window.setAttribute(Qt.WA_TranslucentBackground)
        
        # Use simpler window flags - no WindowStaysOnTopHint or Tool
        cls._button_window.setWindowFlags(Qt.FramelessWindowHint)

        # Set up button scene and view using ClickableView instead of QGraphicsView
        cls._button['scene'] = QGraphicsScene()
        cls._button_view = ClickableVideoView(cls._button['scene'], cls._button_window)

        # Define view dimensions (increased to accommodate shadow)
        width = 440  # Increased width
        height = 780  # Increased height

        # Configure view
        cls._button_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._button_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._button_view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        cls._button_view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        cls._button_view.setFrameStyle(0)
        cls._button_view.setStyleSheet("background: transparent;")

        # Set view geometry
        cls._button_view.setGeometry(0, 0, width, height)

        # Set scene rect to match view
        scene_rect = QRectF(0, 0, width, height)
        cls._button['scene'].setSceneRect(scene_rect)

        # Set up placeholders for images
        cls._button['shadow_item'] = cls._button['scene'].addPixmap(QPixmap())
        cls._button['bg_image_item'] = cls._button['scene'].addPixmap(QPixmap())

        # Position button window
        cls._button_window.setGeometry(340, 290, width, height) # Adjusted button window size

        print("[qt init]Help button initialization complete")



def init_background(cls):
    """Initialize Qt components for displaying the background image"""
    try:
        # Get the main window's content widget to parent to
        from qt_main import QtKioskApp
        main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
        
        if not main_window:
            print("[qt init] Error: No main window available for parenting background window")
            return
        
        # Use content_widget as the parent to preserve proper z-ordering
        content_widget = QtKioskApp.instance.content_widget if QtKioskApp.instance else None
        if not content_widget:
            print("[qt init] Error: No content widget available, using main window")
            content_widget = main_window
            
        # Create background directly in the main window's content area
        # This is critical to ensure proper z-ordering
        cls._background_window = QWidget(content_widget)
        
        # Make it fill the entire parent and stay in the background
        cls._background_window.setGeometry(0, 0, main_window.width(), main_window.height())
        cls._background_window.lower()  # Ensure it stays at the back
        cls._background_window.setAutoFillBackground(True)  # Important for proper rendering
        
        # Create scene and view
        cls._background_scene = QGraphicsScene()
        cls._background_view = QGraphicsView(cls._background_scene, cls._background_window)
        cls._background_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._background_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._background_view.setStyleSheet("background: transparent; border: none;")
        cls._background_view.setFrameShape(QGraphicsView.NoFrame)
        cls._background_view.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Make view fill the background window
        cls._background_view.setGeometry(0, 0, main_window.width(), main_window.height())
        
        # Create pixmap item
        cls._background_pixmap_item = cls._background_scene.addPixmap(QPixmap())
        
        # Set scene rect to match view size
        cls._background_scene.setSceneRect(0, 0, main_window.width(), main_window.height())
        
        # Mark as initialized
        cls._background_initialized = True
        
        print("[qt_overlay] Background components initialized")
        
    except Exception as e:
        print(f"[qt_overlay] Error initializing background components: {str(e)}")
        traceback.print_exc()
        cls._background_initialized = False
        
    # --- Waiting Screen Label Methods ---

def init_waiting_label(cls):
    """Initialize the waiting screen label overlay."""
    if hasattr(cls, '_waiting_label_initialized') and cls._waiting_label_initialized:
        return

    print("[qt init] Initializing waiting screen label...")
    
    # Get the main window if available
    from qt_main import QtKioskApp
    main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
    
    try:
        screen_rect = cls._app.primaryScreen().geometry()
        screen_width = screen_rect.width()
        screen_height = screen_rect.height()

        # Parent to main window instead of being a separate top-level window
        window = QWidget(main_window)
        window.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # Use simpler window flags - avoid WindowStaysOnTopHint
        window.setWindowFlags(Qt.FramelessWindowHint)
        
        # Set geometry before creating view/scene
        window.setGeometry(0, 0, screen_width, screen_height)

        scene = QGraphicsScene(0, 0, screen_width, screen_height)
        view = QGraphicsView(scene, window)
        view.setParent(window) # Explicitly set parent
        view.setStyleSheet("background: transparent; border: 0px;")
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setRenderHint(QPainter.Antialiasing)
        # Ensure view covers the whole window area
        view.setGeometry(0, 0, screen_width, screen_height)

        text_item = QGraphicsTextItem()
        font = QFont("Arial", 24)
        text_item.setFont(font)
        text_item.setDefaultTextColor(Qt.white)
        # Set alignment within the text item's bounding rect
        text_item.setTextWidth(screen_width * 0.8) # Limit width for centering

        scene.addItem(text_item)

        cls._waiting_label = {
            'window': window,
            'view': view,
            'scene': scene,
            'text_item': text_item
        }
        cls._waiting_label_initialized = True
        print("[qt init] Waiting screen label initialized.")

    except Exception as e:
        print(f"[qt init] Error initializing waiting screen label: {e}")
        traceback.print_exc()
        cls._waiting_label = None # Ensure it's None on error
        cls._waiting_label_initialized = False
