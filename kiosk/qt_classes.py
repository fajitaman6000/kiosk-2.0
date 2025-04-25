print("[qt_classes] Beginning imports ...")
from PyQt5.QtCore import Qt, QRectF, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QGraphicsView, QGraphicsItem
print("[qt_classes] Ending imports ...")

class ClickableVideoView(QGraphicsView):
    """Custom QGraphicsView for video display that handles clicks"""
    clicked = pyqtSignal() # Signal emitted on click

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self._is_skippable = False

    def mousePressEvent(self, event):
        # print("[qt_classes] Video view clicked.") # Reduce debug noise
        if event.button() == Qt.LeftButton and self._is_skippable:
            print("[qt_classes] Video is skippable, emitting clicked signal.")
            self.clicked.emit()
        super().mousePressEvent(event)
        
    def keyPressEvent(self, event):
        """Handle key press events and allow system key combinations to pass through."""
        # Pass Alt+Tab and other system shortcuts through
        import win32gui
        if event.modifiers() & Qt.AltModifier:
            # Let system handle Alt+Tab and other Alt key combinations
            print("[qt_classes] Allowing Alt key combination to pass through")
            super().keyPressEvent(event)
            return
            
        # Let Escape key close the video if skippable
        if event.key() == Qt.Key_Escape and self._is_skippable:
            print("[qt_classes] Escape pressed on skippable video, emitting clicked signal")
            self.clicked.emit()
            event.accept()
            return
            
        # For other keys, use default handling
        super().keyPressEvent(event)

    def set_skippable(self, skippable):
        print(f"[qt_classes] Setting video skippable: {skippable}")
        self._is_skippable = skippable

class ClickableButtonView(QGraphicsView):
    """Custom QGraphicsView for button elements that handles clicks"""
    clicked = pyqtSignal() # Signal emitted on click

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            print("[qt_classes] Button view clicked, emitting clicked signal.")
            self.clicked.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        """Handle key press events, primarily for accessibility or alternative input."""
        # Allow standard key presses like Enter/Space to maybe trigger click in future
        if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Space):
            print("[qt_classes] Button key pressed, emitting clicked signal.")
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)

class ClickableHintView(QGraphicsView):
    """Custom QGraphicsView for fullscreen hint display that handles clicks"""
    clicked = pyqtSignal() # Signal emitted on click

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)

    def mousePressEvent(self, event):
        # print("[qt_classes] Fullscreen hint view clicked.") # Debug
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
        try:
            self.update_signal.emit(time_str)
        except Exception as e:
            print(f"[qt_classes] Error in TimerThread.update_display: {e}")

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
        try:
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
        except Exception as e:
            print(f"[qt_classes] Error in VideoFrameItem.setImage: {e}")

    def boundingRect(self):
        """Return the bounding rectangle of the image."""
        try:
            # Crucial: Must return the correct size for proper redraws
            if not self._image.isNull():
                return QRectF(0, 0, self._image.width(), self._image.height())
            else:
                return QRectF() # Return empty rect if no image
        except Exception as e:
            print(f"[qt_classes] Error in VideoFrameItem.boundingRect: {e}")
            return QRectF()

    def paint(self, painter, option, widget=None):
        """Paint the stored QImage directly onto the painter."""
        try:
            if not self._image.isNull():
                # Draw the image at the item's local origin (0,0)
                painter.drawImage(0, 0, self._image)
            # else: draw nothing if no image
        except Exception as e:
            print(f"[qt_classes] Error in VideoFrameItem.paint: {e}")
  
class HelpButtonThread(QThread):
    """Dedicated thread for button updates"""
    update_signal = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        
    def run(self):
        # Thread just emits signals, actual updates happen in main thread
        pass
    
    def update_button(self, button_data):
        try:
            self.update_signal.emit(button_data)
        except Exception as e:
            print(f"[qt_classes] Error in HelpButtonThread.update_button: {e}")

class HintTextThread(QThread):
    """Dedicated thread for hint text updates"""
    update_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

    def run(self):
        # Thread just emits signals, actual updates happen in main thread
        pass

    def update_text(self, text_data):
        try:
            # Print diagnostic info to help identify thread issues
            print(f"[qt_classes] HintTextThread emitting update_signal with text: {text_data.get('text', '')[:30]}...")
            self.update_signal.emit(text_data)
        except Exception as e:
            print(f"[qt_classes] Error in HintTextThread.update_text: {e}")
            import traceback
            traceback.print_exc()

class HintRequestTextThread(QThread):
    """Dedicated thread for hint request text updates"""
    update_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()

    def run(self):
        # Thread just emits signals, actual updates happen in main thread
        pass

    def update_text(self, text):
        try:
            # Print diagnostic info to help identify thread issues
            print(f"[qt_classes] HintRequestTextThread emitting update_signal with text: {text}")
            self.update_signal.emit(text)
        except Exception as e:
            print(f"[qt_classes] Error in HintRequestTextThread.update_text: {e}")
            import traceback
            traceback.print_exc()
