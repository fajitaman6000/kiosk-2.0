from PyQt5.QtWidgets import QWidget, QSizePolicy
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QPoint, QRect
from PyQt5.QtGui import QPainter, QTransform, QFont, QColor, QPen, QBrush, QPixmap

class RotatedWidget(QWidget):
    """
    Base class for widgets that require 270-degree rotation.
    Provides consistent rotation behavior and event handling.
    
    Key Features:
    - Maintains exact Tkinter canvas-like rotation behavior
    - Handles mouse events in rotated space
    - Preserves image references to prevent garbage collection
    - Provides consistent text metrics in rotated space
    """
    
    clicked = pyqtSignal(QPoint)  # Signal emitted when widget is clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rotation = 270  # Match Tkinter's rotation angle
        self._text = ""
        self._font = QFont('Arial', 24)
        self._text_color = QColor('white')
        self._background_color = QColor('black')
        self._background_image = None
        self._background_pixmap = None  # Store QPixmap to prevent garbage collection
        self._alignment = Qt.AlignCenter
        self._text_width = None  # For text wrapping
        
        # Enable mouse tracking for proper event handling
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Set size policy to handle rotation correctly
        self.setSizePolicy(
            QSizePolicy.Preferred,
            QSizePolicy.Preferred
        )
    
    def sizeHint(self):
        """Override sizeHint to handle rotation"""
        base_size = super().sizeHint()
        if self._rotation in (90, 270):
            return QSize(base_size.height(), base_size.width())
        return base_size
        
    def minimumSizeHint(self):
        """Override minimumSizeHint to handle rotation"""
        base_size = super().minimumSizeHint()
        if self._rotation in (90, 270):
            return QSize(base_size.height(), base_size.width())
        return base_size
        
    def setRotatedText(self, text):
        """Set the text to be displayed with rotation"""
        self._text = text
        self.update()
        
    def setRotatedFont(self, font):
        """Set the font for rotated text"""
        if isinstance(font, str):
            self._font = QFont(font)
        else:
            self._font = font
        self.update()
        
    def setRotatedTextColor(self, color):
        """Set the color for rotated text"""
        self._text_color = QColor(color)
        self.update()
        
    def setBackgroundColor(self, color):
        """Set the background color"""
        self._background_color = QColor(color)
        self.update()
        
    def setBackgroundImage(self, image_or_path):
        """
        Set the background image. Accepts either a QImage/QPixmap or a file path.
        Maintains reference to prevent garbage collection.
        """
        if isinstance(image_or_path, str):
            self._background_pixmap = QPixmap(image_or_path)
        else:
            self._background_pixmap = QPixmap.fromImage(image_or_path)
        self._background_image = self._background_pixmap
        self.update()
        
    def setAlignment(self, alignment):
        """Set text alignment in rotated space"""
        self._alignment = alignment
        self.update()
        
    def setTextWidth(self, width):
        """Set width for text wrapping in rotated space"""
        self._text_width = width
        self.update()
        
    def paintEvent(self, event):
        """Main paint event handler"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Draw background
        if self._background_color.alpha() > 0:
            painter.fillRect(self.rect(), self._background_color)
            
        if self._background_image and not self._background_image.isNull():
            scaled_pixmap = self._background_image.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            painter.drawPixmap(self.rect(), scaled_pixmap)
        
        # Setup rotation transform
        transform = QTransform()
        
        # Calculate center point for rotation
        center = self.rect().center()
        transform.translate(center.x(), center.y())
        transform.rotate(self._rotation)
        transform.translate(-center.x(), -center.y())
        
        painter.setTransform(transform)
        
        # Draw rotated content
        self._paint_rotated(painter)
        
    def _paint_rotated(self, painter):
        """Draw the rotated content"""
        if not self._text:
            return
            
        painter.setFont(self._font)
        painter.setPen(QPen(self._text_color))
        
        # Calculate text rectangle in rotated space
        if self._rotation in (90, 270):
            text_rect = QRect(0, 0, self.height(), self.width())
        else:
            text_rect = self.rect()
            
        # Handle text wrapping
        flags = self._alignment
        if self._text_width is not None:
            flags |= Qt.TextWordWrap
            text_rect.setWidth(self._text_width)
            
        painter.drawText(text_rect, flags, self._text)
        
    def mousePressEvent(self, event):
        """Handle mouse press with coordinate transformation"""
        transformed_pos = self._transform_point(event.pos())
        if event.button() == Qt.LeftButton:
            self.clicked.emit(transformed_pos)
        super().mousePressEvent(event)
        
    def _transform_point(self, point):
        """Transform a point from widget coordinates to rotated space"""
        transform = QTransform()
        center = self.rect().center()
        
        # Apply inverse rotation around center
        transform.translate(center.x(), center.y())
        transform.rotate(-self._rotation)
        transform.translate(-center.x(), -center.y())
        
        return transform.map(point)
        
    def event(self, event):
        """Handle all events with coordinate transformation"""
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