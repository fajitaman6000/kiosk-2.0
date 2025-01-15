# qt_overlay.py
from PyQt5.QtCore import Qt, QRectF, QThread, pyqtSignal, QMetaObject, Q_ARG, Qt, QPointF
from PyQt5.QtGui import QTransform, QFont, QPainter, QPixmap, QImage, QPen, QBrush
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QGraphicsScene, QGraphicsView, QGraphicsTextItem, QGraphicsPixmapItem
from PIL import Image
import sys
import win32gui
import win32con
import os
import io
import traceback
from config import ROOM_CONFIG

class ClickableView(QGraphicsView):
    """Custom QGraphicsView that handles mouse clicks"""
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self._click_callback = None
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._click_callback:
            # Get the scene position
            scene_pos = self.mapToScene(event.pos())
            # Check if click is within button bounds
            items = self.scene().items(scene_pos)
            for item in items:
                if isinstance(item, QGraphicsPixmapItem):
                    self._click_callback()
                    break
        super().mousePressEvent(event)
        
    def set_click_callback(self, callback):
        self._click_callback = callback

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

class Overlay:
    _app = None
    _window = None
    _parent_hwnd = None
    _initialized = False
    _timer_thread = None
    _button_thread = None
    
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
        cls.init_timer()
        cls.init_help_button()
    
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
            print("Warning: Attempting to init_timer before base initialization")
            return
                
        if not hasattr(cls, '_timer'):
            print("\nInitializing timer components...")
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
            print("Setting up background placeholder...")
            cls._timer.bg_image_item = cls._timer.scene.addPixmap(QPixmap())
            
            # Create timer text and add it after background
            print("Setting up timer text...")
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
                1300,
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
                
            print("Timer initialization complete")

    @classmethod
    def update_timer_display(cls, time_str):
        """Update the timer display with the given time string"""
        if not hasattr(cls, '_timer') or not cls._timer.text_item:
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
        print(f"\nAttempting to load timer background for room {room_number}")

        if not hasattr(cls, '_timer'):
            print("Timer not initialized yet")
            return

        try:
            bg_filename = cls._timer.timer_backgrounds.get(room_number)
            if not bg_filename:
                print(f"No timer background defined for room {room_number}")
                return

            bg_path = os.path.join("timer_backgrounds", bg_filename)
            print(f"Looking for background at: {bg_path}")

            if not os.path.exists(bg_path):
                print(f"Timer background not found: {bg_path}")
                return

            # Load and resize the background image
            print("Loading background image...")
            bg_img = Image.open(bg_path)
            bg_img = bg_img.resize((500,750))

            # Convert to QPixmap
            print("Converting to QPixmap...")
            buf = io.BytesIO()
            bg_img.save(buf, format='PNG')
            qimg = QImage()
            qimg.loadFromData(buf.getvalue())
            pixmap = QPixmap.fromImage(qimg)

            # Clear Previous
            if cls._timer.bg_image_item:
                cls._timer.bg_image_item.setPixmap(QPixmap())
            
            # Update the background
            print("Setting background pixmap...")
            cls._timer.bg_image_item.setPixmap(pixmap)
            cls._timer._current_image = pixmap  # Store reference
            cls._timer_window.update()  # Force refresh
            print("Background loaded successfully")

        except Exception as e:
            print(f"Error loading timer background for room {room_number}:")
            traceback.print_exc()

    @classmethod
    def init_help_button(cls):
        if not cls._initialized:
            print("Warning: Attempting to init_help_button before base initialization")
            return

        if not hasattr(cls, '_button'):
            print("\nInitializing help button components...")
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
            cls._button_view = ClickableView(cls._button['scene'], cls._button_window)

            # Define view dimensions (increased to accommodate shadow)
            width = 330  # Increased width
            height = 620  # Increased height

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
            print(f"\nView Setup Debug:")
            print(f"View geometry: {cls._button_view.geometry()}")
            print(f"Scene rect: {scene_rect}")
            print(f"View matrix: {cls._button_view.transform()}")

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

            print("Help button initialization complete")

    @classmethod
    def load_button_images(cls, room_number):
        """Load the button and shadow images for the specified room"""
        try:
            # Load button image
            button_filename = ROOM_CONFIG['buttons'].get(room_number)
            button_path = os.path.join("hint_button_backgrounds", button_filename)

            if not os.path.exists(button_path):
                print(f"Error: Button image not found at: {button_path}")
                return False

            # Use QImage to load directly
            qimage = QImage(button_path)
            if qimage.isNull():
                print("Failed to load button image directly")
                return False

            # Convert to pixmap and scale
            button_pixmap = QPixmap.fromImage(qimage).scaled(
                240, 530, Qt.KeepAspectRatio, Qt.SmoothTransformation  # Keep adjusted scaling for button
            )
            cls._button['bg_image_item'].setPixmap(button_pixmap)

            # Load shadow image
            shadow_path = os.path.join("hint_button_backgrounds", "shadow.png")
            shadow_qimage = QImage(shadow_path)
            if shadow_qimage.isNull():
                print("Failed to load shadow image directly")
                return False

            # Convert to pixmap and scale (larger scaling for shadow)
            shadow_pixmap = QPixmap.fromImage(shadow_qimage).scaled(
                330, 620, Qt.KeepAspectRatio, Qt.SmoothTransformation  # Increased shadow size
            )
            cls._button['shadow_item'].setPixmap(shadow_pixmap)

            # Set the origin for rotation to the center of the pixmap
            cls._button['bg_image_item'].setTransformOriginPoint(button_pixmap.width() / 2, button_pixmap.height() / 2)

            # Debug info
            print(f"\nImage Debug:")
            print(f"Button image format: {qimage.format()}")
            print(f"Button image size: {qimage.size()}")
            print(f"Button pixmap size: {button_pixmap.size()}")
            print(f"Shadow pixmap size: {shadow_pixmap.size()}")

            return True

        except Exception as e:
            print(f"Error loading images: {e}")
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

        # Check visibility conditions
        show_button = (
            not ui.hint_cooldown and
            not (current_minutes > 42 and current_minutes <= 45 and not time_exceeded_45)
        )

        print(f"\nHelp Button Visibility Check - Time: {current_minutes:.2f}, Cooldown: {ui.hint_cooldown}, Exceeded 45: {time_exceeded_45}")

        if show_button:
            if not cls._button_window.isVisible():
                # Load images if needed
                if not cls._button.get('bg_image_item', None) or cls._button['bg_image_item'].pixmap().isNull():
                    if not cls.load_button_images(assigned_room):
                        print("Failed to load button images.")
                        return
                
                # Set the origin for rotation to the center of the pixmap
                button_rect = cls._button['bg_image_item'].boundingRect()
                cls._button['bg_image_item'].setTransformOriginPoint(button_rect.width() / 2, button_rect.height() / 2)

                # Set up click handling
                cls._button_view.set_click_callback(ui.message_handler.request_help)

                # Rotate the button image item 90 degrees clockwise
                cls._button['bg_image_item'].setRotation(360)

                # Get scene and view dimensions
                scene_rect = cls._button['scene'].sceneRect()

                # Center the button within the scene
                button_x = (scene_rect.width() - button_rect.width()) / 2
                button_y = (scene_rect.height() - button_rect.height()) / 2
                cls._button['bg_image_item'].setPos(button_x, button_y)

                # Center the shadow within the scene
                shadow_x = (scene_rect.width() - cls._button['shadow_item'].boundingRect().width()) / 2
                shadow_y = (scene_rect.height() - cls._button['shadow_item'].boundingRect().height()) / 2
                cls._button['shadow_item'].setPos(shadow_x, shadow_y)

                # Debug prints
                print("\nButton Positioning Debug:")
                print(f"Button pos: {cls._button['bg_image_item'].pos()}")
                print(f"Button scene pos: {cls._button['bg_image_item'].scenePos()}")
                print(f"Button bounding rect: {cls._button['bg_image_item'].boundingRect()}")
                print(f"Button scene bounding rect: {cls._button['bg_image_item'].sceneBoundingRect()}")

                # Force updates
                cls._button_window.show()
                cls._button_window.raise_()
                cls._button_view.viewport().update()
        else:
            if cls._button_window.isVisible():
                cls._button_window.hide()
                print("Help button hidden")

    @classmethod
    def hide_help_button(cls):
        """Hide the help button"""
        if hasattr(cls, '_button_window') and cls._button_window:
            cls._button_window.hide()

    @classmethod
    def hide_cooldown(cls):
        """Hide just the cooldown overlay"""
        if cls._window:
            cls._window.hide()

    @classmethod
    def hide(cls):
        """Hide all overlay windows and clean up timer resources"""
        if cls._window:
            cls._window.hide()
        if hasattr(cls, '_timer_window') and cls._timer_window:
            cls._timer_window.hide()
        if hasattr(cls, '_button_window') and cls._button_window:
            cls._button_window.hide()

        # Clean up timer thread if it exists
        if cls._timer_thread is not None:
            cls._timer_thread.quit()
            cls._timer_thread.wait()
            cls._timer_thread = None

        # Clear timer display and associated items
        if hasattr(cls, '_timer') and cls._timer:
            if cls._timer.text_item:
                cls._timer.text_item.setPlainText("")
            if cls._timer.bg_image_item:
                cls._timer.bg_image_item.setPixmap(QPixmap()) # Clear the pixmap
            if hasattr(cls, '_timer_scene') and cls._timer.scene:
                cls._timer.scene.clear() # Clear the scene of existing items
        
        # Clear button view if it exists
        if hasattr(cls, '_button_view') and cls._button_view:
            cls._button['scene'].clear()
            cls._button_view.set_click_callback(None) # Deregister callback