print("[qt init] Beginning imports ...")
from PyQt5.QtCore import Qt, QRectF, QThread, pyqtSignal, QMetaObject, Q_ARG, Qt, QPointF, pyqtSlot, QBuffer, QIODevice, QObject, QTimer
from PyQt5.QtGui import QTransform, QFont, QPainter, QPixmap, QImage, QPen, QBrush, QColor
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QGraphicsScene, QGraphicsView, QGraphicsTextItem, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsItem, QVBoxLayout
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
    
    # Get the main window and container widget
    from qt_main import QtKioskApp
    main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
    # Use the fullscreen hint container instead of creating a new window
    container = QtKioskApp.instance.fullscreen_hint_container if QtKioskApp.instance else None
    
    if not container:
        print("[qt init] Error: No fullscreen hint container available")
        return  # Can't proceed without container
    
    try:
        # No need to create a new window, use container directly
        cls._fullscreen_hint_window = container  # Store reference to container

        # Create scene and view using the clickable view
        cls._fullscreen_hint_scene = QGraphicsScene(cls._fullscreen_hint_window)
        cls._fullscreen_hint_view = ClickableHintView(cls._fullscreen_hint_scene, cls._fullscreen_hint_window)
        cls._fullscreen_hint_view.setStyleSheet("background: transparent; border: none;")
        cls._fullscreen_hint_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._fullscreen_hint_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # --- FIX: Call setRenderHint separately for each flag ---
        cls._fullscreen_hint_view.setRenderHint(QPainter.Antialiasing, True)
        cls._fullscreen_hint_view.setRenderHint(QPainter.SmoothPixmapTransform, True)
        # --- END FIX ---

        cls._fullscreen_hint_view.setCacheMode(QGraphicsView.CacheNone)
        cls._fullscreen_hint_view.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)

        # Create and add pixmap item
        cls._fullscreen_hint_pixmap_item = QGraphicsPixmapItem()
        cls._fullscreen_hint_scene.addItem(cls._fullscreen_hint_pixmap_item)

        # Layout for container
        layout = QVBoxLayout(cls._fullscreen_hint_window)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(cls._fullscreen_hint_view)
        
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
    
    # Get the main window and container widget
    from qt_main import QtKioskApp
    main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
    container = QtKioskApp.instance.view_image_container if QtKioskApp.instance else None
    
    if not container:
        print("[qt init] Warning: No container available for View Image button")
        return
        
    try:
        cls._view_image_button = {
            'window': container,  # Use the container provided by main window
            'scene': QGraphicsScene(),
            'view': None,
            'rect': None,
            'text_item': None
        }

        # Scene setup (already created)
        scene = cls._view_image_button['scene']

        # View setup (Using ClickableHintView for click signal)
        view = ClickableHintView(scene, container)
        view.setStyleSheet("background: transparent; border: none;")
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        cls._view_image_button['view'] = view

        # Button dimensions
        button_width = 100
        button_height = 300

        # Rectangle (background)
        rect = QGraphicsRectItem(0, 0, button_width, button_height)
        rect.setBrush(QBrush(QColor(0, 0, 255, 200)))  # Blue, semi-transparent
        rect.setPen(QPen(Qt.NoPen))  # No border
        scene.addItem(rect)
        cls._view_image_button['rect'] = rect

        # Text item
        text_item = QGraphicsTextItem("VIEW IMAGE HINT")
        text_item.setDefaultTextColor(Qt.white)
        text_item.setFont(QFont('Arial', 24))
        scene.addItem(text_item)
        cls._view_image_button['text_item'] = text_item

        # Calculate centers
        button_center_x = button_width / 2
        button_center_y = button_height / 2
        text_rect = text_item.boundingRect()
        text_center_x = text_rect.width() / 2
        text_center_y = text_rect.height() / 2

        # Position the item's top-left so its center is at the button's center
        initial_pos_x = button_center_x - text_center_x
        initial_pos_y = button_center_y - text_center_y
        text_item.setPos(initial_pos_x, initial_pos_y)

        # Set transform origin to the item's local center
        text_item.setTransformOriginPoint(text_center_x, text_center_y)

        # Rotate
        text_item.setRotation(90)

        # Add the view to the container layout
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(view)
        
        # Set scene rect
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
    
    # Get the main window and container widget
    from qt_main import QtKioskApp
    main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
    container = QtKioskApp.instance.view_solution_container if QtKioskApp.instance else None
    
    if not container:
        print("[qt init] Warning: No container available for View Solution button")
        return
        
    try:
        cls._view_solution_button = {
            'window': container,  # Use the container provided by main window
            'scene': QGraphicsScene(),
            'view': None,
            'rect': None,
            'text_item': None
        }

        # Scene setup (already created)
        scene = cls._view_solution_button['scene']

        # View setup (Using ClickableHintView for click signal)
        view = ClickableHintView(scene, container)
        view.setStyleSheet("background: transparent; border: none;")
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        cls._view_solution_button['view'] = view

        # Button dimensions
        button_width = 100
        button_height = 400  # Note: Taller than image button

        # Rectangle (background)
        rect = QGraphicsRectItem(0, 0, button_width, button_height)
        rect.setBrush(QBrush(QColor(0, 0, 255, 200)))  # Blue, semi-transparent
        rect.setPen(QPen(Qt.NoPen))  # No border
        scene.addItem(rect)
        cls._view_solution_button['rect'] = rect

        # Text Item
        text_item = QGraphicsTextItem("VIEW SOLUTION")
        text_item.setDefaultTextColor(Qt.white)
        text_item.setFont(QFont('Arial', 24))
        scene.addItem(text_item)
        cls._view_solution_button['text_item'] = text_item

        # Calculate centers
        button_center_x = button_width / 2
        button_center_y = button_height / 2
        text_rect = text_item.boundingRect()
        text_center_x = text_rect.width() / 2
        text_center_y = text_rect.height() / 2

        # Position the item's top-left so its center is at the button's center
        initial_pos_x = button_center_x - text_center_x
        initial_pos_y = button_center_y - text_center_y
        text_item.setPos(initial_pos_x, initial_pos_y)

        # Set transform origin to the item's local center
        text_item.setTransformOriginPoint(text_center_x, text_center_y)

        # Rotate
        text_item.setRotation(90)

        # Add the view to the container layout
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(view)
        
        # Set scene rect
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
        return  # Already initialized

    print("[qt init] Initializing video display components...")
    
    # Get the video container from main window
    from qt_main import QtKioskApp
    main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
    container = QtKioskApp.instance.video_container if QtKioskApp.instance else None
    
    if not container:
        print("[qt init] Error: No container available for video display")
        return  # Can't proceed without container
    
    try:
        # Use the container directly instead of creating a new window
        cls._video_window = container
        
        # Create scene and view
        cls._video_scene = QGraphicsScene(cls._video_window)
        cls._video_view = ClickableVideoView(cls._video_scene, cls._video_window)
        cls._video_view.setStyleSheet("background: transparent; border: none;")
        cls._video_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._video_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._video_view.setRenderHint(QPainter.Antialiasing, False)
        cls._video_view.setCacheMode(QGraphicsView.CacheNone)
        cls._video_view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

        # Use the custom VideoFrameItem
        cls._video_frame_item = VideoFrameItem()
        cls._video_scene.addItem(cls._video_frame_item)

        # Set up layout for container
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(cls._video_view)
        
        # Set scene dimensions
        screen_geometry = QApplication.desktop().screenGeometry()
        width = screen_geometry.width()
        height = screen_geometry.height()
        cls._video_scene.setSceneRect(0, 0, width, height)
        cls._video_frame_item.setPos(0, 0)  # Place item at top-left
        
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
    # Get the hint container from main window
    from qt_main import QtKioskApp
    main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
    container = QtKioskApp.instance.hint_container if QtKioskApp.instance else None
    
    if not container:
        print("[qt init] Error: No container available for hint text overlay")
        return  # Can't proceed without container
    
    if not hasattr(cls, '_hint_text') or not cls._hint_text:
        cls._hint_text = {
            'window': container,  # Use the container directly
            'scene': None,
            'view': None,
            'text_item': None,
            'bg_image_item': None,
            'current_background': None
        }

    # Create scene if needed
    if not cls._hint_text['scene']:
        cls._hint_text['scene'] = QGraphicsScene()
        
    # Create view if needed
    if not cls._hint_text['view']:
        cls._hint_text['view'] = QGraphicsView(cls._hint_text['scene'], cls._hint_text['window'])
        # Make view transparent
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
        
        # Add view to container layout
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(cls._hint_text['view'])
        
        # Set scene rect
        width = container.width() or 588  # Default width if not yet set
        height = container.height() or 951  # Default height if not yet set
        cls._hint_text['scene'].setSceneRect(0, 0, width, height)

    # Create text item if needed
    if not cls._hint_text['text_item']:
        cls._hint_text['text_item'] = QGraphicsTextItem()
        cls._hint_text['text_item'].setDefaultTextColor(Qt.white)
        font = QFont('Arial', 22)
        cls._hint_text['text_item'].setFont(font)
        cls._hint_text['scene'].addItem(cls._hint_text['text_item'])

    # Set up background image for the hint text
    if not cls._hint_text['bg_image_item']:
        cls._hint_text['bg_image_item'] = cls._hint_text['scene'].addPixmap(QPixmap())
        cls._hint_text['bg_image_item'].setZValue(-1)  # Set the image to the background layer


