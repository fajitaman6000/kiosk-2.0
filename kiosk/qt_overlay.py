# qt_overlay.py
print("[qt overlay] Beginning imports ...", flush=True)
print("[qt_overlay] Importing PyQt5.QtCore...", flush=True)
from PyQt5.QtCore import Qt, QRectF, QThread, pyqtSignal, QMetaObject, Q_ARG, Qt, QPointF, pyqtSlot, QBuffer, QIODevice, QObject, QTimer
print("[qt_overlay] Imported PyQt5.QtCore.", flush=True)

print("[qt_overlay] Importing PyQt5.QtGui...", flush=True)
from PyQt5.QtGui import QTransform, QFont, QPainter, QPixmap, QImage, QPen, QBrush, QColor
print("[qt_overlay] Imported PyQt5.QtGui.", flush=True)

print("[qt_overlay] Importing PyQt5.QtWidgets...", flush=True)
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QGraphicsScene, QGraphicsView, QGraphicsTextItem, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsItem
print("[qt_overlay] Imported PyQt5.QtWidgets.", flush=True)

print("[qt_overlay] Importing PIL...", flush=True)
from PIL import Image
print("[qt_overlay] Imported PIL.", flush=True)

print("[qt_overlay] Importing sys...", flush=True)
import sys
print("[qt_overlay] Imported sys.", flush=True)

print("[qt_overlay] Importing win32gui...", flush=True)
import win32gui
print("[qt_overlay] Imported win32gui.", flush=True)

print("[qt_overlay] Importing win32con...", flush=True)
import win32con
print("[qt_overlay] Imported win32con.", flush=True)

print("[qt_overlay] Importing os...", flush=True)
import os
print("[qt_overlay] Imported os.", flush=True)

print("[qt_overlay] Importing io...", flush=True)
import io
print("[qt_overlay] Imported io.", flush=True)

print("[qt_overlay] Importing traceback...", flush=True)
import traceback
print("[qt_overlay] Imported traceback.", flush=True)

print("[qt_overlay] Importing numpy...", flush=True)
import numpy as np # Needed for type hints / checks potentially
print("[qt_overlay] Imported numpy.", flush=True)

print("[qt_overlay] Importing config...", flush=True)
from config import ROOM_CONFIG
print("[qt_overlay] Imported config.", flush=True)

print("[qt_overlay] Importing cv2...", flush=True)
import cv2
print("[qt_overlay] Imported cv2.", flush=True)

print("[qt_overlay] Importing base64...", flush=True)
import base64
print("[qt_overlay] Imported base64.", flush=True)

print("[qt_overlay] Importing qt_classes...", flush=True)
from qt_classes import ClickableHintView, ClickableVideoView, TimerThread, TimerDisplay, HelpButtonThread, HintTextThread, HintRequestTextThread, VideoFrameItem
print("[qt_overlay] Imported qt_classes.", flush=True)

print("[qt_overlay] Importing qt_init...", flush=True)
from qt_init import init_fullscreen_hint, init_view_image_button, init_view_solution_button, init_video_display, init_hint_text_overlay, init_hint_request_text_overlay, init_gm_assistance_overlay, init_background, init_waiting_label, init_view_image_button, init_view_solution_button, init_timer, init_help_button
print("[qt_overlay] Imported qt_init.", flush=True)

print("[qt_overlay] Importing threading...", flush=True)
import threading
print("[qt_overlay] Imported threading.", flush=True)
print("[qt overlay] Ending imports ...", flush=True)

class OverlayBridge(QObject):
    """Receives invocations from other threads and calls Overlay class methods."""
    def __init__(self):
        super().__init__()
        self._timers = []  # Keep track of active timers

    # Add new signal for timer background updates
    timer_background_update_signal = pyqtSignal(QPixmap)
    # Add signal for complete timer background loading
    load_timer_background_signal = pyqtSignal(int)  # room_number
        
    @pyqtSlot(int, object)
    def schedule_timer(self, delay_ms, callback):
        """Schedule a timer in the Qt main thread"""
        if delay_ms == 0:
            # For immediate execution, use invokeMethod directly
            QMetaObject.invokeMethod(self, "execute_callback",
                                   Qt.QueuedConnection,
                                   Q_ARG(object, callback))
        else:
            # For delayed execution, create a single-shot timer
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self._handle_timer_timeout(timer, callback))
            self._timers.append(timer)
            timer.start(delay_ms)

    def _handle_timer_timeout(self, timer, callback):
        """Handle timer timeout and cleanup"""
        try:
            callback()
        except Exception as e:
            print(f"[qt overlay] Error executing callback: {e}")
            traceback.print_exc()
        finally:
            if timer in self._timers:
                self._timers.remove(timer)
            timer.deleteLater()

    @pyqtSlot(object)
    def execute_callback(self, callback):
        """Execute the callback in the Qt main thread"""
        try:
            callback()
        except Exception as e:
            print(f"[qt overlay] Error executing callback: {e}")
            traceback.print_exc()

    @pyqtSlot(bool, object) # For is_skippable (bool), click_callback (Python object)
    def prepare_video_display_slot(self, is_skippable, click_callback):
        # print("[qt_overlay] prepare_video_display_slot called")
        try:
            Overlay.prepare_video_display(is_skippable, click_callback)
            # Note: Returning success via BlockingQueuedConnection is complex.
            # We assume success if no exception occurs during the call.
        except Exception as e:
            print(f"[qt_overlay] Error in prepare_video_display_slot: {e}")
            traceback.print_exc()

    @pyqtSlot()
    def show_video_display_slot(self):
        # print("[qt_overlay] show_video_display_slot called")
        Overlay.show_video_display()

    @pyqtSlot()
    def hide_video_display_slot(self):
        # print("[qt_overlay] hide_video_display_slot called")
        Overlay.hide_video_display()

    @pyqtSlot()
    def destroy_video_display_slot(self):
        # print("[qt_overlay] destroy_video_display_slot called")
        Overlay.destroy_video_display()

    @pyqtSlot(object) # Frame data is a numpy array (object)
    def update_video_frame_slot(self, frame_data):
        # print("[qt_overlay] update_video_frame_slot called") # Very noisy
        Overlay.update_video_frame(frame_data)

    @pyqtSlot()
    def hide_all_overlays_slot(self):
        Overlay.hide_all_overlays()

    @pyqtSlot()
    def show_all_overlays_slot(self):
        Overlay.show_all_overlays()

    @pyqtSlot(bool)
    def check_game_loss_visibility_slot(self, game_lost):
        Overlay._check_game_loss_visibility(game_lost)

    @pyqtSlot(bool)
    def check_game_win_visibility_slot(self, game_won):
        Overlay._check_game_win_visibility(game_won)

    @pyqtSlot()
    def on_closing_slot(self):
        if hasattr(Overlay, '_kiosk_app') and Overlay._kiosk_app:
            Overlay._kiosk_app.on_closing()

    @pyqtSlot()
    def hide_overlays_for_video_slot(self):
        """No longer hides UI elements for video playback, since video is in its own top-level window."""
        Overlay.hide_overlays_for_video() # Now a no-op
        
    @pyqtSlot()
    def show_background_slot(self):
        """Show the background image if it exists."""
        Overlay.show_background()
        
    @pyqtSlot(QPixmap)
    def set_timer_background_slot(self, pixmap):
        """Update the timer background pixmap in the main thread."""
        Overlay._actual_timer_background_update(pixmap)
        
    @pyqtSlot(int)
    def load_timer_background_slot(self, room_number):
        """Load timer background in the main thread."""
        Overlay._actual_load_timer_background(room_number)

def convert_cv_qt(cv_img):
    """Convert from an opencv image (assuming BGR) to QPixmap"""
    try:
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        # Avoid scaling here if possible
        return QPixmap.fromImage(convert_to_Qt_format)
    except Exception as e:
        print(f"Error in convert_cv_qt: {e}")
        return QPixmap() # Return empty pixmap on error

