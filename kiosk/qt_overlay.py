# qt_overlay.py
print("[qt overlay] Beginning imports ...")
from PyQt5.QtCore import Qt, QRectF, QThread, pyqtSignal, QMetaObject, Q_ARG, Qt, QPointF, pyqtSlot, QBuffer, QIODevice, QObject
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
print("[qt overlay] Ending imports ...")

class ClickableVideoView(QGraphicsView):
    """Custom QGraphicsView for video display that handles clicks"""
    clicked = pyqtSignal() # Signal emitted on click

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self._is_skippable = False

    def mousePressEvent(self, event):
        # print("[qt overlay] Video view clicked.") # Reduce debug noise
        if event.button() == Qt.LeftButton and self._is_skippable:
            print("[qt overlay] Video is skippable, emitting clicked signal.")
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_skippable(self, skippable):
        print(f"[qt overlay] Setting video skippable: {skippable}")
        self._is_skippable = skippable

# qt_overlay.py (add this class near ClickableVideoView)
class ClickableHintView(QGraphicsView):
    """Custom QGraphicsView for fullscreen hint display that handles clicks"""
    clicked = pyqtSignal() # Signal emitted on click

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)

    def mousePressEvent(self, event):
        # print("[qt overlay] Fullscreen hint view clicked.") # Debug
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

class TimerThread(QThread):
    """Dedicated thread for timer updates"""
    update_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
    def run(self):
        # Thread just emits signals, actual updates happen in main thread
        pass
        
    def update_display(self, time_str):
        self.update_signal.emit(time_str)

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

