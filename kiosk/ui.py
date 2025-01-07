# Core PyQt5 imports
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QFrame, QVBoxLayout, 
    QSizePolicy, QApplication
)
from PyQt5.QtCore import (
    Qt, QTimer, QSize, pyqtSignal, QPoint, QRect,
    QPropertyAnimation
)
from PyQt5.QtGui import (
    QPixmap, QPainter, QImage, QColor, QTransform,
    QFont, QPalette, QBrush
)

# Custom widget imports
from rotated_widget import RotatedWidget, RotatedLabel, RotatedButton

# Python standard library
import os
import base64
import io
import traceback
import time

# Image processing
from PIL import Image  # Still needed for some image operations

class FullscreenImageViewer(QWidget):
    """Custom widget for displaying fullscreen rotated images with touch support"""
    
    clicked = pyqtSignal()  # Signal emitted when widget is clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: black;")
        
    def setImage(self, image):
        """Set the image to display"""
        self.image = image
        self.update()
        
    def paintEvent(self, event):
        """Custom paint event to handle rotated image display"""
        if not self.image:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Calculate centered position
        x = (self.width() - self.image.width()) // 2
        y = (self.height() - self.image.height()) // 2
        painter.drawPixmap(x, y, self.image)
        
    def mousePressEvent(self, event):
        """Handle mouse/touch press events"""
        self.clicked.emit()

