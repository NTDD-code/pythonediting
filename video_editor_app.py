import sys
import os
import cv2
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QGraphicsView, QGraphicsScene,
                             QGraphicsRectItem, QGraphicsTextItem, QAction,
                             QFileDialog, QMessageBox, QSizePolicy, QFrame,
                             QToolBar, QLabel, QSlider, QStyle, QPushButton,
                             QScrollArea, QMenu) # Added QMenu for context menu
from PyQt5.QtGui import QColor, QBrush, QPen, QFont, QPainter, QImage, QPixmap, QIcon, QTransform, QDrag
from PyQt5.QtCore import Qt, QRectF, QPointF, QTimer, QTime, QUrl, QMimeData, QByteArray, QDataStream, QIODevice, pyqtSignal

# Import the new PyQtTimelineView component
from pyqt_timeline import PyQtTimelineView, PyQtTimelineClip # Assuming pyqt_timeline.py is in the same directory

# You will need to install PyQt5: pip install PyQt5
# You might also need to install opencv-python: pip install opencv-python
# And Pillow: pip install Pillow

class VideoEditorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project_path = os.path.dirname(os.path.abspath(__file__))
        self.setWindowTitle("Simple Video Editor (PyQt)")
        self.setGeometry(100, 100, 1280, 720)
        self.setMinimumSize(1100, 600)

        # Initialize collections
        self.thumbnail_widgets = [] # Store thumbnail widgets (PyQt)

        # Video playback variables
        self.current_video = None # OpenCV VideoCapture object
        self.current_video_path = None
        self.video_playing = False
        self.current_frame = None # QPixmap or QImage for the current frame
        self.frame_count = 0
        self.current_frame_pos = 0
        self.fps = 0
        self.video_duration = 0 # Store total video duration in seconds

        # Timer for video playback
        self.video_timer = QTimer(self)
        self.video_timer.timeout.connect(self.update_video_frame)


        # --- Main Layout ---
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- Left: Project/Media Panel ---
        self.media_panel = QFrame(self)
        self.media_panel.setFrameShape(QFrame.StyledPanel)
        self.media_panel.setFrameShadow(QFrame.Sunken)
        self.media_panel.setMinimumWidth(260)
        self.media_panel.setMaximumWidth(350) # Limit max width
        media_layout = QVBoxLayout(self.media_panel)
        media_layout.setContentsMargins(0, 0, 0, 0)

        media_header = QLabel("Project", self.media_panel)
        media_header.setFont(QFont("Segoe UI", 12, QFont.Bold))
        media_header.setStyleSheet("background-color: #181818; color: #fff; padding: 10px 12px;")
        media_header.setFixedHeight(40) # Fixed height for header
        media_layout.addWidget(media_header)

        # Scroll area for thumbnails
        self.media_scroll_area = QScrollArea(self.media_panel)
        self.media_scroll_area.setWidgetResizable(True)
        self.media_scroll_area_content = QWidget()
        # Use QVBoxLayout for list arrangement
        self.media_scroll_area_layout = QVBoxLayout(self.media_scroll_area_content)
        self.media_scroll_area_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter) # Align items to top-center
        self.media_scroll_area.setWidget(self.media_scroll_area_content)
        media_layout.addWidget(self.media_scroll_area)


        main_layout.addWidget(self.media_panel)

        # --- Center: Preview and Timeline ---
        center_layout = QVBoxLayout()

        # Center Top: Program/Preview Panel
        self.preview_panel = QFrame(self)
        self.preview_panel.setFrameShape(QFrame.StyledPanel)
        self.preview_panel.setFrameShadow(QFrame.Sunken)
        preview_layout = QVBoxLayout(self.preview_panel)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        preview_header = QLabel("Program", self.preview_panel)
        preview_header.setFont(QFont("Segoe UI", 12, QFont.Bold))
        preview_header.setStyleSheet("background-color: #181818; color: #fff; padding: 10px 12px;")
        preview_header.setFixedHeight(40) # Fixed height for header
        preview_layout.addWidget(preview_header)

        # Preview area (QLabel to display frames)
        self.preview_label = QLabel("Preview", self.preview_panel)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #000; color: #888; font-size: 20pt; font-weight: bold;")
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_layout.addWidget(self.preview_label)

        # Preview controls
        self.preview_controls = QFrame(self.preview_panel)
        self.preview_controls.setStyleSheet("background-color: #181818;")
        preview_controls_layout = QHBoxLayout(self.preview_controls)

        # Play/Pause button
        self.play_button = QPushButton(self.preview_controls)
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay)) # Set initial icon
        self.play_button.clicked.connect(self.toggle_play)
        self.play_button.setFixedSize(30, 30) # Fixed size for button
        preview_controls_layout.addWidget(self.play_button)

        # Time slider
        self.time_slider = QSlider(Qt.Horizontal, self.preview_controls)
        self.time_slider.setRange(0, 0) # Initial range
        self.time_slider.sliderMoved.connect(self.on_slider_change_time)
        preview_controls_layout.addWidget(self.time_slider)

        # Time label
        self.time_label = QLabel("00:00 / 00:00", self.preview_controls)
        self.time_label.setStyleSheet("color: white;")
        preview_controls_layout.addWidget(self.time_label)

        preview_layout.addWidget(self.preview_controls)

        center_layout.addWidget(self.preview_panel, 2) # Stretch preview panel

        # Center Bottom: Timeline Panel (using PyQtTimelineView)
        self.timeline_view = PyQtTimelineView(self) # Create an instance of the PyQt timeline view
        self.timeline_view.setMinimumHeight(160)
        # Connect signals from the timeline view to slots in the main app
        self.timeline_view.playheadMoved.connect(self.on_playhead_move)
        self.timeline_view.clipDoubleClicked.connect(self.load_clip_into_preview)
        self.timeline_view.clipRightClicked.connect(self.show_timeline_clip_context_menu) # Connect right-click signal
        self.timeline_view.selectionChanged.connect(self.on_timeline_selection_changed) # Connect selection change signal

        center_layout.addWidget(self.timeline_view, 1) # Stretch timeline panel

        main_layout.addLayout(center_layout, 3) # Stretch center section

        # --- Right: Effects Panel (Placeholder) ---
        self.effects_panel = QFrame(self)
        self.effects_panel.setFrameShape(QFrame.StyledPanel)
        self.effects_panel.setFrameShadow(QFrame.Sunken)
        self.effects_panel.setMinimumWidth(200)
        self.effects_panel.setMaximumWidth(300) # Limit max width
        effects_layout = QVBoxLayout(self.effects_panel)
        effects_layout.setContentsMargins(0, 0, 0, 0)

        effects_header = QLabel("Effects", self.effects_panel)
        effects_header.setFont(QFont("Segoe UI", 12, QFont.Bold))
        effects_header.setStyleSheet("background-color: #181818; color: #fff; padding: 10px 12px;")
        effects_header.setFixedHeight(40) # Fixed height for header
        effects_layout.addWidget(effects_header)

        effects_content = QLabel("Effects Panel (Coming Soon)", self.effects_panel)
        effects_content.setAlignment(Qt.AlignCenter)
        effects_content.setStyleSheet("color: #888;")
        effects_layout.addWidget(effects_content)


        main_layout.addWidget(self.effects_panel)

        # --- Menu Bar ---
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        import_action = QAction("Import Video", self)
        import_action.triggered.connect(self.import_video)
        file_menu.addAction(import_action)

        export_action = QAction("Export Timeline", self)
        export_action.triggered.connect(self.export_timeline)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # --- Style (Optional: Dark Theme) ---
        self.setStyleSheet("""
            QMainWindow { background-color: #232323; }
            QFrame { background-color: #232323; border: 1px solid #333; }
            QLabel { color: white; }
            QPushButton {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #444;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #3a3a3a; }
            QPushButton:pressed { background-color: #1a1a1a; }
            QSlider::groove:horizontal {
                border: 1px solid #444;
                height: 8px;
                background: #333;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #00aaff;
                border: 1px solid #5c5c5c;
                width: 18px;
                margin: -2px 0; /* handle is placed on top of the groove */
                border-radius: 9px;
            }
             QScrollArea { border: none; } # Remove border from scroll area
             QWidget#media_scroll_area_content { background-color: #232323; } # Set background for content widget
        """)

        # Connect keyboard shortcuts (example: Delete selected clips)
        delete_action = QAction(self)
        delete_action.setShortcut(Qt.Key_Delete)
        delete_action.triggered.connect(self.delete_selected_timeline_clips)
        self.addAction(delete_action)


    def import_video(self):
        """Import video files to the project bin (media panel)."""
        filetypes = "Video files (*.mp4 *.avi *.mov *.mkv);;All files (*.*)"
        filepaths, _ = QFileDialog.getOpenFileNames(self, "Open Video Files", "", filetypes)
        if filepaths:
            for filepath in filepaths:
                self.add_thumbnail(filepath)

    def add_thumbnail(self, video_path):
        """Add a thumbnail for a video file in the media panel."""
        if not os.path.exists(video_path):
            QMessageBox.warning(self, "File Not Found", f"Video file not found: {os.path.basename(video_path)}")
            return

        try:
            # Extract the first frame of the video using OpenCV
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                QMessageBox.warning(self, "Error", f"Could not open video file: {os.path.basename(video_path)}")
                return

            success, frame = cap.read()
            if success:
                # Convert to QImage and scale for thumbnail
                height, width, channel = frame.shape
                bytes_per_line = 3 * width
                q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
                thumbnail_pixmap = QPixmap.fromImage(q_image).scaled(150, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            else:
                # Create a placeholder if frame cannot be read
                thumbnail_pixmap = QPixmap(150, 100)
                thumbnail_pixmap.fill(QColor("gray"))
                painter = QPainter(thumbnail_pixmap)
                painter.setPen(Qt.white)
                painter.setFont(QFont("Segoe UI", 10))
                painter.drawText(thumbnail_pixmap.rect(), Qt.AlignCenter, "No Preview")
                painter.end()


            # Get video duration
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration_sec = frame_count / fps if fps > 0 else 0
            cap.release()

            # Create a widget for the thumbnail item
            thumbnail_widget = QFrame(self.media_scroll_area_content)
            thumbnail_widget.setStyleSheet("border: 1px solid #444; background-color: #232323;")
            thumbnail_layout = QVBoxLayout(thumbnail_widget)
            thumbnail_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
            thumbnail_layout.setContentsMargins(5, 5, 5, 5)

            # Thumbnail image label
            image_label = QLabel(thumbnail_widget)
            image_label.setPixmap(thumbnail_pixmap)
            image_label.setAlignment(Qt.AlignCenter)
            thumbnail_layout.addWidget(image_label)

            # Filename label
            filename = os.path.basename(video_path)
            name_label = QLabel(filename, thumbnail_widget)
            name_label.setStyleSheet("color: white; border: none;") # Remove border from label
            name_label.setAlignment(Qt.AlignCenter)
            name_label.setWordWrap(True) # Wrap long filenames
            thumbnail_layout.addWidget(name_label)

            # Duration label
            minutes = int(duration_sec // 60)
            seconds = int(duration_sec % 60)
            duration_str = f"{minutes:02d}:{seconds:02d}"
            duration_label = QLabel(duration_str, thumbnail_widget)
            duration_label.setStyleSheet("color: yellow; font-size: 9pt; border: none;") # Remove border from label
            duration_label.setAlignment(Qt.AlignCenter)
            thumbnail_layout.addWidget(duration_label)

            # Store video path and duration in the widget for drag and drop
            thumbnail_widget.video_path = video_path
            thumbnail_widget.video_duration = duration_sec
            thumbnail_widget.video_frame_count = frame_count # Store frame count
            thumbnail_widget.video_fps = fps # Store fps


            self.media_scroll_area_layout.addWidget(thumbnail_widget)
            self.thumbnail_widgets.append(thumbnail_widget)

            # Enable drag and drop for the thumbnail widget
            self.enable_drag_drop(thumbnail_widget)

            # Bind double click to load clip into preview
            thumbnail_widget.mouseDoubleClickEvent = lambda event: self.load_clip_into_preview(video_path)


        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process video: {os.path.basename(video_path)}\n{e}")


    def enable_drag_drop(self, widget):
        """Enable drag and drop functionality for a widget."""
        # For simplicity, we'll handle drag and drop manually.
        # A more robust implementation might use QMimeData and dragEnterEvent/dropEvent.
        widget.mousePressEvent = lambda event: self.on_drag_start(event, widget)
        widget.mouseMoveEvent = lambda event: self.on_drag_motion(event, widget)
        widget.mouseReleaseEvent = lambda event: self.on_drag_stop(event, widget)

    def on_drag_start(self, event, widget):
        """Handle drag start for a thumbnail widget."""
        if event.button() == Qt.LeftButton:
            widget._drag_start_pos = event.pos() # Position relative to the widget
            widget._is_dragging = False # Flag to check if actual drag starts

    def on_drag_motion(self, event, widget):
        """Handle drag motion for a thumbnail widget."""
        if event.buttons() & Qt.LeftButton:
            # Check if the mouse has moved beyond a certain threshold to start dragging
            if not hasattr(widget, '_is_dragging') or not widget._is_dragging:
                 if (event.pos() - widget._drag_start_pos).manhattanLength() > QApplication.startDragDistance():
                     widget._is_dragging = True
                     # Start the drag operation (optional, for visual feedback)
                     # Create a QPixmap of the widget for drag visual
                     pixmap = widget.grab()
                     drag = QDrag(widget)
                     # Store video path and duration in QMimeData
                     mime_data = QMimeData()
                     # Use a custom MIME type for our clip data
                     mime_type = "application/x-video-clip-data"
                     # Package data into a QByteArray
                     data = QByteArray()
                     stream = QDataStream(data, QIODevice.WriteOnly)
                     stream.writeQString(widget.video_path)
                     stream.writeDouble(widget.video_duration)
                     stream.writeInt(widget.video_frame_count)
                     stream.writeDouble(widget.video_fps)
                     # You could also include thumbnail pixmap data here if needed
                     mime_data.setData(mime_type, data)

                     drag.setMimeData(mime_data)
                     drag.setPixmap(pixmap)
                     # Set the hotspot (the point on the pixmap that is under the cursor)
                     drag.setHotSpot(event.pos())

                     # Execute the drag
                     drag.exec_(Qt.CopyAction | Qt.MoveAction)


            # If dragging, you might update a drag preview window position here
            # (similar to the Tkinter version, but using PyQt widgets)
            # This is handled by the QDrag object when exec_() is called


    def on_drag_stop(self, event, widget):
        """Handle drag stop for a thumbnail widget."""
        # The drop handling is typically done in the target widget's dropEvent
        # In this case, the timeline_view would need to implement dragEnterEvent and dropEvent.
        # For the manual drag handling here, we just need to reset the drag flag.
        if hasattr(widget, '_is_dragging'):
            widget._is_dragging = False # Reset drag flag
        widget._drag_start_pos = None # Reset drag start position


    def load_clip_into_preview(self, video_path):
        """Loads the specified video clip into the preview pane for playback."""
        if not os.path.exists(video_path):
            QMessageBox.warning(self, "File Not Found", f"Video file not found: {os.path.basename(video_path)}")
            return

        # Stop current playback if any
        self.stop_video()

        try:
            # Open the new video file
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                QMessageBox.warning(self, "Error", f"Could not open video file: {os.path.basename(video_path)}")
                return

            # Update video playback variables
            self.current_video = cap
            self.current_video_path = video_path # Store current video path
            self.frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = cap.get(cv2.CAP_PROP_FPS)
            self.video_duration = self.frame_count / self.fps if self.fps > 0 else 0
            self.current_frame_pos = 0 # Start from the beginning of the loaded clip

            # Update time slider and label
            self.time_slider.setRange(0, int(self.video_duration * 1000)) # Use milliseconds for better precision
            self.time_slider.setValue(0)
            self.update_time_label()

            # Start the video timer
            if self.fps > 0:
                 self.video_timer.start(int(1000 / self.fps)) # Set timer interval based on FPS
            else:
                 self.video_timer.start(33) # Default to ~30 FPS if fps is 0


            print(f"Loaded clip: {os.path.basename(video_path)} into preview.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading video for preview: {e}")
            self.stop_video() # Ensure cleanup if an error occurs


    def stop_video(self):
        """Stops video playback and releases the video capture object."""
        self.video_playing = False
        self.video_timer.stop() # Stop the timer
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay)) # Set play icon

        if self.current_video is not None:
            self.current_video.release()
            self.current_video = None
            self.current_video_path = None # Clear current video path
            self.frame_count = 0
            self.fps = 0
            self.video_duration = 0
            self.current_frame_pos = 0
            # Reset slider range and position
            self.time_slider.setRange(0, 0)
            self.time_slider.setValue(0)
            self.update_time_label() # Update time label to 00:00 / 00:00

        # Clear preview label
        self.preview_label.clear()
        self.preview_label.setText("Preview") # Show placeholder text


    def export_timeline(self):
        """Export the timeline as a single video."""
        timeline_clips_data = self.timeline_view.scene.get_clips_data() # Get clip data from PyQt timeline scene
        if not timeline_clips_data:
            QMessageBox.information(self, "Export", "No clips in timeline to export.")
            return

        # Get output path
        output_path, _ = QFileDialog.getSaveFileName(self, "Export Timeline", "", "MP4 files (*.mp4);;All files (*.*)")
        if not output_path:
            return

        # Sort clips by start time
        sorted_clips = sorted(timeline_clips_data, key=lambda x: x.get('start_time', 0))

        try:
            # Initialize video writer
            first_valid_clip_data = None
            for clip_data in sorted_clips:
                clip_path = clip_data.get('video_path')
                if clip_path and os.path.exists(clip_path):
                     first_valid_clip_data = clip_data
                     break

            if not first_valid_clip_data:
                 QMessageBox.critical(self, "Export Error", "No valid video files found in timeline clips.")
                 return

            first_clip_cap = cv2.VideoCapture(first_valid_clip_data['video_path'])
            if not first_clip_cap.isOpened():
                 QMessageBox.critical(self, "Export Error", f"Could not open the first clip for export: {os.path.basename(first_valid_clip_data['video_path'])}")
                 return

            frame_width = int(first_clip_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(first_clip_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = first_clip_cap.get(cv2.CAP_PROP_FPS)
            first_clip_cap.release()

            if fps == 0:
                 QMessageBox.critical(self, "Export Error", "Cannot determine frame rate from the first clip.")
                 return

            # Define the codec and create VideoWriter object
            fourcc = cv2.VideoWriter_fourcc(*'mp4v') # Or 'XVID', 'MJPG'
            out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))

            if not out.isOpened():
                 QMessageBox.critical(self, "Export Error", "Could not initialize video writer. Check codec availability or file path permissions.")
                 return

            # Process each clip
            for clip_data in sorted_clips:
                video_path = clip_data.get('video_path')
                if not video_path or not os.path.exists(video_path):
                     print(f"Warning: Skipping missing clip file during export: {os.path.basename(video_path if video_path else 'N/A')}")
                     continue

                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                     print(f"Warning: Could not open clip for reading during export: {os.path.basename(video_path)}")
                     continue

                # Read and write frames from the clip
                # In a real editor, you'd handle trimming/splitting based on clip_data start/end points
                # For this simple export, we just concatenate the full clips in order
                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break
                    # Ensure frame size matches the output writer size (simple resizing for now)
                    if frame.shape[1] != frame_width or frame.shape[0] != frame_height:
                         frame = cv2.resize(frame, (frame_width, frame_height))
                    out.write(frame)
                cap.release()

            out.release()
            QMessageBox.information(self, "Export", "Timeline exported successfully!")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export timeline: {str(e)}")
        finally:
            if 'out' in locals() and out.isOpened():
                 out.release()


    def toggle_play(self):
        """Toggle video playback."""
        if self.current_video is None:
            # If no video is loaded in preview, try to load the clip at the current playhead position
            timeline_clips_data = self.timeline_view.scene.get_clips_data()
            if timeline_clips_data:
                playhead_x = self.timeline_view.scene.playhead_item.pos().x()
                playhead_time = playhead_x / self.timeline_view.timeline_scale

                target_clip_data = None
                # Find the clip the playhead is currently over
                for clip_data in sorted(timeline_clips_data, key=lambda x: x.get('start_time', 0)):
                     clip_start_time = clip_data.get('start_time', 0)
                     clip_duration = clip_data.get('duration', 0)
                     if clip_start_time <= playhead_time < clip_start_time + clip_duration:
                         target_clip_data = clip_data
                         break
                     elif playhead_time < clip_start_time:
                          # Playhead is before this clip, so the previous clip (if any) or no clip is the target
                          break # Since clips are sorted, no need to check further

                # If playhead is before the first clip, load the first clip
                if target_clip_data is None and timeline_clips_data:
                     target_clip_data = sorted(timeline_clips_data, key=lambda x: x.get('start_time', 0))[0]
                     # Adjust playhead to the start of the first clip if it was before it
                     if playhead_time < target_clip_data.get('start_time', 0):
                          self.on_playhead_move(target_clip_data.get('start_time', 0) * self.timeline_view.timeline_scale)


                if target_clip_data and target_clip_data.get('video_path'):
                    self.load_clip_into_preview(target_clip_data['video_path'])
                    # Set playback position within the newly loaded clip based on timeline playhead time
                    time_in_clip = playhead_time - target_clip_data.get('start_time', 0)
                    if self.current_video is not None and self.fps > 0:
                         frame_position = int(time_in_clip * self.fps)
                         frame_position = max(0, min(frame_position, self.frame_count - 1))
                         self.current_video.set(cv2.CAP_PROP_POS_FRAMES, frame_position)
                         self.current_frame_pos = frame_position
                         self.update_time_label()
                         # Update the slider based on the position within the new clip's duration
                         if self.video_duration > 0:
                              slider_value = (time_in_clip / self.video_duration) * self.time_slider.maximum() # Scale to slider range (milliseconds)
                              self.time_slider.blockSignals(True) # Block signals to prevent recursive calls
                              self.time_slider.setValue(int(slider_value))
                              self.time_slider.blockSignals(False) # Unblock signals


                else:
                     QMessageBox.information(self, "Playback", "No valid clip found at the current playhead position.")
                     return # Exit if no valid clip or path

            else:
                 QMessageBox.information(self, "Playback", "No clips on the timeline to play.")
                 return # Exit if no clips on timeline


        # If a video is already loaded, just toggle play/pause
        if self.current_video is not None:
            self.video_playing = not self.video_playing
            if self.video_playing:
                self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause)) # Set pause icon
                if not self.video_timer.isActive():
                     if self.fps > 0:
                          self.video_timer.start(int(1000 / self.fps))
                     else:
                          self.video_timer.start(33) # Default to ~30 FPS
            else:
                self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay)) # Set play icon
                self.video_timer.stop()


    def update_video_frame(self):
        """Update video frame in preview and move timeline playhead."""
        if self.current_video is not None and self.video_playing:
            ret, frame = self.current_video.read()
            if ret:
                self.current_frame_pos += 1
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Convert to QImage and then QPixmap for the QLabel
                height, width, channel = frame.shape
                bytes_per_line = 3 * width
                q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(q_image)

                # Scale pixmap to fit the preview label while maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.preview_label.setPixmap(scaled_pixmap)
                self.preview_label.setAlignment(Qt.AlignCenter) # Center the image


                self.update_time_label()

                # Update slider position based on current frame (using time in seconds)
                if self.fps > 0:
                    current_time_in_clip = self.current_frame_pos / self.fps
                    if self.video_duration > 0:
                         slider_value = (current_time_in_clip / self.video_duration) * self.time_slider.maximum() # Scale to slider range (milliseconds)
                         self.time_slider.blockSignals(True) # Block signals to prevent recursive calls
                         self.time_slider.setValue(int(slider_value))
                         self.time_slider.blockSignals(False) # Unblock signals


                # Move timeline playhead
                # Calculate time in seconds within the current clip
                time_in_current_clip = self.current_frame_pos / self.fps if self.fps > 0 else 0

                # Find the start time of the current clip on the timeline
                current_clip_start_time = 0
                if self.current_video_path:
                     timeline_clips_data = self.timeline_view.scene.get_clips_data()
                     for clip_data in timeline_clips_data:
                         if clip_data.get('video_path') == self.current_video_path:
                             current_clip_start_time = clip_data.get('start_time', 0)
                             break

                # Calculate the absolute time on the timeline
                absolute_timeline_time = current_clip_start_time + time_in_current_clip

                # Calculate the corresponding playhead position in pixels
                playhead_pixel_pos = absolute_timeline_time * self.timeline_view.timeline_scale
                self.timeline_view.move_playhead_to_scene_pos(playhead_pixel_pos)


            else:
                # End of video or error reading frame
                self.video_playing = False
                self.video_timer.stop()
                self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay)) # Set play icon

                # Set frame position and slider to the end of the video
                self.current_frame_pos = self.frame_count
                self.update_time_label()
                self.time_slider.blockSignals(True)
                self.time_slider.setValue(self.time_slider.maximum())
                self.time_slider.blockSignals(False)

                # Optionally, reset playhead to the end of the clip or move to the next clip
                # For now, it stops at the end of the currently loaded clip.
                # To move to the next clip, you'd need to find the next clip on the timeline
                # and call load_clip_into_preview with its path and set the playhead position.


    def update_time_label(self):
        """Update the time display label."""
        current_msec = int((self.current_frame_pos / self.fps) * 1000) if self.fps > 0 else 0
        total_msec = int(self.video_duration * 1000)

        current_time = QTime(0, 0).addMSecs(current_msec)
        total_time = QTime(0, 0).addMSecs(total_msec)

        # Format time based on total duration (HH:MM:SS or MM:SS)
        if total_msec >= 3600000: # Use HH:MM:SS if total duration is an hour or more
             time_text = f"{current_time.toString('HH:mm:ss')} / {total_time.toString('HH:mm:ss')}"
        else: # Use MM:SS
             time_text = f"{current_time.toString('mm:ss')} / {total_time.toString('mm:ss')}"

        self.time_label.setText(time_text)


    def on_slider_change_time(self, value):
        """Handle time slider change - based on milliseconds."""
        if self.current_video is not None and self.fps > 0:
            # Convert slider value (milliseconds) to frame position
            time_in_seconds = value / 1000.0
            frame_position = int(time_in_seconds * self.fps)

            # Ensure frame position is within bounds
            frame_position = max(0, min(frame_position, self.frame_count - 1))

            # Only update video frame if the position has changed significantly
            if abs(frame_position - self.current_frame_pos) > 1: # Check for more than 1 frame difference
                self.current_video.set(cv2.CAP_PROP_POS_FRAMES, frame_position)
                self.current_frame_pos = frame_position
                self.update_time_label()

                # Move timeline playhead based on slider change within the current clip
                time_in_current_clip = self.current_frame_pos / self.fps if self.fps > 0 else 0
                current_clip_start_time = 0
                if self.current_video_path:
                     timeline_clips_data = self.timeline_view.scene.get_clips_data()
                     for clip_data in timeline_clips_data:
                         if clip_data.get('video_path') == self.current_video_path:
                             current_clip_start_time = clip_data.get('start_time', 0)
                             break

                absolute_timeline_time = current_clip_start_time + time_in_current_clip
                playhead_pixel_pos = absolute_timeline_time * self.timeline_view.timeline_scale
                self.timeline_view.move_playhead_to_scene_pos(playhead_pixel_pos)


    def on_playhead_move(self, x_pos):
        """Handle playhead movement in timeline (triggered by timeline view)."""
        # Convert playhead pixel position to time in seconds
        timeline_time_in_seconds = x_pos / self.timeline_view.timeline_scale

        # Find which clip on the timeline corresponds to this time
        target_clip_data = None
        clip_start_time = 0

        timeline_clips_data = self.timeline_view.scene.get_clips_data()
        # Sort clips by start time to make this efficient
        sorted_clips = sorted(timeline_clips_data, key=lambda x: x.get('start_time', 0))

        for clip_data in sorted_clips:
             clip_start_time = clip_data.get('start_time', 0)
             clip_duration = clip_data.get('duration', 0)
             # Check if the timeline time falls within this clip's duration (with a small tolerance)
             if clip_start_time <= timeline_time_in_seconds < clip_start_time + clip_duration + 0.001: # Add tolerance
                 target_clip_data = clip_data
                 break # Found the clip

        if target_clip_data:
            # Calculate the time position within the target clip
            time_in_target_clip = timeline_time_in_seconds - clip_start_time

            # If the playhead moved to a different clip than the one currently in preview
            if self.current_video_path != target_clip_data.get('video_path'):
                print(f"Playhead moved to a new clip: {os.path.basename(target_clip_data.get('video_path', 'N/A'))}")
                # Load the new clip into the preview
                video_path = target_clip_data.get('video_path')
                if video_path:
                    self.load_clip_into_preview(video_path)
                    # Set the frame position within the newly loaded clip
                    if self.current_video is not None and self.fps > 0:
                        frame_position = int(time_in_target_clip * self.fps)
                        # Ensure frame position is within bounds of the new clip
                        frame_position = max(0, min(frame_position, self.frame_count - 1))
                        self.current_video.set(cv2.CAP_PROP_POS_FRAMES, frame_position)
                        self.current_frame_pos = frame_position
                        self.update_time_label()
                        # Update the slider based on the position within the new clip's duration
                        if self.video_duration > 0:
                             slider_value = (time_in_target_clip / self.video_duration) * self.time_slider.maximum()
                             self.time_slider.blockSignals(True)
                             self.time_slider.setValue(int(slider_value))
                             self.time_slider.blockSignals(False)


            # If the playhead is still within the same clip that's in preview
            elif self.current_video is not None and self.fps > 0:
                 # Update the frame position in the current video
                 time_in_current_clip = timeline_time_in_seconds - clip_start_time # Recalculate based on current playhead position
                 frame_position = int(time_in_current_clip * self.fps)
                 # Ensure frame position is within bounds
                 frame_position = max(0, min(frame_position, self.frame_count - 1))

                 # Only update video frame if the position has changed significantly
                 if abs(frame_position - self.current_frame_pos) > 1: # Check for more than 1 frame difference
                     self.current_video.set(cv2.CAP_PROP_POS_FRAMES, frame_position)
                     self.current_frame_pos = frame_position
                     self.update_time_label()
                     # Update the slider based on the position within the current clip's duration
                     if self.video_duration > 0:
                         slider_value = (time_in_current_clip / self.video_duration) * self.time_slider.maximum()
                         self.time_slider.blockSignals(True)
                         self.time_slider.setValue(int(slider_value))
                         self.time_slider.blockSignals(False)

        else:
            # Playhead is not over any clip. Stop playback and clear preview.
            self.stop_video()
            # Clear preview label
            self.preview_label.clear()
            self.preview_label.setText("Preview") # Show placeholder text
            self.time_label.setText("00:00 / 00:00")
            self.time_slider.setRange(0, 0)
            self.time_slider.setValue(0)

    def show_timeline_clip_context_menu(self, clip_item, scene_pos):
        """Show context menu for a timeline clip."""
        menu = QMenu(self)
        # Add actions to the menu
        split_action = menu.addAction("Split at Playhead")
        trim_start_action = menu.addAction("Trim Start to Playhead")
        trim_end_action = menu.addAction("Trim End to Playhead")
        menu.addSeparator()
        delete_action = menu.addAction("Delete Clip")

        # Connect actions to slots
        split_action.triggered.connect(lambda: self.split_timeline_clip(clip_item))
        trim_start_action.triggered.connect(lambda: self.trim_timeline_clip_start(clip_item))
        trim_end_action.triggered.connect(lambda: self.trim_timeline_clip_end(clip_item))
        delete_action.triggered.connect(lambda: self.delete_timeline_clip(clip_item))

        # Show the menu at the global position of the mouse event
        menu.exec_(self.timeline_view.mapToGlobal(self.timeline_view.mapFromScene(scene_pos)))


    def split_timeline_clip(self, clip_item):
        """Split the given timeline clip at the current playhead position."""
        playhead_x = self.timeline_view.scene.playhead_item.pos().x()
        clip_x = clip_item.pos().x()
        clip_width = clip_item.rect().width()

        # Check if playhead is within the clip's horizontal bounds (with tolerance)
        tolerance = 1 # pixels
        if playhead_x <= clip_x + tolerance or playhead_x >= clip_x + clip_width - tolerance:
            QMessageBox.information(self, "Split Clip", "Playhead must be positioned within the clip.")
            return

        # Calculate split point in time
        timeline_scale = self.timeline_view.timeline_scale
        playhead_time = playhead_x / timeline_scale
        clip_start_time = clip_item.clip_data.get('start_time', 0)
        clip_duration = clip_item.clip_data.get('duration', 0)
        clip_fps = clip_item.clip_data.get('fps', 0)

        time_in_clip = playhead_time - clip_start_time

        # Calculate new durations and frame counts
        first_part_duration = time_in_clip
        second_part_duration = clip_duration - time_in_clip

        first_part_frames = int(first_part_duration * clip_fps) if clip_fps > 0 else 0
        second_part_frames = clip_item.clip_data.get('frame_count', 0) - first_part_frames


        # Update the first part (the original clip item)
        clip_item.clip_data['duration'] = first_part_duration
        clip_item.clip_data['frame_count'] = first_part_frames
        # Update visual width
        new_width = max(50, int(first_part_duration * timeline_scale))
        clip_item.setRect(clip_item.rect().x(), clip_item.rect().y(), new_width, clip_item.rect().height())
        clip_item.text_item.setTextWidth(new_width - 10) # Update text wrap

        # Create data for the second part (new clip)
        second_part_data = clip_item.clip_data.copy() # Copy existing data
        second_part_data['duration'] = second_part_duration
        second_part_data['frame_count'] = second_part_frames
        second_part_data['start_time'] = playhead_time # New start time is playhead time
        second_part_data['filename'] = os.path.basename(second_part_data.get('video_path', 'Unknown')) + " (2)" # Rename


        # Add the second part as a new clip item
        # Position the new clip at the playhead's x position and the same track y
        new_clip_item = self.timeline_view.scene.add_clip(second_part_data, playhead_x, clip_item.pos().y())

        # Deselect all and select the two new parts (original updated and new)
        self.timeline_view.scene.clearSelection()
        clip_item.setSelected(True)
        if new_clip_item:
             new_clip_item.setSelected(True)

        # Update scene rectangle
        self.timeline_view.scene.update_scene_rect()


    def trim_timeline_clip_start(self, clip_item):
        """Trim the start of the given timeline clip to the current playhead position."""
        playhead_x = self.timeline_view.scene.playhead_item.pos().x()
        clip_x = clip_item.pos().x()
        clip_width = clip_item.rect().width()

        # Check if playhead is within the clip's horizontal bounds (with tolerance)
        tolerance = 1 # pixels
        if playhead_x <= clip_x + tolerance or playhead_x >= clip_x + clip_width - tolerance:
            QMessageBox.information(self, "Trim Clip", "Playhead must be positioned within the clip.")
            return

        # Calculate trim point in time
        timeline_scale = self.timeline_view.timeline_scale
        playhead_time = playhead_x / timeline_scale
        clip_start_time = clip_item.clip_data.get('start_time', 0)
        clip_duration = clip_item.clip_data.get('duration', 0)
        clip_fps = clip_item.clip_data.get('fps', 0)

        time_to_trim = playhead_time - clip_start_time

        # Calculate new duration and frame count
        new_duration = clip_duration - time_to_trim
        trimmed_frames = int(time_to_trim * clip_fps) if clip_fps > 0 else 0
        new_frame_count = clip_item.clip_data.get('frame_count', 0) - trimmed_frames

        # Update the clip data
        clip_item.clip_data['start_time'] = playhead_time # New start time is playhead time
        clip_item.clip_data['duration'] = new_duration
        clip_item.clip_data['frame_count'] = new_frame_count

        # Update visual representation (position and width)
        new_width = max(50, int(new_duration * timeline_scale))
        clip_item.setPos(playhead_x, clip_item.pos().y()) # New position is playhead x
        clip_item.setRect(0, 0, new_width, clip_item.rect().height()) # Rect relative to item's new position
        clip_item.text_item.setTextWidth(new_width - 10) # Update text wrap

        # Update scene rectangle
        self.timeline_view.scene.update_scene_rect()


    def trim_timeline_clip_end(self, clip_item):
        """Trim the end of the given timeline clip to the current playhead position."""
        playhead_x = self.timeline_view.scene.playhead_item.pos().x()
        clip_x = clip_item.pos().x()
        clip_width = clip_item.rect().width()

        # Check if playhead is within the clip's horizontal bounds (with tolerance)
        tolerance = 1 # pixels
        if playhead_x <= clip_x + tolerance or playhead_x >= clip_x + clip_width - tolerance:
            QMessageBox.information(self, "Trim Clip", "Playhead must be positioned within the clip.")
            return

        # Calculate trim point in time
        timeline_scale = self.timeline_view.timeline_scale
        playhead_time = playhead_x / timeline_scale
        clip_start_time = clip_item.clip_data.get('start_time', 0)
        clip_duration = clip_item.clip_data.get('duration', 0)
        clip_fps = clip_item.clip_data.get('fps', 0)

        time_to_trim = (clip_start_time + clip_duration) - playhead_time

        # Calculate new duration and frame count
        new_duration = clip_duration - time_to_trim
        trimmed_frames = int(time_to_trim * clip_fps) if clip_fps > 0 else 0
        new_frame_count = clip_item.clip_data.get('frame_count', 0) - trimmed_frames # This might not be accurate for trimming end

        # Recalculate frame count based on new duration and original start frame
        # This requires knowing the original start frame index of the clip, which is not stored.
        # For simplicity, let's just update the duration and visual width for now.
        # A more robust implementation would track original start frame index.
        new_frame_count = int(new_duration * clip_fps) if clip_fps > 0 else 0


        # Update the clip data
        clip_item.clip_data['duration'] = new_duration
        clip_item.clip_data['frame_count'] = new_frame_count # Update frame count based on new duration


        # Update visual representation (width)
        new_width = max(50, int(new_duration * timeline_scale))
        # The position remains the same, only the width changes
        clip_item.setRect(clip_item.rect().x(), clip_item.rect().y(), new_width, clip_item.rect().height())
        clip_item.text_item.setTextWidth(new_width - 10) # Update text wrap


        # Update scene rectangle
        self.timeline_view.scene.update_scene_rect()


    def delete_timeline_clip(self, clip_item):
        """Delete the given timeline clip from the scene."""
        if clip_item in self.timeline_view.scene.timeline_clips_items:
            # Remove from scene's lists
            self.timeline_view.scene.timeline_clips_items.remove(clip_item)
            if clip_item.clip_data in self.timeline_view.scene.timeline_data:
                self.timeline_view.scene.timeline_data.remove(clip_item.clip_data)

            # Remove from the scene
            self.timeline_view.scene.removeItem(clip_item)

            # Update the scene rectangle after deletion
            self.timeline_view.scene.update_scene_rect()

            # Emit selection changed signal as selected items are deleted
            self.timeline_view.scene.selectionChanged.emit() # Emit from the scene


    def delete_selected_timeline_clips(self):
        """Delete all selected clips from the timeline."""
        selected_items = self.timeline_view.scene.selectedItems()
        if not selected_items:
            return

        # Confirmation dialog (optional)
        # reply = QMessageBox.question(self, 'Delete Clips', 'Are you sure you want to delete the selected clips?',
        #                              QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        # if reply == QMessageBox.No:
        #     return

        # Create a list of clips to delete to avoid modifying the list while iterating
        clips_to_delete = [item for item in selected_items if isinstance(item, PyQtTimelineClip)]

        for clip_item in clips_to_delete:
            self.delete_timeline_clip(clip_item) # Use the single clip deletion logic


    def on_timeline_selection_changed(self):
        """Handle selection changes in the timeline view."""
        # This slot is connected to the timeline_view.selectionChanged signal.
        # You can use self.timeline_view.get_selected_clips_data() to get the selected clips' data.
        # Example: print the number of selected clips
        # print(f"Timeline selection changed. Selected clips: {len(self.timeline_view.get_selected_clips_data())}")
        pass # Implement logic based on timeline selection if needed


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Set a dark fusion style (optional)
    app.setStyle("Fusion")
    # Set a dark color palette (optional)
    palette = app.palette()
    palette.setColor(palette.Window, QColor(53, 53, 53))
    palette.setColor(palette.WindowText, Qt.white)
    palette.setColor(palette.Base, QColor(25, 25, 25))
    palette.setColor(palette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(palette.ToolTipBase, Qt.white)
    palette.setColor(palette.ToolTipText, Qt.white)
    palette.setColor(palette.Text, Qt.white)
    palette.setColor(palette.Button, QColor(53, 53, 53))
    palette.setColor(palette.ButtonText, Qt.white)
    palette.setColor(palette.BrightText, Qt.red)
    palette.setColor(palette.Link, QColor(42, 130, 218))
    palette.setColor(palette.Highlight, QColor(42, 130, 218))
    palette.setColor(palette.HighlightedText, Qt.black)
    app.setPalette(palette)


    mainWin = VideoEditorApp()
    mainWin.show()
    sys.exit(app.exec_())