def init_hint_request_text_overlay(cls):
    """Initialize hint request text overlay components."""
    # Get the hint request container from main window
    from qt_main import QtKioskApp
    main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
    container = QtKioskApp.instance.hint_request_container if QtKioskApp.instance else None
    
    if not container:
        print("[qt init] Error: No container available for hint request text overlay")
        return  # Can't proceed without container
    
    if not hasattr(cls, '_hint_request_text') or not cls._hint_request_text:
        cls._hint_request_text = {
            'window': container,  # Use the container directly
            'scene': None,
            'view': None,
            'text_item': None
        }

    # Create scene if needed
    if not cls._hint_request_text['scene']:
        cls._hint_request_text['scene'] = QGraphicsScene()
        
    # Create view if needed
    if not cls._hint_request_text['view']:
        cls._hint_request_text['view'] = QGraphicsView(cls._hint_request_text['scene'], cls._hint_request_text['window'])
        # Make view transparent
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
        
        # Add view to container layout
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(cls._hint_request_text['view'])
        
        # Set scene rect
        width = container.width() or 300  # Default width if not yet set
        height = container.height() or 100  # Default height if not yet set
        cls._hint_request_text['scene'].setSceneRect(0, 0, width, height)

    # Create text item if needed
    if not cls._hint_request_text['text_item']:
        cls._hint_request_text['text_item'] = QGraphicsTextItem()
        cls._hint_request_text['text_item'].setDefaultTextColor(Qt.yellow)
        font = QFont('Arial', 24)
        cls._hint_request_text['text_item'].setFont(font)
        cls._hint_request_text['scene'].addItem(cls._hint_request_text['text_item'])
        
    print("[qt init] Hint request text overlay initialized.")


