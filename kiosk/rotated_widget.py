from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QSizePolicy
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QPoint, QRect
from PyQt5.QtGui import QPainter, QTransform, QFont, QColor, QPen, QBrush

class RotatedWidget(QWidget):
    """
    Base class for all widgets that need 270-degree rotation.
    This serves as the foundation for all rotated UI elements in the kiosk.
    
    Key Features:
    - Handles 270-degree rotation automatically
    - Maintains correct size hints for layout management
    - Provides consistent painting interface for subclasses
    - Manages coordinate transformation for events
    - Handles text metrics in rotated space
    - Supports background images and colors
    """
    
    # Signal emitted when clicked, with transformed coordinates
    clicked = pyqtSignal(QPoint)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rotation = 270
        self._background_mode = Qt.TransparentMode
        self._background_color = None
        self._background_image = None
        self._text = ""
        self._font = QFont('Arial', 24)
        self._text_color = QColor('white')
        self._alignment = Qt.AlignCenter
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
        
        # Set up widget properties
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        
    def sizeHint(self):
        """
        Override sizeHint to swap width/height for rotation.
        Critical for proper layout behavior in Qt's layout system.
        """
        base_size = super().sizeHint()
        return QSize(base_size.height(), base_size.width())
        
    def minimumSizeHint(self):
        """
        Override minimumSizeHint to maintain rotation-aware sizing.
        This ensures widgets don't collapse in layouts.
        """
        base_size = super().minimumSizeHint()
        return QSize(base_size.height(), base_size.width())
        
    def setRotatedText(self, text):
        """Set the text to be displayed in the rotated space."""
        self._text = text
        self.update()
        
    def setRotatedFont(self, font):
        """Set the font for rotated text."""
        if isinstance(font, str):
            self._font = QFont(font)
        else:
            self._font = font
        self.update()
        
    def setRotatedTextColor(self, color):
        """Set the color for rotated text."""
        self._text_color = QColor(color)
        self.update()
        
    def setBackgroundColor(self, color):
        """Set the background color."""
        self._background_color = QColor(color)
        self.update()
        
    def setBackgroundImage(self, image):
        """Set the background image."""
        self._background_image = image
        self.update()
        
    def setAlignment(self, alignment):
        """Set text alignment in rotated space."""
        self._alignment = alignment
        self.update()
        
    def paintEvent(self, event):
        """
        Core painting logic that handles rotation.
        Subclasses should override _paint_rotated instead of this method.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        
        # Draw background if set
        if self._background_color:
            painter.fillRect(self.rect(), self._background_color)
            
        if self._background_image:
            painter.drawImage(self.rect(), self._background_image)
        
        # Setup rotation transform
        transform = QTransform()
        transform.translate(self.width(), 0)
        transform.rotate(self._rotation)
        painter.setTransform(transform)
        
        # Call subclass painting
        self._paint_rotated(painter)
        
    def _paint_rotated(self, painter):
        """
        Default implementation draws text if set.
        Subclasses can override for custom painting.
        """
        if self._text:
            painter.setFont(self._font)
            painter.setPen(QPen(self._text_color))
            
            # Calculate text rect in rotated space
            text_rect = QRect(0, 0, self.height(), self.width())
            painter.drawText(text_rect, self._alignment, self._text)
            
    def mousePressEvent(self, event):
        """Handle mouse press with coordinate transformation."""
        transformed_pos = self._transform_point(event.pos())
        if event.button() == Qt.LeftButton:
            self.clicked.emit(transformed_pos)
        super().mousePressEvent(event)
        
    def _transform_point(self, point):
        """Transform a point from widget coordinates to rotated space."""
        transform = QTransform()
        transform.rotate(-self._rotation)
        transform.translate(-self.height(), 0)
        return transform.map(point)
        
    def event(self, event):
        """
        Handle coordinate transformation for all events.
        This ensures mouse/touch events work correctly in rotated space.
        """
        # Transform coordinates for mouse/touch events
        if event.type() in (Qt.MouseButtonPress, Qt.MouseButtonRelease, 
                          Qt.MouseMove, Qt.TouchBegin, Qt.TouchUpdate, 
                          Qt.TouchEnd):
            transformed_pos = self._transform_point(event.pos())
            event.accept()
            
            # Create new event with transformed coordinates
            new_event = event.__class__(
                event.type(),
                transformed_pos,
                event.button() if hasattr(event, 'button') else Qt.NoButton,
                event.buttons() if hasattr(event, 'buttons') else Qt.NoButton,
                event.modifiers()
            )
            return super().event(new_event)
            
        return super().event(event)


class RotatedLabel(RotatedWidget):
    """
    A QLabel-like widget that displays rotated text.
    Direct replacement for Tkinter Labels with rotation.
    """
    
    def __init__(self, parent=None, text="", color="white", background="black"):
        super().__init__(parent)
        self.setRotatedText(text)
        self.setRotatedTextColor(color)
        self.setBackgroundColor(background)


class RotatedButton(RotatedWidget):
    """
    A QPushButton-like widget that displays rotated text and handles clicks.
    Direct replacement for Tkinter Buttons with rotation.
    """
    
    def __init__(self, parent=None, text="", color="white", background="blue"):
        super().__init__(parent)
        self.setRotatedText(text)
        self.setRotatedTextColor(color)
        self.setBackgroundColor(background)
        
    def _paint_rotated(self, painter):
        """Custom painting for button appearance."""
        # Draw button background
        painter.setBrush(QBrush(self._background_color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, self.height(), self.width())
        
        # Draw text
        if self._text:
            painter.setFont(self._font)
            painter.setPen(QPen(self._text_color))
            text_rect = QRect(0, 0, self.height(), self.width())
            painter.drawText(text_rect, self._alignment, self._text)