class VideoFrameItem(QGraphicsItem):
    """A QGraphicsItem that paints a QImage directly, avoiding QPixmap conversion."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._image = QImage() # Initialize with an empty QImage

    def setImage(self, image):
        """Sets the QImage to be displayed."""
        if isinstance(image, QImage) and not image.isNull():
            # PrepareGeometryChange is necessary if the image size changes
            if self._image.size() != image.size():
                self.prepareGeometryChange()
            self._image = image # Keep the QImage reference
            # No need to call update() here explicitly,
            # the view/scene update in Overlay.update_video_frame triggers the repaint
        elif image is None or (isinstance(image, QImage) and image.isNull()):
             # Handle setting an empty image (e.g., on stop)
             if not self._image.isNull():
                 self.prepareGeometryChange()
                 self._image = QImage() # Reset to empty
             # No update needed if already empty

    def boundingRect(self):
        """Return the bounding rectangle of the image."""
        # Crucial: Must return the correct size for proper redraws
        if not self._image.isNull():
            return QRectF(0, 0, self._image.width(), self._image.height())
        else:
            return QRectF() # Return empty rect if no image

    def paint(self, painter, option, widget=None):
        """Paint the stored QImage directly onto the painter."""
        if not self._image.isNull():
            # Draw the image at the item's local origin (0,0)
            painter.drawImage(0, 0, self._image)
        # else: draw nothing if no image
  
class HelpButtonThread(QThread):
    """Dedicated thread for button updates"""
    update_signal = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        
    def run(self):
        # Thread just emits signals, actual updates happen in main thread
        pass
    
    def update_button(self, button_data):
        self.update_signal.emit(button_data)

class HintTextThread(QThread):
    """Dedicated thread for hint text updates"""
    update_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

    def run(self):
        # Thread just emits signals, actual updates happen in main thread
        pass

    def update_text(self, text_data):
        self.update_signal.emit(text_data)

class HintRequestTextThread(QThread):
    """Dedicated thread for hint request text updates"""
    update_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()

    def run(self):
        # Thread just emits signals, actual updates happen in main thread
        pass

    def update_text(self, text):
        self.update_signal.emit(text)


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

class OverlayBridge(QObject):
    """Receives invocations from other threads and calls Overlay class methods."""

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


class Overlay:
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

    @classmethod
    def init(cls, tkinter_root=None):
        """Initialize Qt application and base window"""
        if not cls._app:
            cls._app = QApplication.instance()
            if cls._app is None:
                print("[qt overlay] Creating QApplication...")
                cls._app = QApplication(sys.argv)
            else:
                print("[qt overlay] Using existing QApplication instance.")

        if not cls._bridge:
            print("[qt overlay] Creating OverlayBridge...")
            cls._bridge = OverlayBridge()

        # --- Store kiosk_app reference early ---
        if tkinter_root and hasattr(tkinter_root, 'kiosk_app'):
             cls._kiosk_app = tkinter_root.kiosk_app
             print(f"[qt overlay] Stored kiosk_app reference: {cls._kiosk_app}")
        else:
             print("[qt overlay] Warning: No kiosk_app reference found on tkinter_root.")
             cls._kiosk_app = None # Important for checks later


        # --- Rest of init ---
        if tkinter_root:
            cls._parent_hwnd = tkinter_root.winfo_id()
        else:
            cls._parent_hwnd = None

        if not cls._window:
            cls._window = QWidget()
            cls._window.setAttribute(Qt.WA_TranslucentBackground)
            cls._window.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool |
                Qt.WindowDoesNotAcceptFocus
            )
            cls._window.setAttribute(Qt.WA_ShowWithoutActivating)
            if cls._parent_hwnd:
                 try:
                    win32gui.SetParent(int(cls._window.winId()), cls._parent_hwnd)
                    style = win32gui.GetWindowLong(int(cls._window.winId()), win32con.GWL_EXSTYLE)
                    win32gui.SetWindowLong(
                        int(cls._window.winId()),
                        win32con.GWL_EXSTYLE,
                        style | win32con.WS_EX_NOACTIVATE
                    )
                 except Exception as e:
                     print(f"[qt overlay] Error setting parent/style for main window: {e}")

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


        cls._initialized = True

        # Initialize all overlays
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
        
    @classmethod
    def _init_fullscreen_hint(cls):
        """Initialize fullscreen hint display components."""
        if cls._fullscreen_hint_initialized:
            return

        print("[qt overlay] Initializing fullscreen hint components...")
        try:
            # Create window
            cls._fullscreen_hint_window = QWidget() # No parent initially needed for fullscreen
            cls._fullscreen_hint_window.setStyleSheet("background-color: black;") # Black background
            cls._fullscreen_hint_window.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool
            )
            cls._fullscreen_hint_window.setAttribute(Qt.WA_ShowWithoutActivating)
            cls._fullscreen_hint_window.setAttribute(Qt.WA_OpaquePaintEvent, True) # Optimization

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

            # Initial full screen setup (will be refined when image is shown)
            screen_geometry = QApplication.desktop().screenGeometry()
            width = screen_geometry.width()
            height = screen_geometry.height()

            cls._fullscreen_hint_window.setGeometry(0, 0, width, height)
            cls._fullscreen_hint_view.setGeometry(0, 0, width, height)
            cls._fullscreen_hint_scene.setSceneRect(0, 0, width, height)
            cls._fullscreen_hint_pixmap_item.setPos(0, 0) # Place item at top-left

            cls._fullscreen_hint_initialized = True
            print("[qt overlay] Fullscreen hint components initialized.")

        except Exception as e:
            print(f"[qt overlay] Error initializing fullscreen hint display: {e}")
            traceback.print_exc()
            cls._fullscreen_hint_initialized = False
    
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
        if cls._view_image_button_initialized:
            return
        print("[qt overlay] Initializing View Image Hint button components...")
        try:
            cls._view_image_button = {
                'window': QWidget(cls._window), # Parent to main overlay window
                'scene': QGraphicsScene(),
                'view': None,
                'rect': None,
                'text_item': None
            }

            # Window setup
            win = cls._view_image_button['window']
            win.setAttribute(Qt.WA_TranslucentBackground)
            win.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool |
                Qt.WindowDoesNotAcceptFocus
            )
            win.setAttribute(Qt.WA_ShowWithoutActivating)

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

            # Text Item
            text_item = QGraphicsTextItem("VIEW IMAGE HINT")
            text_item.setDefaultTextColor(Qt.white)
            text_item.setFont(QFont('Arial', 24)) # Match ui.py
            scene.addItem(text_item)
            cls._view_image_button['text_item'] = text_item

            # Rotate and Center Text within Rectangle
            text_item.setTransformOriginPoint(text_item.boundingRect().center())
            text_item.setRotation(270) # Match ui.py
            # After rotation, center it
            rotated_text_width = text_item.boundingRect().height() # Width becomes height after 270 deg rot
            rotated_text_height = text_item.boundingRect().width() # Height becomes width
            text_x = (button_width - rotated_text_width) / 2
            text_y = (button_height - rotated_text_height) / 2
            # Need to adjust y slightly because rotation origin isn't perfect top-left
            text_item.setPos(text_x, text_y + rotated_text_height) # Adjust based on bottom-left corner after rotation


            # Set geometry for view and scene rect
            view.setGeometry(0, 0, button_width, button_height)
            scene.setSceneRect(0, 0, button_width, button_height)

            # Win32 parent/style
            if cls._parent_hwnd:
                style = win32gui.GetWindowLong(int(win.winId()), win32con.GWL_EXSTYLE)
                win32gui.SetWindowLong(int(win.winId()), win32con.GWL_EXSTYLE, style | win32con.WS_EX_NOACTIVATE)

            cls._view_image_button_initialized = True
            print("[qt overlay] View Image Hint button initialized.")
        except Exception as e:
            print(f"[qt overlay] Error initializing View Image Hint button: {e}")
            traceback.print_exc()
            cls._view_image_button_initialized = False

    @classmethod
    def _init_view_solution_button(cls):
        """Initialize the 'View Solution' button components."""
        if cls._view_solution_button_initialized:
            return
        print("[qt overlay] Initializing View Solution button components...")
        try:
            cls._view_solution_button = {
                'window': QWidget(cls._window), # Parent to main overlay window
                'scene': QGraphicsScene(),
                'view': None,
                'rect': None,
                'text_item': None
            }

            # Window setup
            win = cls._view_solution_button['window']
            win.setAttribute(Qt.WA_TranslucentBackground)
            win.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool |
                Qt.WindowDoesNotAcceptFocus
            )
            win.setAttribute(Qt.WA_ShowWithoutActivating)

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
            text_item = QGraphicsTextItem("VIEW SOLUTION") # Different text
            text_item.setDefaultTextColor(Qt.white)
            text_item.setFont(QFont('Arial', 24)) # Match ui.py
            scene.addItem(text_item)
            cls._view_solution_button['text_item'] = text_item

            # Rotate and Center Text within Rectangle
            text_item.setTransformOriginPoint(text_item.boundingRect().center())
            text_item.setRotation(270) # Match ui.py
            # After rotation, center it
            rotated_text_width = text_item.boundingRect().height()
            rotated_text_height = text_item.boundingRect().width()
            text_x = (button_width - rotated_text_width) / 2
            text_y = (button_height - rotated_text_height) / 2
            text_item.setPos(text_x, text_y + rotated_text_height) # Adjust based on bottom-left corner

            # Set geometry for view and scene rect
            view.setGeometry(0, 0, button_width, button_height)
            scene.setSceneRect(0, 0, button_width, button_height)

            # Win32 parent/style
            if cls._parent_hwnd:
                style = win32gui.GetWindowLong(int(win.winId()), win32con.GWL_EXSTYLE)
                win32gui.SetWindowLong(int(win.winId()), win32con.GWL_EXSTYLE, style | win32con.WS_EX_NOACTIVATE)

            cls._view_solution_button_initialized = True
            print("[qt overlay] View Solution button initialized.")
        except Exception as e:
            print(f"[qt overlay] Error initializing View Solution button: {e}")
            traceback.print_exc()
            cls._view_solution_button_initialized = False

    @classmethod
    def _on_view_image_button_clicked(cls):
        """Callback when the Qt 'View Image Hint' button is clicked."""
        print("[qt overlay] View Image Hint button clicked.")
        if cls._view_image_button_ui_instance and hasattr(cls._view_image_button_ui_instance, 'stored_image_data'):
            if cls._view_image_button_ui_instance.stored_image_data:
                # Directly call the method that shows the fullscreen hint overlay
                Overlay.show_fullscreen_hint(
                    cls._view_image_button_ui_instance.stored_image_data,
                    cls._view_image_button_ui_instance # Pass ui instance back
                )
            else:
                print("[qt overlay] Warning: Clicked View Image Hint, but no stored_image_data found.")
        else:
            print("[qt overlay] Error: No UI instance available for View Image Hint click.")

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
        if cls._video_is_initialized:
            return # Already initialized

        print("[qt overlay] Initializing video display components...")
        try:
            # Create video window
            cls._video_window = QWidget() # No parent initially
            cls._video_window.setStyleSheet("background-color: black;") # Explicit black background
            cls._video_window.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool
            )
            cls._video_window.setAttribute(Qt.WA_ShowWithoutActivating)
            cls._video_window.setAttribute(Qt.WA_OpaquePaintEvent, True)

            # Create scene and view
            cls._video_scene = QGraphicsScene(cls._video_window)
            cls._video_view = ClickableVideoView(cls._video_scene, cls._video_window) # Use custom view
            cls._video_view.setStyleSheet("background: transparent; border: none;") # View transparent, window black
            cls._video_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._video_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._video_view.setRenderHint(QPainter.Antialiasing, False)
            cls._video_view.setCacheMode(QGraphicsView.CacheNone)
            cls._video_view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

            # --- Create and add the CUSTOM VideoFrameItem ---
            # --- REMOVE ---
            # cls._video_pixmap_item = QGraphicsPixmapItem()
            # cls._video_scene.addItem(cls._video_pixmap_item)
            # +++ ADD +++
            cls._video_frame_item = VideoFrameItem() # Use the new custom item
            cls._video_scene.addItem(cls._video_frame_item)
            # --- END CHANGE ---

            # Full screen setup
            screen_geometry = QApplication.desktop().screenGeometry()
            width = screen_geometry.width()
            height = screen_geometry.height()

            cls._video_window.setGeometry(0, 0, width, height)
            cls._video_view.setGeometry(0, 0, width, height)
            cls._video_scene.setSceneRect(0, 0, width, height)
            cls._video_frame_item.setPos(0, 0) # Place item at top-left

            cls._video_is_initialized = True
            print("[qt overlay] Video display components initialized.")

        except Exception as e:
            print(f"[qt overlay] Error initializing video display: {e}")
            traceback.print_exc()
            cls._video_is_initialized = False

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
# --- END SNIPPET ---

    @classmethod
    def _init_hint_text_overlay(cls):
        """Initialize hint text overlay components."""
        if not hasattr(cls, '_hint_text') or not cls._hint_text:
            cls._hint_text = {
                'window': None,
                'scene': None,
                'view': None,
                'text_item': None,
                'bg_image_item': None,
                'current_background': None
            }

        # Create hint window if needed
        if not cls._hint_text['window']:
            cls._hint_text['window'] = QWidget(cls._window)
            cls._hint_text['window'].setAttribute(Qt.WA_TranslucentBackground)
            cls._hint_text['window'].setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool |
                Qt.WindowDoesNotAcceptFocus
            )
            cls._hint_text['window'].setAttribute(Qt.WA_ShowWithoutActivating)

        # Create scene and view if needed
        if not cls._hint_text['scene']:
            cls._hint_text['scene'] = QGraphicsScene()
        if not cls._hint_text['view']:
            cls._hint_text['view'] = QGraphicsView(cls._hint_text['scene'], cls._hint_text['window'])
            cls._hint_text['view'].setStyleSheet("""
                QGraphicsView {
                    background: transparent;
                    border: none;
                }
            """)
            cls._hint_text['view'].setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._hint_text['view'].setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._hint_text['view'].setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        # Create text item if needed
        if not cls._hint_text['text_item']:
            cls._hint_text['text_item'] = QGraphicsTextItem()
            cls._hint_text['text_item'].setDefaultTextColor(Qt.white)
            font = QFont('Arial', 22)
            cls._hint_text['text_item'].setFont(font)
            cls._hint_text['scene'].addItem(cls._hint_text['text_item'])

        # Set up background image first
        if not cls._hint_text['bg_image_item']:
           cls._hint_text['bg_image_item'] = cls._hint_text['scene'].addPixmap(QPixmap())
           cls._hint_text['bg_image_item'].setZValue(-1) # Set the image to the background layer

        if cls._parent_hwnd:
            style = win32gui.GetWindowLong(int(cls._hint_text['window'].winId()), win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(
                int(cls._hint_text['window'].winId()),
                win32con.GWL_EXSTYLE,
                style | win32con.WS_EX_NOACTIVATE
            )

    @classmethod
    def _init_hint_request_text_overlay(cls):
        """Initialize hint request text overlay components."""
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
            cls._hint_request_text['window'] = QWidget(cls._window)
            cls._hint_request_text['window'].setAttribute(Qt.WA_TranslucentBackground)
            cls._hint_request_text['window'].setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool |
                Qt.WindowDoesNotAcceptFocus
            )
            cls._hint_request_text['window'].setAttribute(Qt.WA_ShowWithoutActivating)

        # Create scene and view if needed
        if not cls._hint_request_text['scene']:
            cls._hint_request_text['scene'] = QGraphicsScene()
        if not cls._hint_request_text['view']:
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

        # Create text item if needed
        if not cls._hint_request_text['text_item']:
            cls._hint_request_text['text_item'] = QGraphicsTextItem()
            cls._hint_request_text['text_item'].setDefaultTextColor(Qt.yellow)
            font = QFont('Arial', 24)
            cls._hint_request_text['text_item'].setFont(font)
            cls._hint_request_text['scene'].addItem(cls._hint_request_text['text_item'])

        if cls._parent_hwnd:
            style = win32gui.GetWindowLong(int(cls._hint_request_text['window'].winId()), win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(
                int(cls._hint_request_text['window'].winId()),
                win32con.GWL_EXSTYLE,
                style | win32con.WS_EX_NOACTIVATE
            )

    @classmethod
    def _init_gm_assistance_overlay(cls):
        """Initialize game master assistance overlay components."""
        print("[qt overlay] Initializing GM assistance overlay...")
        print(f"[qt overlay] Has kiosk_app: {hasattr(cls, 'kiosk_app')}")
        if hasattr(cls, 'kiosk_app') and cls._kiosk_app is not None:
            print(f"[qt overlay] Using kiosk_app with computer_name: {cls._kiosk_app.computer_name}")
        else:
            print("[qt overlay] No kiosk_app available")
            
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
                            print("[qt overlay] Yes button clicked - GM assistance accepted")
                            # Send message to admin using the kiosk app's network
                            if hasattr(cls, 'kiosk_app') and cls._kiosk_app is not None:
                                print(f"[qt overlay] Found kiosk_app with computer_name: {cls._kiosk_app.computer_name}")
                                try:
                                    cls._kiosk_app.network.send_message({
                                        'type': 'gm_assistance_accepted',
                                        'computer_name': cls._kiosk_app.computer_name
                                    })
                                    print("[qt overlay] Message sent successfully")
                                except Exception as e:
                                    print(f"[qt overlay] Error sending message: {e}")
                                    traceback.print_exc()
                            else:
                                print("[qt overlay] Error: kiosk_app not found or is None")
                                print(f"[qt overlay] Has kiosk_app attribute: {hasattr(cls, 'kiosk_app')}")
                                if hasattr(cls, 'kiosk_app'):
                                    print(f"[qt overlay] kiosk_app value: {cls._kiosk_app}")
                            # Hide the overlay after accepting
                            cls.hide_gm_assistance()
                            break
                        elif item == cls._gm_assistance_overlay['no_rect'] or item == cls._gm_assistance_overlay['no_button']:
                            print("[qt overlay] Player clicked \"No\" - In-room assistance declined")
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
            cls._gm_assistance_overlay['window'].show()
            cls._gm_assistance_overlay['view'].show()
            cls._gm_assistance_overlay['window'].raise_()

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
        """Internal helper to perform the actual hiding, now thread-safe."""
        print("[qt_overlay.py - _actual_hide] === STARTING _actual_hide() ===")

        if cls._window:
            cls._window.hide()
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
            cls._button_view.set_click_callback(None)
        print("[qt_overlay.py - _actual_hide] === COMPLETED _actual_hide() ===")

    @classmethod
    def show_loss_screen(cls):
        """Display the game loss screen."""
        if not cls._initialized:
            return

        # --- Create/Rebuild Loss Screen Elements --- (GOOD PRACTICE)
        if hasattr(cls, '_loss_screen') and cls._loss_screen:
            if cls._loss_screen.get('window'):
                cls._loss_screen['window'].hide()  # Hide before deleting
                cls._loss_screen['window'].deleteLater()
                cls._loss_screen['window'] = None
            if cls._loss_screen.get('scene'):
                cls._loss_screen['scene'].clear()  # Clear items
                cls._loss_screen['scene'] = None
            if cls._loss_screen.get('view'):
                cls._loss_screen['view'].deleteLater()
                cls._loss_screen['view'] = None
            # Remove the text item attribute, as we'll be using an image.
            if '_text_item' in cls._loss_screen:
                del cls._loss_screen['_text_item']


        if not hasattr(cls, '_loss_screen'):
            cls._loss_screen = {}

        cls._loss_screen['window'] = QWidget(cls._window)  # Parent to main if needed
        cls._loss_screen['window'].setAttribute(Qt.WA_TranslucentBackground)
        cls._loss_screen['window'].setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowDoesNotAcceptFocus
        )
        cls._loss_screen['window'].setAttribute(Qt.WA_ShowWithoutActivating)

        cls._loss_screen['scene'] = QGraphicsScene()
        cls._loss_screen['view'] = QGraphicsView(cls._loss_screen['scene'], cls._loss_screen['window'])
        cls._loss_screen['view'].setStyleSheet("""
            QGraphicsView {
                background: transparent;  /* Or a loss-screen background */
                border: none;
            }
        """)
        cls._loss_screen['view'].setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._loss_screen['view'].setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._loss_screen['view'].setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        # --- Image Item Instead of Text Item ---
        cls._loss_screen['image_item'] = QGraphicsPixmapItem()
        cls._loss_screen['scene'].addItem(cls._loss_screen['image_item'])


        if cls._parent_hwnd:  # Set window attributes if parent exists
            style = win32gui.GetWindowLong(int(cls._loss_screen['window'].winId()), win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(
                int(cls._loss_screen['window'].winId()),
                win32con.GWL_EXSTYLE,
                style | win32con.WS_EX_NOACTIVATE
            )

        # --- Geometry and Positioning ---
        width = 1920
        height = 1080
        cls._loss_screen['window'].setGeometry(0, 0, width, height)  # Full screen
        cls._loss_screen['view'].setGeometry(0, 0, width, height)
        cls._loss_screen['scene'].setSceneRect(QRectF(0, 0, width, height))

        # --- Load and Set Image ---
        image_path = os.path.join("other_files", "loss.png")
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            # --- Scale the Pixmap ---
            scale_factor = 0.5
            scaled_pixmap = pixmap.scaled(
                int(pixmap.width() * scale_factor),
                int(pixmap.height() * scale_factor),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation  # Use SmoothTransformation for better quality
            )
            cls._loss_screen['image_item'].setPixmap(scaled_pixmap)

            # --- Positioning the Image ---
            cls._loss_screen['image_item'].setTransform(QTransform())
            cls._loss_screen['image_item'].setRotation(90)


            image_width = scaled_pixmap.width()  # Use scaled width and height
            image_height = scaled_pixmap.height() # Use scaled width and height
            cls._loss_screen['image_item'].setPos(
                (width + image_height) / 2,
                (height - image_width) / 2
            )

        else:
            print(f"[qt overlay] Loss image not found: {image_path}")
            #  Fallback to text display IF the image is missing.  Good practice.
            cls._loss_screen['text_item'] = QGraphicsTextItem()
            cls._loss_screen['text_item'].setDefaultTextColor(Qt.white)
            font = QFont('Arial', 48)
            cls._loss_screen['text_item'].setFont(font)
            cls._loss_screen['scene'].addItem(cls._loss_screen['text_item'])
            message = "Time's up! A host will arrive to collect you shortly."
            cls._loss_screen['text_item'].setHtml(
                f'<div style="background-color: rgba(0, 0, 0, 180); padding: 20px;">{message}</div>'
            )
            cls._loss_screen['text_item'].setTransform(QTransform())
            cls._loss_screen['text_item'].setRotation(90)
            text_width = cls._loss_screen['text_item'].boundingRect().width()
            text_height = cls._loss_screen['text_item'].boundingRect().height()
            cls._loss_screen['text_item'].setPos(
                (width + text_height) / 2,
                (height - text_width) / 2
            )
            

        cls._loss_screen['window'].show()
        cls._loss_screen['window'].raise_()

    @classmethod
    def hide_loss_screen(cls):
        """Hide the loss screen."""
        if hasattr(cls, '_loss_screen') and cls._loss_screen and cls._loss_screen.get('window'):
            cls._loss_screen['window'].hide()

    @classmethod
    def show_victory_screen(cls):
        """Display the game victory screen."""
        if not cls._initialized:
            return

        # --- Create/Rebuild Victory Screen Elements ---
        if hasattr(cls, '_victory_screen') and cls._victory_screen:
            if cls._victory_screen.get('window'):
                cls._victory_screen['window'].hide()  # Hide before deleting
                cls._victory_screen['window'].deleteLater()
                cls._victory_screen['window'] = None
            if cls._victory_screen.get('scene'):
                cls._victory_screen['scene'].clear()  # Clear items
                cls._victory_screen['scene'] = None
            if cls._victory_screen.get('view'):
                cls._victory_screen['view'].deleteLater()
                cls._victory_screen['view'] = None
            # Remove the text item attribute, as we'll be using an image.
            if '_text_item' in cls._victory_screen:
                del cls._victory_screen['_text_item']


        # Initialize _victory_screen as a dictionary HERE:
        if not hasattr(cls, '_victory_screen') or cls._victory_screen is None:
            cls._victory_screen = {}

        cls._victory_screen['window'] = QWidget(cls._window)  # Parent to main if needed
        cls._victory_screen['window'].setAttribute(Qt.WA_TranslucentBackground)
        cls._victory_screen['window'].setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowDoesNotAcceptFocus
        )
        cls._victory_screen['window'].setAttribute(Qt.WA_ShowWithoutActivating)

        cls._victory_screen['scene'] = QGraphicsScene()
        cls._victory_screen['view'] = QGraphicsView(cls._victory_screen['scene'], cls._victory_screen['window'])
        cls._victory_screen['view'].setStyleSheet("""
            QGraphicsView {
                background: transparent;  /* Or a victory-screen background */
                border: none;
            }
        """)
        cls._victory_screen['view'].setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._victory_screen['view'].setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cls._victory_screen['view'].setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        # --- Image Item Instead of Text Item ---
        cls._victory_screen['image_item'] = QGraphicsPixmapItem()
        cls._victory_screen['scene'].addItem(cls._victory_screen['image_item'])


        if cls._parent_hwnd:  # Set window attributes if parent exists
            style = win32gui.GetWindowLong(int(cls._victory_screen['window'].winId()), win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(
                int(cls._victory_screen['window'].winId()),
                win32con.GWL_EXSTYLE,
                style | win32con.WS_EX_NOACTIVATE
            )

        # --- Geometry and Positioning ---
        width = 1920
        height = 1080
        cls._victory_screen['window'].setGeometry(0, 0, width, height)  # Full screen
        cls._victory_screen['view'].setGeometry(0, 0, width, height)
        cls._victory_screen['scene'].setSceneRect(QRectF(0, 0, width, height))

        # --- Load and Set Image ---
        image_path = os.path.join("other_files", "victory.png")  # CHANGED FILENAME
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            # --- Scale the Pixmap ---
            scale_factor = 0.5
            scaled_pixmap = pixmap.scaled(
                int(pixmap.width() * scale_factor),
                int(pixmap.height() * scale_factor),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation  # Use SmoothTransformation for better quality
            )
            cls._victory_screen['image_item'].setPixmap(scaled_pixmap)

            # --- Positioning the Image ---
            cls._victory_screen['image_item'].setTransform(QTransform())
            cls._victory_screen['image_item'].setRotation(90)


            image_width = scaled_pixmap.width()  # Use scaled width and height
            image_height = scaled_pixmap.height() # Use scaled width and height
            cls._victory_screen['image_item'].setPos(
                (width + image_height) / 2,
                (height - image_width) / 2
            )

        else:
            print(f"[qt overlay] Victory image not found: {image_path}")
            #  Fallback to text display IF the image is missing.  Good practice.
            cls._victory_screen['text_item'] = QGraphicsTextItem()
            cls._victory_screen['text_item'].setDefaultTextColor(Qt.white)
            font = QFont('Arial', 48)
            cls._victory_screen['text_item'].setFont(font)
            cls._victory_screen['scene'].addItem(cls._victory_screen['text_item'])
            message = "Congratulations! You won!"  # CHANGED MESSAGE
            cls._victory_screen['text_item'].setHtml(
                f'<div style="background-color: rgba(0, 0, 0, 180); padding: 20px;">{message}</div>'
            )
            cls._victory_screen['text_item'].setTransform(QTransform())
            cls._victory_screen['text_item'].setRotation(90)
            text_width = cls._victory_screen['text_item'].boundingRect().width()
            text_height = cls._victory_screen['text_item'].boundingRect().height()
            cls._victory_screen['text_item'].setPos(
                (width + text_height) / 2,
                (height - text_width) / 2
            )


        cls._victory_screen['window'].show()
        cls._victory_screen['window'].raise_()

    @classmethod
    def hide_victory_screen(cls):
        """Hide the victory screen."""
        if hasattr(cls, '_victory_screen') and cls._victory_screen and cls._victory_screen.get('window'):
            cls._victory_screen['window'].hide()

    @classmethod
    def _check_game_loss_visibility(cls, game_lost):
        """Helper to control visibility based on game_lost flag."""
        if game_lost:
            # Game is lost, hide ALL other elements
            cls.hide_all_overlays()  # Existing method
            cls.show_loss_screen()

        else:
            # Game is NOT lost, proceed as before
            cls.hide_loss_screen()
            cls.show_all_overlays()

    @classmethod
    def _check_game_win_visibility(cls, game_won):
        if game_won:
            cls.hide_all_overlays()
            cls.show_victory_screen()
        else:
            cls.hide_victory_screen()
            cls.show_all_overlays()

    @classmethod
    def _actual_hint_text_update(cls, data):
        """Update the hint text in the main thread."""
        try:
            if not cls._hint_text['window']:
                print("[qt overlay]Error: Hint text window not initialized")
                return

            text = data.get('text', "")
            room_number = data.get('room_number')

            width = 588
            height = 951
            
            # Set hint window size and position
            cls._hint_text['window'].setGeometry(850, 80, width, height)
            cls._hint_text['view'].setGeometry(0, 0, width, height)
            cls._hint_text['scene'].setSceneRect(QRectF(0, 0, width, height))

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

            cls._hint_text['text_item'].setHtml(
                f'<div style="background-color: transparent; padding: 20px;text-align:center;width:{height-40}px">{text}</div>'
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
            #print(f"[qt overlay]Text position set to: {cls._hint_text['text_item'].pos()}")
            
            #print(f"[qt overlay]Text bounding rectangle set to: {cls._hint_text['text_item'].boundingRect()}")
            
            
            # ADDED CHECK: Only show if no video is playing.
            if not cls._kiosk_app.video_manager.is_playing:
                cls._hint_text['window'].show()
                cls._hint_text['window'].raise_()
        except Exception as e:
            print(f"[qt overlay]Error in _actual_hint_text_update: {e}")
            traceback.print_exc()
    
    @classmethod
    def hide_hint_text(cls):
        """Hide the hint text overlay (thread-safe)."""
        print("[qt overlay.hide_hint_text] Called")
        if hasattr(cls, '_hint_text') and cls._hint_text and cls._hint_text['window']:
            QMetaObject.invokeMethod(
                cls._hint_text['window'],
                "hide",
                Qt.QueuedConnection  # Use QueuedConnection for thread safety
            )
            print("[qt overlay.hide_hint_text] hide() invoked via QMetaObject")
        else:
            print("[qt overlay.hide_hint_text] _hint_text or window does not exist")
    
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
        """Hide the hint request text overlay"""
        if hasattr(cls, '_hint_request_text') and cls._hint_request_text and cls._hint_request_text['window']:
            cls._hint_request_text['window'].hide()

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
        """Initialize the timer display components"""
        if not cls._initialized:
            print("[qt overlay]Warning: Attempting to init_timer before base initialization")
            return
                
        if not hasattr(cls, '_timer'):
            print("[qt overlay]Initializing timer components...")
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
                
            # Set up background image first
            print("[qt overlay]Setting up background placeholder...")
            cls._timer.bg_image_item = cls._timer.scene.addPixmap(QPixmap())
            
            # Create timer text and add it after background
            print("[qt overlay]Setting up timer text...")
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

            if cls._parent_hwnd:
                style = win32gui.GetWindowLong(int(cls._timer_window.winId()), win32con.GWL_EXSTYLE)
                win32gui.SetWindowLong(
                    int(cls._timer_window.winId()),
                    win32con.GWL_EXSTYLE,
                    style | win32con.WS_EX_NOACTIVATE
                )
                
            print("[qt overlay]Timer initialization complete")

    @classmethod
    def update_timer_display(cls, time_str):
        """Update timer display, but NOT if game is lost."""
        if not hasattr(cls, '_timer') or not cls._timer.text_item:
            return
        if cls._kiosk_app.timer.game_lost:  # Don't update if game is lost
            return
        if cls._kiosk_app.timer.game_won: # Don't update if game is won.
            return
            
        # Initialize timer thread if needed
        if cls._timer_thread is None:
            cls._timer_thread = TimerThread()
            cls._timer_thread.update_signal.connect(cls._actual_timer_update)
            cls._timer_thread.start()
        
        # Send update through thread
        cls._timer_thread.update_display(time_str)

    @classmethod
    def _actual_timer_update(cls, time_str):
        """Actual update method that runs in the main thread"""
        if hasattr(cls, '_timer') and cls._timer.text_item:
            cls._timer.text_item.setHtml(f'<div>{time_str}</div>')
            cls._timer.text_item.setPos(350, 145)
            if cls._timer_window:
                cls._timer_window.show()
                cls._timer_window.raise_()

    @classmethod
    def load_timer_background(cls, room_number):
        """Load the timer background for the specified room"""
        print(f"[qt overlay]Attempting to load timer background for room {room_number}")

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

            # Clear Previous
            if cls._timer.bg_image_item:
                cls._timer.bg_image_item.setPixmap(QPixmap())
            
            # Update the background
            print("[qt overlay]Setting background pixmap...")
            cls._timer.bg_image_item.setPixmap(pixmap)
            cls._timer._current_image = pixmap  # Store reference
            cls._timer_window.update()  # Force refresh
            print("[qt overlay]Background loaded successfully")

        except Exception as e:
            print(f"[qt overlay]Error loading timer background for room {room_number}:")
            traceback.print_exc()

    @classmethod
    def init_help_button(cls):
        if not cls._initialized:
            print("[qt overlay]Warning: Attempting to init_help_button before base initialization")
            return

        if not hasattr(cls, '_button'):
            print("[qt overlay]Initializing help button components...")
            cls._button = {}

            # Create a separate window for the button
            cls._button_window = QWidget(cls._window)
            cls._button_window.setAttribute(Qt.WA_TranslucentBackground)
            cls._button_window.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool |
                Qt.WindowDoesNotAcceptFocus
            )
            cls._button_window.setAttribute(Qt.WA_ShowWithoutActivating)

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

            # Debug prints
            #print(f"[qt overlay]View Setup Debug:")
            #print(f"[qt overlay]View geometry: {cls._button_view.geometry()}")
            #print(f"[qt overlay]Scene rect: {scene_rect}")
            #print(f"[qt overlay]View matrix: {cls._button_view.transform()}")

            # Set up placeholders for images
            cls._button['shadow_item'] = cls._button['scene'].addPixmap(QPixmap())
            cls._button['bg_image_item'] = cls._button['scene'].addPixmap(QPixmap())

            # Position button window
            cls._button_window.setGeometry(340, 290, width, height) # Adjusted button window size

            if cls._parent_hwnd:
                style = win32gui.GetWindowLong(int(cls._button_window.winId()), win32con.GWL_EXSTYLE)
                win32gui.SetWindowLong(
                    int(cls._button_window.winId()),
                    win32con.GWL_EXSTYLE,
                    style | win32con.WS_EX_NOACTIVATE
                )

            print("[qt overlay]Help button initialization complete")

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
            #print(f"[qt overlay]Image Debug:")
            #print(f"[qt overlay]Button image format: {qimage.format()}")
            #print(f"[qt overlay]Button image size: {qimage.size()}")
            #print(f"[qt overlay]Button pixmap size: {button_pixmap.size()}")
            #print(f"[qt overlay]Shadow pixmap size: {shadow_pixmap.size()}")

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
        """Actual help button update method that runs in the main thread"""
        ui = button_data['ui']
        timer = button_data['timer']
        hints_requested = button_data['hints_requested']
        time_exceeded_45 = button_data['time_exceeded_45']
        assigned_room = button_data['assigned_room']
        current_minutes = timer.time_remaining / 60

        # Check visibility conditions - NOW includes game_lost
        show_button = (
            not ui.hint_cooldown and
            not (current_minutes > 42 and current_minutes <= 45 and not time_exceeded_45) and
            not timer.game_lost  and # Don't show if game is lost
            not timer.game_won # Don't show if game is wo
        )

        #print(f"[qt overlay]Help Button Visibility Check - Time: {current_minutes:.2f}, Cooldown: {ui.hint_cooldown}, Exceeded 45: {time_exceeded_45}")

        try:
            if not cls._kiosk_app.video_manager.is_playing and not cls._kiosk_app.ui.image_is_fullscreen and show_button:
                # Rebuild the button window to make sure everything is clean
                if hasattr(cls, '_button_window') and cls._button_window:
                   cls._button_window.hide()
                   cls._button_window.deleteLater()
                   cls._button_window = None

                # Create a separate window for the button
                cls._button_window = QWidget(cls._window)
                cls._button_window.setAttribute(Qt.WA_TranslucentBackground)
                cls._button_window.setWindowFlags(
                    Qt.FramelessWindowHint |
                    Qt.WindowStaysOnTopHint |
                    Qt.Tool |
                    Qt.WindowDoesNotAcceptFocus
                )
                cls._button_window.setAttribute(Qt.WA_ShowWithoutActivating)

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

                # Debug prints
                #print(f"[qt overlay]View Setup Debug:")
                #print(f"[qt overlay]View geometry: {cls._button_view.geometry()}")
                #print(f"[qt overlay]Scene rect: {scene_rect}")
                #print(f"[qt overlay]View matrix: {cls._button_view.transform()}")

                # Set up placeholders for images
                cls._button['shadow_item'] = cls._button['scene'].addPixmap(QPixmap())
                cls._button['bg_image_item'] = cls._button['scene'].addPixmap(QPixmap())

                # Position button window
                cls._button_window.setGeometry(340, 290, width, height) # Adjusted button window size

                if cls._parent_hwnd:
                    style = win32gui.GetWindowLong(int(cls._button_window.winId()), win32con.GWL_EXSTYLE)
                    win32gui.SetWindowLong(
                        int(cls._button_window.winId()),
                        win32con.GWL_EXSTYLE,
                        style | win32con.WS_EX_NOACTIVATE
                    )

                # Load images
                if not cls.load_button_images(assigned_room):
                    print("[qt overlay]Failed to load button images.")
                    return

                # Set the origin for rotation to the center of the pixmap
                button_rect = cls._button['bg_image_item'].boundingRect()
                cls._button['bg_image_item'].setTransformOriginPoint(button_rect.width() / 2, button_rect.height() / 2)

                # Make the button view "skippable" (which means clickable in this context)
                cls._button_view.set_skippable(True)

                # Set up click handling using Qt signals/slots
                try:
                    # Disconnect any previous connections first to avoid duplicates
                    cls._button_view.clicked.disconnect()
                except TypeError:
                    # No connections existed, which is fine
                    pass
                except Exception as e:
                    # Catch potential errors during disconnection
                    print(f"[qt overlay] Error disconnecting previous button click signal: {e}")

                # Connect the request_help function to the clicked signal
                cls._button_view.clicked.connect(ui.message_handler.request_help)
                print("[qt overlay] Connected help button click signal.")

                # Rotate the button image item 90 degrees clockwise
                cls._button['bg_image_item'].setRotation(360)

                # MANUAL POSITIONING BEGINS HERE
                # Define offsets for position
                button_x_offset = -40 # Adjust to move the button within it's parent window
                button_y_offset = -73 # Adjust to move the button within it's parent window

                shadow_x_offset = 0  # Adjust to move the shadow within it's parent window
                shadow_y_offset = 0 # Adjust to move the shadow within it's parent window

                cls._button['bg_image_item'].setPos(button_x_offset, button_y_offset)
                cls._button['shadow_item'].setPos(shadow_x_offset, shadow_y_offset)

                # RE-APPLY PARENTING RIGHT BEFORE SHOWING
                if cls._parent_hwnd:
                    win32gui.SetParent(int(cls._button_window.winId()), cls._parent_hwnd)

                # Show
                cls._button_window.show()
                cls._button_window.raise_()
                cls._button_view.viewport().update()
            else:
                if hasattr(cls, '_button_window') and cls._button_window and cls._button_window.isVisible():
                    cls._button_window.hide()
                    print("[qt overlay]Help button hidden")

            # Only show hint text if it's not empty ---
            if ui.current_hint:  # First, check for the existence of current_hint
                hint_text = ui.current_hint if isinstance(ui.current_hint, str) else ui.current_hint.get('text', '')
                if hint_text is not None and hint_text.strip() != "":
                    print("[qt_overlay] Restoring hint text from within _actual_help_button_update")
                    cls.show_hint_text(hint_text, assigned_room)  # Show if not empty
                else:
                    print("[qt_overlay] Hint text is empty, not restoring from within _actual_help_button_update")
            else:
                print("[qt overlay]current hint is None, hiding hint text window from update_help_button.")
                Overlay.hide_hint_text()
        except Exception as e:
           print(f"[qt overlay]Exception during help button update: {e}")
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

            # print("[qt overlay] Non-video overlay UI elements hidden.") # Reduce noise
        except Exception as e:
            print(f"[qt overlay] Error hiding non-video overlays: {e}")
            traceback.print_exc()

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


        if game_lost:
            # print("[qt overlay] Game lost, showing loss screen only.") # Reduce noise
            cls.show_loss_screen()
            return

        if game_won:
            # print("[qt overlay] Game won, showing victory screen only.") # Reduce noise
            cls.show_victory_screen()
            return

        # --- RESTORE OTHER OVERLAYS (if game not won/lost) ---
        try:
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
                    ui_instance.parent_app.root.after(10, ui_instance.parent_app._actual_help_button_update) # Use parent_app reference

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
            # Uses the main overlay window (cls._window)
            if hasattr(cls, '_window') and cls._window:
                 should_show_cooldown = False
                 if ui_instance:
                     # Check the actual cooldown state *AND* if the cooldown text item has content
                     if ui_instance.hint_cooldown and hasattr(cls, '_text_item') and cls._text_item.toPlainText().strip():
                         should_show_cooldown = True

                 if should_show_cooldown:
                     # Show if not already visible
                     if not cls._window.isVisible(): cls._window.show()
                     cls._window.raise_() # Ensure it's on top
                 else:
                     # Explicitly hide if cooldown shouldn't be shown
                     if cls._window.isVisible():
                         # print("[qt overlay show_all] Hiding cooldown overlay.") # Debug
                         cls._window.hide()


            # --- Restore GM Assistance ---
            # GM Assistance (only if it was previously visible and window available)
            if hasattr(cls, '_gm_assistance_overlay') and cls._gm_assistance_overlay and cls._gm_assistance_overlay.get('window'):
                gm_window = cls._gm_assistance_overlay['window']
                # Use get method with default False to avoid KeyError if _was_visible doesn't exist yet
                was_visible_flag = cls._gm_assistance_overlay.get('_was_visible', False)
                if was_visible_flag:
                    # Show if not already visible
                    if not gm_window.isVisible(): gm_window.show()
                    gm_window.raise_() # Ensure it's on top
                    # Reset flag after showing it once
                    cls._gm_assistance_overlay['_was_visible'] = False
                else:
                    # Ensure it's hidden if it wasn't flagged as visible
                    if gm_window.isVisible():
                        gm_window.hide()


            # print("[qt overlay] Non-video overlay UI elements restored.") # Reduce noise
        except Exception as e:
            print(f"[qt overlay] Error showing non-video overlays: {e}")
            traceback.print_exc()

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
        if cls._gm_assistance_overlay and cls._gm_assistance_overlay['window']:
            cls._gm_assistance_overlay['window'].hide()
            # DO NOT reset _was_visible here.  We want to remember it was shown.