def init_gm_assistance_overlay(cls):
    """Initialize game master assistance overlay components."""
    print("[qt init] Initializing GM assistance overlay...")
    
    # Get the GM assistance container from main window
    from qt_main import QtKioskApp
    main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
    container = QtKioskApp.instance.gm_assistance_container if QtKioskApp.instance else None
    
    if not container:
        print("[qt init] Error: No container available for GM assistance overlay")
        return  # Can't proceed without container
    
    if not hasattr(cls, '_gm_assistance_overlay') or not cls._gm_assistance_overlay:
        cls._gm_assistance_overlay = {
            'window': container,  # Use the container directly
            'scene': QGraphicsScene(),
            'view': None,
            'text_item': None,
            'yes_button': None,
            'no_button': None,
            'yes_rect': None,
            'no_rect': None
        }

        # Set up scene and view
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
        yes_rect = QGraphicsRectItem(0, 0, 200, 60)
        yes_rect.setBrush(QBrush(QColor(0, 128, 0, 204)))  # Semi-transparent green
        yes_rect.setPen(QPen(Qt.white))
        cls._gm_assistance_overlay['yes_rect'] = yes_rect
        cls._gm_assistance_overlay['scene'].addItem(yes_rect)

        no_rect = QGraphicsRectItem(0, 0, 200, 60)
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
        
        # Add view to container layout
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(cls._gm_assistance_overlay['view'])

        # Set scene dimensions and element positions
        window_width = 400
        window_height = 600
        cls._gm_assistance_overlay['scene'].setSceneRect(0, 0, window_width, window_height)

        # Position text in center
        text_rect = cls._gm_assistance_overlay['text_item'].boundingRect()
        x_center = (window_width - text_rect.width()) / 2
        y_center = 100  # Top position
        cls._gm_assistance_overlay['text_item'].setPos(x_center, y_center)

        # Position buttons
        button_spacing = 50  # Space between buttons
        button_width = 200
        button_height = 60
        
        # Position Yes button and its background
        base_x = (window_width - button_width) / 2
        base_y = 300  # Middle position
        cls._gm_assistance_overlay['yes_rect'].setPos(base_x, base_y)

        # Center Yes text in button
        yes_text_width = cls._gm_assistance_overlay['yes_button'].boundingRect().width()
        yes_text_height = cls._gm_assistance_overlay['yes_button'].boundingRect().height()
        yes_rect_center_x = base_x + button_width/2
        yes_rect_center_y = base_y + button_height/2
        cls._gm_assistance_overlay['yes_button'].setPos(
            yes_rect_center_x - yes_text_width/2,
            yes_rect_center_y - yes_text_height/2
        )

        # Position No button and its background
        cls._gm_assistance_overlay['no_rect'].setPos(base_x, base_y + button_height + button_spacing)
        
        # Center No text in button
        no_text_width = cls._gm_assistance_overlay['no_button'].boundingRect().width()
        no_text_height = cls._gm_assistance_overlay['no_button'].boundingRect().height()
        no_rect_center_x = base_x + button_width/2
        no_rect_center_y = (base_y + button_height + button_spacing) + button_height/2
        cls._gm_assistance_overlay['no_button'].setPos(
            no_rect_center_x - no_text_width/2,
            no_rect_center_y - no_text_height/2
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
                        if hasattr(cls, '_kiosk_app') and cls._kiosk_app is not None:
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
        old_view.deleteLater()
        
        # Replace old view in layout
        layout.removeWidget(old_view)
        layout.addWidget(cls._gm_assistance_overlay['view'])

        # Hide initially
        container.hide()
        
        print("[qt init] GM assistance overlay initialized")



def init_timer(cls):
    """Initialize the timer display components"""
    if not cls._initialized:
        print("[qt init]Warning: Attempting to init_timer before base initialization")
        return
    
    # Get the timer container from main window
    from qt_main import QtKioskApp
    main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
    container = QtKioskApp.instance.timer_container if QtKioskApp.instance else None
    
    if not container:
        print("[qt init] Error: No container available for timer")
        return  # Can't proceed without container
            
    if not hasattr(cls, '_timer'):
        print("[qt init]Initializing timer components...")
        cls._timer = TimerDisplay()
            
        # Use the container directly
        cls._timer_window = container
            
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
        
        # Add view to container layout
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(cls._timer_view)
        
        # Set scene dimensions
        width = 500
        height = 750 
        cls._timer.scene.setSceneRect(QRectF(0, 0, width, height))
            
        # Apply rotation to text
        cls._timer.text_item.setTransform(QTransform())
        cls._timer.text_item.setRotation(90)
            
        print("[qt init]Timer initialization complete")



def init_help_button(cls):
    if not cls._initialized:
        print("[qt init]Warning: Attempting to init_help_button before base initialization")
        return
    
    # Get the help button container from main window
    from qt_main import QtKioskApp
    main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
    container = QtKioskApp.instance.help_button_container if QtKioskApp.instance else None
    
    if not container:
        print("[qt init] Error: No container available for help button")
        return  # Can't proceed without container

    if not hasattr(cls, '_button'):
        print("[qt init]Initializing help button components...")
        cls._button = {}

        # Use the container directly
        cls._button_window = container

        # Set up button scene and view using ClickableView
        cls._button['scene'] = QGraphicsScene()
        cls._button_view = ClickableVideoView(cls._button['scene'], cls._button_window)

        # Configure view
        cls._button_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._button_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._button_view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        cls._button_view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        cls._button_view.setFrameStyle(0)
        cls._button_view.setStyleSheet("background: transparent;")

        # Add view to container layout
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(cls._button_view)

        # Define dimensions
        width = 440
        height = 780

        # Set scene rect
        scene_rect = QRectF(0, 0, width, height)
        cls._button['scene'].setSceneRect(scene_rect)

        # Set up placeholders for images
        cls._button['shadow_item'] = cls._button['scene'].addPixmap(QPixmap())
        cls._button['bg_image_item'] = cls._button['scene'].addPixmap(QPixmap())

        print("[qt init]Help button initialization complete")



def init_background(cls):
    """Initialize Qt components for displaying the background image"""
    try:
        # Get the background container from main window
        from qt_main import QtKioskApp
        main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
        container = QtKioskApp.instance.background_container if QtKioskApp.instance else None
        
        if not container:
            print("[qt init] Error: No container available for background")
            return  # Can't proceed without container
            
        # Use the container directly
        cls._background_window = container
        
        # Create scene and view
        cls._background_scene = QGraphicsScene()
        cls._background_view = QGraphicsView(cls._background_scene, cls._background_window)
        cls._background_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._background_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._background_view.setStyleSheet("background: transparent; border: none;")
        cls._background_view.setFrameShape(QGraphicsView.NoFrame)
        cls._background_view.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Add view to container layout
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(cls._background_view)
        
        # Create pixmap item
        cls._background_pixmap_item = cls._background_scene.addPixmap(QPixmap())
        
        # Set scene dimensions
        screen_geometry = QApplication.desktop().screenGeometry()
        width = screen_geometry.width()
        height = screen_geometry.height()
        cls._background_scene.setSceneRect(0, 0, width, height)
        
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
    
    # Get the waiting container from main window
    from qt_main import QtKioskApp
    main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
    container = QtKioskApp.instance.waiting_container if QtKioskApp.instance else None
    
    if not container:
        print("[qt init] Error: No container available for waiting screen")
        return  # Can't proceed without container
    
    try:
        # Get screen dimensions
        screen_rect = cls._app.primaryScreen().geometry()
        screen_width = screen_rect.width()
        screen_height = screen_rect.height()

        # Use the container directly
        window = container
        
        # Create scene and view
        scene = QGraphicsScene(0, 0, screen_width, screen_height)
        view = QGraphicsView(scene, window)
        view.setStyleSheet("background: transparent; border: 0px;")
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setRenderHint(QPainter.Antialiasing)
        
        # Add view to container layout
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(view)

        # Create text item
        text_item = QGraphicsTextItem()
        font = QFont("Arial", 24)
        text_item.setFont(font)
        text_item.setDefaultTextColor(Qt.white)
        text_item.setTextWidth(screen_width * 0.8)  # Limit width for centering

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
        cls._waiting_label = None  # Ensure it's None on error
        cls._waiting_label_initialized = False
