print("[qt_classes] Beginning imports ...", flush=True)
print("[qt_classes] Importing PyQt5.QtCore...", flush=True)
from PyQt5.QtCore import Qt, QRectF, QThread, pyqtSignal, Qt
print("[qt_classes] Imported PyQt5.QtCore.", flush=True)
print("[qt_classes] Importing PyQt5.QtGui...", flush=True)
from PyQt5.QtGui import QImage
print("[qt_classes] Imported PyQt5.QtGui.", flush=True)
print("[qt_classes] Importing PyQt5.QtWidgets...", flush=True)
from PyQt5.QtWidgets import QGraphicsView, QGraphicsItem
print("[qt_classes] Imported PyQt5.QtWidgets.", flush=True)
print("[qt_classes] Ending imports ...", flush=True)

class ClickableVideoView(QGraphicsView):
    """Custom QGraphicsView for video display that handles clicks""" # also repurposed for the hint button!
    clicked = pyqtSignal() # Signal emitted on click

    def __init__(self, scene, parent=None):
        print("[qt_classes] Initializing ClickableVideoView...", flush=True)
        super().__init__(scene, parent)
        self._is_skippable = False
        print("[qt_classes] ClickableVideoView initialized.", flush=True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._is_skippable:
            self.clicked.emit() # Emit the signal directly
        super().mousePressEvent(event)
        
    def keyPressEvent(self, event):
        """Handle key press events and allow system key combinations to pass through."""
        # Pass Alt+Tab and other system shortcuts through
        import win32gui
        if event.modifiers() & Qt.AltModifier:
            # Let system handle Alt+Tab and other Alt key combinations
            print("[qt_classes] Allowing Alt key combination to pass through", flush=True)
            super().keyPressEvent(event)
            return
            
        # Let Escape key close the video if skippable
        if event.key() == Qt.Key_Escape and self._is_skippable:
            print("[qt_classes] Escape pressed on skippable video, emitting clicked signal", flush=True)
            self.clicked.emit()
            event.accept()
            return
            
        # For other keys, use default handling
        super().keyPressEvent(event)

    def set_skippable(self, skippable):
        print(f"[qt_classes] Setting video skippable: {skippable}", flush=True)
        self._is_skippable = skippable

class ClickableHintView(QGraphicsView):
    """Custom QGraphicsView for fullscreen hint display that handles clicks"""
    clicked = pyqtSignal() # Signal emitted on click

    def __init__(self, scene, parent=None):
        print("[qt_classes] Initializing ClickableHintView...", flush=True)
        super().__init__(scene, parent)
        print("[qt_classes] ClickableHintView initialized.", flush=True)

    def mousePressEvent(self, event):
        # print("[qt_classes] Fullscreen hint view clicked.") # Debug
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

class TimerThread(QThread):
    """Dedicated thread for timer updates"""
    update_signal = pyqtSignal(str)
    
    def __init__(self):
        print("[qt_classes] Initializing TimerThread...", flush=True)
        super().__init__()
        print("[qt_classes] TimerThread initialized.", flush=True)
        
    def run(self):
        # Thread just emits signals, actual updates happen in main thread
        pass
        
    def update_display(self, time_str):
        try:
            self.update_signal.emit(time_str)
        except Exception as e:
            print(f"[qt_classes] Error in TimerThread.update_display: {e}", flush=True)

class TimerDisplay:
    """Handles the visual elements of the timer display"""
    def __init__(self):
        print("[qt_classes] Initializing TimerDisplay...", flush=True)
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
        print("[qt_classes] TimerDisplay initialized.", flush=True)

class VideoFrameItem(QGraphicsItem):
    """A QGraphicsItem that paints a QImage directly, avoiding QPixmap conversion."""
    def __init__(self, parent=None):
        print("[qt_classes] Initializing VideoFrameItem...", flush=True)
        super().__init__(parent)
        self._image = QImage() # Initialize with an empty QImage
        print("[qt_classes] VideoFrameItem initialized.", flush=True)

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
            print(f"[qt_classes] Error in VideoFrameItem.setImage: {e}", flush=True)

    def boundingRect(self):
        """Return the bounding rectangle of the image."""
        try:
            # Crucial: Must return the correct size for proper redraws
            if not self._image.isNull():
                return QRectF(0, 0, self._image.width(), self._image.height())
            else:
                return QRectF() # Return empty rect if no image
        except Exception as e:
            print(f"[qt_classes] Error in VideoFrameItem.boundingRect: {e}", flush=True)
            return QRectF()

    def paint(self, painter, option, widget=None):
        """Paint the stored QImage directly onto the painter."""
        try:
            if not self._image.isNull():
                # Draw the image at the item's local origin (0,0)
                painter.drawImage(0, 0, self._image)
            # else: draw nothing if no image
        except Exception as e:
            print(f"[qt_classes] Error in VideoFrameItem.paint: {e}", flush=True)
  
class HelpButtonThread(QThread):
    """Dedicated thread for button updates"""
    update_signal = pyqtSignal(dict)
    
    def __init__(self):
        print("[qt_classes] Initializing HelpButtonThread...", flush=True)
        super().__init__()
        print("[qt_classes] HelpButtonThread initialized.", flush=True)
        
    def run(self):
        # Thread just emits signals, actual updates happen in main thread
        pass
    
    def update_button(self, button_data):
        try:
            self.update_signal.emit(button_data)
        except Exception as e:
            print(f"[qt_classes] Error in HelpButtonThread.update_button: {e}", flush=True)

class HintTextThread(QThread):
    """Dedicated thread for hint text updates"""
    update_signal = pyqtSignal(dict)

    def __init__(self):
        print("[qt_classes] Initializing HintTextThread...", flush=True)
        super().__init__()
        print("[qt_classes] HintTextThread initialized.", flush=True)

    def run(self):
        # Thread just emits signals, actual updates happen in main thread
        pass

    def update_text(self, text_data):
        try:
            # Print diagnostic info to help identify thread issues
            #print(f"[qt_classes] HintTextThread emitting update_signal with text: {text_data.get('text', '')[:30]}...", flush=True)
            self.update_signal.emit(text_data)
        except Exception as e:
            print(f"[qt_classes] Error in HintTextThread.update_text: {e}", flush=True)
            import traceback
            traceback.print_exc()

class HintRequestTextThread(QThread):
    """Dedicated thread for hint request text updates"""
    update_signal = pyqtSignal(str)

    def __init__(self):
        print("[qt_classes] Initializing HintRequestTextThread...", flush=True)
        super().__init__()
        print("[qt_classes] HintRequestTextThread initialized.", flush=True)

    def run(self):
        # Thread just emits signals, actual updates happen in main thread
        pass

    def update_text(self, text):
        try:
            # Print diagnostic info to help identify thread issues
            print(f"[qt_classes] HintRequestTextThread emitting update_signal with text: {text}", flush=True)
            self.update_signal.emit(text)
        except Exception as e:
            print(f"[qt_classes] Error in HintRequestTextThread.update_text: {e}", flush=True)
            import traceback
            traceback.print_exc()