class Overlay:
    TIMER_DEBUG = False
    _app = None
    _window = None
    _parent_hwnd = None
    _initialized = False
    _timer_thread = None
    _button_thread = None
    _hint_text_thread = None
    _hint_text = None
    _hint_request_text = None
    _hint_request_text_thread = None
    _gm_assistance_overlay = None  # Add GM assistance overlay variable
    _victory_screen = None  # Victory screen data
    _loss_screen = None # Loss screen data
    _game_won = False       # Flag for game won status
    _kiosk_app = None # Store kiosk_app reference explicitly
        # --- new class variables for video display ---
    _video_window = None
    _video_view = None
    _video_scene = None
    _video_frame_item = None # Custom item to draw QImage directly
    _video_click_callback = None # To store callback from video_manager
    _video_is_initialized = False
    _bridge = None
    _last_frame = None
     # --- Fullscreen Hint ---
    _fullscreen_hint_window = None
    _fullscreen_hint_scene = None
    _fullscreen_hint_view = None
    _fullscreen_hint_pixmap_item = None
    _fullscreen_hint_pixmap = None # To store the loaded/scaled pixmap
    _fullscreen_hint_ui_instance = None # To call restore_hint_view
    _fullscreen_hint_initialized = False
    # --- image/video buttons ---
    _view_image_button = None # Dictionary to hold window, scene, view, rect, text
    _view_image_button_initialized = False
    _view_image_button_ui_instance = None # To store ui instance for click

    _view_solution_button = None # Dictionary to hold window, scene, view, rect, text
    _view_solution_button_initialized = False
    _view_solution_button_ui_instance = None # To store ui instance for click

    # --- Waiting Screen ---
    _waiting_label = None # Dictionary: {'window': QWidget, 'view': QGraphicsView, 'scene': QGraphicsScene, 'text_item': QGraphicsTextItem}
    _waiting_label_initialized = False
    
    # --- Background image ---
    _background_window = None
    _background_scene = None
    _background_view = None
    _background_pixmap_item = None
    _background_initialized = False
    
    # --- Loss Screen ---
    _loss_screen_window = None
    _loss_screen_scene = None
    _loss_screen_view = None
    _loss_screen_pixmap_item = None
    _loss_screen_initialized = False
    
    # --- Victory Screen ---
    _victory_screen_window = None
    _victory_screen_scene = None
    _victory_screen_view = None
    _victory_screen_pixmap_item = None
    _victory_screen_initialized = False
    
    # Add the _ui_manager class variable to the list of class variables
    _ui_manager = None  # Reference to the UI manager for callbacks
    
    _current_hint_text_color = "#ffffff"
    _current_timer_text_color = "#ffffff"

    #_hint_background_cache = {}
    
    @classmethod
    def init(cls):
        print("[qt_overlay] Initializing Overlay...", flush=True)
        """Initialize the Qt overlay system."""
        if cls._initialized:
            return

        # Create QApplication if it doesn't exist
        if not QApplication.instance():
            print("[qt overlay] Creating QApplication...")
            cls._app = QApplication([])
            
        # Initialize timer scheduler in Qt main thread
        from message_handler import init_timer_scheduler
        init_timer_scheduler()

        # Create bridge for thread-safe operations
        print("[qt overlay] Creating OverlayBridge...")
        cls._bridge = OverlayBridge()
        
        # Connect timer background update signal
        print("[qt overlay] Connecting timer background update signal...")
        cls._bridge.timer_background_update_signal.connect(cls._actual_timer_background_update)
        cls._bridge.load_timer_background_signal.connect(cls._actual_load_timer_background)

        print("[qt overlay] Kiosk_app reference needs to be set separately.")

        # Get the main window if available
        from qt_main import QtKioskApp
        main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
        content_widget = QtKioskApp.instance.content_widget if QtKioskApp.instance else None
        
        if not main_window or not content_widget:
            print("[qt overlay] Warning: No main window/content widget available yet")
            # Create a temporary parent window if needed
            if not cls._window:
                cls._window = QWidget()
        else:
            print("[qt overlay] Using content widget as parent")
            # Use content_widget instead of main_window to preserve layering
            cls._window = content_widget
        
        # Create main overlay components if needed
        if not hasattr(cls, '_scene') or cls._scene is None:
            cls._scene = QGraphicsScene()
            cls._view = QGraphicsView(cls._scene, cls._window)
            cls._view.setStyleSheet("background: transparent; border: none;")
            cls._view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
            cls._text_item = QGraphicsTextItem()
            cls._text_item.setDefaultTextColor(Qt.yellow)
            font = QFont('Arial', 24)
            cls._text_item.setFont(font)
            cls._scene.addItem(cls._text_item)

        # Mark as initialized before creating components
        cls._initialized = True

        # Initialize background first to ensure it's at the bottom
        cls._init_background()  # Initialize background component
        
        # Then initialize all other overlays that should appear above it
        cls._init_hint_text_overlay()
        cls._init_hint_request_text_overlay()
        cls._init_gm_assistance_overlay()
        cls._init_video_display() # Initialize video components
        cls._init_fullscreen_hint()

        # Initialize timer and help button
        cls.init_timer()
        cls.init_help_button()

        # Hide GM assistance overlay initially
        cls.hide_gm_assistance()
        # Hide video display initially
        cls.hide_video_display()
        # Hide fullscreen hint initially
        cls.hide_fullscreen_hint()
        
        cls.hide_view_image_button()
        cls.hide_view_solution_button()
        cls._init_waiting_label() # Initialize waiting label
        cls.hide_waiting_screen_label() # Hide waiting label on init

        print("[qt overlay] Initialization complete.")
        print("[qt_overlay] Overlay initialized.", flush=True)
    
    @classmethod
    def set_kiosk_app(cls, kiosk_app):
        """Set the kiosk_app reference directly."""
        cls._kiosk_app = kiosk_app
        print(f"[qt overlay] Kiosk_app reference set: {kiosk_app}")

    @classmethod
    def _init_fullscreen_hint(cls):
        print("[qt_overlay] Initializing fullscreen hint...", flush=True)
        """Initialize fullscreen hint display components."""
        init_fullscreen_hint(cls)
        print("[qt_overlay] Fullscreen hint initialized.", flush=True)
    
    @classmethod
    def show_fullscreen_hint(cls, image_data_base64, ui_instance):
        """Displays the base64 image data in a fullscreen Qt overlay."""
        if not cls._initialized:
            print("[qt overlay] Overlay not initialized.")
            return
        if not image_data_base64:
            print("[qt overlay] No image data provided for fullscreen hint.")
            return
        if not ui_instance:
            print("[qt overlay] UI instance not provided for fullscreen hint.")
            return

        try:
            # Ensure initialized
            if not cls._fullscreen_hint_initialized:
                cls._init_fullscreen_hint()
            if not cls._fullscreen_hint_initialized: # Check again if init failed
                print("[qt overlay] Fullscreen hint failed to initialize.")
                return

            # Store UI instance for callback
            cls._fullscreen_hint_ui_instance = ui_instance

            print("[qt overlay] Showing fullscreen hint.")
            # 1. Hide other non-video overlays
            cls.hide_all_overlays() # Make sure this hides timer, buttons, text hints etc.
            
            # Explicitly hide the view image button when showing fullscreen image
            cls.hide_view_image_button()

            # 2. Decode and load image
            image_bytes = base64.b64decode(image_data_base64)
            q_image = QImage()
            q_image.loadFromData(image_bytes)
            if q_image.isNull():
                print("[qt overlay] Failed to load image data into QImage.")
                cls._fullscreen_hint_ui_instance = None # Clear instance if failed
                cls.show_all_overlays() # Restore UI on failure
                return
            pixmap = QPixmap.fromImage(q_image)

            # 3. Get screen dimensions for sizing calculations
            screen_width = QApplication.desktop().screenGeometry().width()
            screen_height = QApplication.desktop().screenGeometry().height()
            margin = 50 # Add some margin for padding

            # For 90 degree rotation, we swap width/height in calculations
            # The width becomes height, and height becomes width
            available_width = screen_height - (2 * margin)  # When rotated, width is constrained by screen height
            available_height = screen_width - (2 * margin)  # When rotated, height is constrained by screen width

            # Get original dimensions
            original_width = pixmap.width()
            original_height = pixmap.height()

            # Calculate scale factors for both dimensions
            width_scale = available_width / original_width
            height_scale = available_height / original_height

            # Use the smaller scale factor to ensure image fits in both dimensions
            scale_factor = min(width_scale, height_scale)

            # Calculate new dimensions - we want this LARGE, not tiny
            new_width = int(original_width * scale_factor)
            new_height = int(original_height * scale_factor)

            print(f"[qt overlay] Original image size: {original_width}x{original_height}")
            print(f"[qt overlay] New image size: {new_width}x{new_height}")
            print(f"[qt overlay] Scale factor: {scale_factor}")

            # Scale the pixmap to the exact size we want
            scaled_pixmap = pixmap.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            cls._fullscreen_hint_pixmap = scaled_pixmap # Store reference

            # 4. Configure scene and view for fullscreen display
            cls._fullscreen_hint_window.setGeometry(QApplication.desktop().screenGeometry())
            cls._fullscreen_hint_view.setGeometry(0, 0, screen_width, screen_height)
            cls._fullscreen_hint_scene.setSceneRect(0, 0, screen_width, screen_height)

            # Reset any existing transformations
            cls._fullscreen_hint_view.resetTransform()
            cls._fullscreen_hint_pixmap_item.setTransform(QTransform())
            
            # 5. Apply pixmap to item
            cls._fullscreen_hint_pixmap_item.setPixmap(cls._fullscreen_hint_pixmap)
            
            # Set the transform origin point to the center of the image
            cls._fullscreen_hint_pixmap_item.setTransformOriginPoint(new_width/2, new_height/2)
            
            # Position the image at the center of the screen
            center_x = screen_width / 2
            center_y = screen_height / 2
            item_origin_x = new_width / 2
            item_origin_y = new_height / 2
            cls._fullscreen_hint_pixmap_item.setPos(center_x - item_origin_x, center_y - item_origin_y)
            
            # Apply rotation after positioning
            cls._fullscreen_hint_pixmap_item.setRotation(90)

            # 6. Initially disconnect any previous click handler
            try:
                cls._fullscreen_hint_view.clicked.disconnect() # Disconnect previous
            except TypeError:
                pass # No connection existed

            # 7. Show window (without click handler connected)
            cls._fullscreen_hint_window.show()
            cls._fullscreen_hint_window.raise_()
            QApplication.processEvents() # Process pending events
            
            # 8. Connect click handler after 1.5 second delay
            print("[qt overlay] Setting 1.5 second delay before enabling click-to-close")
            QTimer.singleShot(1500, lambda: cls._enable_fullscreen_hint_close())

        except Exception as e:
            print(f"[qt overlay] Error showing fullscreen hint: {e}")
            traceback.print_exc()
            # Attempt to restore UI if error occurs
            if cls._fullscreen_hint_ui_instance:
                cls._fullscreen_hint_ui_instance = None
            cls.hide_fullscreen_hint() # Try to hide potentially broken overlay
            cls.show_all_overlays()    # Try to restore other overlays
            
    @classmethod
    def _enable_fullscreen_hint_close(cls):
        """Enable the click-to-close functionality for fullscreen hint after delay"""
        print("[qt overlay] Enabling click-to-close for fullscreen hint")
        try:
            if cls._fullscreen_hint_window and cls._fullscreen_hint_window.isVisible():
                # Now connect the click handler to allow closing
                cls._fullscreen_hint_view.clicked.connect(cls.hide_fullscreen_hint)
        except Exception as e:
            print(f"[qt overlay] Error enabling fullscreen hint close: {e}")
            traceback.print_exc()

    @classmethod
    def hide_fullscreen_hint(cls, restore_ui=True):
        """Hides the fullscreen hint overlay and optionally restores the normal UI."""
        if cls._fullscreen_hint_window and cls._fullscreen_hint_initialized:
            # Always hide the window and clear its content
            if cls._fullscreen_hint_window.isVisible():
                cls._fullscreen_hint_window.hide()
                # Clear the pixmap item to free memory
                cls._fullscreen_hint_pixmap_item.setPixmap(QPixmap())
                cls._fullscreen_hint_pixmap = None # Clear stored pixmap

            if restore_ui:
                # This is the original logic for when a user clicks to close the image.
                cls.hide_view_image_button()
                cls.show_all_overlays()

                if cls._fullscreen_hint_ui_instance:
                    try:
                        print("[qt overlay] Calling restore_hint_view...")
                        cls._fullscreen_hint_ui_instance.restore_hint_view()
                    except Exception as e:
                        print(f"[qt overlay] Error calling restore_hint_view: {e}")
                        traceback.print_exc()
            else:
                # This is the logic for a hard reset: just reset the flag in the UI manager.
                if cls._fullscreen_hint_ui_instance and hasattr(cls._fullscreen_hint_ui_instance, 'image_is_fullscreen'):
                    cls._fullscreen_hint_ui_instance.image_is_fullscreen = False

    @classmethod
    def _init_view_image_button(cls):
        print("[qt_overlay] Initializing view image button...", flush=True)
        """Initialize the 'View Image Hint' button components."""
        init_view_image_button(cls)
        print("[qt_overlay] View image button initialized.", flush=True)

    @classmethod
    def _init_view_solution_button(cls):
        print("[qt_overlay] Initializing view solution button...", flush=True)
        """Initialize the 'View Solution' button components."""
        init_view_solution_button(cls)
        print("[qt_overlay] View solution button initialized.", flush=True)

    @classmethod
    def _on_view_image_button_clicked(cls):
        """Callback when the Qt 'View Image Hint' button is clicked."""
        print("[qt overlay] View Image button clicked.")
        if hasattr(cls, '_ui_manager') and cls._ui_manager and hasattr(cls._ui_manager, 'on_view_image_clicked'):
            cls._ui_manager.on_view_image_clicked()
        else:
            print("[qt overlay] Error: No UI manager or on_view_image_clicked method available for View Image click.")

    @classmethod
    def _on_view_solution_button_clicked(cls):
        """Callback when the Qt 'View Solution' button is clicked."""
        print("[qt overlay] View Solution button clicked.")
        if hasattr(cls, '_ui_manager') and cls._ui_manager and hasattr(cls._ui_manager, 'on_view_solution_clicked'):
            cls._ui_manager.on_view_solution_clicked()
        else:
            print("[qt overlay] Error: No UI manager or on_view_solution_clicked method available for View Solution click.")

    @classmethod
    def show_view_image_button(cls, ui_instance):
        """Shows the 'View Image Hint' button overlay."""
        if not ui_instance:
            print("[qt overlay] Error: ui_instance required to show view image button.")
            return
        if not cls._initialized:
            print("[qt overlay] Overlay not initialized.")
            return

        if not cls._view_image_button_initialized:
            cls._init_view_image_button()
        if not cls._view_image_button_initialized: # Check again if init failed
            print("[qt overlay] View Image Hint button failed to initialize.")
            return

        try:
            print("[qt overlay] Showing View Image Hint button.")
            cls._view_image_button_ui_instance = ui_instance # Store instance for click

            button_info = cls._view_image_button
            win = button_info['window']
            view = button_info['view']

            # Dimensions (from ui.py)
            button_width = 100
            button_height = 300
            hint_window_x = 850 # Known position of the main hint text window
            hint_window_height = 951 # Known height of main hint text window
            hint_window_y = 80 # Known Y of main hint text window

            # Calculate position (Place it to the left of the hint text)
            button_x = hint_window_x - button_width - 10 # 10px gap
            # Center vertically relative to the hint text window
            button_y = hint_window_y + (hint_window_height - button_height) // 2

            # Set window geometry
            win.setGeometry(button_x, button_y, button_width, button_height)

            # Connect click signal (disconnect first to avoid duplicates)
            try:
                view.clicked.disconnect()
            except TypeError:
                pass # No connection existed
            view.clicked.connect(cls._on_view_image_button_clicked)

            # Show
            win.show()
            win.raise_()

        except Exception as e:
            print(f"[qt overlay] Error showing View Image Hint button: {e}")
            traceback.print_exc()

    @classmethod
    def show_view_solution_button(cls, ui_instance):
        """Shows the 'View Solution' button overlay."""
        if not ui_instance:
            print("[qt overlay] Error: ui_instance required to show view solution button.")
            return
        if not cls._initialized:
            print("[qt overlay] Overlay not initialized.")
            return

        if not cls._view_solution_button_initialized:
            cls._init_view_solution_button()
        if not cls._view_solution_button_initialized: # Check again
            print("[qt overlay] View Solution button failed to initialize.")
            return

        try:
            print("[qt overlay] Showing View Solution button.")
            cls._view_solution_button_ui_instance = ui_instance # Store instance

            button_info = cls._view_solution_button
            win = button_info['window']
            view = button_info['view']

            # Dimensions (from ui.py)
            button_width = 100
            button_height = 400 # Taller
            hint_window_x = 850
            hint_window_height = 951
            hint_window_y = 80

            # Calculate position (Place it to the left of the hint text)
            button_x = hint_window_x - button_width - 10
            # Center vertically relative to the hint text window
            button_y = hint_window_y + (hint_window_height - button_height) // 2

            # Set window geometry
            win.setGeometry(button_x, button_y, button_width, button_height)

            # Connect click signal
            try:
                view.clicked.disconnect()
            except TypeError:
                pass
            view.clicked.connect(cls._on_view_solution_button_clicked)

            # Show
            win.show()
            win.raise_()

        except Exception as e:
            print(f"[qt overlay] Error showing View Solution button: {e}")
            traceback.print_exc()

    @classmethod
    def hide_view_image_button(cls):
        """Hides the 'View Image Hint' button overlay."""
        if cls._view_image_button_initialized and cls._view_image_button and cls._view_image_button['window']:
            if cls._view_image_button['window'].isVisible():
                # print("[qt overlay] Hiding View Image Hint button.") # Debug
                cls._view_image_button['window'].hide()
                # Optionally disconnect signal here if needed
                # cls._view_image_button_ui_instance = None # Clear instance ref
        # else:
            # print("[qt overlay] View Image Hint button not initialized or window missing.") # Debug

    @classmethod
    def hide_view_solution_button(cls):
        """Hides the 'View Solution' button overlay."""
        if cls._view_solution_button_initialized and cls._view_solution_button and cls._view_solution_button['window']:
            if cls._view_solution_button['window'].isVisible():
                # print("[qt overlay] Hiding View Solution button.") # Debug
                cls._view_solution_button['window'].hide()
                # Optionally disconnect signal here if needed
                # cls._view_solution_button_ui_instance = None # Clear instance ref
        # else:
            # print("[qt overlay] View Solution button not initialized or window missing.") # Debug

    @classmethod
    def _init_video_display(cls):
        print("[qt_overlay] Initializing video display...", flush=True)
        """Initialize video display components (window, scene, view, item)."""
        init_video_display(cls)
        print("[qt_overlay] Video display initialized.", flush=True)

    @classmethod
    def prepare_video_display(cls, is_skippable, click_callback):
        """Prepare the video display, set skippable state and connect callback."""
        if not cls._video_is_initialized:
            print("[qt overlay] Video display not initialized, attempting now.")
            cls._init_video_display()
            if not cls._video_is_initialized:
                print("[qt overlay] Failed to initialize video display during prepare.")
                return

        if not cls._video_window or not cls._video_view or not cls._video_frame_item: # Check for frame item
            print("[qt overlay] Error: Video window, view, or frame item is missing during prepare.")
            return

        print(f"[qt overlay] Preparing video display. Skippable: {is_skippable}")
        cls._video_click_callback = click_callback
        cls._video_view.set_skippable(is_skippable)

        try:
            if cls._video_view.receivers(cls._video_view.clicked) > 0:
                cls._video_view.clicked.disconnect()
        except TypeError:
            pass
        except Exception as e:
            print(f"[qt overlay] Error disconnecting video click signal: {e}")

        if click_callback:
            try:
                cls._video_view.clicked.connect(cls._video_click_callback)
                print("[qt overlay] Connected video click signal.")
            except Exception as e:
                print(f"[qt overlay] Error connecting video click signal: {e}")
        else:
            print("[qt overlay] No click callback provided for video.")

        screen_geometry = QApplication.desktop().screenGeometry()
        cls._video_window.setGeometry(screen_geometry)
        cls._video_view.setGeometry(0, 0, screen_geometry.width(), screen_geometry.height())
        cls._video_scene.setSceneRect(0, 0, screen_geometry.width(), screen_geometry.height())

        # --- Clear previous frame using the custom item's method ---
        # --- REMOVE ---
        # cls._video_pixmap_item.setPixmap(QPixmap())
        # +++ ADD +++
        cls._video_frame_item.setImage(None) # Set empty image in the custom item
        # --- END CHANGE ---
        cls._last_frame = None

        cls._video_frame_item.setPos(0,0)

    @classmethod
    def show_video_display(cls):
        """Show the video display window."""
        if cls._video_window and cls._video_is_initialized:
            print("[qt overlay] Showing video display.")
            # Ensure it's visible and on top within the application
            cls._video_window.show()
            cls._video_window.raise_()
            cls._video_window.activateWindow() # Set focus to the video window initially
            
            # Get the handle to the main application window
            from qt_main import QtKioskApp
            if QtKioskApp.instance and QtKioskApp.instance.main_window:
                # Make the video window a child of the main window in the window hierarchy
                # but not in the widget hierarchy, so it can be tabbed away from
                import win32gui
                try:
                    main_hwnd = int(QtKioskApp.instance.main_window.winId())
                    video_hwnd = int(cls._video_window.winId())
                    # Set the main window as owner (not parent) of the video window
                    # This keeps visual hierarchy while allowing tabbing out
                    win32gui.SetWindowLong(video_hwnd, win32con.GWL_HWNDPARENT, main_hwnd)
                except Exception as e:
                    print(f"[qt overlay] Error setting window parent relationship: {e}")
                    
            QApplication.processEvents() # Process pending events
        else:
            print("[qt overlay] Cannot show video display: not initialized or window missing.")

    @classmethod
    def hide_video_display(cls):
        """Hide the video display window."""
        if cls._video_window and cls._video_is_initialized:
            if cls._video_window.isVisible():
                cls._video_window.hide()
            # Clear frame in custom item
            if cls._video_frame_item:
                cls._video_frame_item.setImage(None) # Clear the image
            cls._last_frame = None

    @classmethod
    def destroy_video_display(cls):
        """Hide and clean up video display resources."""
        thread_id = threading.get_ident()
        print(f"[qt overlay][DESTROY_{thread_id}] +++ destroy_video_display ENTERED (Thread: {thread_id}) +++") # ADDED PRINT
        if cls._video_window and cls._video_is_initialized:
            print(f"[qt overlay][DESTROY_{thread_id}] Video window exists and is initialized. Destroying...")
            if cls._video_window.isVisible():
                print(f"[qt overlay][DESTROY_{thread_id}] Hiding video window...")
                cls._video_window.hide()

            try:
                if cls._video_view and cls._video_view.receivers(cls._video_view.clicked) > 0:
                    print(f"[qt overlay][DESTROY_{thread_id}] Disconnecting video click signal...")
                    cls._video_view.clicked.disconnect()
            except TypeError:
                pass # No signal connected
            except Exception as e:
                print(f"[qt overlay][DESTROY_{thread_id}] Error disconnecting video signal: {e}")

            # --- Schedule Qt objects for deletion ---
            print(f"[qt overlay][DESTROY_{thread_id}] Scheduling Qt objects for deletion...")
            if cls._video_frame_item and cls._video_scene:
                if cls._video_frame_item in cls._video_scene.items():
                    print(f"[qt overlay][DESTROY_{thread_id}] Removing video_frame_item from scene...")
                    cls._video_scene.removeItem(cls._video_frame_item)
                # Don't call deleteLater on items removed from scene explicitly, might be redundant/problematic
                # cls._video_frame_item.deleteLater()

            if cls._video_view:
                print(f"[qt overlay][DESTROY_{thread_id}] Scheduling video_view deletion...")
                cls._video_view.deleteLater()
            if cls._video_scene:
                print(f"[qt overlay][DESTROY_{thread_id}] Scheduling video_scene deletion...")
                cls._video_scene.deleteLater()
            if cls._video_window: # Check again as deleteLater might have been called
                print(f"[qt overlay][DESTROY_{thread_id}] Scheduling video_window deletion...")
                cls._video_window.deleteLater()

            # --- Reset state variables ---
            print(f"[qt overlay][DESTROY_{thread_id}] Resetting state variables...")
            cls._video_window = None
            cls._video_view = None
            cls._video_scene = None
            cls._video_frame_item = None
            cls._video_click_callback = None
            cls._last_frame = None
            cls._video_is_initialized = False
            print(f"[qt overlay][DESTROY_{thread_id}] Video display destroyed.")
        else:
            print(f"[qt overlay][DESTROY_{thread_id}] Video display not destroyed (window missing or not initialized).")
        print(f"[qt overlay][DESTROY_{thread_id}] --- destroy_video_display FINISHED (Thread: {thread_id}) ---") # ADDED PRINT

    @classmethod
    def update_video_frame(cls, frame_data):
        """
        Receives raw frame data (NumPy array BGR) and updates the display.
        MUST be called from the main GUI thread (via bridge slot).
        Scales the frame to fit the view while maintaining aspect ratio.
        """
        if not cls._video_window or not cls._video_frame_item or not cls._video_is_initialized or not cls._video_window.isVisible():
            return

        if frame_data is None or not isinstance(frame_data, np.ndarray):
            # print("[qt overlay] Invalid or null frame data received.") # Can be noisy if video ends
            # If frame is None (e.g., end of video), ensure the last frame is cleared
            if frame_data is None and cls._video_frame_item:
                 cls._video_frame_item.setImage(None)
                 cls._last_frame = None
                 if cls._video_view:
                     cls._video_view.viewport().update()
            return

        try:
            height, width, channel = frame_data.shape
            if channel != 3:
                print(f"[qt overlay] Unexpected frame channel count: {channel}")
                return

            bytes_per_line = channel * width
            if not frame_data.flags['C_CONTIGUOUS']:
                frame_data = np.ascontiguousarray(frame_data)

            # Create QImage wrapper (NO QPixmap!)
            # Assuming BGR input from OpenCV's cap.read()
            q_image = QImage(frame_data.data, width, height, bytes_per_line, QImage.Format_BGR888)

            # Set the QImage on the custom item
            cls._video_frame_item.setImage(q_image)

            # Keep the QImage reference alive (important!)
            cls._last_frame = q_image

            # --- SCALING LOGIC ---
            # Get the item and view references
            item = cls._video_frame_item
            view = cls._video_view

            if item and view:
                # Get the current bounding rectangle of the item (based on the new q_image)
                item_rect = item.boundingRect()
                if not item_rect.isEmpty():
                    # Tell the view to scale the item's rectangle to fit within the view,
                    # maintaining the aspect ratio. This handles both upscaling and downscaling
                    # for display purposes.
                    view.fitInView(item_rect, Qt.KeepAspectRatio)

            # Trigger Viewport Update (might be redundant after fitInView, but safe)
            if cls._video_view:
                cls._video_view.viewport().update()

        except Exception as e:
            print(f"[qt overlay] Error updating video frame: {e}")
            traceback.print_exc()

    @classmethod
    def _init_hint_text_overlay(cls):
        print("[qt_overlay] Initializing hint text overlay...", flush=True)
        """Initialize hint text overlay components."""
        init_hint_text_overlay(cls)
        print("[qt_overlay] Hint text overlay initialized.", flush=True)

    @classmethod
    def _init_hint_request_text_overlay(cls):
        print("[qt_overlay] Initializing hint request text overlay...", flush=True)
        """Initialize hint request text overlay components."""
        init_hint_request_text_overlay(cls)
        print("[qt_overlay] Hint request text overlay initialized.", flush=True)

    @classmethod
    def _init_gm_assistance_overlay(cls):
        print("[qt_overlay] Initializing GM assistance overlay...", flush=True)
        """Initialize game master assistance overlay components."""
        init_gm_assistance_overlay(cls)
        print("[qt_overlay] GM assistance overlay initialized.", flush=True)

    @classmethod
    def show_hint_text(cls, text, room_number=None, priority=False):
        """Show hint text using a Qt overlay."""
        if not cls._initialized or not cls._hint_text['window']:
            return

        # Skip the thread for priority hints
        if priority:
            # Call update directly for immediate display
            cls._actual_hint_text_update({'text': text, 'room_number': room_number})
            return

        # Initialize hint text thread if needed
        if cls._hint_text_thread is None:
            cls._hint_text_thread = HintTextThread()
            cls._hint_text_thread.update_signal.connect(cls._actual_hint_text_update)
            cls._hint_text_thread.start()

        # Send update through thread
        cls._hint_text_thread.update_text({'text': text, 'room_number': room_number})

    @classmethod
    def _actual_hint_text_update(cls, data):
        """Update the hint text in the main thread."""
        try:
            if not cls._hint_text['window']:
                print("[qt overlay]Error: Hint text window not initialized")
                return

            text = data.get('text', "")
            text = text.replace('\n', '<br>') #respect newlines
            room_number = data.get('room_number')

            # 1. First, ensure the background remains visible
            if hasattr(cls, '_background_window') and cls._background_window:
                cls._background_window.show()
                cls._background_window.lower()  # Keep the background at the bottom

            # Ensure the window itself is fully transparent
            cls._hint_text['window'].setAttribute(Qt.WA_TranslucentBackground, True)
            cls._hint_text['view'].viewport().setAutoFillBackground(False)
            
            # Make sure the hint text window has the correct size and position
            width = cls._hint_text['window'].width()
            height = cls._hint_text['window'].height()
            
            # Update hint background only if a room number is present
            if room_number:
                background_name = None
                background_map = {
                    1: "casino_heist.png",
                    2: "morning_after.png",
                    3: "wizard_trials.png",
                    4: "zombie_outbreak.png",
                    5: "haunted_manor.png",
                    6: "atlantis_rising.png",
                    7: "time_machine.png"
                }

                if room_number in background_map:
                    background_name = background_map[room_number]

                if background_name:
                   # Load and resize the background image
                    bg_path = os.path.join("hint_backgrounds", background_name)
                    if os.path.exists(bg_path):
                         bg_img = Image.open(bg_path)
                         bg_img = bg_img.resize((width, height))
                         # Convert to QPixmap
                         buf = io.BytesIO()
                         bg_img.save(buf, format='PNG')
                         qimg = QImage()
                         qimg.loadFromData(buf.getvalue())
                         pixmap = QPixmap.fromImage(qimg)
                         cls._hint_text['bg_image_item'].setPixmap(pixmap)
                         cls._hint_text['current_background'] = pixmap
                         
            # Clear the existing text before updating
            cls._hint_text['text_item'].setHtml("")

            # Wrap text every 33 characters, avoiding breaking words
            wrapped_text = ""
            remaining_text = text
            while remaining_text:
                # If remaining text is shorter than max length, add it all
                if len(remaining_text) <= 38:
                    wrapped_text += remaining_text
                    break
                
                # Find the last space within the 33 character limit
                cut_point = 33
                while cut_point > 0 and remaining_text[cut_point] != ' ' and remaining_text[cut_point-1] != ' ':
                    cut_point -= 1
                
                # If no space found, force cut at 33
                if cut_point == 0:
                    cut_point = 33
                
                # Add the chunk and a line break
                wrapped_text += remaining_text[:cut_point] + "<br>"
                remaining_text = remaining_text[cut_point:].lstrip()

            # Use theme color for hint text
            color = cls._current_hint_text_color if hasattr(cls, '_current_hint_text_color') else '#ffffff'
            # Set text with transparent background explicitly
            cls._hint_text['text_item'].setHtml(
                f'<div style="background-color: transparent; color: {color}; padding: 20px; text-align:center; width:{height-40}px">{wrapped_text}</div>'
            )

            cls._hint_text['text_item'].setTransform(QTransform())
            cls._hint_text['text_item'].setRotation(90)
            cls._hint_text['text_item'].setZValue(1)  # Text should be above the background

            text_width = cls._hint_text['text_item'].boundingRect().width()
            text_height = cls._hint_text['text_item'].boundingRect().height()
            cls._hint_text['text_item'].setPos(
                (width + text_height) / 2,
                (height - text_width) / 2
            )
            
            # ADDED CHECK: Only show if no video is playing.
            if not cls._kiosk_app.video_manager.is_playing:
                # Show the window but don't raise it above other elements
                cls._hint_text['window'].show()
        except Exception as e:
            print(f"[qt overlay]Error in _actual_hint_text_update: {e}")
            traceback.print_exc()
    
    @classmethod
    def hide_hint_text(cls):
        """Hide the hint text overlay and clear its content."""
        if(cls.TIMER_DEBUG): ("[qt overlay.hide_hint_text] Called")
        if hasattr(cls, '_hint_text') and cls._hint_text and cls._hint_text['window']:
            # Hide the window
            try:
                cls._hint_text['window'].hide()
            except Exception as e:
                print(f"[qt overlay] Error hiding hint text window: {e}")
            
            # Clear the text content if it exists
            if 'text_item' in cls._hint_text and cls._hint_text['text_item']:
                try:
                    cls._hint_text['text_item'].setPlainText("")
                    if(cls.TIMER_DEBUG): ("[qt overlay] Hint text content cleared")
                except Exception as e:
                    print(f"[qt overlay] Error clearing hint text: {e}")
        else:
            print("[qt overlay] _hint_text or window does not exist")
    
    @classmethod
    def show_hint_request_text(cls):
        """Show hint request text"""
        if not cls._initialized or not cls._hint_request_text['window']:
            return

         # Initialize hint request text thread if needed
        if cls._hint_request_text_thread is None:
            cls._hint_request_text_thread = HintRequestTextThread()
            cls._hint_request_text_thread.update_signal.connect(cls._actual_hint_request_text_update)
            cls._hint_request_text_thread.start()

        # Send update through thread
        cls._hint_request_text_thread.update_text("HINT REQUESTED")

    @classmethod
    def _actual_hint_request_text_update(cls, text):
        """Update the hint request text in the main thread."""
        try:
            if not hasattr(cls, '_hint_request_text') or not cls._hint_request_text:
                print("[qt overlay]Error: Hint request text window not initialized")
                return

            # --- SIMPLIFIED SETUP ---
            # We keep separate objects, but position them like the cooldown.

            # Rebuild objects before updating (GOOD PRACTICE, KEEPS THINGS CLEAN)
            if hasattr(cls, '_hint_request_text') and cls._hint_request_text:
               if cls._hint_request_text.get('window'):
                   cls._hint_request_text['window'].hide()
                   cls._hint_request_text['window'].deleteLater()
                   cls._hint_request_text['window'] = None
               if cls._hint_request_text.get('scene'):
                   cls._hint_request_text['scene'].clear()
                   cls._hint_request_text['scene'] = None
               if cls._hint_request_text.get('view'):
                   cls._hint_request_text['view'].deleteLater()
                   cls._hint_request_text['view'] = None
               cls._hint_request_text['text_item'] = None


            cls._hint_request_text['window'] = QWidget(cls._window)  # Parent to main window
            cls._hint_request_text['window'].setAttribute(Qt.WA_TranslucentBackground)
            cls._hint_request_text['window'].setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool |
                Qt.WindowDoesNotAcceptFocus
            )
            cls._hint_request_text['window'].setAttribute(Qt.WA_ShowWithoutActivating)

            cls._hint_request_text['scene'] = QGraphicsScene()
            cls._hint_request_text['view'] = QGraphicsView(cls._hint_request_text['scene'], cls._hint_request_text['window'])
            cls._hint_request_text['view'].setStyleSheet("""
                QGraphicsView {
                    background: transparent;
                    border: none;
                }
            """)
            cls._hint_request_text['view'].setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._hint_request_text['view'].setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._hint_request_text['view'].setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

            cls._hint_request_text['text_item'] = QGraphicsTextItem()
            cls._hint_request_text['text_item'].setDefaultTextColor(Qt.white) # Keep the color
            font = QFont('Arial', 36)  # Keep the font
            cls._hint_request_text['text_item'].setFont(font)
            cls._hint_request_text['scene'].addItem(cls._hint_request_text['text_item'])

            if cls._parent_hwnd:
                style = win32gui.GetWindowLong(int(cls._hint_request_text['window'].winId()), win32con.GWL_EXSTYLE)
                win32gui.SetWindowLong(
                    int(cls._hint_request_text['window'].winId()),
                    win32con.GWL_EXSTYLE,
                    style | win32con.WS_EX_NOACTIVATE
                )
                
            # --- POSITIONING (LIKE show_hint_cooldown) ---
            width = 100  # Match cooldown width
            height = 1079  # Match cooldown height

            cls._hint_request_text['window'].setGeometry(510, 0, width, height) # Same position as cooldown
            cls._hint_request_text['view'].setGeometry(0, 0, width, height)
            cls._hint_request_text['scene'].setSceneRect(QRectF(0, 0, width, height))

            # --- STYLING AND ROTATION (LIKE show_hint_cooldown) ---

            cls._hint_request_text['text_item'].setHtml(
                f'<div style="background-color: rgba(0, 0, 0, 180); padding: 20px;">{text}</div>'
            )

            cls._hint_request_text['text_item'].setTransform(QTransform())
            cls._hint_request_text['text_item'].setRotation(90) # Same rotation

            text_width = cls._hint_request_text['text_item'].boundingRect().width()
            text_height = cls._hint_request_text['text_item'].boundingRect().height()
            cls._hint_request_text['text_item'].setPos(
                (width + text_height) / 2,  # Center like cooldown
                (height - text_width) / 2
            )

            cls._hint_request_text['window'].show()
            cls._hint_request_text['window'].raise_()

        except Exception as e:
            print(f"[qt overlay]Error in _actual_hint_request_text_update: {e}")
            traceback.print_exc()

    @classmethod
    def hide_hint_request_text(cls):
        """Hide the hint request text overlay and clear its content"""
        if hasattr(cls, '_hint_request_text') and cls._hint_request_text:
            # Hide the window if it exists
            if cls._hint_request_text.get('window'):
                try:
                    cls._hint_request_text['window'].hide()
                except Exception as e:
                    print(f"[qt overlay] Error hiding hint request window: {e}")
            
            # Clear the text content if it exists
            if cls._hint_request_text.get('text_item'):
                try:
                    cls._hint_request_text['text_item'].setPlainText("")
                    if(cls._app.kiosk_app_instance.UI_DEBUG): print("[qt overlay] Hint request text cleared")
                except Exception as e:
                    print(f"[qt overlay] Error clearing hint request text: {e}")

    @classmethod
    def show_hint_cooldown(cls, seconds):
        """Show cooldown message with proper rotation"""
        if not cls._initialized:
            return
        
        # First, ensure background is visible
        if hasattr(cls, '_background_window') and cls._background_window:
            cls._background_window.show()
            cls._background_window.lower()  # Keep background at the bottom
        
        # Get main window and content widget
        from qt_main import QtKioskApp
        main_window = QtKioskApp.instance.main_window if QtKioskApp.instance else None
        content_widget = QtKioskApp.instance.content_widget if QtKioskApp.instance else None
        
        # Define cooldown dimensions
        width = 100
        height = 1079
        
        # If we don't have a dedicated window for cooldown, create one
        if not hasattr(cls, '_cooldown_window') or not cls._cooldown_window:
            parent = content_widget if content_widget else (main_window if main_window else None)
            if not parent:
                print("[qt overlay] No parent available for cooldown window")
                return
            
            # Create dedicated cooldown window
            cls._cooldown_window = QWidget(parent)
            cls._cooldown_window.setAttribute(Qt.WA_TranslucentBackground, True)
            cls._cooldown_window.setGeometry(510, 0, width, height)
            
            # Create scene and view
            cls._cooldown_scene = QGraphicsScene()
            cls._cooldown_view = QGraphicsView(cls._cooldown_scene, cls._cooldown_window)
            cls._cooldown_view.viewport().setAutoFillBackground(False)
            cls._cooldown_view.setStyleSheet("background: transparent; border: none;")
            cls._cooldown_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._cooldown_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._cooldown_view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
            cls._cooldown_view.setGeometry(0, 0, width, height)
            cls._cooldown_scene.setSceneRect(0, 0, width, height)
            
            # Create text item
            cls._cooldown_text = QGraphicsTextItem()
            cls._cooldown_text.setDefaultTextColor(Qt.white)
            font = QFont('Arial', 20)
            cls._cooldown_text.setFont(font)
            cls._cooldown_scene.addItem(cls._cooldown_text)
        
        # Update cooldown message
        message = f"Please wait {seconds} seconds until requesting the next hint."
        cls._cooldown_text.setHtml(
            f'<div style="background-color: rgba(0, 0, 0, 180); padding: 20px;">{message}</div>'
        )
        
        # Rotate and position text
        cls._cooldown_text.setTransform(QTransform())
        cls._cooldown_text.setRotation(90)
        
        text_width = cls._cooldown_text.boundingRect().width()
        text_height = cls._cooldown_text.boundingRect().height()
        cls._cooldown_text.setPos(
            (width + text_height) / 2,
            (height - text_width) / 2
        )
        
        # Show but don't raise
        cls._cooldown_window.show()

    @classmethod
    def init_timer(cls):
        print("[qt_overlay] Initializing timer...", flush=True)
        """Initialize the timer display components"""
        init_timer(cls)
        print("[qt_overlay] Timer initialized.", flush=True)

    @classmethod
    def update_timer_display(cls, time_str):
        thread_id = threading.get_ident()
        if(cls.TIMER_DEBUG): (f"[qt_overlay][{thread_id}] update_timer_display ENTERED with time: {time_str}")
        """Update timer display, but NOT if game is lost."""
        if(cls.TIMER_DEBUG): (f"\n[DEBUG OVERLAY] update_timer_display called with time: {time_str}")
        
        if not hasattr(cls, '_timer') or not cls._timer.text_item:
            print(f"[qt overlay][{thread_id}] Timer or text_item not initialized, returning.")
            return
            
        if hasattr(cls, '_kiosk_app') and cls._kiosk_app and hasattr(cls._kiosk_app, 'timer'):
            if cls._kiosk_app.timer.game_lost:  # Don't update if game is lost
                print(f"[qt overlay][{thread_id}] Game is lost, not updating timer, returning.")
                return
                
            if cls._kiosk_app.timer.game_won:  # Don't update if game is won
                print(f"[qt overlay][{thread_id}] Game is won, not updating timer, returning.")
                return
        else:
             print(f"[qt overlay][{thread_id}] Warning: Cannot check game lost/won status (kiosk_app or timer missing).")
            
        # Initialize timer thread if needed
        if(cls.TIMER_DEBUG): (f"[qt_overlay][{thread_id}] Checking if _timer_thread is None...")
        if cls._timer_thread is None:
            print(f"[qt_overlay][{thread_id}] _timer_thread IS None. Creating TimerThread...")
            cls._timer_thread = TimerThread() # Creates TimerThread from qt_classes
            print(f"[qt_overlay][{thread_id}] TimerThread instance created. Connecting signal...")
            try:
                 # Explicitly use QueuedConnection
                 cls._timer_thread.update_signal.connect(cls._actual_timer_update, Qt.QueuedConnection)
                 print(f"[qt_overlay][{thread_id}] update_signal connected (Queued). Starting thread...")
                 cls._timer_thread.start()
                 print(f"[qt_overlay][{thread_id}] TimerThread started.")
            except Exception as e:
                 print(f"[qt_overlay][{thread_id}] !!! EXCEPTION during TimerThread signal connection/start: {e}")
                 traceback.print_exc()
                 # Potentially reset _timer_thread to None to allow retry?
                 # cls._timer_thread = None 
                 return # Avoid proceeding if connection failed
        else:
             if(cls.TIMER_DEBUG): (f"[qt_overlay][{thread_id}] _timer_thread already exists.")
             pass
        
        # Send update through thread
        if(cls.TIMER_DEBUG): (f"[qt_overlay][{thread_id}] Calling _timer_thread.update_display('{time_str}')...")
        if cls._timer_thread:
            cls._timer_thread.update_display(time_str)
            if(cls.TIMER_DEBUG): (f"[qt_overlay][{thread_id}] _timer_thread.update_display called.")
        else:
            print(f"[qt_overlay][{thread_id}] !!! _timer_thread is None AFTER check/creation! Cannot call update_display.")
        if(cls.TIMER_DEBUG): (f"[qt_overlay][{thread_id}] update_timer_display EXITED.")

    @classmethod
    def hide_timer(cls):
        """Hide the timer display."""
        if hasattr(cls, '_timer_window') and cls._timer_window:
            if cls._timer_window.isVisible():
                cls._timer_window.hide()
                print("[qt overlay] Timer hidden")

    @classmethod
    def _actual_timer_update(cls, time_str):
        thread_id = threading.get_ident()
        if(cls.TIMER_DEBUG): (f"[qt_overlay][{thread_id}] _actual_timer_update ENTERED with time: {time_str}")
        """Actual update method that runs in the main thread"""
        if(cls.TIMER_DEBUG): (f"\n[DEBUG OVERLAY] _actual_timer_update called with time: {time_str}")
        
        if(cls.TIMER_DEBUG): (f"[qt_overlay][{thread_id}] Checking _timer and _timer.text_item existence...")
        if hasattr(cls, '_timer') and cls._timer.text_item:
            try:
                color = cls._current_timer_text_color if hasattr(cls, '_current_timer_text_color') else '#ffffff'
                cls._timer.text_item.setHtml(f'<div style="color: {color};">{time_str}</div>')
                cls._timer.text_item.setPos(350, 145)
                if cls._timer_window:
                    cls._timer_window.show()
                    cls._timer_window.raise_()
            except Exception as e:
                print(f"[qt_overlay][{thread_id}] !!! EXCEPTION during setHtml/setPos/show/raise: {e}")
                traceback.print_exc()
        else:
            print(f"[qt_overlay][{thread_id}] Timer or text_item not available for update.")
        if(cls.TIMER_DEBUG): (f"[qt_overlay][{thread_id}] _actual_timer_update EXITED.")

    @classmethod
    def load_timer_background(cls, room_number):
        """Load the timer background for the specified room"""
        print(f"[qt overlay]Attempting to load timer background for room {room_number}")

        # Ensure bridge is initialized
        if not cls._bridge:
            print("[qt overlay]Bridge not initialized, initializing now...")
            if not cls._initialized:
                cls.init()  # Initialize the whole overlay if needed
            else:
                # Just create the bridge if overlay is already initialized
                cls._bridge = OverlayBridge()
                cls._bridge.timer_background_update_signal.connect(cls._actual_timer_background_update)
                cls._bridge.load_timer_background_signal.connect(cls._actual_load_timer_background)

        # Use the bridge to perform the entire loading operation in the main thread
        print(f"[qt overlay]Sending background load request to main thread for room {room_number}")
        cls._bridge.load_timer_background_signal.emit(room_number)
            
    @classmethod
    def _actual_load_timer_background(cls, room_number):
        """Perform the entire timer background loading operation in the main thread"""
        print(f"[qt overlay]Loading timer background in main thread for room {room_number}")
        
        if not hasattr(cls, '_timer'):
            print("[qt overlay]Timer not initialized yet")
            return

        try:
            bg_filename = cls._timer.timer_backgrounds.get(room_number)
            if not bg_filename:
                print(f"[qt overlay]No timer background defined for room {room_number}")
                return

            bg_path = os.path.join("timer_backgrounds", bg_filename)
            print(f"[qt overlay]Looking for background at: {bg_path}")

            if not os.path.exists(bg_path):
                print(f"[qt overlay]Timer background not found: {bg_path}")
                return

            # Load and resize the background image
            print("[qt overlay]Loading background image...")
            bg_img = Image.open(bg_path)
            bg_img = bg_img.resize((500,750))

            # Convert to QPixmap
            print("[qt overlay]Converting to QPixmap...")
            buf = io.BytesIO()
            bg_img.save(buf, format='PNG')
            qimg = QImage()
            qimg.loadFromData(buf.getvalue())
            pixmap = QPixmap.fromImage(qimg)

            # Update the UI directly since we're in the main thread
            cls._actual_timer_background_update(pixmap)

        except Exception as e:
            print(f"[qt overlay]Error loading timer background for room {room_number}:")
            traceback.print_exc()

    @classmethod
    def _actual_timer_background_update(cls, pixmap):
        """Actual timer background update method that runs in the main thread"""
        try:
            if not hasattr(cls, '_timer') or not cls._timer.bg_image_item:
                print("[qt overlay]Timer or bg_image_item not initialized")
                return
                
            # Clear Previous
            cls._timer.bg_image_item.setPixmap(QPixmap())
            
            # Update the background
            print("[qt overlay]Setting background pixmap...")
            cls._timer.bg_image_item.setPixmap(pixmap)
            cls._timer._current_image = pixmap  # Store reference
            if cls._timer_window:
                cls._timer_window.update()  # Force refresh
            print("[qt overlay]Background loaded successfully")
        except Exception as e:
            print(f"[qt overlay]Error in _actual_timer_background_update: {e}")
            traceback.print_exc()

    @classmethod
    def init_help_button(cls):
        print("[qt_overlay] Initializing help button...", flush=True)
        """Initialize the help button components."""
        init_help_button(cls)
        print("[qt_overlay] Help button initialized.", flush=True)

    @classmethod
    def load_button_images(cls, room_number):
        """Load the button and shadow images for the specified room"""
        try:
            # Load button image
            button_filename = ROOM_CONFIG['buttons'].get(room_number)
            button_path = os.path.join("hint_button_backgrounds", button_filename)

            if not os.path.exists(button_path):
                print(f"[qt overlay]Error: Button image not found at: {button_path}")
                return False

            # Use QImage to load directly
            qimage = QImage(button_path)
            if qimage.isNull():
                print("[qt overlay]Failed to load button image directly")
                return False

            # Convert to pixmap and scale
            button_pixmap = QPixmap.fromImage(qimage).scaled(
                320, 700, Qt.KeepAspectRatio, Qt.SmoothTransformation  # Keep adjusted scaling for button
            )
            cls._button['bg_image_item'].setPixmap(button_pixmap)

            # Load shadow image
            shadow_path = os.path.join("hint_button_backgrounds", "shadow.png")
            shadow_qimage = QImage(shadow_path)
            if shadow_qimage.isNull():
                print("[qt overlay]Failed to load shadow image directly")
                return False

            # Convert to pixmap and scale (larger scaling for shadow)
            shadow_pixmap = QPixmap.fromImage(shadow_qimage).scaled(
                440, 780, Qt.KeepAspectRatio, Qt.SmoothTransformation  # Increased shadow size
            )
            cls._button['shadow_item'].setPixmap(shadow_pixmap)

            # Set the origin for rotation to the center of the pixmap
            cls._button['bg_image_item'].setTransformOriginPoint(button_pixmap.width() / 2, button_pixmap.height() / 2)

            # Debug info
            if(cls.TIMER_DEBUG): (f"[qt overlay]Image Debug:")
            if(cls.TIMER_DEBUG): (f"[qt overlay]Button image format: {qimage.format()}")
            if(cls.TIMER_DEBUG): (f"[qt overlay]Button image size: {qimage.size()}")
            if(cls.TIMER_DEBUG): (f"[qt overlay]Button pixmap size: {button_pixmap.size()}")
            if(cls.TIMER_DEBUG): (f"[qt overlay]Shadow pixmap size: {shadow_pixmap.size()}")

            return True

        except Exception as e:
            print(f"[qt overlay]Error loading images: {e}")
            traceback.print_exc()
            return False

    @classmethod
    def update_help_button(cls, ui, timer, hints_requested, time_exceeded_45, assigned_room):
        """Update the help button based on current state"""
        # Prepare data for button update thread
        button_data = {
            'ui': ui,
            'timer': timer,
            'hints_requested': hints_requested,
            'time_exceeded_45': time_exceeded_45,
            'assigned_room': assigned_room
        }

        # Initialize button thread if needed
        if cls._button_thread is None:
            cls._button_thread = HelpButtonThread()
            cls._button_thread.update_signal.connect(cls._actual_help_button_update)
            cls._button_thread.start()

        # Send the update to the button thread
        cls._button_thread.update_button(button_data)
        
    @classmethod
    def _actual_help_button_update(cls, button_data):
        """
        Actual help button update method that runs in the main thread.
        This version is optimized to create widgets only once and then show/hide/update them.
        """
        try:
            ui = button_data['ui']
            timer = button_data['timer']
            assigned_room = button_data['assigned_room']
            current_minutes = timer.time_remaining / 60

            # 1. Determine if the button *should* be visible based on game logic
            show_button_logic = (
                not ui.hint_cooldown and
                not (current_minutes > 42 and current_minutes <= 45 and not button_data['time_exceeded_45']) and
                not timer.game_lost and
                not timer.game_won and
                not cls._kiosk_app.hint_requested_flag
            )

            # 2. Determine if the button *can* be shown based on UI state (no video/fullscreen image)
            can_show_ui = not cls._kiosk_app.video_manager.is_playing and not cls._kiosk_app.ui.image_is_fullscreen
            
            should_show = show_button_logic and can_show_ui

            # 3. Initialize button components if they don't exist yet
            if not hasattr(cls, '_button_window') or not cls._button_window:
                cls.init_help_button()
                # Set a class variable to track the room the button is configured for
                if not hasattr(cls, '_help_button_room_id'):
                    cls._help_button_room_id = None

            # Ensure components are valid before proceeding
            if not hasattr(cls, '_button_window') or not cls._button_window:
                print("[qt overlay] Critical error: Help button failed to initialize.")
                return

            # 4. Handle visibility and content updates
            button_visible = cls._button_window.isVisible()

            if should_show:
                # If the button should be shown, check if its content (image) is correct
                if cls._help_button_room_id != assigned_room:
                    if cls.load_button_images(assigned_room):
                        # On successful load, update the state
                        cls._help_button_room_id = assigned_room
                        
                        # Re-connect the click signal to ensure it's correct
                        cls._button_view.set_skippable(True)
                        try:
                            cls._button_view.clicked.disconnect()
                        except TypeError:
                            pass # No connection existed, which is fine
                        
                        cls._button_view.clicked.connect(ui.message_handler.request_help)
                        
                        # Set rotation and position (these are cheap operations)
                        cls._button['bg_image_item'].setRotation(360)
                        cls._button['bg_image_item'].setPos(-40, -73)
                        cls._button['shadow_item'].setPos(0, 0)
                        print(f"[qt overlay] Help button images loaded for room {assigned_room}")
                    else:
                        print(f"[qt overlay] Failed to load button images for room {assigned_room}. Button will not be shown.")
                        # If images fail to load, ensure button is hidden
                        if button_visible:
                            cls._button_window.hide()
                        return # Abort if images can't be loaded

                # Now that content is correct, ensure it's visible
                if not button_visible:
                    cls._button_window.show()
                    cls._button_window.raise_()
                    print("[qt overlay] Help button shown")

            else: # If should_show is False
                if button_visible:
                    cls._button_window.hide()
                    # Reset the room ID so it reloads fresh on next show
                    cls._help_button_room_id = None
                    print("[qt overlay] Help button hidden")
        except Exception as e:
           print(f"[qt overlay] Exception during help button update: {e}")
           traceback.print_exc()

    @classmethod
    def hide_help_button(cls):
        """Hide the help button"""
        if hasattr(cls, '_button_window') and cls._button_window:
            cls._button_window.hide()

    @classmethod
    def hide_cooldown(cls):
        """Hide just the cooldown overlay"""
        print("[qt overlay.hide_cooldown] Called")
        # Call our dedicated method that handles cooldown hiding and text clearing
        cls.hide_hint_cooldown()
        
        # Additional handling for legacy windows if needed
        if not hasattr(cls, '_cooldown_window') and cls._window and hasattr(cls, '_text_item') and cls._text_item and cls._text_item.toPlainText().strip().startswith("Please wait"):
            print("[qt overlay] Handling legacy cooldown window")
            # Clear the text content
            if hasattr(cls, '_text_item') and cls._text_item:
                cls._text_item.setPlainText("")

    @classmethod
    def hide(cls):
        """Hide all overlay windows (thread-safe entry point)."""
        print("[qt_overlay.py - hide] === STARTING hide() - Calling _actual_hide via invokeMethod ===")
        # Instead of using QMetaObject.invokeMethod(cls, "_actual_hide", Qt.QueuedConnection)
        # which fails because cls is a class type, not a QObject instance
        if cls._bridge:
            # Use the bridge which is a QObject instance
            QMetaObject.invokeMethod(cls._bridge, "execute_callback", Qt.QueuedConnection, 
                                    Q_ARG(object, cls._actual_hide))
        else:
            # Fallback to direct call if bridge isn't available
            cls._actual_hide()

    @classmethod
    def hide_all_overlays(cls):
        """Hides all overlay components."""
        # Call individual hide methods for better maintainability
        # Order might matter depending on transparency/layering,
        # but generally hiding should be safe in any order.
        cls.hide_timer()
        cls.hide_help_button()
        cls.hide_cooldown()
        cls.hide_hint_text()
        cls.hide_hint_request_text()
        cls.hide_gm_assistance()
        cls.hide_waiting_screen_label()
        #cls.hide_background()
        cls.hide_fullscreen_hint(restore_ui=False)
        cls.hide_view_image_button()
        cls.hide_view_solution_button()
        cls.hide_video_display() # Hide video display if it's showing
        #cls.hide_loss_screen()
        #cls.hide_victory_screen()
        # Note: cls.hide() itself is not called directly here as it might hide the main window
        # if cls._window is the main application window.
        # cls.hide() is intended for the old overlay concept, not individual components.

        print("[qt overlay] All overlay components hidden.")

    @classmethod
    def show_all_overlays(cls):
        """Restore visibility of all Qt overlay UI elements (EXCEPT video and fullscreen hint)."""
        # print("[qt overlay] Restoring non-video overlay UI elements.") # Reduce noise

        # --- CHECK GAME STATE FIRST ---
        game_lost = False
        game_won = False
        ui_instance = None # <-- Get ui instance

        # Use the stored kiosk_app reference safely
        if cls._kiosk_app: # Check if kiosk_app exists
             if hasattr(cls._kiosk_app, 'timer'):
                 game_lost = getattr(cls._kiosk_app.timer, 'game_lost', False)
                 game_won = getattr(cls._kiosk_app.timer, 'game_won', False)
             if hasattr(cls._kiosk_app, 'ui'): # Check if ui exists
                 ui_instance = cls._kiosk_app.ui
        else:
            print("[qt overlay] Warning: _kiosk_app not available in show_all_overlays.")
            # If no kiosk_app or ui, we can't really proceed with state-dependent restores
            return

        # --- RESTORE OTHER OVERLAYS (if game not won/lost) ---
        try:
            # --- Make sure background is visible if initialized ---
            if hasattr(cls, '_background_initialized') and cls._background_initialized and cls._background_window:
                cls._background_window.show()
                cls._background_window.lower()  # Keep at the bottom of the z-order
            
            # --- Restore Timer ---
            # Timer (only if text exists and window is available)
            if hasattr(cls, '_timer_window') and cls._timer_window:
                # Check if timer object and text item exist and have content
                if hasattr(cls, '_timer') and cls._timer.text_item and cls._timer.text_item.toPlainText():
                     # Show if not already visible
                     if not cls._timer_window.isVisible(): cls._timer_window.show()
                     cls._timer_window.raise_() # Ensure it's on top

            # --- Trigger Help Button Update ---
            # Relies on _actual_help_button_update to decide visibility based on state
            if ui_instance and hasattr(ui_instance.parent_app, '_actual_help_button_update'): # Check parent_app reference exists
                if hasattr(ui_instance.parent_app, 'root') and ui_instance.parent_app.root: # Check root exists
                    # print("[qt overlay show_all] Triggering help button update.") # Debug
                    # Replace root.after with QTimer.singleShot
                    QTimer.singleShot(10, ui_instance.parent_app._actual_help_button_update) # Use parent_app reference

            # --- Restore Hint Text ---
            # Hint Text (only if text exists and window is available)
            if hasattr(cls, '_hint_text') and cls._hint_text and cls._hint_text.get('window'):
                hint_window = cls._hint_text['window']
                # Check if the text item exists AND has actual text content
                if '_text_item' in cls._hint_text and cls._hint_text['_text_item'] and cls._hint_text['_text_item'].toPlainText().strip():
                    # Show if not already visible
                    if not hint_window.isVisible():
                        hint_window.show()
                    hint_window.raise_() # Ensure it's on top
                else:
                    # Explicitly hide if no text content
                    if hint_window.isVisible():
                         hint_window.hide()
                    # print("[qt overlay.show_all_overlays] Hint text item has no content, ensuring hint window is hidden.")
                 
            # --- Restore Side Buttons (View Image/Solution) ---
            # **** MOVED OUTSIDE HINT TEXT CHECK ****
            # These depend only on whether the corresponding data exists in the ui_instance
            if ui_instance:
                # Show "View Image Hint" button if image data exists
                if hasattr(ui_instance, 'stored_image_data') and ui_instance.stored_image_data:
                     print("[qt overlay show_all] Stored image data found, showing View Image button.")
                     cls.show_view_image_button(ui_instance)
                else:
                    # Explicitly hide if no data (handles case where data was cleared)
                    # print("[qt overlay show_all] No stored image data, ensuring View Image button is hidden.") # Debug
                    cls.hide_view_image_button()

                # Show "View Solution" button if video info exists
                if hasattr(ui_instance, 'stored_video_info') and ui_instance.stored_video_info:
                     print("[qt overlay show_all] Stored video info found, showing View Solution button.")
                     cls.show_view_solution_button(ui_instance)
                else:
                    # Explicitly hide if no info
                    # print("[qt overlay show_all] No stored video info, ensuring View Solution button is hidden.") # Debug
                    cls.hide_view_solution_button()
            else:
                # If no ui_instance, hide buttons as we can't determine state
                print("[qt overlay show_all] No ui_instance, hiding side buttons.")
                cls.hide_view_image_button()
                cls.hide_view_solution_button()


            # --- Restore Hint Request Text ---
            # Hint Request Text (only if text exists and window is available)
            if hasattr(cls, '_hint_request_text') and cls._hint_request_text and cls._hint_request_text.get('window'):
                 req_window = cls._hint_request_text['window']
                 # Check if the text item exists AND has actual text content
                 if '_text_item' in cls._hint_request_text and cls._hint_request_text['_text_item'] and cls._hint_request_text['_text_item'].toPlainText().strip():
                     # Show if not already visible
                     if not req_window.isVisible(): req_window.show()
                     req_window.raise_() # Ensure it's on top
                 else:
                     # Explicitly hide if no text content
                     if req_window.isVisible():
                        req_window.hide()
                 
            # --- Restore Cooldown Overlay ---
            # CRITICAL FIX: Be much more careful with the main window - ONLY show if specific conditions are met
            if hasattr(cls, '_window') and cls._window:
                 should_show_cooldown = False
                 cooldown_text_valid = False
                 
                 # Check if we have valid cooldown text
                 if hasattr(cls, '_text_item') and cls._text_item and cls._text_item.toPlainText().strip():
                     cooldown_text = cls._text_item.toPlainText().strip()
                     cooldown_text_valid = cooldown_text.startswith("Please wait")
                 
                 # Only show if there's actual cooldown in progress AND valid text
                 if ui_instance and ui_instance.hint_cooldown and cooldown_text_valid:
                     should_show_cooldown = True
                 
                 if should_show_cooldown:
                     # Only show if it contains valid cooldown text AND cooldown is active
                     if not cls._window.isVisible(): cls._window.show()
                     cls._window.raise_() # Ensure it's on top

            # --- Restore new, dedicated cooldown window if it exists ---
            if hasattr(cls, '_cooldown_window') and cls._cooldown_window:
                cooldown_active = ui_instance and ui_instance.hint_cooldown if ui_instance else False
                cooldown_text_valid = False
                
                # Check if cooldown text exists
                if hasattr(cls, '_cooldown_text') and cls._cooldown_text and cls._cooldown_text.toPlainText().strip():
                    cooldown_text_valid = True
                
                if cooldown_active and cooldown_text_valid:
                    # Show dedicated cooldown window
                    if not cls._cooldown_window.isVisible(): cls._cooldown_window.show()
                    cls._cooldown_window.raise_()
                else:
                    # Hide if no active cooldown
                    if cls._cooldown_window.isVisible():
                        cls._cooldown_window.hide()

            # --- Restore GM Assistance ---
            # REMOVED GM Assistance restore logic - its visibility is now solely controlled by explicit calls.

            # print("[qt overlay] Non-video overlay UI elements restored.") # Reduce noise
        except Exception as e:
            print(f"[qt overlay] Error showing non-video overlays: {e}")
            traceback.print_exc()

    @classmethod
    def set_background_image(cls, image_path):
        """
        Display the room background image using Qt.
        
        Args:
            image_path: Path to the background image file
        """
        if not cls._initialized:
            print("[qt_overlay] Cannot set background image - Qt overlay not initialized")
            return
        
        try:
            # Initialize background components if needed
            if not cls._background_initialized:
                cls._init_background()
            
            # Load and scale image
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                print(f"[qt_overlay] Failed to load background image: {image_path}")
                return
                
            # Get screen dimensions
            screen_size = cls._app.primaryScreen().size()
            screen_width = screen_size.width()
            screen_height = screen_size.height()
            
            # Scale pixmap to fit screen
            scaled_pixmap = pixmap.scaled(screen_width, screen_height, 
                                         Qt.KeepAspectRatioByExpanding, 
                                         Qt.SmoothTransformation)
            
            # Update pixmap item
            if cls._background_pixmap_item:
                cls._background_pixmap_item.setPixmap(scaled_pixmap)
                
                # Center pixmap if it's larger than the screen
                if scaled_pixmap.width() > screen_width or scaled_pixmap.height() > screen_height:
                    x_offset = max(0, (scaled_pixmap.width() - screen_width) // 2)
                    y_offset = max(0, (scaled_pixmap.height() - screen_height) // 2)
                    cls._background_pixmap_item.setOffset(-x_offset, -y_offset)
                
                # Make sure window is visible but stays in the background
                cls._background_window.show()
                cls._background_window.lower()  # Critical: keep it at the bottom
                
                # Ensure proper scene rect
                cls._background_scene.setSceneRect(0, 0, screen_width, screen_height)
                
                print(f"[qt_overlay] Background set to: {image_path}")
            
        except Exception as e:
            print(f"[qt_overlay] Error setting background image: {str(e)}")
            traceback.print_exc()
    
    @classmethod
    def _init_background(cls):
        print("[qt_overlay] Initializing background...", flush=True)
        """Initialize Qt components for displaying the background image"""
        init_background(cls)
        print("[qt_overlay] Background initialized.", flush=True)
            
    @classmethod
    def hide_background(cls):
        """Hides the background image."""
        if cls._background_initialized and cls._background_window:
            cls._background_window.hide()
            print("[qt overlay] Background hidden.")

    @classmethod
    def show_background(cls):
        """Show the background image"""
        if cls._background_initialized and cls._background_window:
            cls._background_window.show()
            cls._background_window.lower()  # Keep at the bottom
            print("[qt_overlay] Background shown")

    @classmethod
    def show_gm_assistance(cls):
        """Show the game master assistance overlay."""
        if cls._gm_assistance_overlay and cls._gm_assistance_overlay['window']:
            try:
                # Reset window and view geometry first
                window_width = 400
                window_height = 600
                screen_width = 1920
                screen_height = 1080
                x_pos = (screen_width - window_width) // 2
                y_pos = (screen_height - window_height) // 2

                # Reset window geometry
                cls._gm_assistance_overlay['window'].setGeometry(x_pos, y_pos, window_width, window_height)
                cls._gm_assistance_overlay['view'].setGeometry(0, 0, window_width, window_height)
                cls._gm_assistance_overlay['scene'].setSceneRect(0, 0, window_width, window_height)

                # Reset all rotations and positions first
                cls._gm_assistance_overlay['text_item'].setRotation(0)
                cls._gm_assistance_overlay['yes_button'].setRotation(0)
                cls._gm_assistance_overlay['no_button'].setRotation(0)
                cls._gm_assistance_overlay['yes_rect'].setRotation(0)
                cls._gm_assistance_overlay['no_rect'].setRotation(0)

                # Get the text dimensions before rotation
                text_rect = cls._gm_assistance_overlay['text_item'].boundingRect()
                text_width = text_rect.width()
                text_height = text_rect.height()

                # Calculate positions
                x_center = (window_width - text_height) / 2 + 140
                y_center = (window_height + text_width) / 2

                # Apply rotations
                cls._gm_assistance_overlay['text_item'].setRotation(90)
                cls._gm_assistance_overlay['yes_button'].setRotation(90)
                cls._gm_assistance_overlay['no_button'].setRotation(90)
                cls._gm_assistance_overlay['yes_rect'].setRotation(90)
                cls._gm_assistance_overlay['no_rect'].setRotation(90)

                # Position text
                cls._gm_assistance_overlay['text_item'].setPos(x_center, y_center - text_width)

                # Button positioning
                button_spacing = 270
                button_width = 170
                button_height = 60
                base_x = x_center - 150
                base_y = y_center - text_width/2 + 30

                # Position Yes button and its components
                cls._gm_assistance_overlay['yes_rect'].setPos(base_x, base_y)
                yes_text_width = cls._gm_assistance_overlay['yes_button'].boundingRect().width()
                yes_text_height = cls._gm_assistance_overlay['yes_button'].boundingRect().height()
                yes_rect_center_x = base_x + button_height/2
                yes_rect_center_y = base_y + button_width/2
                cls._gm_assistance_overlay['yes_button'].setPos(
                    yes_rect_center_x - yes_text_height/2,
                    yes_rect_center_y - yes_text_width/2
                )

                # Position No button and its components
                cls._gm_assistance_overlay['no_rect'].setPos(base_x, base_y - button_spacing)
                no_text_width = cls._gm_assistance_overlay['no_button'].boundingRect().width()
                no_text_height = cls._gm_assistance_overlay['no_button'].boundingRect().height()
                no_rect_center_x = base_x + button_height/2
                no_rect_center_y = (base_y - button_spacing) + button_width/2
                cls._gm_assistance_overlay['no_button'].setPos(
                    no_rect_center_x - no_text_height/2,
                    no_rect_center_y - no_text_width/2
                )

                # Set visibility flag BEFORE showing
                cls._gm_assistance_overlay['_was_visible'] = True

                # Show and raise the window
                cls._gm_assistance_overlay['window'].show()
                cls._gm_assistance_overlay['window'].raise_()
                cls._gm_assistance_overlay['view'].viewport().update()

            except Exception as e:
                print(f"[qt overlay] Error showing GM assistance overlay: {e}")
                traceback.print_exc()

    @classmethod
    def hide_gm_assistance(cls):
        """Hide the game master assistance overlay."""
        if cls._gm_assistance_overlay and cls._gm_assistance_overlay.get('window'):
            cls._gm_assistance_overlay['window'].hide()
            # Reset _was_visible flag when hiding
            cls._gm_assistance_overlay['_was_visible'] = False

    @classmethod
    def _init_waiting_label(cls):
        print("[qt_overlay] Initializing waiting label...", flush=True)
        """Initialize the waiting screen label overlay."""
        init_waiting_label(cls)
        print("[qt_overlay] Waiting label initialized.", flush=True)

    @classmethod
    def show_waiting_screen_label(cls, computer_name):
        """Show the waiting screen label with the computer name."""
        try:
            if not cls._initialized:
                 print("[qt overlay] Warning: Overlay not initialized, cannot show waiting label.")
                 return

            if not hasattr(cls, '_waiting_label_initialized') or not cls._waiting_label_initialized or cls._waiting_label is None:
                cls._init_waiting_label()
                if not cls._waiting_label_initialized or cls._waiting_label is None: # Check again after init attempt
                     print("[qt overlay] Error: Failed to initialize waiting label, cannot show.")
                     return

            text = f"Waiting for room assignment.\nComputer Name: {computer_name}"
            text_item = cls._waiting_label['text_item']
            window = cls._waiting_label['window']
            view = cls._waiting_label['view']

            # Update text and ensure alignment/positioning
            # Perform the replacement *before* the f-string to avoid backslash issue in older Python
            processed_text = text.replace('\n', '<br>')
            text_item.setHtml(f"<div style='color: white; text-align: center;'>{processed_text}</div>")

            # Recalculate position to center the text block
            text_rect = text_item.boundingRect()
            scene_rect = view.sceneRect()
            center_x = (scene_rect.width() - text_rect.width()) / 2
            center_y = (scene_rect.height() - text_rect.height()) / 2
            text_item.setPos(center_x, center_y)

            if not window.isVisible():
                print("[qt overlay] Showing waiting screen label.")
                # Ensure geometry is set correctly before showing
                screen_rect = cls._app.primaryScreen().geometry()
                window.setGeometry(screen_rect)
                view.setGeometry(0,0, screen_rect.width(), screen_rect.height())
                window.show()
                window.raise_()
            else:
                # Already visible, just update text (handled above)
                pass
                # print("[qt overlay] Waiting screen label already visible, text updated.") # Debug

        except Exception as e:
            print(f"[qt overlay] Error showing waiting screen label: {e}")
            traceback.print_exc()

    @classmethod
    def hide_waiting_screen_label(cls):
        """Hide the waiting screen label overlay."""
        if hasattr(cls, '_waiting_label_initialized') and cls._waiting_label_initialized and cls._waiting_label and cls._waiting_label.get('window'):
            if cls._waiting_label['window'].isVisible():
                print("[qt overlay] Hiding waiting screen label.")
                cls._waiting_label['window'].hide()
        #else:
            # print("[qt overlay] Waiting screen label not initialized or already hidden.") # Debug noise

    @classmethod
    def _actual_hide(cls):
        """Internal helper to perform the actual hiding, now thread-safe."""
        print("[qt_overlay.py - _actual_hide] === STARTING _actual_hide() ===")

        if cls._window:
            #cls._window.hide() hiding the WINDOW doesn't make any sense because that wouldn't allow anything to be displayed
            pass
        if hasattr(cls, '_timer_window') and cls._timer_window:
            cls._timer_window.hide()
        if hasattr(cls, '_button_window') and cls._button_window:
            cls._button_window.hide()
        if hasattr(cls, '_hint_text') and cls._hint_text and cls._hint_text['window']:
            cls._hint_text['window'].hide()
            cls._hint_text['text_item'].setPlainText("")
        if hasattr(cls, '_hint_request_text') and cls._hint_request_text:
            if cls._hint_request_text['window']:
                cls._hint_request_text['window'].hide()
            if cls._hint_request_text['scene']:
                cls._hint_request_text['scene'].clear()
        if hasattr(cls, '_cooldown_window') and cls._cooldown_window:
            cls._cooldown_window.hide()
        # Hide view solution button
        if hasattr(cls, '_view_solution_button_initialized') and cls._view_solution_button_initialized and cls._view_solution_button and cls._view_solution_button.get('window'):
            cls._view_solution_button['window'].hide()
            cls._view_solution_button_ui_instance = None
        # Hide view image button
        if hasattr(cls, '_view_image_button_initialized') and cls._view_image_button_initialized and cls._view_image_button and cls._view_image_button.get('window'):
            cls._view_image_button['window'].hide()
            cls._view_image_button_ui_instance = None

        if cls._timer_thread is not None:
            cls._timer_thread.quit()
            cls._timer_thread.wait()
            cls._timer_thread = None
        if hasattr(cls, '_timer') and cls._timer:
            if cls._timer.text_item:
                cls._timer.text_item.setPlainText("")
            if cls._timer.bg_image_item:
                cls._timer.bg_image_item.setPixmap(QPixmap())
            if hasattr(cls, '_timer_scene') and cls._timer.scene:
                cls._timer.scene.clear()
        if hasattr(cls, '_button_view') and cls._button_view:
            if hasattr(cls, "_button") and cls._button:
                 if cls._button.get('scene'):
                    cls._button['scene'].clear()
                 else:
                    print("[qt_overlay.py - hide] _button['scene'] does NOT exist")
            else:
                print("[qt_overlay.py - hide] _button does not exist.")
            
            # ClickableVideoView doesn't have set_click_callback, use disconnect instead
            try:
                cls._button_view.clicked.disconnect()
                print("[qt_overlay.py - hide] Disconnected button_view click signals")
            except TypeError:
                # No connections to disconnect
                print("[qt_overlay.py - hide] No click signals to disconnect")
            except Exception as e:
                print(f"[qt_overlay.py - hide] Error disconnecting signals: {e}")
        
        print("[qt_overlay.py - _actual_hide] === COMPLETED _actual_hide() ===")

    @classmethod
    def hide_hint_cooldown(cls):
        """Hide the cooldown display and clear cooldown text"""
        if hasattr(cls, '_cooldown_window') and cls._cooldown_window:
            # Hide the window
            try:
                cls._cooldown_window.hide()
            except Exception as e:
                print(f"[qt overlay] Error hiding cooldown window: {e}")
            
            # Clear the cooldown text content directly
            if hasattr(cls, '_cooldown_text') and cls._cooldown_text:
                try:
                    cls._cooldown_text.setHtml("")
                    print("[qt overlay] Cooldown text cleared")
                except Exception as e:
                    print(f"[qt overlay] Error clearing cooldown text: {e}")
        
        # For backwards compatibility, also handle older cooldown
        if hasattr(cls, '_window') and cls._window:
            print("[qt overlay] Cooldown complete")

    @classmethod
    def hide_overlays_for_video(cls):
        """
        No-op method - UI elements are no longer hidden during video playback
        since video is now displayed in its own standalone top-level window.
        """
        print("[qt overlay] UI elements no longer need to be hidden for video playback (top-level video window)")
        # Intentionally empty - all UI elements remain visible

    @classmethod
    def register_ui_manager(cls, ui_manager):
        """Register the UI manager instance for callbacks."""
        cls._ui_manager = ui_manager
        print(f"[qt overlay] UI manager registered: {ui_manager}")

    @classmethod
    def _init_loss_screen(cls):
        print("[qt_overlay] Initializing loss screen...", flush=True)
        """Initializes the loss screen components."""
        if cls._loss_screen_initialized:
            return

        # Base path for resources
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        image_path = os.path.join(base_path, 'other_files', 'loss.png')

        if not os.path.exists(image_path):
            print(f"[qt overlay] Loss image not found at {image_path}")
            return

        # Manually create components instead of using init_background
        try:
            cls._loss_screen_window = QWidget()
            cls._loss_screen_window.setWindowTitle("Game Over") # Set title here
            cls._loss_screen_window.setWindowFlags(
                Qt.Window | 
                Qt.FramelessWindowHint | 
                Qt.WindowStaysOnTopHint | 
                Qt.Tool # Prevents showing in taskbar
            )
            cls._loss_screen_window.setAttribute(Qt.WA_TranslucentBackground)
            cls._loss_screen_window.setAttribute(Qt.WA_ShowWithoutActivating)

            cls._loss_screen_scene = QGraphicsScene()
            cls._loss_screen_view = QGraphicsView(cls._loss_screen_scene, cls._loss_screen_window)
            cls._loss_screen_view.setStyleSheet("background: transparent; border: none;")
            cls._loss_screen_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._loss_screen_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._loss_screen_view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

            # Load and set pixmap
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                print(f"[qt overlay] Failed to load loss image: {image_path}")
                cls._loss_screen_window.deleteLater()
                cls._loss_screen_window = None
                return

            # Get screen dimensions and scale pixmap
            screen_size = QApplication.primaryScreen().size()
            scaled_pixmap = pixmap.scaled(screen_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            cls._loss_screen_pixmap_item = QGraphicsPixmapItem(scaled_pixmap)
            cls._loss_screen_scene.addItem(cls._loss_screen_pixmap_item)

            # Set geometry and scene rect to fullscreen
            screen_geom = QApplication.primaryScreen().geometry()
            cls._loss_screen_window.setGeometry(screen_geom)
            cls._loss_screen_view.setGeometry(0, 0, screen_geom.width(), screen_geom.height())
            cls._loss_screen_scene.setSceneRect(0, 0, screen_geom.width(), screen_geom.height())

            # Rotate and center the image
            pixmap_rect = cls._loss_screen_pixmap_item.boundingRect()
            cls._loss_screen_pixmap_item.setTransformOriginPoint(pixmap_rect.center())
            cls._loss_screen_pixmap_item.setRotation(90)

            # Calculate center position *after* rotation
            rotated_rect = cls._loss_screen_pixmap_item.mapToScene(pixmap_rect).boundingRect()
            center_x = (screen_geom.width() - rotated_rect.width()) / 2
            center_y = (screen_geom.height() - rotated_rect.height()) / 2
            cls._loss_screen_pixmap_item.setPos(center_x, center_y)

        except Exception as e:
            print(f"[qt overlay] Error manually initializing loss screen: {e}")
            traceback.print_exc()
            if hasattr(cls, '_loss_screen_window') and cls._loss_screen_window:
                cls._loss_screen_window.deleteLater()
                cls._loss_screen_window = None
            return

        if cls._loss_screen_window:
            cls._loss_screen_initialized = True
            print(f"[qt overlay] Loss screen initialized with {image_path}")
        else:
            print(f"[qt overlay] Failed to initialize loss screen.")
        print("[qt_overlay] Loss screen initialized.", flush=True)

    @classmethod
    def show_loss_screen(cls):
        """Displays the game loss screen."""
        try:
            if not cls._loss_screen_initialized:
                try:
                    cls._init_loss_screen()
                except Exception as e:
                    print(f"[qt overlay] Error initializing loss screen: {e}")
                    traceback.print_exc()
                    return

            if cls._loss_screen_initialized and cls._loss_screen_window:
                cls.hide_fullscreen_hint()
                try:
                    cls._loss_screen_window.setWindowState(cls._loss_screen_window.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
                    cls._loss_screen_window.showFullScreen()
                    cls._loss_screen_window.activateWindow()
                    cls._loss_screen_window.raise_()
                    print(f"[qt overlay] Loss screen shown.")
                except Exception as e:
                    print(f"[qt overlay] Error showing loss screen: {e}. Attempting to reinitialize.")
                    traceback.print_exc()
                    
                    try:
                        cls._loss_screen_initialized = False
                        if cls._loss_screen_window:
                            cls._loss_screen_window.deleteLater()
                            cls._loss_screen_window = None
                    except Exception:
                        pass
                    
                    try:
                        cls._init_loss_screen()
                        if cls._loss_screen_initialized and cls._loss_screen_window:
                            cls._loss_screen_window.showFullScreen()
                            print(f"[qt overlay] Loss screen shown after reinitialization.")
                        else:
                            print(f"[qt overlay] Reinitialization of loss screen failed.")
                    except Exception as e2:
                        print(f"[qt overlay] Error reinitializing loss screen: {e2}")
                        traceback.print_exc()
            else:
                print(f"[qt overlay] Cannot show loss screen, not initialized.")
        except Exception as e:
            print(f"[qt overlay] Unhandled exception in show_loss_screen: {e}")
            traceback.print_exc()

    @classmethod
    def hide_loss_screen(cls):
        """Hides the game loss screen."""
        if cls._loss_screen_initialized and cls._loss_screen_window:
            cls._loss_screen_window.hide()
            print(f"[qt overlay] Loss screen hidden.")

    @classmethod
    def _init_victory_screen(cls):
        print("[qt_overlay] Initializing victory screen...", flush=True)
        """Initializes the victory screen components."""
        if cls._victory_screen_initialized:
            return

        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        image_path = os.path.join(base_path, 'other_files', 'victory.png')

        if not os.path.exists(image_path):
            print(f"[qt overlay] Victory image not found at {image_path}")
            return

        # Manually create components instead of using init_background
        try:
            cls._victory_screen_window = QWidget()
            cls._victory_screen_window.setWindowTitle("Victory!") # Set title here
            cls._victory_screen_window.setWindowFlags(
                Qt.Window | 
                Qt.FramelessWindowHint | 
                Qt.WindowStaysOnTopHint | 
                Qt.Tool # Prevents showing in taskbar
            )
            cls._victory_screen_window.setAttribute(Qt.WA_TranslucentBackground)
            cls._victory_screen_window.setAttribute(Qt.WA_ShowWithoutActivating)

            cls._victory_screen_scene = QGraphicsScene()
            cls._victory_screen_view = QGraphicsView(cls._victory_screen_scene, cls._victory_screen_window)
            cls._victory_screen_view.setStyleSheet("background: transparent; border: none;")
            cls._victory_screen_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._victory_screen_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._victory_screen_view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

            # Load and set pixmap
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                print(f"[qt overlay] Failed to load victory image: {image_path}")
                cls._victory_screen_window.deleteLater()
                cls._victory_screen_window = None
                return

            # Get screen dimensions and scale pixmap
            screen_size = QApplication.primaryScreen().size()
            scaled_pixmap = pixmap.scaled(screen_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            cls._victory_screen_pixmap_item = QGraphicsPixmapItem(scaled_pixmap)
            cls._victory_screen_scene.addItem(cls._victory_screen_pixmap_item)

            # Set geometry and scene rect to fullscreen
            screen_geom = QApplication.primaryScreen().geometry()
            cls._victory_screen_window.setGeometry(screen_geom)
            cls._victory_screen_view.setGeometry(0, 0, screen_geom.width(), screen_geom.height())
            cls._victory_screen_scene.setSceneRect(0, 0, screen_geom.width(), screen_geom.height())

            # Rotate and center the image
            pixmap_rect = cls._victory_screen_pixmap_item.boundingRect()
            cls._victory_screen_pixmap_item.setTransformOriginPoint(pixmap_rect.center())
            cls._victory_screen_pixmap_item.setRotation(90)

            # Calculate center position *after* rotation
            rotated_rect = cls._victory_screen_pixmap_item.mapToScene(pixmap_rect).boundingRect()
            center_x = (screen_geom.width() - rotated_rect.width()) / 2
            center_y = (screen_geom.height() - rotated_rect.height()) / 2
            cls._victory_screen_pixmap_item.setPos(center_x, center_y)

        except Exception as e:
            print(f"[qt overlay] Error manually initializing victory screen: {e}")
            traceback.print_exc()
            if hasattr(cls, '_victory_screen_window') and cls._victory_screen_window:
                cls._victory_screen_window.deleteLater()
                cls._victory_screen_window = None
            return

        if cls._victory_screen_window:
            cls._victory_screen_initialized = True
            print(f"[qt overlay] Victory screen initialized with {image_path}")
        else:
            print(f"[qt overlay] Failed to initialize victory screen.")
        print("[qt_overlay] Victory screen initialized.", flush=True)

    @classmethod
    def show_victory_screen(cls):
        """Displays the game victory screen."""
        try:
            # Ensure initialization is done in a safe way
            if not cls._victory_screen_initialized:
                try:
                    cls._init_victory_screen()
                except Exception as e:
                    print(f"[qt overlay] Error initializing victory screen: {e}")
                    traceback.print_exc()
                    return

            # Check if window exists before attempting to display
            if cls._victory_screen_initialized and cls._victory_screen_window:
                cls.hide_fullscreen_hint()
                # Try to show the window directly, catch any errors
                try:
                    cls._victory_screen_window.setWindowState(cls._victory_screen_window.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
                    cls._victory_screen_window.showFullScreen()
                    cls._victory_screen_window.activateWindow()
                    cls._victory_screen_window.raise_()
                    print(f"[qt overlay] Victory screen shown.")
                except Exception as e:
                    # If showing fails, try to reinitialize and show again
                    print(f"[qt overlay] Error showing victory screen: {e}. Attempting to reinitialize.")
                    traceback.print_exc()
                    
                    # Cleanup old window if it exists
                    try:
                        cls._victory_screen_initialized = False
                        if cls._victory_screen_window:
                            cls._victory_screen_window.deleteLater()
                            cls._victory_screen_window = None
                    except Exception:
                        pass  # Ignore errors during cleanup
                    
                    # Try to reinitialize
                    try:
                        cls._init_victory_screen()
                        if cls._victory_screen_initialized and cls._victory_screen_window:
                            cls._victory_screen_window.showFullScreen()
                            print(f"[qt overlay] Victory screen shown after reinitialization.")
                        else:
                            print(f"[qt overlay] Reinitialization of victory screen failed.")
                    except Exception as e2:
                        print(f"[qt overlay] Error reinitializing victory screen: {e2}")
                        traceback.print_exc()
            else:
                print(f"[qt overlay] Cannot show victory screen, not initialized.")
        except Exception as e:
            print(f"[qt overlay] Unhandled exception in show_victory_screen: {e}")
            traceback.print_exc()

    @classmethod
    def hide_victory_screen(cls):
        """Hides the game victory screen."""
        if cls._victory_screen_initialized and cls._victory_screen_window:
            cls._victory_screen_window.hide()
            print(f"[qt overlay] Victory screen hidden.")

    @classmethod
    def set_theme_colors(cls, hint_text_color, timer_text_color):
        cls._current_hint_text_color = hint_text_color
        cls._current_timer_text_color = timer_text_color