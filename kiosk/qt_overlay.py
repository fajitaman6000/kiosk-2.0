# qt_overlay.py
from PyQt5.QtCore import Qt, QRectF, QThread, pyqtSignal, QMetaObject, Q_ARG, Qt, QPointF
from PyQt5.QtGui import QTransform, QFont, QPainter, QPixmap, QImage
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QGraphicsScene, QGraphicsView, QGraphicsTextItem
from PIL import Image
import sys
import win32gui
import win32con
import os
import io
import traceback
from config import ROOM_CONFIG

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

class Overlay:
    _app = None
    _window = None
    _parent_hwnd = None
    _initialized = False
    _timer_thread = None
    
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
        cls.init_help_button() # Moved to the init function
    
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
        """Initialize help button components"""
        if not cls._initialized:
            print("Warning: Attempting to init_help_button before base initialization")
            return
            
        if not hasattr(cls, '_button'):
            print("\nInitializing help button components...")
            cls._button = {}
            
            # Create a separate window for the button
            cls._button_window = QWidget(cls._window)  # Child of main window
            cls._button_window.setAttribute(Qt.WA_TranslucentBackground)
            cls._button_window.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool |
                Qt.WindowDoesNotAcceptFocus
            )
            cls._button_window.setAttribute(Qt.WA_ShowWithoutActivating)
            
            # Set up button scene and view
            cls._button['scene'] = QGraphicsScene()
            cls._button_view = QGraphicsView(cls._button['scene'], cls._button_window)
            cls._button_view.setStyleSheet("""
                QGraphicsView {
                    background: transparent;
                    border: none;
                }
            """)
            cls._button_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._button_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            cls._button_view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
            
            # Set up shadow image
            print("Setting up shadow placeholder...")
            cls._button['shadow_item'] = cls._button['scene'].addPixmap(QPixmap())
            
            # Set up button image
            print("Setting up button image placeholder...")
            cls._button['bg_image_item'] = cls._button['scene'].addPixmap(QPixmap())
            
            # Set up button window dimensions and position
            width = 260
            height = 550
            cls._button_view.setGeometry(0, 0, width, height)
            cls._button['scene'].setSceneRect(QRectF(0, 0, width, height))
            
            # Position button window
            cls._button_window.setGeometry(
                340,
                290,
                width,
                height
            )

            # Initially hide the button window
            cls._button_window.hide()
            
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
        print(f"\nEntering load_button_images for room {room_number}")

        if not hasattr(cls, '_button'):
            print("Button not initialized yet")
            return

        try:
            # --- Shadow Image ---
            shadow_path = os.path.join("hint_button_backgrounds", "shadow.png")
            print(f"Looking for shadow at: {shadow_path}")

            if not os.path.exists(shadow_path):
                print(f"Error: Shadow image not found at: {shadow_path}")
                return  # Stop if shadow not found

            try:
                shadow_img = Image.open(shadow_path)
                print("Shadow image opened successfully")
            except Exception as e:
                print(f"Error opening shadow image: {e}")
                return

            try:
                shadow_img = shadow_img.resize((260 + 40, 550 + 40))
                print("Shadow image resized successfully")
            except Exception as e:
                print(f"Error resizing shadow image: {e}")
                return

            try:
                print("Converting shadow to QPixmap...")
                qimage = QImage.fromData(shadow_img.tobytes(), shadow_img.size[0], shadow_img.size[1], QImage.Format_RGBA8888)
                if qimage.isNull():
                    print("Error: QImage is null after conversion")
                    return
                shadow_pixmap = QPixmap.fromImage(qimage)
                if shadow_pixmap.isNull():
                    print("Error: QPixmap is null after conversion")
                    return
                print("Shadow to QPixmap conversion successful")
            except Exception as e:
                print(f"Error converting shadow to QPixmap: {e}")
                return
                
            try:
                print("Setting shadow pixmap...")
                cls._button['shadow_item'].setPixmap(shadow_pixmap)
                cls._button['shadow_item'].setPos(-20, -20)
                print("Shadow pixmap set successfully")
            except Exception as e:
                print(f"Error setting shadow pixmap: {e}")
                return

            # --- Button Image ---
            button_filename = ROOM_CONFIG['buttons'].get(room_number)
            if button_filename is None:
                print(f"No button image defined for room {room_number}")
                return

            button_path = os.path.join("hint_button_backgrounds", button_filename)
            print(f"Looking for button image at: {button_path}")

            if not os.path.exists(button_path):
                print(f"Error: Button image not found at: {button_path}")
                return

            try:
                button_img = Image.open(button_path)
                print("Button image opened successfully")
            except Exception as e:
                print(f"Error opening button image: {e}")
                return

            try:
                button_img = button_img.resize((260, 550))
                print("Button image resized successfully")
            except Exception as e:
                print(f"Error resizing button image: {e}")
                return

            try:
                print("Converting button to QPixmap...")
                qimage = QImage.fromData(button_img.tobytes(), button_img.size[0], button_img.size[1], QImage.Format_RGBA8888)
                if qimage.isNull():
                    print("Error: QImage is null after conversion")
                    return
                button_pixmap = QPixmap.fromImage(qimage)
                if button_pixmap.isNull():
                    print("Error: QPixmap is null after conversion")
                    return
                print("Button to QPixmap conversion successful")
            except Exception as e:
                print(f"Error converting button to QPixmap: {e}")
                return

            try:
                print("Setting button pixmap...")
                cls._button['bg_image_item'].setPixmap(button_pixmap)
                cls._button_window.update()
                print("Button pixmap set successfully")
            except Exception as e:
                print(f"Error setting button pixmap: {e}")
                return
            
            print("Button images loaded successfully")

        except Exception as e:
            print(f"General error loading button images for room {room_number}:")
            traceback.print_exc()

    @classmethod
    def update_help_button(cls, ui, timer, hints_requested, time_exceeded_45, assigned_room):
        """Create or update the help button based on current state"""
        if not hasattr(cls, '_button_window') or not cls._button_window:
            cls.init_help_button()
        
        current_minutes = timer.time_remaining / 60

        # Check visibility conditions (modified to remove timer.is_running)
        show_button = (
            not ui.hint_cooldown and
            not (current_minutes > 42 and current_minutes <= 45 and not time_exceeded_45)
        )
        
        print(f"\nHelp Button Visibility Check - Time: {current_minutes:.2f}, Cooldown: {ui.hint_cooldown}, Exceeded 45: {time_exceeded_45}")

        if show_button:
            print("Conditions met to show help button")
            if not cls._button_window.isVisible():
                # Load images if not already loaded
                if not cls._button.get('bg_image_item', None) or not cls._button['bg_image_item'].pixmap().isNull():
                    print(f"Calling load_button_images with room: {assigned_room}")
                    cls.load_button_images(assigned_room)
                    
                # Rotate button and shadow
                cls._button['bg_image_item'].setTransform(QTransform().rotate(270), True)
                cls._button['shadow_item'].setTransform(QTransform().rotate(270), True)
                
                # Adjust item positions after rotation
                button_rect = cls._button['bg_image_item'].boundingRect()
                shadow_rect = cls._button['shadow_item'].boundingRect()
                
                # --- Debug Prints ---
                print(f"Button image loaded: {not cls._button['bg_image_item'].pixmap().isNull()}")
                print(f"Shadow image loaded: {not cls._button['shadow_item'].pixmap().isNull()}")
                print(f"Button rect: {button_rect.x()}, {button_rect.y()}, {button_rect.width()}, {button_rect.height()}")
                print(f"Shadow rect: {shadow_rect.x()}, {shadow_rect.y()}, {shadow_rect.width()}, {shadow_rect.height()}")
                # --- End Debug Prints ---
                
                cls._button['bg_image_item'].setPos(
                    (cls._button['scene'].width() + button_rect.width()) / 2,
                    (cls._button['scene'].height() - button_rect.height()) / 2
                )
                cls._button['shadow_item'].setPos(
                    (cls._button['scene'].width() + shadow_rect.width()) / 2 - 20,
                    (cls._button['scene'].height() - shadow_rect.height()) / 2 - 20
                )

                # --- More Debug Prints ---
                print(f"Button item pos after rotation: {cls._button['bg_image_item'].pos()}")
                print(f"Shadow item pos after rotation: {cls._button['shadow_item'].pos()}")
                # --- End Debug Prints ---
                
                cls._button_window.show()
                cls._button_window.raise_()
                print("Help button shown")
            else:
                print("Help button already visible")
                
            # Add click event to the scene
            def handle_click(event):
                print("Click event triggered") # Added debug print
                if cls._button['bg_image_item'].isUnderMouse():
                    print("Click is on the button image") # Added debug print
                    ui.request_help()

            cls._button['scene'].mousePressEvent = handle_click
        else:
            print("Conditions not met to show help button")
            if cls._button_window.isVisible():
                cls._button_window.hide()
                print("Help button hidden")

    @classmethod
    def hide_help_button(cls):
        """Hide the help button"""
        if hasattr(cls, '_button_window') and cls._button_window:
            cls._button_window.hide()

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
            
        # Clear timer display
        if hasattr(cls, '_timer') and cls._timer and cls._timer.text_item:
            cls._timer.text_item.setPlainText("")
            if cls._timer.bg_image_item:
                cls._timer.bg_image_item.setPixmap(QPixmap())