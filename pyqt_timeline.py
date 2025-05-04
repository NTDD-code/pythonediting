import sys
import os
import cv2
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QGraphicsView, QGraphicsScene,
                             QGraphicsRectItem, QGraphicsTextItem, QAction,
                             QFileDialog, QMessageBox, QSizePolicy, QFrame,
                             QToolBar, QLabel, QSlider, QStyle, QPushButton,
                             QScrollArea, QMenu)
from PyQt5.QtGui import QColor, QBrush, QPen, QFont, QPainter, QImage, QPixmap, QIcon, QTransform
from PyQt5.QtCore import Qt, QRectF, QPointF, QTimer, QTime, QUrl, QMimeData, QByteArray, QDataStream, QIODevice, pyqtSignal

# --- PyQt Timeline Component ---
# This component provides a visual timeline with tracks, clips, playhead, and ruler.
# It uses PyQt's Graphics View Framework for rendering and interaction.

class PyQtTimelineClip(QGraphicsRectItem):
    """Represents a video/audio clip item on the timeline scene."""

    def __init__(self, clip_data, x, y, width, height, color=Qt.blue, parent=None):
        super().__init__(x, y, width, height, parent)
        self.clip_data = clip_data # Store the original clip data dictionary
        self.setBrush(QBrush(QColor(color)))
        self.setPen(QPen(Qt.white, 1))
        self.setFlag(QGraphicsRectItem.ItemIsMovable) # Make the item draggable
        self.setFlag(QGraphicsRectItem.ItemIsSelectable) # Make the item selectable
        self.setCursor(Qt.OpenHandCursor) # Change cursor on hover
        self.setAcceptHoverEvents(True) # Enable hover events

        # Add text item for the filename
        self.text_item = QGraphicsTextItem(os.path.basename(clip_data.get('video_path', 'Unknown')), self)
        self.text_item.setDefaultTextColor(Qt.white)
        self.text_item.setFont(QFont("Arial", 8))
        # Position text relative to the item's top-left corner
        self.text_item.setPos(5, 5) # Simple positioning relative to item (0,0)

        # Store original position for drag calculations
        self._drag_start_pos = None

    def mousePressEvent(self, event):
        """Handle mouse button press on the clip item."""
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos() # Store the starting position relative to the item
            self.setSelected(True) # Select the item on click
            self.setCursor(Qt.ClosedHandCursor) # Change cursor while dragging
            # Propagate the event to allow dragging
            super().mousePressEvent(event)
        elif event.button() == Qt.RightButton:
             # Handle right-click for context menu (will be implemented in View)
             super().mousePressEvent(event)


    def mouseMoveEvent(self, event):
        """Handle mouse move event while dragging."""
        if event.buttons() & Qt.LeftButton and self._drag_start_pos is not None:
            # Calculate the change in position
            delta = event.pos() - self._drag_start_pos
            # Calculate the new position in scene coordinates
            new_pos = self.pos() + delta

            # Apply grid snapping (snap to nearest 10 pixels in x)
            snap_x = round(new_pos.x() / 10) * 10
            # Keep y position snapped to track (simplified for now)
            # In a real implementation, you'd find the target track based on new_pos.y()
            # and snap to the track's y position.
            snap_y = round(new_pos.y() / 80) * 80 # Simple snap to track height (assuming 80px tracks)

            # Ensure clip stays within scene bounds (at least the left edge)
            snap_x = max(0, snap_x)
            snap_y = max(0, snap_y) # Prevent dragging above the first track

            # Update the item's position
            self.setPos(snap_x, snap_y)

            # Update the clip data's start time based on the new x position
            # Access timeline_scale from the view
            timeline_scale = self.scene().timeline_view.timeline_scale if self.scene() and hasattr(self.scene(), 'timeline_view') else 100
            self.clip_data['start_time'] = self.pos().x() / timeline_scale

            # Update text item position relative to the clip item (it's a child, so its position is relative)
            # No need to update text_item.setPos() here if it's a child item and its position is relative to the parent.
            # The text item's position (5, 5) is relative to the clip item's top-left corner (0,0).
            pass

            # Propagate the event
            super().mouseMoveEvent(event)


    def mouseReleaseEvent(self, event):
        """Handle mouse button release."""
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = None # Reset drag data
            self.setCursor(Qt.OpenHandCursor) # Restore cursor
            # Propagate the event
            super().mouseReleaseEvent(event)

    def hoverEnterEvent(self, event):
        """Handle mouse hover enter event."""
        # Change border color on hover if not selected
        if not self.isSelected():
            self.setPen(QPen(Qt.yellow, 2))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Handle mouse hover leave event."""
        # Restore border color when hover leaves if not selected
        if not self.isSelected():
            track_type = self.clip_data.get('track_type', 'video') # Assume video if not specified
            clip_border_color = Qt.blue if track_type == "video" else Qt.darkGreen
            self.setPen(QPen(clip_border_color, 1))
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        """Handle changes to the item, like selection state."""
        if change == QGraphicsRectItem.ItemSelectedChange:
            if value:
                # Change border color when selected
                self.setPen(QPen(Qt.cyan, 2))
            else:
                # Restore border color when deselected
                track_type = self.clip_data.get('track_type', 'video') # Assume video if not specified
                clip_border_color = Qt.blue if track_type == "video" else Qt.darkGreen
                self.setPen(QPen(clip_border_color, 1))
            # Emit a signal for selection change (if needed by the main app)
            # self.scene().clipSelectionChanged.emit(self) # Example signal
        return super().itemChange(change, value)


class PyQtTimelineScene(QGraphicsScene):
    """Graphics scene for the timeline, managing clips, tracks, and the playhead."""

    # Define signals that the scene can emit
    playheadMoved = pyqtSignal(float) # Emitted when playhead moves, passes pixel position
    clipDoubleClicked = pyqtSignal(str) # Emitted when a clip is double-clicked, passes video path
    clipRightClicked = pyqtSignal(object, QPointF) # Emitted when a clip is right-clicked, passes clip item and scene position
    selectionChanged = pyqtSignal() # Emitted when selection changes

    def __init__(self, timeline_view, parent=None):
        super().__init__(parent)
        self.setBackgroundBrush(QBrush(QColor("#181818"))) # Dark background
        self.timeline_view = timeline_view # Reference to the view
        self.timeline_clips_items = [] # List to store PyQtTimelineClip items
        self.timeline_data = [] # List to store clip data (dictionaries)

        # Example: Define tracks (simplified representation)
        self.tracks = {
            "V1": {"y": 0, "height": 80, "type": "video", "color": Qt.blue},
            "V2": {"y": 80, "height": 80, "type": "video", "color": Qt.darkBlue},
            "A1": {"y": 160, "height": 80, "type": "audio", "color": Qt.darkGreen},
            "A2": {"y": 240, "height": 80, "type": "audio", "color": Qt.green},
        }
        # Set the scene rectangle to encompass the tracks and some extra space
        scene_height = sum(track["height"] for track in self.tracks.values()) + 100 # Add padding
        self.setSceneRect(0, 0, 5000, scene_height) # Set a large enough initial scene rect

        # Playhead (represented by a line)
        self.playhead_item = self.addLine(0, 0, 0, scene_height, QPen(QColor("#00aaff"), 3))
        self.playhead_item.setZValue(100) # Ensure playhead is on top of everything

        # Connect selection changed signal
        self.selectionChanged.connect(self.on_scene_selection_changed)

    def add_clip(self, clip_data, x_pos, y_pos):
        """Add a clip to the timeline scene."""
        # Determine target track based on y_pos (simplified)
        target_track_name = None
        # Find the track whose y range contains the drop y position
        for name, track_info in self.tracks.items():
             if track_info['y'] <= y_pos < track_info['y'] + track_info['height']:
                 target_track_name = name
                 break

        if not target_track_name:
             print(f"Warning: Could not determine target track for y_pos {y_pos}. Using first track.")
             target_track_name = next(iter(self.tracks))


        track_info = self.tracks[target_track_name]
        # Access timeline_scale from the view
        timeline_scale = self.timeline_view.timeline_scale if self.timeline_view else 100
        clip_width = max(50, int(clip_data.get('duration', 1) * timeline_scale)) # Use get with default
        clip_height = track_info['height'] - 20 # Adjust height based on track

        clip_color = track_info['color'] # Use color defined in track info

        # Create a PyQtTimelineClip item
        # Position the clip at the calculated x and track_y + padding
        clip_item = PyQtTimelineClip(clip_data, x_pos, track_info['y'] + 10, clip_width, clip_height, clip_color)
        self.addItem(clip_item)
        self.timeline_clips_items.append(clip_item) # Store the clip item
        self.timeline_data.append(clip_data) # Store the clip data

        # Update clip data's start time based on initial position
        clip_data['start_time'] = x_pos / timeline_scale
        clip_data['track'] = target_track_name # Store track name in data
        clip_data['track_type'] = track_info['type'] # Store track type in data

        # Update scene rectangle if needed
        self.update_scene_rect()

        return clip_item # Return the created item

    def update_scene_rect(self):
        """Update the scene rectangle based on clip positions and duration."""
        max_x = 0
        max_y = 0
        if self.timeline_clips_items:
            for item in self.timeline_clips_items:
                # Use scene bounding rect to get position and size in scene coordinates
                bbox = item.sceneBoundingRect()
                max_x = max(max_x, bbox.right())
                max_y = max(max_y, bbox.bottom())

        # Ensure scene rect is large enough for tracks and clips
        current_scene_rect = self.sceneRect()
        new_width = max(current_scene_rect.width(), max_x + 200) # Add some padding
        new_height = max(current_scene_rect.height(), max_y + 100) # Add some padding

        self.setSceneRect(0, 0, new_width, new_height)

        # Update playhead line height
        if self.playhead_item:
             self.playhead_item.setLine(self.playhead_item.line().x1(), 0, self.playhead_item.line().x2(), new_height)


    def get_clips_data(self):
        """Return the list of clip data dictionaries."""
        # Ensure clip data is updated with current positions from QGraphicsItems
        timeline_scale = self.timeline_view.timeline_scale if self.timeline_view else 100 # Get scale from view
        for item in self.timeline_clips_items:
             item.clip_data['start_time'] = item.pos().x() / timeline_scale
             # Update track based on current y position if needed (more complex)
             # For simplicity, assuming track doesn't change visually unless explicitly moved to a new track area
             # If implementing track snapping, you'd update track here based on snapped y_pos

        return self.timeline_data

    def move_playhead(self, x_pos):
        """Move the playhead item on the scene."""
        if self.playhead_item:
            # Ensure playhead stays within scene bounds (0 to max timeline duration in pixels)
            max_x = self.sceneRect().right()
            new_x = max(0, min(x_pos, max_x))
            self.playhead_item.setPos(new_x, 0) # Move only in the x direction
            self.playheadMoved.emit(new_x) # Emit signal


    def on_scene_selection_changed(self):
        """Handle selection changes in the scene."""
        # This method is called when the selection changes.
        # You can use self.selectedItems() to get the list of selected items.
        # Emit a signal if the main app needs to know about selection changes.
        self.selectionChanged.emit()


class PyQtTimelineView(QGraphicsView):
    """Graphics view for displaying the PyQt timeline scene with ruler and controls."""

    # Define signals that the view can emit
    # These signals are forwarded from the scene or generated by view interactions
    playheadMoved = pyqtSignal(float) # Emitted when playhead moves, passes pixel position
    clipDoubleClicked = pyqtSignal(str) # Emitted when a clip is double-clicked, passes video path
    clipRightClicked = pyqtSignal(object, QPointF) # Emitted when a clip is right-clicked, passes clip item and scene position
    selectionChanged = pyqtSignal() # Emitted when selection changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.timeline_scale = 100 # pixels per second
        self.playhead_callback = None # Callback for playhead movement (connected via signal)

        self.scene = PyQtTimelineScene(self) # Create the scene
        self.setScene(self.scene) # Set the scene for the view


        self.setRenderHint(QPainter.Antialiasing) # Smoother rendering
        self.setDragMode(QGraphicsView.RubberBandDrag) # Enable selection rectangle
        self.setMouseTracking(True) # Enable mouse tracking

        # Configure scroll bars to follow scene rect
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # State variables for dragging
        self._dragging_playhead = False
        self._playhead_drag_start_scene_x = None # Store start x in scene coordinates

        # Enable dropping onto the view
        self.setAcceptDrops(True)

        # Set the top margin to make space for the ruler
        self.setViewportMargins(0, 20, 0, 0) # Leave 20 pixels at the top for the ruler


    def set_playhead_callback(self, callback):
         """Set callback for playhead movement (connects to playheadMoved signal)."""
         self.playheadMoved.connect(callback)

    def mousePressEvent(self, event):
        """Handle mouse button press on the view."""
        scene_pos = self.mapToScene(event.pos())

        # Check if clicking near the playhead handle (simplified check)
        # Get the playhead item's scene position and create a small rect around its top
        if self.scene.playhead_item:
             ph_x = self.scene.playhead_item.pos().x()
             # Check if click is within the top 20 pixels (ruler area) and near the playhead x
             if event.pos().y() < 20 and abs(event.pos().x() - self.mapFromScene(QPointF(ph_x, 0)).x()) < 10: # Check in view coordinates for ruler area
                  if event.button() == Qt.LeftButton:
                      self._dragging_playhead = True
                      self._playhead_drag_start_scene_x = scene_pos.x()
                      # Accept the event to start drag
                      event.accept()
                      return # Do not call super() to prevent item selection when dragging playhead


        # If not dragging playhead, check for item selection/drag
        item = self.scene.itemAt(scene_pos, self.transform())
        if item:
            # Let the item handle the press event (for selection and drag start)
            super().mousePressEvent(event)
        else:
            # If clicking on empty space, move playhead
            if event.button() == Qt.LeftButton:
                 self.move_playhead_to_scene_pos(scene_pos.x())
                 # Clear selection if clicking empty space without modifier keys
                 if not (event.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier)):
                      self.scene.clearSelection()
            # Allow rubber band selection
            super().mousePressEvent(event)


    def mouseMoveEvent(self, event):
        """Handle mouse move on the view."""
        scene_pos = self.mapToScene(event.pos())

        if self._dragging_playhead:
            # Calculate the change in scene x
            dx = scene_pos.x() - self._playhead_drag_start_scene_x
            # Calculate the new playhead position
            new_playhead_x = self.scene.playhead_item.pos().x() + dx
            self.move_playhead_to_scene_pos(new_playhead_x)
            # Update drag start position for next motion event
            self._playhead_drag_start_scene_x = scene_pos.x()
            event.accept() # Accept the event
        else:
            # Let the scene/items handle movement (for dragging clips or rubber band)
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse button release on the view."""
        if self._dragging_playhead:
            self._dragging_playhead = False
            self._playhead_drag_start_scene_x = None
            # Final playhead position update
            scene_pos = self.mapToScene(event.pos())
            self.move_playhead_to_scene_pos(scene_pos.x())
            event.accept() # Accept the event
        else:
            # Let the scene/items handle the release event (for finishing drag or selection)
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Handle mouse double click on the view."""
        scene_pos = self.mapToScene(event.pos())
        item = self.scene.itemAt(scene_pos, self.transform())

        if isinstance(item, PyQtTimelineClip):
            # Emit the signal when a clip is double-clicked
            self.clipDoubleClicked.emit(item.clip_data.get('video_path'))
            event.accept() # Accept the event
            return # Stop further processing

        # Default double click behavior
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        """Handle context menu request (right-click)."""
        scene_pos = self.mapToScene(event.pos())
        item = self.scene.itemAt(scene_pos, self.transform())

        if isinstance(item, PyQtTimelineClip):
            # Emit signal for clip right-click
            self.clipRightClicked.emit(item, scene_pos)
            event.accept() # Accept the event
        else:
            # Handle context menu for empty timeline area if needed
            super().contextMenuEvent(event) # Show default context menu or do nothing

    def move_playhead_to_scene_pos(self, x_pos):
        """Move the playhead to a specific x position in the scene."""
        # Ensure playhead stays within bounds (0 to max timeline duration in pixels)
        max_x = self.scene.sceneRect().right()
        new_x = max(0, min(x_pos, max_x))

        self.scene.move_playhead(new_x)

        # The signal self.playheadMoved is emitted by scene.move_playhead

    def wheelEvent(self, event):
        """Handle mouse wheel event for zooming."""
        # Check if Control key is pressed for zooming
        if event.modifiers() & Qt.ControlModifier:
            # Determine the zoom factor
            # delta() gives the angle in eighths of a degree. 15 * 8 = 120, so 120 units per notch.
            # A positive delta indicates scrolling up (zoom in), negative down (zoom out).
            zoom_factor = 1.0 + event.angleDelta().y() / 1200.0 # Adjust factor for sensitivity

            # Get the position in the scene under the mouse cursor
            center_point = self.mapToScene(event.pos())

            # Apply the zoom transformation
            # Use QGraphicsView.AnchorUnderMouse to zoom around the mouse cursor
            self.setTransform(QTransform().scale(zoom_factor, 1), QGraphicsView.AnchorUnderMouse) # Only scale horizontally, zoom around mouse

            # Update timeline scale variable
            self.timeline_scale *= zoom_factor
            self.timeline_scale = max(10, min(500, self.timeline_scale)) # Clamp scale

            # Update the width of clip items based on the new scale
            for item in self.scene.timeline_clips_items:
                 new_width = max(50, int(item.clip_data.get('duration', 1) * self.timeline_scale)) # Use get with default
                 # Update the item's internal rectangle directly
                 current_rect = item.rect()
                 item.setRect(current_rect.x(), current_rect.y(), new_width, item.rect().height())

                 # Update text item's wrap width
                 item.text_item.setTextWidth(new_width - 10) # Adjust text wrap

            # Update scene rectangle after zoom
            self.scene.update_scene_rect()

            # Move playhead to maintain its time position relative to the zoom point
            # This is handled implicitly by the TransformAnchorRightClick and centering,
            # but we should ensure the playhead's scene position is consistent with the new scale.
            # Recalculate playhead position based on its time and new scale
            # The AnchorUnderMouse handles the positioning, so we just need to ensure
            # the playhead's scene position is consistent with the new scale.
            # Get the current playhead time based on its old position and old scale
            old_playhead_x = self.scene.playhead_item.pos().x()
            old_scale = self.timeline_scale / zoom_factor # Calculate old scale
            playhead_time = old_playhead_x / old_scale
            # Calculate the new playhead position based on the time and new scale
            new_playhead_x = playhead_time * self.timeline_scale
            self.move_playhead_to_scene_pos(new_playhead_x)


            event.accept() # Accept the event to prevent default scrolling
        else:
            # If Control is not pressed, perform default scrolling
            super().wheelEvent(event)

    # --- Drag and Drop Handling (for dropping items onto the timeline) ---
    def dragEnterEvent(self, event):
        """Handle drag enter event."""
        # Accept the drag if it contains our custom clip data MIME type
        if event.mimeData().hasFormat("application/x-video-clip-data"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        """Handle drag move event."""
        # Accept the drag if it contains our custom clip data MIME type
        if event.mimeData().hasFormat("application/x-video-clip-data"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        """Handle drop event."""
        if event.mimeData().hasFormat("application/x-video-clip-data"):
            # Get the data from the MIME data
            data = event.mimeData().data("application/x-video-clip-data")
            stream = QDataStream(data, QIODevice.ReadOnly)

            # Read the data in the same order it was written
            video_path = stream.readQString()
            video_duration = stream.readDouble()
            video_frame_count = stream.readInt()
            video_fps = stream.readDouble()

            # Get the drop position in scene coordinates
            scene_pos = self.mapToScene(event.pos())

            # Prepare clip data dictionary
            clip_data = {
                'video_path': video_path,
                'duration': video_duration,
                'frame_count': video_frame_count,
                'fps': video_fps,
                'start_time': 0 # Initial start time (will be set by add_clip)
            }

            # Add the clip to the timeline scene
            self.scene.add_clip(clip_data, scene_pos.x(), scene_pos.y())

            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def drawForeground(self, painter, rect):
        """Draw foreground elements like the ruler and playhead handle."""
        super().drawForeground(painter, rect)

        # Draw Ruler
        ruler_height = 20
        painter.setPen(QPen(Qt.gray))
        painter.setFont(QFont("Segoe UI", 7))
        painter.fillRect(int(rect.x()), int(rect.y()), int(rect.width()), ruler_height, QColor("#1e1e1e")) # Ruler background

        # Calculate visible time range in scene coordinates
        visible_scene_rect = self.mapToScene(self.viewport().rect()).boundingRect()
        visible_start_x = visible_scene_rect.left()
        visible_end_x = visible_scene_rect.right()

        # Adjust marker interval based on zoom level
        if self.timeline_scale >= 200:  # Zoomed in a lot
            interval_seconds = 0.25
            major_interval_seconds = 1
        elif self.timeline_scale >= 100:  # Normal zoom
            interval_seconds = 0.5
            major_interval_seconds = 5
        elif self.timeline_scale >= 50:  # Zoomed out some
            interval_seconds = 1
            major_interval_seconds = 5
        else:  # Zoomed out a lot
            interval_seconds = 5
            major_interval_seconds = 30

        # Draw time marks and labels
        start_time = visible_start_x / self.timeline_scale
        end_time = visible_end_x / self.timeline_scale

        # Determine the first and last marker times within the visible range
        first_marker_time = (int(start_time / interval_seconds)) * interval_seconds
        last_marker_time = (int(end_time / interval_seconds) + 2) * interval_seconds # Add padding

        for t in range(int(first_marker_time / interval_seconds), int(last_marker_time / interval_seconds) + 1):
             seconds = t * interval_seconds
             x_pos_scene = seconds * self.timeline_scale
             x_pos_view = self.mapFromScene(QPointF(x_pos_scene, 0)).x() # Convert scene x to view x

             # Is this a major interval?
             is_major = (abs(seconds % major_interval_seconds) < 0.001)

             # Draw marker (taller for major intervals)
             marker_height = 12 if is_major else 5
             painter.setPen(QPen(Qt.white if is_major else Qt.gray))
             painter.drawLine(int(x_pos_view), 0, int(x_pos_view), marker_height) # Cast to int

             # Add time label for major intervals
             if is_major:
                 minutes = int(seconds) // 60
                 seconds_part = int(seconds) % 60
                 # Assuming 30fps for frame display in ruler timecode
                 frames = int((seconds % 1) * 30)
                 time_text = f"{minutes:02d}:{seconds_part:02d}:{frames:02d}"
                 painter.drawText(int(x_pos_view) + 2, 15, time_text) # Cast to int


        # Draw Playhead Handle on Ruler
        if self.scene.playhead_item:
             playhead_x_scene = self.scene.playhead_item.pos().x()
             playhead_x_view = self.mapFromScene(QPointF(playhead_x_scene, 0)).x()

             # Draw a small triangle or rectangle at the top of the playhead line
             handle_size = 10
             painter.setBrush(QBrush(QColor("#00aaff")))
             painter.setPen(Qt.NoPen)
             painter.drawRect(int(playhead_x_view) - handle_size // 2, 0, handle_size, handle_size) # Cast to int

             # Draw playhead time text on ruler
             playhead_time_seconds = playhead_x_scene / self.timeline_scale
             ph_minutes = int(playhead_time_seconds) // 60
             ph_seconds = int(playhead_time_seconds) % 60
             ph_frames = int((playhead_time_seconds % 1) * 30) # Assuming 30fps
             ph_text = f"{ph_minutes:02d}:{ph_seconds:02d}:{ph_frames:02d}"

             # Position playhead time text, ensuring it stays within ruler bounds
             text_x = int(playhead_x_view) + 8
             # Get the estimated width of the text to avoid going off-screen
             # This is a rough estimate, a more accurate way would involve font metrics
             text_width_estimate = len(ph_text) * 5 # Approx 5 pixels per character
             if text_x + text_width_estimate > self.viewport().width():
                  text_x = self.viewport().width() - text_width_estimate - 5 # Position from the right

             painter.setPen(QPen(QColor("#00aaff")))
             painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
             painter.drawText(text_x, 15, ph_text)


    def drawBackground(self, painter, rect):
        """Draw background elements like track headers and separators."""
        super().drawBackground(painter, rect)

        # Draw Track Headers and Separators
        track_header_width = 80 # Fixed width for track headers
        painter.setPen(QPen(QColor("#333333"), 1)) # Separator color

        # Draw track headers and horizontal separators
        for track_name, track_info in self.scene.tracks.items():
            track_y_scene = track_info['y']
            track_height = track_info['height']

            # Draw horizontal separator line above the track
            # Cast float coordinates to int
            painter.drawLine(int(rect.left()), int(track_y_scene), int(rect.right()), int(track_y_scene))

            # Draw track header background
            painter.fillRect(int(rect.left()), int(track_y_scene), track_header_width, track_height, QColor("#222222"))

            # Draw track name label
            painter.setPen(QPen(Qt.white))
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            icon_text = "🎬" if track_info['type'] == "video" else "🎵"
            # Position text within the header area
            painter.drawText(int(rect.left()) + 8, int(track_y_scene) + 8, f"{icon_text} {track_name}")

            # Draw placeholder buttons (M, S)
            painter.setPen(QPen(Qt.white))
            painter.setFont(QFont("Segoe UI", 8))
            painter.fillRect(int(rect.left()) + track_header_width - 40, int(track_y_scene) + 8, 15, 15, QColor("#333")) # M button placeholder
            painter.drawText(int(rect.left()) + track_header_width - 38, int(track_y_scene) + 20, "M")

            painter.fillRect(int(rect.left()) + track_header_width - 20, int(track_y_scene) + 8, 15, 15, QColor("#333")) # S button placeholder
            painter.drawText(int(rect.left()) + track_header_width - 18, int(track_y_scene) + 20, "S")


        # Draw vertical separator line between track headers and timeline area
        painter.drawLine(int(rect.left()) + track_header_width, int(rect.top()), int(rect.left()) + track_header_width, int(rect.bottom()))

        # Set the view's left margin to accommodate track headers
        # This should ideally be done once or on resize, not in drawBackground
        # self.setViewportMargins(track_header_width, 20, 0, 0) # Moved to __init__


    def get_selected_clips_data(self):
        """Return a list of clip data dictionaries for selected clips."""
        selected_data = []
        for item in self.scene.selectedItems():
            if isinstance(item, PyQtTimelineClip):
                selected_data.append(item.clip_data)
        return selected_data

    def delete_selected_clips(self):
        """Delete all selected clips from the timeline."""
        items_to_remove = self.scene.selectedItems()
        if not items_to_remove:
            return

        # Confirmation dialog (optional)
        # reply = QMessageBox.question(self, 'Delete Clips', 'Are you sure you want to delete the selected clips?',
        #                              QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        # if reply == QMessageBox.No:
        #     return

        # Create a list of clips to delete to avoid modifying the list while iterating
        clips_to_delete = [item for item in items_to_remove if isinstance(item, PyQtTimelineClip)]

        for clip_item in clips_to_delete:
            # Remove from scene's lists
            if clip_item in self.scene.timeline_clips_items:
                self.scene.timeline_clips_items.remove(clip_item)
            if clip_item.clip_data in self.scene.timeline_data:
                self.scene.timeline_data.remove(clip_item.clip_data)

            # Remove from the scene
            self.scene.removeItem(clip_item)

        # Update the scene rectangle after deletion
        self.scene.update_scene_rect()

        # Emit selection changed signal as selected items are deleted
        self.scene.selectionChanged.emit() # Emit from the scene


# --- Main Application (using the PyQtTimelineView component) ---
# This part would be in your main video_editor_app.py file

# Example Usage (This part would be in your main application file)
# if __name__ == '__main__':
#     app = QApplication(sys.argv)
#     mainWin = QMainWindow()
#     mainWin.setWindowTitle("PyQt Timeline Component Test")
#     mainWin.setGeometry(100, 100, 800, 400)

#     central_widget = QWidget()
#     mainWin.setCentralWidget(central_widget)
#     layout = QVBoxLayout(central_widget)

#     # Create an instance of the timeline view
#     timeline_view = PyQtTimelineView()
#     layout.addWidget(timeline_view)

#     # Example: Add some dummy clips
#     dummy_clip_data1 = {'video_path': 'dummy_video1.mp4', 'duration': 5.0, 'frame_count': 150, 'fps': 30}
#     dummy_clip_data2 = {'video_path': 'dummy_audio1.mp3', 'duration': 3.0, 'frame_count': 0, 'fps': 0}
#     timeline_view.scene.add_clip(dummy_clip_data1, 50, 0) # Add at x=50, y=0 (will snap to track)
#     timeline_view.scene.add_clip(dummy_clip_data2, 120, 80) # Add at x=120, y=80 (will snap to track)


#     mainWin.show()
#     sys.exit(app.exec_())
