# qt_overlay.py
print("[qt overlay] Beginning imports ...")
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
from qt_init import init_fullscreen_hint, init_view_image_button, init_view_solution_button, init_video_display, init_hint_text_overlay, init_hint_request_text_overlay, init_gm_assistance_overlay, init_background, init_waiting_label, init_view_image_button, init_view_solution_button, init_timer, init_help_button
print("[qt overlay] Ending imports ...")

class OverlayBridge(QObject):
    """Receives invocations from other threads and calls Overlay class methods."""

    def __init__(self):
        super().__init__()
        self._timers = []  # Keep track of active timers

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
        # print("[Bridge] prepare_video_display_slot called")
        try:
            Overlay.prepare_video_display(is_skippable, click_callback)
            # Note: Returning success via BlockingQueuedConnection is complex.
            # We assume success if no exception occurs during the call.
        except Exception as e:
            print(f"[Bridge] Error in prepare_video_display_slot: {e}")
            traceback.print_exc()

    @pyqtSlot()
    def show_video_display_slot(self):
        # print("[Bridge] show_video_display_slot called")
        Overlay.show_video_display()

    @pyqtSlot()
    def hide_video_display_slot(self):
        # print("[Bridge] hide_video_display_slot called")
        Overlay.hide_video_display()

    @pyqtSlot()
    def destroy_video_display_slot(self):
        # print("[Bridge] destroy_video_display_slot called")
        Overlay.destroy_video_display()

    @pyqtSlot(object) # Frame data is a numpy array (object)
    def update_video_frame_slot(self, frame_data):
        # print("[Bridge] update_video_frame_slot called") # Very noisy
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
    """Class to handle overlay windows and QGraphicsView/Scene components."""
    # --- Class Variables ---
    # Window references
    _initialized = False
    _window = None
    _view = None
    _scene = None
    _text_item = None
    _bg_image_item = None
    _parent_hwnd = None
    _kiosk_app = None
    _app = None
    _button = {}  # Initialize the _button dictionary
    
    # State flags
    _game_lost = False
    _game_won = False
    
    # Thread handling
    _timer_thread = None
    _button_thread = None
    _hint_text_thread = None
    _hint_request_text_thread = None
    _hint_text = None
    _hint_request_text = None
    
    # GM assistance overlay
    _gm_assistance_overlay = None
    _victory_screen = None
    
    # Video display
    _video_window = None
    _video_view = None
    _video_scene = None
    _video_frame_item = None
    _video_click_callback = None
    _video_is_initialized = False
    _bridge = None
    _last_frame = None
    
    # Fullscreen Hint
    _fullscreen_hint_window = None
    _fullscreen_hint_scene = None
    _fullscreen_hint_view = None
    _fullscreen_hint_pixmap_item = None
    _fullscreen_hint_pixmap = None
    _fullscreen_hint_ui_instance = None
    _fullscreen_hint_initialized = False
    
    # Image/video buttons
    _view_image_button = None
    _view_image_button_initialized = False
    _view_image_button_ui_instance = None
    
    _view_solution_button = None
    _view_solution_button_initialized = False
    _view_solution_button_ui_instance = None
    
    # Waiting Screen
    _waiting_label = None
    _waiting_label_initialized = False
    
    # Background image
    _background_window = None
    _background_scene = None
    _background_view = None
    _background_pixmap_item = None
    _background_initialized = False
    
    @classmethod
    def init(cls):
        """Initialize the overlay window and components."""
        if cls._initialized:
            print("[qt overlay] Already initialized, skipping.")
            return

        print("[qt overlay] Creating OverlayBridge...")
        cls._bridge = OverlayBridge()
        
        if not cls._kiosk_app:
            print("[qt overlay] Kiosk_app reference needs to be set separately. ")

        # Look for an existing QApplication instance
        app = QApplication.instance()
        
        if app is None:
            print("[qt overlay] ERROR: No QApplication instance found!")
            return

        # Set app reference
        cls._app = app
        
        # Look for main window in the app if available
        main_parent = None
        if hasattr(app, 'main_window'):
            main_parent = app.main_window
            print(f"[qt overlay] Using main app window as parent: {main_parent}")
        
        # Create the overlay window with main window as parent if available
        cls._window = QWidget(main_parent) 
        cls._window.setAttribute(Qt.WA_TranslucentBackground)
        
        # Set appropriate window flags based on parent situation
        if main_parent:
            # If it has a parent, only need frameless hint
            cls._window.setWindowFlags(Qt.FramelessWindowHint)
        else:
            # If no parent, set up as independent overlay
            cls._window.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool # Make it a tool window
            )
            cls._window.setAttribute(Qt.WA_ShowWithoutActivating)
            
        # Create scene and view
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
        
        # Get screen size
        screen_geometry = QApplication.desktop().screenGeometry()
        width = screen_geometry.width()
        height = screen_geometry.height()
        
        # Set window and view size
        cls._window.setGeometry(0, 0, width, height)
        cls._view.setGeometry(0, 0, width, height)
        cls._scene.setSceneRect(0, 0, width, height)
        
        # Create text item
        cls._text_item = QGraphicsTextItem()
        cls._text_item.setDefaultTextColor(Qt.white)
        cls._text_item.setFont(QFont('Arial', 26))
        cls._scene.addItem(cls._text_item)
        cls._text_item.setPos(50, 50)
        
        # Background image item
        cls._bg_image_item = cls._scene.addPixmap(QPixmap())
        cls._bg_image_item.setZValue(-1)
                
        # Try to initialize other UI elements
        from qt_init import init_timer, init_help_button, init_background, init_fullscreen_hint, init_video_display
        from qt_init import init_view_image_button, init_view_solution_button, init_hint_text_overlay
        from qt_init import init_hint_request_text_overlay, init_gm_assistance_overlay, init_waiting_label
        
        try:
            init_background(cls)
        except Exception as e:
            print(f"[qt overlay] Error initializing background: {e}")
            traceback.print_exc()
            
        try:
            init_gm_assistance_overlay(cls)
        except Exception as e:
            print(f"[qt overlay] Error initializing gm_assistance_overlay: {e}")
            traceback.print_exc()
            
        try:
            init_video_display(cls)
        except Exception as e:
            print(f"[qt overlay] Error initializing video display: {e}")
            traceback.print_exc()
            
        try:
            init_fullscreen_hint(cls)
        except Exception as e:
            print(f"[qt overlay] Error initializing fullscreen hint: {e}")
            traceback.print_exc()
            
        try:
            init_timer(cls)
        except Exception as e:
            print(f"[qt overlay] Error initializing timer: {e}")
            traceback.print_exc()
            
        try:
            init_help_button(cls)
        except Exception as e:
            print(f"[qt overlay] Error initializing help button: {e}")
            traceback.print_exc()
            
        cls._initialized = True

    @classmethod
    def set_kiosk_app(cls, kiosk_app):
        """Set the kiosk_app reference directly."""
        cls._kiosk_app = kiosk_app
        print(f"[qt overlay] Kiosk_app reference set: {kiosk_app}")

    @classmethod
    def _init_fullscreen_hint(cls):
        """Initialize fullscreen hint display components."""
        init_fullscreen_hint(cls)
    
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

            # 3. Get screen dimensions and calculate scaling/positioning (reuse ui.py logic)
            screen_width = QApplication.desktop().screenGeometry().width()
            screen_height = QApplication.desktop().screenGeometry().height()
            margin = 50 # Same margin as tk version

            # Calculate resize ratio maintaining aspect ratio (rotated logic)
            # Note: We use the original pixmap dimensions for calculation
            img_width = pixmap.width()
            img_height = pixmap.height()

            # Ratios considering the final rotated orientation within screen bounds
            width_ratio = (screen_height - 80) / img_width # Target width is screen height after rotation
            height_ratio = (screen_width - (2 * margin) - 80) / img_height # Target height is screen width after rotation
            ratio = min(width_ratio, height_ratio)

            scaled_width = int(img_width * ratio)
            scaled_height = int(img_height * ratio)

            # Scale pixmap smoothly
            scaled_pixmap = pixmap.scaled(scaled_width, scaled_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            cls._fullscreen_hint_pixmap = scaled_pixmap # Store reference

            # 4. Apply pixmap, rotation, and position
            cls._fullscreen_hint_pixmap_item.setPixmap(cls._fullscreen_hint_pixmap)
            cls._fullscreen_hint_pixmap_item.setTransformOriginPoint(cls._fullscreen_hint_pixmap.width() / 2, cls._fullscreen_hint_pixmap.height() / 2)
            cls._fullscreen_hint_pixmap_item.setRotation(90) # Rotate

            # Calculate position for centered *rotated* image
            # Center point of the screen area (considering margins)
            center_x_screen = (screen_width - (2 * margin)) / 2 + margin
            center_y_screen = screen_height / 2

            # The item's top-left corner after rotation needs to be calculated
            # Rotated width is scaled_height, rotated height is scaled_width
            rotated_width = scaled_height
            rotated_height = scaled_width
            pos_x = center_x_screen - (rotated_width / 2)
            pos_y = center_y_screen - (rotated_height / 2)

            # Adjust position because rotation happens around the top-left by default before origin change
            # Need to translate to center *then* rotate effectively.
            # Easier way: Set position *after* rotation, considering the bounding box change.
            # The final top-left corner for the rotated item to be centered:
            final_pos_x = (screen_width + rotated_width) / 2 - rotated_width + margin # Complicated - let's try centering the view contents instead
            final_pos_y = (screen_height - rotated_height) / 2

            # Let's try centering using the item's bounding rect after transform
            cls._fullscreen_hint_pixmap_item.setPos(0,0) # Reset position first
            rotated_bounding_rect = cls._fullscreen_hint_pixmap_item.mapToScene(cls._fullscreen_hint_pixmap_item.boundingRect()).boundingRect()

            final_pos_x_new = (screen_width - rotated_bounding_rect.width()) / 2
            final_pos_y_new = (screen_height - rotated_bounding_rect.height()) / 2
            cls._fullscreen_hint_pixmap_item.setPos(final_pos_x_new, final_pos_y_new)


            # --- Alternative: FitInView (Easier) ---
            # Reset transform before fitting
            # cls._fullscreen_hint_pixmap_item.setTransform(QTransform())
            # cls._fullscreen_hint_pixmap_item.setPixmap(cls._fullscreen_hint_pixmap) # Set unrotated pixmap
            # cls._fullscreen_hint_view.resetTransform()
            # cls._fullscreen_hint_view.setSceneRect(cls._fullscreen_hint_pixmap_item.boundingRect()) # Set scene rect to pixmap size
            # cls._fullscreen_hint_view.fitInView(cls._fullscreen_hint_pixmap_item, Qt.KeepAspectRatio)
            # cls._fullscreen_hint_view.rotate(90) # Rotate the entire view


            # 5. Connect click handler
            try:
                cls._fullscreen_hint_view.clicked.disconnect() # Disconnect previous
            except TypeError:
                pass # No connection existed
            cls._fullscreen_hint_view.clicked.connect(cls.hide_fullscreen_hint)

            # 6. Show window
            cls._fullscreen_hint_window.setGeometry(QApplication.desktop().screenGeometry()) # Ensure fullscreen
            cls._fullscreen_hint_view.setGeometry(0, 0, screen_width, screen_height) # View covers window
            cls._fullscreen_hint_scene.setSceneRect(0,0, screen_width, screen_height) # Scene covers view

            cls._fullscreen_hint_window.show()
            cls._fullscreen_hint_window.raise_()
            QApplication.processEvents() # Process pending events

        except Exception as e:
            print(f"[qt overlay] Error showing fullscreen hint: {e}")
            traceback.print_exc()
            # Attempt to restore UI if error occurs
            if cls._fullscreen_hint_ui_instance:
                cls._fullscreen_hint_ui_instance = None
            cls.hide_fullscreen_hint() # Try to hide potentially broken overlay
            cls.show_all_overlays()    # Try to restore other overlays

    @classmethod
    def hide_fullscreen_hint(cls):
        """Hides the fullscreen hint overlay and restores the normal UI."""
        # print("[qt overlay] Hiding fullscreen hint.") # Debug
        if cls._fullscreen_hint_window and cls._fullscreen_hint_initialized:
            if cls._fullscreen_hint_window.isVisible():
                cls._fullscreen_hint_window.hide()
                # Clear the pixmap item to free memory
                cls._fullscreen_hint_pixmap_item.setPixmap(QPixmap())
                cls._fullscreen_hint_pixmap = None # Clear stored pixmap


            # Restore other overlays *first*
            cls.show_all_overlays()

            # Call the UI restoration logic *after* hiding and showing others
            if cls._fullscreen_hint_ui_instance:
                # Use invokeMethod or after(0) if direct call causes issues
                # Direct call likely okay as hide is triggered by user click in main thread
                try:
                    print("[qt overlay] Calling restore_hint_view...")
                    cls._fullscreen_hint_ui_instance.restore_hint_view()
                except Exception as e:
                    print(f"[qt overlay] Error calling restore_hint_view: {e}")
                    traceback.print_exc()
                finally:
                    # Clear reference once called
                    cls._fullscreen_hint_ui_instance = None
            else:
                 print("[qt overlay] Warning: No UI instance found to call restore_hint_view.")

        # else:
            # print("[qt overlay] Fullscreen hint window not visible or not initialized.") # Debug

    @classmethod
    def _init_view_image_button(cls):
        """Initialize the 'View Image Hint' button components."""
        init_view_image_button(cls)

    @classmethod
    def _init_view_solution_button(cls):
        """Initialize the 'View Solution' button components."""
        init_view_solution_button(cls)

    @classmethod
    def _on_view_image_button_clicked(cls):
        """Callback when the Qt 'View Image Hint' button is clicked."""
        print("[qt overlay] View Image button clicked.")

    @classmethod
    def _on_view_solution_button_clicked(cls):
        """Callback when the Qt 'View Solution' button is clicked."""
        print("[qt overlay] View Solution button clicked.")
        if cls._view_solution_button_ui_instance and hasattr(cls._view_solution_button_ui_instance, 'toggle_solution_video'):
            # Call the existing toggle method in ui.py
            # Ensure this call happens in the main thread if ui.py methods aren't thread-safe
            # Since the click event happens in the main Qt thread, a direct call should be okay.
            cls._view_solution_button_ui_instance.toggle_solution_video()
        else:
            print("[qt overlay] Error: No UI instance or toggle_solution_video method available for View Solution click.")

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
        """Initialize video display components (window, scene, view, item)."""
        init_video_display(cls)

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
            # Ensure it's visible and on top
            cls._video_window.show()
            cls._video_window.raise_()
            cls._video_window.activateWindow() # Try to ensure it gets focus/clicks
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
        if cls._video_window and cls._video_is_initialized:
            print("[qt overlay] Destroying video display.")
            if cls._video_window.isVisible():
                cls._video_window.hide()

            try:
                if cls._video_view and cls._video_view.receivers(cls._video_view.clicked) > 0:
                    cls._video_view.clicked.disconnect()
            except TypeError:
                pass
            except Exception as e:
                print(f"[qt overlay] Error disconnecting video signal during destroy: {e}")


            # --- Schedule custom item for deletion ---
            if cls._video_frame_item and cls._video_scene:
                # Check if item is still in the scene before removing
                if cls._video_frame_item in cls._video_scene.items():
                    cls._video_scene.removeItem(cls._video_frame_item)
                #cls._video_frame_item.deleteLater() # Schedule custom item deletion
            # --- END CHANGE ---

            if cls._video_view:
                cls._video_view.deleteLater()
            if cls._video_scene:
                cls._video_scene.deleteLater()
            cls._video_window.deleteLater()

            # --- Reset state ---
            cls._video_window = None
            cls._video_view = None
            cls._video_scene = None
            # --- REMOVE ---
            # cls._video_pixmap_item = None
            # +++ ADD +++
            cls._video_frame_item = None # Reset custom item reference
            # --- END CHANGE ---
            cls._video_click_callback = None
            cls._last_frame = None
            cls._video_is_initialized = False

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
        """Initialize hint text overlay components."""
        init_hint_text_overlay(cls)

    @classmethod
    def _init_hint_request_text_overlay(cls):
        """Initialize hint request text overlay components."""
        init_hint_request_text_overlay(cls)

    @classmethod
    def _init_gm_assistance_overlay(cls):
        """Initialize game master assistance overlay components."""
        init_gm_assistance_overlay(cls)

    @classmethod
    def show_hint_text(cls, text, room_number=None):
        """Show hint text using a Qt overlay."""
        if not cls._initialized or not cls._hint_text['window']:
            return

         # Initialize hint text thread if needed
        if cls._hint_text_thread is None:
            cls._hint_text_thread = HintTextThread()
            cls._hint_text_thread.update_signal.connect(cls._actual_hint_text_update)
            cls._hint_text_thread.start()

        # Send update through thread
        cls._hint_text_thread.update_text({'text':text, 'room_number':room_number})

    @classmethod
    def _actual_hide(cls):
        """Actually hide the overlay window."""
        if cls._initialized and cls._window:
            cls._window.hide()
        if cls._button_view and cls._button_window:
            # Removed call to set_click_callback as it doesn't exist in ClickableVideoView
            cls._button_window.hide()
            
    @classmethod
    def _actual_help_button_update(cls, ui_instance=None, show=True, disable=False):
        """Update help button based on settings."""
        import logging
        import os  # Using os.path instead of importing from kiosk
        
        logging.debug(f"_actual_help_button_update: show={show}, disable={disable}")
        
        # Initialize button if it doesn't exist
        if not hasattr(cls, '_button_view') or cls._button_view is None:
            if '_button' not in cls.__dict__ or not isinstance(cls._button, dict):
                cls._button = {}
                
            # Create button scene, view, and window if they don't exist
            if 'scene' not in cls._button:
                from PyQt5.QtWidgets import QGraphicsScene
                cls._button['scene'] = QGraphicsScene()
                
            if not hasattr(cls, '_button_window') or cls._button_window is None:
                from PyQt5.QtWidgets import QWidget
                from PyQt5.QtCore import Qt
                cls._button_window = QWidget()
                cls._button_window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
                cls._button_window.setAttribute(Qt.WA_TranslucentBackground)
                
            # Create clickable view
            from qt_classes import ClickableVideoView
            cls._button_view = ClickableVideoView(cls._button['scene'], cls._button_window)
            cls._button_view.setAlignment(Qt.AlignCenter)
            
            # Connect clicked signal to handler
            if ui_instance and hasattr(ui_instance, 'message_handler'):
                # Connect to request_help method instead of help_button_clicked
                cls._button_view.clicked.connect(ui_instance.message_handler.request_help)
                logging.debug("Connected button view clicked signal to message_handler.request_help")
        
        if show and not disable:
            logging.debug("Showing help button")
            # Set button as skippable (clickable)
            cls._button_view.set_skippable(True)
            
            # Show button window if it exists
            if hasattr(cls, '_button_window') and cls._button_window:
                cls._button_window.show()
        else:
            logging.debug(f"Not showing help button, show={show}, disable={disable}")
            # Hide button window if it exists
            if hasattr(cls, '_button_window') and cls._button_window:
                cls._button_window.hide()

    @classmethod
    def hide_help_button(cls):
        """Hide the help button"""
        if hasattr(cls, '_button_window') and cls._button_window:
            cls._button_window.hide()

    @classmethod
    def hide_cooldown(cls):
        """Hide just the cooldown overlay"""
        print("[qt overlay.hide_cooldown] Called")
        if cls._window:
            QMetaObject.invokeMethod(
                cls._window,
                "hide",
                Qt.QueuedConnection
            )
            print("[qt_overlay.hide_cooldown] hide() invoked")
    
    @classmethod
    def hide(cls):
        """Hide all overlay windows (thread-safe entry point)."""
        print("[qt_overlay.py - hide] === STARTING hide() - Calling _actual_hide via invokeMethod ===")
        QMetaObject.invokeMethod(cls, "_actual_hide", Qt.QueuedConnection)

    @classmethod
    def hide_all_overlays(cls):
        """Hide all Qt overlay UI elements temporarily (EXCEPT video)."""
        # print("[qt overlay] Hiding non-video overlay UI elements") # Reduce noise
        try:
            # Existing hides...
            if hasattr(cls, '_timer_window') and cls._timer_window and cls._timer_window.isVisible():
                cls._timer_window.hide()
            if hasattr(cls, '_button_window') and cls._button_window and cls._button_window.isVisible():
                 cls._button_window.hide()
            if hasattr(cls, '_hint_text') and cls._hint_text and cls._hint_text.get('window') and cls._hint_text['window'].isVisible():
                 cls._hint_text['window'].hide()
            if hasattr(cls, '_hint_request_text') and cls._hint_request_text and cls._hint_request_text.get('window') and cls._hint_request_text['window'].isVisible():
                 cls._hint_request_text['window'].hide()
            if hasattr(cls, '_gm_assistance_overlay') and cls._gm_assistance_overlay and cls._gm_assistance_overlay.get('window'):
                gm_window = cls._gm_assistance_overlay['window']
                # Store visibility state ONLY if window exists and might be visible
                if gm_window:
                   cls._gm_assistance_overlay['_was_visible'] = gm_window.isVisible()
                   if cls._gm_assistance_overlay['_was_visible']:
                       gm_window.hide()
                else:
                   cls._gm_assistance_overlay['_was_visible'] = False # Ensure flag exists

            if hasattr(cls, '_window') and cls._window and cls._window.isVisible(): # Cooldown window
                cls._window.hide()

            cls.hide_victory_screen()
            cls.hide_loss_screen()

            # --- ADD HIDES FOR NEW BUTTONS ---
            cls.hide_view_image_button()
            cls.hide_view_solution_button()
            # --- END ADD HIDES ---
            cls.hide_waiting_screen_label() # <--- Add hide for waiting label here

            # print("[qt overlay] Non-video overlay UI elements hidden.") # Reduce noise
        except Exception as e:
            print(f"[qt overlay] Error hiding non-video overlays: {e}")
            traceback.print_exc()
            
    @classmethod
    def show_all_overlays(cls):
        """Show all the overlays that were previously hidden."""
        try:
            print("[qt_overlay] show_all_overlays called")
            
            # First, ensure the background is at the bottom of the z-order
            if hasattr(cls, '_background_window') and cls._background_window:
                cls._background_window.show()
                cls._background_window.lower()
                cls._background_window.setAttribute(Qt.WA_AlwaysStackOnBottom, True)
            
            # Show primary overlay components
            if cls._window:
                cls._window.show()
                
            # Show timer if available
            if hasattr(cls, '_timer_window') and cls._timer_window:
                cls._timer_window.show()
                cls._timer_window.raise_()
                
            # Show help button if available
            if hasattr(cls, '_button_window') and cls._button_window:
                cls._button_window.show()
                cls._button_window.raise_()
                
            # Show hint text if available
            if hasattr(cls, '_hint_text') and cls._hint_text and cls._hint_text.get('window'):
                cls._hint_text['window'].show()
                cls._hint_text['window'].raise_()
                
            # Show hint request text if available
            if hasattr(cls, '_hint_request_text') and cls._hint_request_text and cls._hint_request_text.get('window'):
                cls._hint_request_text['window'].show()
                cls._hint_request_text['window'].raise_()
                
            # Image view button
            if hasattr(cls, '_view_image_button_initialized') and cls._view_image_button_initialized and cls._view_image_button.get('window'):
                cls._view_image_button['window'].show()
                cls._view_image_button['window'].raise_()
                
            # Solution view button
            if hasattr(cls, '_view_solution_button_initialized') and cls._view_solution_button_initialized and cls._view_solution_button.get('window'):
                cls._view_solution_button['window'].show()
                cls._view_solution_button['window'].raise_()
                
            # Update the help button (it will check if it should be shown)
            if cls._kiosk_app:
                try:
                    cls.update_help_button(
                        cls._kiosk_app.ui, 
                        cls._kiosk_app.timer, 
                        cls._kiosk_app.hints_requested, 
                        cls._kiosk_app.time_exceeded_45, 
                        cls._kiosk_app.assigned_room
                    )
                except Exception as e:
                    print(f"[qt_overlay] Error updating help button: {e}")
            
            # Force a UI refresh to ensure correct stacking
            cls.refresh_ui()
                    
            print("[qt_overlay] All overlays shown")
            
        except Exception as e:
            print(f"[qt_overlay] Error in show_all_overlays: {e}")
            traceback.print_exc()

    @classmethod
    def set_background_image(cls, image_path):
        """Set the background image from a file."""
        print(f"[qt_overlay] Loading background image: {image_path}")
        try:
            if not cls._background_initialized:
                print("[qt_overlay] Background not initialized.")
                from qt_init import init_background
                init_background(cls)
                
            # Load the image
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                print(f"[qt_overlay] Error loading background image: {image_path}")
                return False
                
            # Scale pixmap to fit screen while maintaining aspect ratio
            pixmap = pixmap.scaled(
                cls._background_view.width(),
                cls._background_view.height(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )
            
            # Update the pixmap item
            cls._background_pixmap_item.setPixmap(pixmap)
            
            # Show the background window
            cls._background_window.show()
            
            # Ensure it stays at the bottom
            cls._background_window.lower()
            
            return True
        except Exception as e:
            print(f"[qt_overlay] Error setting background image: {e}")
            traceback.print_exc()
            return False

    @classmethod
    def update_timer_display(cls, time_str):
        """Update the timer display with the given time string."""
        if not hasattr(cls, '_timer') or not cls._timer:
            print("[qt_overlay] Timer not initialized, can't update display.")
            return False
            
        try:
            cls._timer.text_item.setPlainText(time_str)
            # Show timer window
            if hasattr(cls, '_timer_window') and cls._timer_window:
                cls._timer_window.show()
                cls._timer_window.raise_()
            return True
        except Exception as e:
            print(f"[qt_overlay] Error updating timer display: {e}")
            traceback.print_exc()
            return False

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
            # DO NOT reset _was_visible here. We want to remember it was shown.
            
    @classmethod
    def _init_waiting_label(cls):
        """Initialize the waiting screen label overlay."""
        init_waiting_label(cls)

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
    def refresh_ui(cls):
        """Force refresh all UI components to ensure proper display."""
        print("[qt_overlay] Refreshing UI components...")
        try:
            # Make sure background is at bottom, all other components on top
            if cls._background_initialized and cls._background_window:
                cls._background_window.lower()
                
            # Ensure timer is visible
            if hasattr(cls, '_timer_window') and cls._timer_window:
                cls._timer_window.show()
                cls._timer_window.raise_()
                
            # Show main window
            if cls._window:
                cls._window.show()
                cls._window.raise_()
                
            # Show button window if it exists
            if hasattr(cls, '_button_window') and cls._button_window:
                cls._button_window.raise_()
                
            # Raise other windows if they exist
            if hasattr(cls, '_hint_text') and cls._hint_text and cls._hint_text.get('window'):
                cls._hint_text['window'].raise_()
                
            if hasattr(cls, '_hint_request_text') and cls._hint_request_text and cls._hint_request_text.get('window'):
                cls._hint_request_text['window'].raise_()
                
            if hasattr(cls, '_view_image_button') and cls._view_image_button and cls._view_image_button.get('window'):
                cls._view_image_button['window'].raise_()
                
            if hasattr(cls, '_view_solution_button') and cls._view_solution_button and cls._view_solution_button.get('window'):
                cls._view_solution_button['window'].raise_()
                
        except Exception as e:
            print(f"[qt_overlay] Error refreshing UI: {e}")
            traceback.print_exc()
            
    @classmethod
    def update_help_button(cls, ui_instance=None, timer=None, hints_requested=0, time_exceeded_45=False, assigned_room=None):
        """Update help button visibility based on game state.
        
        This is a bridge to the _actual_help_button_update method which ensures button is only shown when appropriate.
        """
        try:
            # Only show the button if:
            # - We have a UI instance
            # - Game is not over (won or lost)
            # - Video is not playing
            # - Full screen image not showing
            
            # Get values from parameters
            show = False
            disable = False
            
            if timer and timer.game_lost or timer and timer.game_won:
                # Don't show if game is over
                show = False
            elif ui_instance and hasattr(ui_instance, 'hint_cooldown') and ui_instance.hint_cooldown:
                # Don't show during cooldown
                show = False
            elif not cls._kiosk_app or not hasattr(cls._kiosk_app, 'video_manager'):
                # Don't show if app not properly initialized
                show = False
            elif hasattr(cls._kiosk_app, 'video_manager') and cls._kiosk_app.video_manager.is_playing:
                # Don't show if video is playing
                show = False
            elif hasattr(cls._kiosk_app, 'ui') and hasattr(cls._kiosk_app.ui, 'image_is_fullscreen') and cls._kiosk_app.ui.image_is_fullscreen:
                # Don't show if full screen image is showing
                show = False
            else:
                # Default: show button
                show = True
                
            # Call the function that actually updates the button
            cls._actual_help_button_update(ui_instance, show, disable)
            
        except Exception as e:
            print(f"[qt_overlay] Error updating help button: {e}")
            traceback.print_exc()