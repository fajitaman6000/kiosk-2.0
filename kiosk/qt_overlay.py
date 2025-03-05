# qt_overlay.py
from PyQt5.QtCore import Qt, QRectF, QThread, pyqtSignal, QMetaObject, Q_ARG, Qt, QPointF
from PyQt5.QtGui import QTransform, QFont, QPainter, QPixmap, QImage, QPen, QBrush, QColor
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QGraphicsScene, QGraphicsView, QGraphicsTextItem, QGraphicsPixmapItem, QGraphicsRectItem
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

    @classmethod
    def init(cls, tkinter_root=None):
        """Initialize Qt application and base window"""
        if not cls._app:
            cls._app = QApplication(sys.argv)
            
        # Store Tkinter window handle and kiosk_app reference first
        if tkinter_root:
            cls._parent_hwnd = tkinter_root.winfo_id()
            # Store kiosk app reference
            if hasattr(tkinter_root, 'kiosk_app'):
                print("[qt overlay] Found kiosk_app on tkinter_root")
                # Store as class variable
                cls.kiosk_app = tkinter_root.kiosk_app
                print(f"[qt overlay] Stored kiosk_app with computer_name: {cls.kiosk_app.computer_name}")
            else:
                print("[qt overlay] Warning: tkinter_root does not have kiosk_app attribute")
                cls.kiosk_app = None
                print("[qt overlay] Set kiosk_app to None")
        else:
            print("[qt overlay] Warning: No tkinter_root provided")
            cls.kiosk_app = None
            cls._parent_hwnd = None
            
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
        
        # Initialize all overlays after kiosk_app is stored
        cls._init_hint_text_overlay()
        cls._init_hint_request_text_overlay()
        cls._init_gm_assistance_overlay()
        
        # Initialize timer and help button
        cls.init_timer()
        cls.init_help_button()

        # Hide GM assistance overlay
        cls.hide_gm_assistance()
        

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
        if hasattr(cls, 'kiosk_app') and cls.kiosk_app is not None:
            print(f"[qt overlay] Using kiosk_app with computer_name: {cls.kiosk_app.computer_name}")
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
                            if hasattr(cls, 'kiosk_app') and cls.kiosk_app is not None:
                                print(f"[qt overlay] Found kiosk_app with computer_name: {cls.kiosk_app.computer_name}")
                                try:
                                    cls.kiosk_app.network.send_message({
                                        'type': 'gm_assistance_accepted',
                                        'computer_name': cls.kiosk_app.computer_name
                                    })
                                    print("[qt overlay] Message sent successfully")
                                except Exception as e:
                                    print(f"[qt overlay] Error sending message: {e}")
                                    traceback.print_exc()
                            else:
                                print("[qt overlay] Error: kiosk_app not found or is None")
                                print(f"[qt overlay] Has kiosk_app attribute: {hasattr(cls, 'kiosk_app')}")
                                if hasattr(cls, 'kiosk_app'):
                                    print(f"[qt overlay] kiosk_app value: {cls.kiosk_app}")
                            # Hide the overlay after accepting
                            cls.hide_gm_assistance()
                            break
                        elif item == cls._gm_assistance_overlay['no_rect'] or item == cls._gm_assistance_overlay['no_button']:
                            print("[qt overlay] No button clicked - GM assistance declined")
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
            if not cls.kiosk_app.video_manager.is_playing:
                cls._hint_text['window'].show()
                cls._hint_text['window'].raise_()
        except Exception as e:
            print(f"[qt overlay]Error in _actual_hint_text_update: {e}")
            traceback.print_exc()
    
    @classmethod
    def hide_hint_text(cls):
        """Hide the hint text overlay"""
        if hasattr(cls, '_hint_text') and cls._hint_text and cls._hint_text['window']:
            cls._hint_text['window'].hide()
    
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
            print("[qt overlay]\nInitializing timer components...")
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
        if cls.kiosk_app.timer.game_lost:  # Don't update if game is lost
            return
        if cls.kiosk_app.timer.game_won: # Don't update if game is won.
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
        print(f"[qt overlay]\nAttempting to load timer background for room {room_number}")

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
            print("[qt overlay]\nInitializing help button components...")
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
            #print(f"[qt overlay]\nView Setup Debug:")
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
            #print(f"[qt overlay]\nImage Debug:")
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

        #print(f"[qt overlay]\nHelp Button Visibility Check - Time: {current_minutes:.2f}, Cooldown: {ui.hint_cooldown}, Exceeded 45: {time_exceeded_45}")

        try:
            if not cls.kiosk_app.video_manager.is_playing and show_button:
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
                cls._button_view = ClickableView(cls._button['scene'], cls._button_window)

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
                #print(f"[qt overlay]\nView Setup Debug:")
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

                # Set up click handling
                cls._button_view.set_click_callback(ui.message_handler.request_help)

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
        if hasattr(cls, '_hint_text') and cls._hint_text and cls._hint_text['window']:
            cls._hint_text['window'].hide()
            cls._hint_text['text_item'].setPlainText("")  # Or setHtml("")
        # Clear hint request overlay
        if hasattr(cls, '_hint_request_text') and cls._hint_request_text:
            if cls._hint_request_text['window']:
                cls._hint_request_text['window'].hide()

            if cls._hint_request_text['scene']:
                cls._hint_request_text['scene'].clear()

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

    @classmethod
    def hide_all_overlays(cls):
        """Hide all Qt overlay UI elements temporarily"""
        print("[qt overlay]Hiding all overlay UI elements for video")
        try:
            if hasattr(cls, '_timer_window') and cls._timer_window:
                print("[qt overlay]Hiding timer window")
                cls._timer_window.hide()
            if hasattr(cls, '_button_window') and cls._button_window:
                print("[qt overlay]Hiding button window")
                cls._button_window.hide()
            if hasattr(cls, '_hint_text') and cls._hint_text and cls._hint_text['window']:
                print("[qt overlay]Hiding hint text window")
                cls._hint_text['window'].hide()
            if hasattr(cls, '_hint_request_text') and cls._hint_request_text and cls._hint_request_text['window']:
                print("[qt overlay]Hiding hint request text window")
                cls._hint_request_text['window'].hide()
            if hasattr(cls, '_gm_assistance_overlay') and cls._gm_assistance_overlay and cls._gm_assistance_overlay['window']:
                print("[qt overlay]Hiding GM assistance window")
                # Store visibility BEFORE hiding
                cls._gm_assistance_overlay['_was_visible'] = cls._gm_assistance_overlay['window'].isVisible()
                cls._gm_assistance_overlay['window'].hide()
            if cls._window:
                print("[qt overlay]Hiding main window")
                cls._window.hide()
            cls.hide_victory_screen() # Hide victory screen too
            print("[qt overlay]All overlay UI elements hidden")
        except Exception as e:
            print(f"[qt overlay]Error hiding overlays: {e}")
            traceback.print_exc()

    @classmethod
    def show_all_overlays(cls):
        """Restore visibility of all Qt overlay UI elements"""
        print("[qt overlay]Restoring all overlay UI elements")

        if cls.kiosk_app.timer.game_lost:
            # Game is lost, ONLY show the loss screen, nothing else
            cls.show_loss_screen()
            return  # IMPORTANT: Exit early
        if cls.kiosk_app.timer.game_won:
            cls.show_victory_screen()
            return

        try:
            if hasattr(cls, '_timer_window') and cls._timer_window:
                print("[qt overlay]Showing timer window")
                # Check if the timer display needs to be updated before showing
                if hasattr(cls, '_timer') and cls._timer.text_item:
                    current_time_str = cls._timer.text_item.toPlainText()
                    if current_time_str:  # Only show if there's a time to display
                        cls._timer_window.show()
                        cls._timer_window.raise_()

            if hasattr(cls, '_button_window') and cls._button_window:
                print("[qt overlay]Showing button window")
                cls._button_window.show()
                cls._button_window.raise_()
            if hasattr(cls, '_hint_text') and cls._hint_text and cls._hint_text['window']:
                print("[qt overlay]Showing hint text window")
                cls._hint_text['window'].show()
                cls._hint_text['window'].raise_()
            if hasattr(cls, '_hint_request_text') and cls._hint_request_text and cls._hint_request_text['window']:
                print("[qt overlay]Showing hint request text window")
                cls._hint_request_text['window'].show()
                cls._hint_request_text['window'].raise_()
            # Added condition to show cooldown window
            if cls._window:
                if hasattr(cls._text_item, 'toPlainText'):
                  current_cooldown_text = cls._text_item.toPlainText()
                  if current_cooldown_text:
                      cls._window.show()
                      cls._window.raise_()

            # ONLY show GM assistance if it was previously visible
            if hasattr(cls, '_gm_assistance_overlay') and cls._gm_assistance_overlay and cls._gm_assistance_overlay['window']:
                if hasattr(cls._gm_assistance_overlay, '_was_visible') and cls._gm_assistance_overlay['_was_visible']:  # Check the flag
                    print("[qt overlay]Showing GM assistance window (previously visible)")
                    cls._gm_assistance_overlay['window'].show()
                    cls._gm_assistance_overlay['window'].raise_()
                    cls._gm_assistance_overlay['_was_visible'] = False  # Reset flag after showing
                else:
                    print("[qt overlay]GM assistance window was NOT previously visible, not showing")
            print("[qt overlay]All overlay UI elements restored")
        except Exception as e:
            print(f"[qt overlay]Error showing overlays: {e}")
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