class KioskUI(QWidget):
    """
    Main UI container for the kiosk application.
    Handles all widget creation, status displays, and hint system.
    Direct replacement for Tkinter UI with identical functionality.
    """
    
    # Signals for state changes
    hint_requested = pyqtSignal()
    cooldown_complete = pyqtSignal()
    
    def __init__(self, parent, computer_name, room_config, message_handler):
        super().__init__(parent)
        self.computer_name = computer_name
        self.room_config = room_config
        self.message_handler = message_handler
        
        # State variables (maintained from Tkinter version)
        self.background_image = None
        self.hint_cooldown = False
        self.current_hint = None
        self.stored_image_data = None
        self.video_is_playing = False
        
        # Initialize UI components
        self._setup_root()
        self._create_status_frame()
        
        # Timer for cooldown
        self.cooldown_timer = QTimer(self)
        self.cooldown_timer.timeout.connect(self._update_cooldown)
        self.cooldown_seconds_left = 0
        
        # Set up proper widget cleanup
        self.destroyed.connect(self._cleanup)
        
    def _setup_root(self):
        """Configure the root widget properties"""
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: black;")
        
    def _create_status_frame(self):
        """Create the status display frame (510,0 to 610,1079)"""
        self.status_frame = QFrame(self)
        self.status_frame.setFixedSize(100, 1079)
        self.status_frame.setStyleSheet("background-color: black;")
        self.status_frame.hide()
        
        # Create rotated text displays
        self.pending_text = RotatedLabel(self.status_frame)
        self.pending_text.setFixedSize(100, 1079)
        self.pending_text.hide()
        
        self.cooldown_text = RotatedLabel(self.status_frame)
        self.cooldown_text.setFixedSize(100, 1079)
        self.cooldown_text.hide()
    
    def show_status_frame(self):
        """Show and position the status frame"""
        self.status_frame.move(510, 0)  # Use move for Qt positioning
        self.status_frame.show()

    def hide_status_frame(self):
        """Hide the status frame"""
        self.status_frame.hide()

    def load_background(self, room_number):
        """Load and set the room-specific background image"""
        if room_number not in self.room_config['backgrounds']:
            return None
            
        filename = self.room_config['backgrounds'][room_number]
        path = os.path.join("Backgrounds", filename)
        
        try:
            if os.path.exists(path):
                image = QImage(path)
                if not image.isNull():
                    # Scale image to screen size
                    screen_size = self.window().size()
                    image = image.scaled(screen_size, Qt.KeepAspectRatio, 
                                      Qt.SmoothTransformation)
                    return QPixmap.fromImage(image)
        except Exception as e:
            print(f"Error loading background: {str(e)}")
        return None
        
    def setup_waiting_screen(self):
        """Display the initial waiting screen"""
        waiting_text = (f"Waiting for room assignment...\n"
                    f"Computer Name: {self.computer_name}")
        
        self.waiting_label = RotatedLabel(self)
        self.waiting_label.setRotatedText(waiting_text)
        self.waiting_label.setFixedSize(400, 100)
        
        # Center the waiting label
        x = self.width() // 2 - 200
        y = self.height() // 2 - 50
        self.waiting_label.move(x, y)
        self.waiting_label.show()
        
    def clear_all_labels(self):
        """Clear all UI elements and cancel pending timers"""
        if self.cooldown_timer.isActive():
            self.cooldown_timer.stop()
            
        self.hint_cooldown = False
        
        # Clear UI elements
        for widget in [self.pending_text, self.cooldown_text]:
            if widget:
                widget.hide()
                
        if hasattr(self, 'hint_label') and self.hint_label:
            self.hint_label.deleteLater()
            self.hint_label = None
            
        if hasattr(self, 'help_button') and self.help_button:
            self.help_button.deleteLater()
            self.help_button = None
        
    def clear_hints(self):
        """Clear all visible hints without resetting other kiosk state"""
        print("\nClearing visible hints...")
        
        # Clear hint-related widgets
        if hasattr(self, 'hint_label') and self.hint_label:
            self.hint_label.deleteLater()
            self.hint_label = None
            
        if hasattr(self, 'image_button') and self.image_button:
            self.image_button.deleteLater()
            self.image_button = None
            
        if hasattr(self, 'video_solution_button') and self.video_solution_button:
            self.video_solution_button.deleteLater()
            self.video_solution_button = None
            
        # Reset hint state
        self.current_hint = None
        self.stored_image_data = None
        self.stored_video_info = None
        
        print("Hint clearing complete")

    def setup_room_interface(self, room_number):
        """Set up the room-specific interface"""
        # Store any existing status messages
        pending_text = self.pending_text.text() if hasattr(self, 'pending_text') else None
        cooldown_text = self.cooldown_text.text() if hasattr(self, 'cooldown_text') else None
        
        # Clear existing widgets except timer
        for child in self.findChildren(QWidget):
            if child is not self.message_handler.timer.timer_frame:
                child.deleteLater()
                
        # Recreate status frame
        self._create_status_frame()
        
        # Restore status messages if they existed
        if pending_text:
            self.pending_text.setRotatedText(pending_text)
            self.pending_text.show()
        
        if cooldown_text:
            self.cooldown_text.setRotatedText(cooldown_text)
            self.cooldown_text.show()
            
        # Set up background
        self.background_image = self.load_background(room_number)
        if self.background_image:
            background_label = QLabel(self)
            background_label.setPixmap(self.background_image)
            background_label.setGeometry(0, 0, self.width(), self.height())
            background_label.lower()
            
        # Load room-specific timer background
        self.message_handler.timer.load_room_background(room_number)
        
        # Restore hint if there was one
        if self.current_hint:
            self.show_hint(self.current_hint, start_cooldown=False)
            
        # Restore help button if not in cooldown
        if not self.hint_cooldown:
            self.create_help_button()
            
        # Ensure timer stays on top
        self.message_handler.timer.raise_()

    def _create_button_with_background(self):
        """Create the help button with room-specific background and shadow"""
        # Define button dimensions
        canvas_width = 260
        canvas_height = 550
        
        try:
            # Create container for button and shadow
            container = QWidget(self)
            container.setFixedSize(canvas_width + 40, canvas_height + 40)
            container.move(
                int(self.width() * 0.19 - container.width()/2),
                int(self.height() * 0.5 - container.height()/2)
            )
            
            # Load and create shadow
            shadow_path = os.path.join("hint_button_backgrounds", "shadow.png")
            if os.path.exists(shadow_path):
                shadow_image = QImage(shadow_path)
                shadow_image = shadow_image.scaled(
                    container.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                shadow_label = QLabel(container)
                shadow_label.setPixmap(QPixmap.fromImage(shadow_image))
                shadow_label.setGeometry(0, 0, container.width(), container.height())
            
            # Get room-specific button background
            button_name = None
            if hasattr(self.message_handler, 'assigned_room'):
                button_map = {
                    1: "casino_heist.png",
                    2: "morning_after.png",
                    3: "wizard_trials.png",
                    4: "zombie_outbreak.png",
                    5: "haunted_manor.png",
                    6: "atlantis_rising.png",
                    7: "time_machine.png"
                }
                room_num = self.message_handler.assigned_room
                button_name = button_map.get(room_num)
            
            if button_name:
                button_path = os.path.join("hint_button_backgrounds", button_name)
                if os.path.exists(button_path):
                    # Create rotated button widget
                    self.help_button = RotatedButton(container)
                    self.help_button.setFixedSize(canvas_width, canvas_height)
                    self.help_button.move(20, 20)  # Offset for shadow
                    
                    # Load and set background
                    button_image = QImage(button_path)
                    if not button_image.isNull():
                        self.help_button.setBackgroundImage(button_image)
                        self.help_button.clicked.connect(self.request_help)
                        print("Successfully created help button with background")
                    else:
                        print(f"Failed to load button image: {button_path}")
                        self._create_fallback_button(container)
                else:
                    print(f"Button image not found: {button_path}")
                    self._create_fallback_button(container)
            else:
                print("No room assigned or room number not in button map")
                self._create_fallback_button(container)
                
        except Exception as e:
            print(f"Error creating image button: {str(e)}")
            traceback.print_exc()
            self._create_fallback_button(None)
       
    def create_help_button(self):
        """Create the help request button if conditions are met"""
        # Get current timer value
        current_time = self.message_handler.timer.time_remaining
        minutes_remaining = current_time / 60
        
        print("Attempting to create help button if needed")
        
        # Check timer conditions
        has_exceeded_45 = (hasattr(self.message_handler, 'time_exceeded_45') and 
                          self.message_handler.time_exceeded_45)
                          
        # First check cooldown
        if self.hint_cooldown:
            print("In cooldown - hiding help button")
            if hasattr(self, 'help_button'):
                self.help_button.deleteLater()
                self.help_button = None
            return
            
        # Check visibility conditions
        should_hide = (
            minutes_remaining > 42 and 
            minutes_remaining <= 45 and 
            not has_exceeded_45
        )
        
        if should_hide:
            if hasattr(self, 'help_button'):
                print("Removing help button due to timer conditions")
                self.help_button.deleteLater()
                self.help_button = None
            return
        elif not hasattr(self, 'help_button') or self.help_button is None:
            print("Conditions met to show help button - creating new button")
            self._create_button_with_background()
        else:
            print("Help button already exists")

    def _create_fallback_button(self, container=None):
        """Create a basic fallback button when image loading fails"""
        try:
            button_width = 260
            button_height = 550
            
            if container is None:
                # Create container widget
                container = QWidget(self)
                container.setFixedSize(button_width + 40, button_height + 40)
                container.move(
                    int(self.width() * 0.19 - container.width()/2),
                    int(self.height() * 0.5 - container.height()/2)
                )
            
            # Create simple button with solid background
            self.help_button = RotatedButton(container)
            self.help_button.setFixedSize(button_width, button_height)
            self.help_button.move(20, 20)  # Offset for shadow effect
            self.help_button.setRotatedText("REQUEST HINT")
            self.help_button.setRotatedFont(QFont('Arial', 24))
            self.help_button.setRotatedTextColor(QColor('white'))
            self.help_button.setBackgroundColor(QColor('blue'))
            self.help_button.clicked.connect(self.request_help)
            self.help_button.show()
            
            print("Created fallback help button")
            
        except Exception as e:
            print(f"Error creating fallback button: {e}")
            traceback.print_exc()

    def request_help(self):
        """Process help request and show status message"""
        if not self.hint_cooldown:
            # Update hint count
            if hasattr(self.message_handler, 'hints_requested'):
                self.message_handler.hints_requested += 1
                
            # Clear existing hint
            if hasattr(self, 'hint_label') and self.hint_label:
                self.hint_label.hide()
                self.current_hint = None
                
            # Remove help button
            if hasattr(self, 'help_button') and self.help_button:
                self.help_button.deleteLater()
                self.help_button = None
                
            # Show status frame with message
            self.show_status_frame()
            self.pending_text.setRotatedText("Hint Requested, please wait...")
            self.pending_text.show()
            self.cooldown_text.hide()
            
            # Send help request
            self.message_handler.network.send_message({
                'type': 'help_request',
                **self.message_handler.get_stats()
            })

    def show_hint(self, text_or_data, start_cooldown=True):
        """Shows the hint text and optionally creates an image received button
        
        Args:
            text_or_data: Either a string containing hint text or a dict with 'text' and optional 'image' keys
            start_cooldown: Boolean indicating whether to start the cooldown timer (default: True)
        """
        print("\n=== PROCESSING NEW HINT ===")
        print(f"Received hint data: {type(text_or_data)}")
        
        try:
            # Remove existing UI elements
            if self.help_button:
                self.help_button.deleteLater()
                self.help_button = None
            
            if hasattr(self, 'fullscreen_image') and self.fullscreen_image:
                self.fullscreen_image.deleteLater()
                self.fullscreen_image = None
                
            # Clear any existing video solution
            if hasattr(self, 'video_solution_button') and self.video_solution_button:
                print("Clearing existing video solution")
                self.video_solution_button.deleteLater()
                self.video_solution_button = None
                
            # Stop any playing video
            if hasattr(self, 'video_is_playing') and self.video_is_playing:
                print("Stopping playing video")
                self.message_handler.video_manager.stop_video()
                self.video_is_playing = False
                
            # Clear stored video info
            if hasattr(self, 'stored_video_info'):
                self.stored_video_info = None

            # Start cooldown timer only if requested
            if start_cooldown:
                self.start_cooldown()
            self.current_hint = text_or_data
            
            # Calculate dimensions for hint area
            hint_width = 1499 - 911  # = 588
            hint_height = 1015 - 64  # = 951
            
            # Create or update hint container
            if not hasattr(self, 'hint_label') or self.hint_label is None:
                # Create hint container widget
                self.hint_label = QWidget(self)
                self.hint_label.setFixedSize(hint_width, hint_height)
                self.hint_label.setStyleSheet("background-color: black;")
                self.hint_label.move(911, 64)
                
                # Create layout for hint content
                self.hint_layout = QVBoxLayout(self.hint_label)
                self.hint_layout.setContentsMargins(0, 0, 0, 0)
                self.hint_layout.setSpacing(0)
                
            # Clear existing content
            while self.hint_layout.count():
                item = self.hint_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            # Load room-specific hint background
            background_name = None
            if hasattr(self.message_handler, 'assigned_room'):
                room_num = self.message_handler.assigned_room
                background_map = {
                    1: "casino_heist.png",
                    2: "morning_after.png",
                    3: "wizard_trials.png",
                    4: "zombie_outbreak.png",
                    5: "haunted_manor.png",
                    6: "atlantis_rising.png",
                    7: "time_machine.png"
                }
                if room_num in background_map:
                    background_name = background_map[room_num]

            if background_name:
                try:
                    bg_path = os.path.join("hint_backgrounds", background_name)
                    if os.path.exists(bg_path):
                        # Load and set background
                        bg_image = QImage(bg_path)
                        if not bg_image.isNull():
                            bg_image = bg_image.scaled(
                                hint_width, 
                                hint_height,
                                Qt.KeepAspectRatio,
                                Qt.SmoothTransformation
                            )
                            # Set background using stylesheet with QWidget
                            self.hint_label.setStyleSheet(
                                f"background-image: url({bg_path});"
                                f"background-position: center;"
                                f"background-repeat: no-repeat;"
                            )
                except Exception as e:
                    print(f"Error loading hint background: {e}")

            # Parse hint data
            hint_text = ""
            self.stored_image_data = None

            if isinstance(text_or_data, str):
                hint_text = text_or_data
            elif isinstance(text_or_data, dict):
                hint_text = text_or_data.get('text', '')
                self.stored_image_data = text_or_data.get('image')
            else:
                hint_text = str(text_or_data)

            if hint_text:
                # Create rotated text display
                text_widget = RotatedLabel(self.hint_label)
                text_widget.setRotatedText(hint_text)
                text_widget.setRotatedFont(QFont('Arial', 20))
                text_widget.setRotatedTextColor(QColor('black'))
                
                # Position text widget
                text_x = hint_width/2 if self.stored_image_data else hint_width/2
                text_widget.move(int(text_x), hint_height//2)
                text_widget.setAlignment(Qt.AlignCenter)
                
                # Add to layout
                self.hint_layout.addWidget(text_widget)

            # Create image received button if image exists
            if self.stored_image_data:
                button_width = 100  # Narrower button
                button_height = 300  # Taller for better text visibility
                
                # Create image button using RotatedButton
                self.image_button = RotatedButton(self)
                self.image_button.setFixedSize(button_width, button_height)
                self.image_button.setRotatedText("VIEW IMAGE HINT")
                self.image_button.setRotatedFont(QFont('Arial', 24))
                self.image_button.setRotatedTextColor(QColor('white'))
                self.image_button.setBackgroundColor(QColor('blue'))
                
                # Position button
                self.image_button.move(
                    750,  # Further left, away from hint text
                    hint_height//2 - button_height//2 + 64  # Keep vertical center alignment
                )
                
                # Connect click handler
                self.image_button.clicked.connect(self.show_fullscreen_image)
                self.image_button.show()

        except Exception as e:
            print("\nCritical error in show_hint:")
            traceback.print_exc()
            try:
                if hasattr(self, 'hint_label') and self.hint_label:
                    # Clear existing content
                    while self.hint_layout.count():
                        item = self.hint_layout.takeAt(0)
                        if item.widget():
                            item.widget().deleteLater()
                            
                    # Show error message
                    error_text = RotatedLabel(self.hint_label)
                    error_text.setRotatedText(f"Error displaying hint: {str(e)}")
                    error_text.setRotatedFont(QFont('Arial', 16))
                    error_text.setRotatedTextColor(QColor('red'))
                    error_text.setAlignment(Qt.AlignCenter)
                    self.hint_layout.addWidget(error_text)
            except:
                pass
            
    def show_fullscreen_image(self):
        """Display the image in nearly fullscreen with margins"""
        if not self.stored_image_data:
            return
            
        try:
            # Hide hint interface
            if self.hint_label:
                self.hint_label.hide()
            if hasattr(self, 'image_button') and self.image_button:
                self.image_button.hide()
                
            # Calculate dimensions (full screen minus margins)
            screen_width = self.window().width()
            screen_height = self.window().height()
            margin = 50  # pixels on each side
            
            # Create fullscreen widget
            self.fullscreen_image = FullscreenImageViewer(self)
            self.fullscreen_image.setFixedSize(screen_width - (2 * margin), screen_height)
            self.fullscreen_image.move(margin, 0)
            
            # Connect click handler
            self.fullscreen_image.clicked.connect(self.restore_hint_view)
            
            try:
                # Decode and process image
                image_bytes = base64.b64decode(self.stored_image_data)
                image = QImage()
                if not image.loadFromData(image_bytes):
                    raise Exception("Failed to load image data")
                
                # Calculate resize ratio maintaining aspect ratio
                width_ratio = (screen_height - 80) / image.width()  # Leave margin for height
                height_ratio = (screen_width - (2 * margin) - 80) / image.height()  # Leave margin for width
                ratio = min(width_ratio, height_ratio)
                
                # Resize image
                new_size = QSize(
                    int(image.width() * ratio),
                    int(image.height() * ratio)
                )
                image = image.scaled(new_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                
                # Rotate image 90 degrees
                transform = QTransform()
                transform.rotate(90)
                image = image.transformed(transform, Qt.SmoothTransformation)
                
                # Convert to QPixmap for display
                pixmap = QPixmap.fromImage(image)
                self.fullscreen_image.setImage(pixmap)
                
            except Exception as e:
                print(f"Error processing image: {e}")
                # Show error message using RotatedLabel
                error_label = RotatedLabel(self.fullscreen_image)
                error_label.setRotatedText(f"Error displaying image: {str(e)}")
                error_label.setRotatedFont(QFont('Arial', 16))
                error_label.setRotatedTextColor(QColor('red'))
                error_label.setAlignment(Qt.AlignCenter)
                error_label.show()
                
            # Show the fullscreen viewer
            self.fullscreen_image.show()
            self.fullscreen_image.raise_()
            
        except Exception as e:
            print("\nError in show_fullscreen_image:")
            traceback.print_exc()
            if hasattr(self, 'fullscreen_image') and self.fullscreen_image:
                self.fullscreen_image.deleteLater()
            self.fullscreen_image = None
        
    def restore_hint_view(self):
        """Return to the original hint view"""
        if self.fullscreen_image:
            self.fullscreen_image.deleteLater()
            self.fullscreen_image = None
            
        if self.hint_label:
            self.hint_label.move(911, 64)  # Use move instead of place
            self.hint_label.show()
            
        # Restore image button with consistent positioning
        if self.image_button:
            hint_height = 1015 - 64  # Maintain original calculations
            button_height = 200
            self.image_button.move(
                750,  # Match previous x-position
                int(hint_height/2 - button_height/2 + 64)  # Keep centered
            )
            self.image_button.show()

    def start_cooldown(self):
        """Start the cooldown timer"""
        print("Starting cooldown timer")
        
        # Cancel any existing cooldown timer
        if self.cooldown_timer.isActive():
            self.cooldown_timer.stop()
        
        # Clear any existing request status
        self.pending_text.hide()
        
        self.hint_cooldown = True
        self.show_status_frame()
        self.cooldown_seconds_left = 45  # Start 45 second cooldown
        self.update_cooldown()
        
    def update_cooldown(self):
        """Updates the cooldown counter in the status frame"""
        try:
            if self.cooldown_seconds_left > 0 and self.hint_cooldown:
                # Update cooldown text
                cooldown_text = (
                    f"Please wait {self.cooldown_seconds_left} seconds "
                    "until requesting the next hint."
                )
                self.cooldown_text.setRotatedText(cooldown_text)
                self.cooldown_text.show()
                
                # Decrement counter
                self.cooldown_seconds_left -= 1
                
                # Start timer for next update
                self.cooldown_timer.start(1000)  # 1 second interval
            else:
                # Clean up cooldown state
                print("Cooldown complete - resetting state")
                self.hint_cooldown = False
                self.cooldown_text.hide()
                self.hide_status_frame()
                self.create_help_button()  # Recreate help button when cooldown ends
                
        except Exception as e:
            print(f"Error in cooldown update: {e}")

    def show_video_solution(self, room_folder, video_filename):
        """Shows a button to play the video solution, similar to image hints"""
        try:
            print(f"\nShowing video solution for {room_folder}/{video_filename}")
            
            # Store video info first
            self.stored_video_info = {
                'room_folder': room_folder,
                'video_filename': video_filename
            }
            
            # Safely remove existing button if it exists
            if hasattr(self, 'video_solution_button') and self.video_solution_button:
                self.video_solution_button.deleteLater()
                self.video_solution_button = None
                
            # Create video solution button using RotatedButton
            button_width = 100
            button_height = 400
            
            self.video_solution_button = RotatedButton(self)
            self.video_solution_button.setFixedSize(button_width, button_height)
            self.video_solution_button.setRotatedText("VIEW SOLUTION")
            self.video_solution_button.setRotatedFont(QFont('Arial', 24))
            self.video_solution_button.setRotatedTextColor(QColor('white'))
            self.video_solution_button.setBackgroundColor(QColor('blue'))
            
            # Position button
            hint_height = 1015 - 64
            self.video_solution_button.move(
                750,
                hint_height//2 - button_height//2 + 64
            )
            
            # Connect click handler
            self.video_solution_button.clicked.connect(self.toggle_solution_video)
            self.video_solution_button.show()
            
            print("Successfully created video solution button")
            
        except Exception as e:
            print(f"\nError creating video solution button:")
            traceback.print_exc()
            self.stored_video_info = None
            self.video_solution_button = None

    def toggle_solution_video(self):
        """Toggle video solution playback while preserving cooldown state"""
        try:
            print("\nToggling solution video")
            # If video is already playing, stop it
            if hasattr(self, 'video_is_playing') and self.video_is_playing:
                print("Stopping current video")
                self.message_handler.video_manager.stop_video()
                self.video_is_playing = False
                
                # Restore the button
                if hasattr(self, 'video_solution_button') and self.video_solution_button:
                    print("Restoring solution button")
                    self.video_solution_button.move(
                        750,
                        (1015 - 64)//2 - 100 + 64
                    )
                    self.video_solution_button.show()
                
                # Restore hint label if it exists
                if hasattr(self, 'hint_label') and self.hint_label:
                    print("Restoring hint label")
                    self.hint_label.show()
                    
                # Restore cooldown display if still in cooldown
                if self.hint_cooldown:
                    print("Restoring cooldown display")
                    self.show_status_frame()
                    
            # If video is not playing, start it
            else:
                print("Starting video playback")
                if hasattr(self, 'stored_video_info'):
                    # Store cooldown state before hiding UI
                    if self.hint_cooldown and hasattr(self, 'cooldown_text'):
                        self.stored_cooldown_text = self.cooldown_text.text()
                    else:
                        self.stored_cooldown_text = None
                    
                    # Hide UI elements
                    if hasattr(self, 'hint_label') and self.hint_label:
                        print("Hiding hint label")
                        self.hint_label.hide()
                    
                    if hasattr(self, 'video_solution_button') and self.video_solution_button:
                        print("Hiding solution button")
                        self.video_solution_button.hide()
                        
                    if self.hint_cooldown:
                        self.status_frame.hide()
                        
                    # Construct video path
                    video_path = os.path.join(
                        "video_solutions",
                        self.stored_video_info['room_folder'],
                        f"{self.stored_video_info['video_filename']}.mp4"
                    )
                    
                    print(f"Video path: {video_path}")
                    if os.path.exists(video_path):
                        print("Playing video")
                        self.video_is_playing = True
                        self.message_handler.video_manager.play_video(
                            video_path,
                            on_complete=self.handle_video_completion
                        )
                    else:
                        print(f"Error: Video file not found at {video_path}")
                else:
                    print("Error: No video info stored")
                    
        except Exception as e:
            print(f"\nError in toggle_solution_video: {e}")
            traceback.print_exc()

    def handle_video_completion(self):
        """Handle cleanup after video finishes playing while maintaining cooldown state"""
        print("\nHandling video completion")
        self.video_is_playing = False
        
        try:
            # Store video info before cleanup
            stored_video_info = None
            if hasattr(self, 'stored_video_info') and self.stored_video_info:
                stored_video_info = self.stored_video_info.copy()
            
            # Store cooldown state
            was_in_cooldown = self.hint_cooldown
            cooldown_timer_active = self.cooldown_timer.isActive()
            cooldown_seconds = self.cooldown_seconds_left if hasattr(self, 'cooldown_seconds_left') else 0
            
            # Clear UI state without affecting cooldown
            print("Clearing UI state...")
            if hasattr(self, 'hint_label') and self.hint_label:
                self.hint_label.hide()
            if hasattr(self, 'help_button') and self.help_button:
                self.help_button.deleteLater()
                self.help_button = None
            if hasattr(self, 'video_solution_button') and self.video_solution_button:
                self.video_solution_button.deleteLater()
                self.video_solution_button = None
                
            # Restore room interface - this will properly recreate the hint display area
            if self.message_handler.assigned_room:
                print("Restoring room interface")
                self.setup_room_interface(self.message_handler.assigned_room)
                
                # If we had a video solution, create a fresh button
                if stored_video_info:
                    print("Creating fresh video solution button")
                    self.show_video_solution(
                        stored_video_info['room_folder'],
                        stored_video_info['video_filename']
                    )
            
            # Restore cooldown state if it was active
            if was_in_cooldown:
                print("Restoring cooldown state")
                self.hint_cooldown = True
                if cooldown_timer_active:
                    self.cooldown_seconds_left = cooldown_seconds
                    self.update_cooldown()
                    self.cooldown_timer.start(1000)
                self.show_status_frame()
            else:
                # Only refresh help button if not in cooldown
                QTimer.singleShot(100, self.create_help_button)
                
        except Exception as e:
            print(f"\nError in handle_video_completion: {e}")
            traceback.print_exc()
            
    def _cleanup(self):
        """Proper cleanup when widget is destroyed"""
        print("\nCleaning up KioskUI...")
        
        # Stop timers
        if self.cooldown_timer.isActive():
            self.cooldown_timer.stop()
            
        # Clean up video manager if it exists
        if hasattr(self.message_handler, 'video_manager'):
            if self.video_is_playing:
                self.message_handler.video_manager.stop_video()
                
        # Clear stored data
        self.stored_image_data = None
        self.current_hint = None
        
        print("KioskUI cleanup complete")