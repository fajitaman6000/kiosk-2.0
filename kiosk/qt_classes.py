print("[qt classes] Beginning imports ...")
from PyQt5.QtCore import Qt, QRectF, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QGraphicsView, QGraphicsItem
print("[qt classes] Ending imports ...")

class ClickableVideoView(QGraphicsView):
    """Custom QGraphicsView for video display that handles clicks"""
    clicked = pyqtSignal() # Signal emitted on click

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self._is_skippable = False

    def mousePressEvent(self, event):
        # print("[qt classes] Video view clicked.") # Reduce debug noise
        if event.button() == Qt.LeftButton and self._is_skippable:
            print("[qt classes] Video is skippable, emitting clicked signal.")
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_skippable(self, skippable):
        print(f"[qt classes] Setting video skippable: {skippable}")
        self._is_skippable = skippable

class ClickableHintView(QGraphicsView):
    """Custom QGraphicsView for fullscreen hint display that handles clicks"""
    clicked = pyqtSignal() # Signal emitted on click

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)

    def mousePressEvent(self, event):
        # print("[qt classes] Fullscreen hint view clicked.") # Debug
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
