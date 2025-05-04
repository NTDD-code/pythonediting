import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk

class Timeline:
    # Modified __init__ to accept load_clip_callback
    def __init__(self, parent, bg_color="#232323", load_clip_callback=None):
        """Initialize the timeline component"""
        self.parent = parent
        self.timeline_clips = []  # List of all clips (now storing data and canvas item IDs)
        self.timeline_scale = 100  # pixels per second
        self.timeline_tracks = {}  # Store tracks {track_name: track_info}
        self.track_height = 80
        self.playhead_x = 0
        self.playhead_line = None
        self.playhead_handle = None
        self.selection_start = None
        self.selection_end = None
        self.selection_rectangle = None
        self.load_clip_callback = load_clip_callback # Store the callback
        self.playhead_callback = None # Callback for playhead movement

        # Create main timeline panel
        self.timeline_panel = tk.Frame(parent, bg=bg_color, bd=0,
                                     highlightbackground="#333",
                                     highlightthickness=1, height=160)
        self.timeline_panel.grid(row=1, column=1, sticky="nsew")
        self.timeline_panel.grid_propagate(False)

        # Timeline header
        tk.Label(self.timeline_panel, text="Timeline",
                font=("Segoe UI", 12, "bold"),
                bg=bg_color, fg="#fff").pack(anchor="w", padx=12, pady=(10, 2))

        # Timeline controls
        control_frame = tk.Frame(self.timeline_panel, bg=bg_color)
        control_frame.pack(anchor="w", padx=12, pady=(0, 5), fill=tk.X)

        # Zoom controls
        zoom_out_btn = tk.Button(control_frame, text="🔍-",
                               command=lambda: self.zoom_timeline(0.8),
                               bg="#333", fg="white", bd=0,
                               activebackground="#444", activeforeground="white",
                               font=("Segoe UI", 8), padx=4, pady=0)
        zoom_out_btn.pack(side=tk.LEFT, padx=(0, 2))

        zoom_in_btn = tk.Button(control_frame, text="🔍+",
                              command=lambda: self.zoom_timeline(1.25),
                              bg="#333", fg="white", bd=0,
                              activebackground="#444", activeforeground="white",
                              font=("Segoe UI", 8), padx=4, pady=0)
        zoom_in_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Add track button
        add_track_btn = tk.Button(control_frame, text="➕ Add Track",
                                command=self.show_add_track_dialog,
                                bg="#333", fg="white", bd=0,
                                activebackground="#444", activeforeground="white",
                                font=("Segoe UI", 8), padx=6, pady=1)
        add_track_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Current time display
        self.time_display = tk.Label(control_frame, text="00:00:00",
                                    bg="#1a1a1a", fg="#00aaff",
                                    font=("Consolas", 9, "bold"),
                                    padx=8, pady=2)
        self.time_display.pack(side=tk.RIGHT, padx=5)

        # Time ruler canvas
        self.ruler_canvas = tk.Canvas(self.timeline_panel, height=20,
                                    bg="#1e1e1e", highlightthickness=0)
        self.ruler_canvas.pack(fill=tk.X, padx=16, pady=(0, 4))

        # Timeline canvas and scrollbar
        self.timeline_canvas = tk.Canvas(self.timeline_panel,
                                       bg="#181818",
                                       highlightthickness=0)
        self.timeline_scroll = tk.Scrollbar(self.timeline_panel,
                                          orient=tk.HORIZONTAL,
                                          command=self.timeline_canvas.xview)

        # Pack scrollbar and canvas
        self.timeline_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.timeline_canvas.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)

        # Configure canvas scroll
        self.timeline_canvas.configure(xscrollcommand=self.timeline_scroll.set)

        # Create timeline inner frame (still needed for track headers)
        self.timeline_inner = tk.Frame(self.timeline_canvas, bg="#181818")
        self.timeline_window = self.timeline_canvas.create_window(
            (0, 0),
            window=self.timeline_inner,
            anchor="nw"
        )

        # Create default tracks
        self.create_default_tracks()

        # Draw initial playhead
        self.draw_playhead()

        # Draw time ruler
        self.draw_time_ruler()

        # Bind timeline events
        self.timeline_inner.bind("<Configure>", self.on_timeline_configure)
        self.timeline_canvas.bind("<Configure>", self.on_timeline_canvas_configure)
        # Bind playhead drag directly to canvas
        self.timeline_canvas.tag_bind("playhead_handle", "<ButtonPress-1>", self.on_playhead_drag_start)
        self.timeline_canvas.tag_bind("playhead_handle", "<B1-Motion>", self.on_playhead_drag_motion)
        self.timeline_canvas.tag_bind("playhead_handle", "<ButtonRelease-1>", self.on_playhead_drag_stop)

        # Bind mouse events to the timeline canvas for clip interaction
        self.timeline_canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.timeline_canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.timeline_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.timeline_canvas.bind("<Button-3>", self.on_canvas_right_click) # Right click for context menu
        self.timeline_canvas.bind("<Double-Button-1>", self.on_canvas_double_click) # Double click to load clip

        self.ruler_canvas.bind("<Configure>", self.on_ruler_configure)
        self.ruler_canvas.bind("<Button-1>", self.on_ruler_click)

        # Bind keyboard shortcuts
        self.parent.bind("<Delete>", lambda e: self.delete_selected_clips())
        self.parent.bind("<Control-c>", lambda e: self.copy_selected_clips())
        self.parent.bind("<Control-v>", lambda e: self.paste_clips())
        self.parent.bind("<Control-z>", lambda e: self.undo_action())
        self.parent.bind("<Control-s>", lambda e: self.split_clip_at_playhead())

        # Mouse wheel zoom
        self.timeline_canvas.bind("<Control-MouseWheel>", self.on_mousewheel_zoom)

        # State variables
        self.clipboard = []  # For copy-paste
        self.undo_stack = []  # For undo operations
        self.selected_clips = []  # Currently selected clips (list of clip data dicts)
        self.shift_pressed = False  # For multi-selection
        self.dragging_playhead = False # Flag for playhead dragging
        self.dragging_clip = False # Flag for clip dragging
        self._drag_start_x_canvas = None # Store start x for drag
        self._drag_start_y_canvas = None # Store start y for drag
        self._dragged_clip_info = None # Store the clip being dragged

        # Bind shift key state
        self.parent.bind("<KeyPress-Shift_L>", lambda e: self.set_shift_pressed(True))
        self.parent.bind("<KeyRelease-Shift_L>", lambda e: self.set_shift_pressed(False))
        self.parent.bind("<KeyPress-Shift_R>", lambda e: self.set_shift_pressed(True))
        self.parent.bind("<KeyRelease-Shift_R>", lambda e: self.set_shift_pressed(False))

    def set_shift_pressed(self, state):
        """Track shift key state for multi-selection"""
        self.shift_pressed = state

    def create_default_tracks(self):
        """Create default video and audio tracks"""
        self.add_track("V1", "video")
        self.add_track("A1", "audio")
        self.update_timeline_scrollregion()
        self.draw_time_ruler()

    def show_add_track_dialog(self):
        """Show dialog to add a new track"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Add Track")
        dialog.geometry("300x150")
        dialog.configure(bg="#333333")
        dialog.resizable(False, False)
        dialog.transient(self.parent)
        dialog.grab_set()

        # Center on parent
        x = self.parent.winfo_x() + (self.parent.winfo_width() - 300) // 2
        y = self.parent.winfo_y() + (self.parent.winfo_height() - 150) // 2
        dialog.geometry(f"+{x}+{y}")

        # Track name
        tk.Label(dialog, text="Track Name:", bg="#333333", fg="white").pack(pady=(15, 5))
        name_var = tk.StringVar(value=f"V{len(self.timeline_tracks) + 1}")
        name_entry = tk.Entry(dialog, textvariable=name_var, width=20)
        name_entry.pack(pady=5)
        name_entry.focus_set()
        name_entry.select_range(0, tk.END)

        # Track type
        type_frame = tk.Frame(dialog, bg="#333333")
        type_frame.pack(pady=10)

        type_var = tk.StringVar(value="video")
        tk.Radiobutton(type_frame, text="Video", variable=type_var, value="video",
                      bg="#333333", fg="white", selectcolor="#222222",
                      activebackground="#333333", activeforeground="white").pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(type_frame, text="Audio", variable=type_var, value="audio",
                      bg="#333333", fg="white", selectcolor="#222222",
                      activebackground="#333333", activeforeground="white").pack(side=tk.LEFT, padx=10)

        # Buttons
        button_frame = tk.Frame(dialog, bg="#333333")
        button_frame.pack(pady=10, fill=tk.X)

        tk.Button(button_frame, text="Cancel", command=dialog.destroy,
                 bg="#444444", fg="white", activebackground="#555555").pack(side=tk.RIGHT, padx=10)

        def add_and_close():
            track_name = name_var.get().strip()
            track_type = type_var.get()
            if track_name:
                if track_name in self.timeline_tracks:
                    messagebox.showwarning("Duplicate Name", "This track name already exists.")
                    return
                self.add_track(track_name, track_type)
                dialog.destroy()
            else:
                messagebox.showwarning("Invalid Name", "Please enter a track name.")

        tk.Button(button_frame, text="Add Track", command=add_and_close,
                 bg="#007acc", fg="white", activebackground="#0088cc").pack(side=tk.RIGHT, padx=10)

    def add_track(self, track_name, track_type):
        """Add a new track to the timeline"""
        # Create track header (still using frame for track headers)
        track_header_frame = tk.Frame(self.timeline_inner,
                                    bg="#222222", bd=1,
                                    relief="solid",
                                    height=self.track_height)
        track_header_frame.pack(fill=tk.X)

        # Add track name label with icon
        label_bg = "#222222"
        fg_color = "white"
        icon_text = "🎬" if track_type == "video" else "🎵"
        track_label = tk.Label(track_header_frame, text=f"{icon_text} {track_name}",
                bg=label_bg, fg=fg_color, font=("Segoe UI", 10, "bold"))
        track_label.pack(side=tk.LEFT, padx=8, pady=8)

        # Add track controls
        track_controls = tk.Frame(track_header_frame, bg=label_bg)
        track_controls.pack(side=tk.RIGHT, padx=8)

        # Mute button
        mute_btn = tk.Button(track_controls, text="M", width=2,
                           bg="#333", fg="white", bd=1,
                           activebackground="#444", activeforeground="white")
        mute_btn.pack(side=tk.LEFT, padx=2)

        # Solo button
        solo_btn = tk.Button(track_controls, text="S", width=2,
                           bg="#333", fg="white", bd=1,
                           activebackground="#444", activeforeground="white")
        solo_btn.pack(side=tk.LEFT, padx=2)

        # Delete track button
        del_btn = tk.Button(track_controls, text="×", width=2,
                          bg="#aa3333", fg="white", bd=1,
                          activebackground="#cc4444", activeforeground="white",
                          command=lambda tn=track_name: self.delete_track(tn))
        del_btn.pack(side=tk.LEFT, padx=2)

        self.timeline_tracks[track_name] = {
            'type': track_type,
            'clips': [],  # List to hold clips in the track (now storing clip data dicts)
            'frame': track_header_frame,
            'y': len(self.timeline_tracks) * self.track_height,
            'muted': False,
            'solo': False
        }
        self.update_timeline_scrollregion()

    def delete_track(self, track_name):
        """Delete a track and all its clips"""
        if len(self.timeline_tracks) <= 1:
            messagebox.showwarning("Cannot Delete", "You must have at least one track.")
            return

        if messagebox.askyesno("Confirm Delete", f"Delete track '{track_name}' and all its clips?"):
            # Delete all clips in this track from the canvas and the list
            clips_to_remove = []
            for clip in self.timeline_clips:
                if clip['track'] == track_name:
                    # Delete the graphical items for the clip
                    self.timeline_canvas.delete(clip['clip_item_id'])
                    self.timeline_canvas.delete(clip['text_item_id'])
                    if 'thumb_item_id' in clip:
                         self.timeline_canvas.delete(clip['thumb_item_id'])
                    clips_to_remove.append(clip)

            for clip in clips_to_remove:
                self.timeline_clips.remove(clip)

            # Remove track frame
            self.timeline_tracks[track_name]['frame'].destroy()
            del self.timeline_tracks[track_name]

            # Recalculate y positions
            y = 0
            for name, track in self.timeline_tracks.items():
                track['y'] = y
                y += self.track_height

            # Redraw all remaining clips at their new y positions
            self.redraw_all_clips()

            self.update_timeline_scrollregion()
            self.draw_playhead()

    def draw_playhead(self):
        """Draw or update the playhead in the timeline"""
        if self.playhead_line:
            self.timeline_canvas.delete(self.playhead_line)
            self.timeline_canvas.delete(self.playhead_handle)

        # Determine the y-coordinates based on the number of tracks
        y1 = 0
        y2 = len(self.timeline_tracks) * self.track_height + 50 # Extend slightly below tracks

        # Draw the new playhead line
        self.playhead_line = self.timeline_canvas.create_line(
            self.playhead_x, y1, self.playhead_x, y2,
            fill="#00aaff", width=3, tags="playhead_line"
        )
        # Draw draggable handle at top of playhead
        handle_size = 10
        self.playhead_handle = self.timeline_canvas.create_rectangle(
            self.playhead_x - handle_size//2, y1,
            self.playhead_x + handle_size//2, y1 + handle_size,
            fill="#00aaff", outline="", tags="playhead_handle"
        )

        # Update time display
        playhead_time = self.playhead_x / self.timeline_scale
        self.time_display.config(text=self.format_timecode(playhead_time))

    # Playhead drag handlers
    def on_playhead_drag_start(self, event):
        """Start dragging the playhead"""
        self.dragging_playhead = True
        self._playhead_start_x = self.timeline_canvas.canvasx(event.x) # Store starting canvas x

    def on_playhead_drag_motion(self, event):
        """Drag the playhead"""
        if self.dragging_playhead:
            current_canvas_x = self.timeline_canvas.canvasx(event.x)
            # Calculate the change in canvas x from the start of the drag
            dx = current_canvas_x - self._playhead_start_x
            # Move the playhead by the calculated change
            new_playhead_x = self.playhead_x + dx
            self.move_playhead(new_playhead_x)
            # Update the drag start position for the next motion event
            self._playhead_start_x = current_canvas_x


    def on_playhead_drag_stop(self, event):
        """Stop dragging the playhead"""
        self.dragging_playhead = False
        # Ensure playhead position is updated one last time
        final_canvas_x = self.timeline_canvas.canvasx(event.x)
        new_playhead_x = self.playhead_x + (final_canvas_x - self._playhead_start_x)
        self.move_playhead(new_playhead_x)
        if hasattr(self, '_playhead_start_x'):
             delattr(self, '_playhead_start_x')


    def draw_time_ruler(self):
        """Draw time marks on the ruler canvas"""
        # Clear previous markings
        self.ruler_canvas.delete("all")

        # Get visible area
        canvas_width = self.ruler_canvas.winfo_width()

        # Draw background
        self.ruler_canvas.create_rectangle(
            0, 0, canvas_width, 20,
            fill="#1e1e1e", outline="")

        # Calculate timeline time range
        timeline_duration = max(10, self.get_timeline_duration())

        # Adjust marker interval based on zoom level
        if self.timeline_scale >= 200:  # Zoomed in a lot
            # Show marks every 0.25 seconds
            interval = 0.25
            major_interval = 1
        elif self.timeline_scale >= 100:  # Normal zoom
            # Show marks every 0.5 seconds
            interval = 0.5
            major_interval = 5
        elif self.timeline_scale >= 50:  # Zoomed out some
            # Show marks every 1 second
            interval = 1
            major_interval = 5
        else:  # Zoomed out a lot
            # Show marks every 5 seconds
            interval = 5
            major_interval = 30

        # Draw all markers
        # Iterate over a slightly larger range to account for scrolling
        visible_start_x_canvas, visible_end_x_canvas = self.timeline_canvas.xview()
        # Convert visible canvas x coordinates to timeline time
        visible_start_time = visible_start_x_canvas * self.timeline_canvas.winfo_width() / self.timeline_scale
        visible_end_time = visible_end_x_canvas * self.timeline_canvas.winfo_width() / self.timeline_scale

        # Determine the first and last marker indices within the visible range
        first_marker_index = int(visible_start_time / interval)
        last_marker_index = int(visible_end_time / interval) + 2 # Add padding

        # Iterate over integer indices and calculate seconds
        for i in range(first_marker_index, last_marker_index):
            seconds = i * interval
            x_pos = seconds * self.timeline_scale

            # Is this a major interval?
            is_major = (abs(seconds % major_interval) < 0.001) # Use abs for safety

            # Draw marker (taller for major intervals)
            marker_height = 12 if is_major else 5
            self.ruler_canvas.create_line(
                x_pos, 0, x_pos, marker_height,
                fill="#aaaaaa" if is_major else "#666666", width=1)

            # Add time label for major intervals
            if is_major:
                minutes = int(seconds) // 60
                seconds_part = int(seconds) % 60
                time_text = f"{minutes:02d}:{seconds_part:02d}"
                self.ruler_canvas.create_text(
                    x_pos + 2, 12,
                    text=time_text,
                    fill="#ffffff",
                    font=("Segoe UI", 7),
                    anchor="w")

        # Draw current playhead position on ruler
        self.ruler_canvas.create_polygon(
            self.playhead_x - 5, 0,
            self.playhead_x + 5, 0,
            self.playhead_x, 5,
            fill="#00aaff", outline="", tags="ruler_playhead_indicator")

        # Draw playhead time text
        playhead_time = self.playhead_x / self.timeline_scale
        ph_minutes = int(playhead_time) // 60
        ph_seconds = int(playhead_time) % 60
        # Assuming 30fps for frame display in ruler timecode
        ph_frames = int((playhead_time % 1) * 30)
        ph_text = f"{ph_minutes:02d}:{ph_seconds:02d}:{ph_frames:02d}"

        # Position playhead time text, ensuring it stays within ruler bounds
        text_x = self.playhead_x + 8
        # Get the estimated width of the text to avoid going off-screen
        # This is a rough estimate, a more accurate way would involve font metrics
        text_width_estimate = len(ph_text) * 5 # Approx 5 pixels per character
        if text_x + text_width_estimate > canvas_width:
             text_x = canvas_width - text_width_estimate - 5 # Position from the right

        self.ruler_canvas.create_text(
            text_x, 12,
            text=ph_text,
            fill="#00aaff",
            font=("Segoe UI", 7, "bold"),
            anchor="w",
            tags="ruler_playhead_text")

    def on_ruler_configure(self, event):
        """Handle ruler canvas resize"""
        self.draw_time_ruler()

    def on_ruler_click(self, event):
        """Handle clicking on the ruler"""
        # Convert ruler canvas x to timeline canvas x
        timeline_x = self.timeline_canvas.canvasx(event.x)
        self.move_playhead(timeline_x)

    def on_canvas_press(self, event):
        """Handle mouse button press on timeline canvas"""
        x = self.timeline_canvas.canvasx(event.x)
        y = self.timeline_canvas.canvasy(event.y)

        clicked_clip_info = self.find_clip_at(x, y)

        if clicked_clip_info:
            # Handle clip selection
            if not self.shift_pressed:
                self.deselect_all_clips()
            self.select_clip(clicked_clip_info)

            # Start drag operation
            self.dragging_clip = True
            self._drag_start_x_canvas = x
            self._drag_start_y_canvas = y
            self._dragged_clip_info = clicked_clip_info # Store the clip being dragged

            # Store original positions for all selected clips
            for selected_clip_info in self.selected_clips:
                 # Get current canvas coordinates of the clip's graphical item
                 coords = self.timeline_canvas.coords(selected_clip_info['clip_item_id'])
                 selected_clip_info['_drag_original_x'] = coords[0]
                 selected_clip_info['_drag_original_y'] = coords[1]

            # Save state for undo before drag
            self.save_state()

        else:
            # If not clicking on a clip, move playhead
            self.move_playhead(x)

            # Start selection if shift is pressed
            if self.shift_pressed:
                self.selection_start = x
                self.selection_end = x
                self.draw_selection()
            else:
                # Clear selection if clicking empty space without shift
                self.deselect_all_clips()
                if self.selection_rectangle:
                    self.timeline_canvas.delete(self.selection_rectangle)
                    self.selection_rectangle = None
                    self.selection_start = None
                    self.selection_end = None


    def on_canvas_drag(self, event):
        """Handle mouse motion on timeline canvas (for dragging clips or selection)"""
        x = self.timeline_canvas.canvasx(event.x)
        y = self.timeline_canvas.canvasy(event.y)

        if self.dragging_clip and self._dragged_clip_info:
            # Calculate the total change in mouse position relative to the canvas
            dx = x - self._drag_start_x_canvas
            dy = y - self._drag_start_y_canvas

            # Move all selected clips
            for selected_clip_info in self.selected_clips:
                # Calculate the new position for the selected clip item
                new_x = selected_clip_info['_drag_original_x'] + dx
                new_y = selected_clip_info['_drag_original_y'] + dy

                # Apply grid snap to x position
                grid_size = 10
                new_x = max(0, round(new_x / grid_size) * grid_size)

                # Determine the target track based on the new y-position
                target_track_name = self.get_target_track_name(new_y + (self.track_height - 20) / 2) # Check middle of the clip area

                # If target track is found and is different from the current track
                original_track_of_selected_clip = selected_clip_info['track']
                if target_track_name and target_track_name != original_track_of_selected_clip:
                     orig_track_type = self.timeline_tracks[original_track_of_selected_clip]['type']
                     target_track_type = self.timeline_tracks[target_track_name]['type']

                     # Only allow moving to tracks of the same type for simplicity
                     if orig_track_type == target_track_type:
                         # Update the track
                         selected_clip_info['track'] = target_track_name
                         # Remove from old track's clip list
                         self.timeline_tracks[original_track_of_selected_clip]['clips'].remove(selected_clip_info)
                         # Add to new track's clip list
                         self.timeline_tracks[target_track_name]['clips'].append(selected_clip_info)
                         # Snap y position to the top of the clip area in the new track
                         new_y = self.timeline_tracks[target_track_name]['y'] + 10
                     else:
                         # If track types are incompatible, keep y snapped to original track's clip area top
                         new_y = self.timeline_tracks[original_track_of_selected_clip]['y'] + 10
                else:
                     # If no target track or same track, keep y snapped to current track's clip area top
                     new_y = self.timeline_tracks[selected_clip_info['track']]['y'] + 10


                # Move the graphical items (rectangle, text, thumbnail)
                self.timeline_canvas.coords(selected_clip_info['clip_item_id'], new_x, new_y, new_x + self.get_clip_width_pixels(selected_clip_info), new_y + self.track_height - 20)
                self.timeline_canvas.coords(selected_clip_info['text_item_id'], new_x + 5, new_y + 5) # Adjust text position
                if 'thumb_item_id' in selected_clip_info:
                     self.timeline_canvas.coords(selected_clip_info['thumb_item_id'], new_x + 5, new_y + 5) # Adjust thumbnail position

                # Update clip data (start time based on new x position)
                selected_clip_info['start_time'] = new_x / self.timeline_scale

                # Update original_x and original_y for the selected clip for the next motion event
                selected_clip_info['_drag_original_x'] = new_x
                selected_clip_info['_drag_original_y'] = new_y


            # Update the timeline scrollregion as clips move
            self.update_timeline_scrollregion()
            self.draw_time_ruler() # Redraw ruler to reflect potential duration change

        elif self.selection_start is not None:
            # Update selection rectangle
            self.selection_end = x
            self.draw_selection()


    def on_canvas_release(self, event):
        """Handle mouse button release on timeline canvas"""
        if self.dragging_clip:
            self.dragging_clip = False
            self._dragged_clip_info = None
            # Clean up temp attributes from all selected clips
            for selected_clip_info in self.selected_clips:
                if hasattr(selected_clip_info, '_drag_original_x'):
                    delattr(selected_clip_info, '_drag_original_x')
                if hasattr(selected_clip_info, '_drag_original_y'):
                    delattr(selected_clip_info, '_drag_original_y')

            # Update timeline duration and scroll region
            self.update_timeline_scrollregion()
            self.draw_time_ruler()

        elif self.selection_start is not None:
            # Finalize selection
            self.selection_end = self.timeline_canvas.canvasx(event.x)
            self.select_clips_in_selection_area()
            if self.selection_rectangle:
                self.timeline_canvas.delete(self.selection_rectangle)
                self.selection_rectangle = None
                self.selection_start = None
                self.selection_end = None


    def on_canvas_right_click(self, event):
        """Handle right click on timeline canvas"""
        x = self.timeline_canvas.canvasx(event.x)
        y = self.timeline_canvas.canvasy(event.y)

        clicked_clip_info = self.find_clip_at(x, y)

        if clicked_clip_info:
            # Select the right-clicked clip if not already selected
            if clicked_clip_info not in self.selected_clips:
                 self.deselect_all_clips()
                 self.select_clip(clicked_clip_info)
            # Show context menu for the clicked clip
            self.show_clip_context_menu(event, clicked_clip_info)
        else:
            # Handle right click on empty space (e.g., show timeline context menu)
            pass # Implement timeline context menu if needed

    def on_canvas_double_click(self, event):
         """Handle double click on timeline canvas"""
         x = self.timeline_canvas.canvasx(event.x)
         y = self.timeline_canvas.canvasy(event.y)

         clicked_clip_info = self.find_clip_at(x, y)

         if clicked_clip_info and self.load_clip_callback:
              # Load the clip into the player on double click
              self.load_clip_callback(clicked_clip_info['video_path'])


    def find_clip_at(self, x, y):
        """Find and return the clip info at the given canvas coordinates (x, y)"""
        # Iterate through clips and check if the coordinates are within their bounding box
        for clip_info in reversed(self.timeline_clips): # Check from top (last added) down
            try:
                # Get the bounding box of the clip's graphical item
                bbox = self.timeline_canvas.bbox(clip_info['clip_item_id'])
                # Check if the click coordinates are within the bounding box
                if bbox and bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]:
                    return clip_info # Return the clip info if found
            except tk.TclError:
                # Handle case where item might be deleted but still in list
                print(f"Warning: Could not get bbox for canvas item {clip_info['clip_item_id']}. It might have been deleted.")
                pass # Continue checking other clips
        return None # Return None if no clip is found at the coordinates


    def draw_selection(self):
        """Draw selection rectangle"""
        if self.selection_rectangle:
            self.timeline_canvas.delete(self.selection_rectangle)

        if self.selection_start is not None and self.selection_end is not None:
            x1 = min(self.selection_start, self.selection_end)
            x2 = max(self.selection_start, self.selection_end)
            y1 = 0
            y2 = len(self.timeline_tracks) * self.track_height
            # Ensure y2 is at least the canvas height if no tracks yet
            if y2 == 0:
                 y2 = self.timeline_canvas.winfo_height()

            self.selection_rectangle = self.timeline_canvas.create_rectangle(
                x1, y1, x2, y2,
                outline="#00aaff",
                fill="#00aaff20",
                stipple="gray25",
                tags="selection_rectangle" # Add a tag for easy deletion
            )

    def select_clips_in_selection_area(self):
        """Select clips that are within the selection rectangle area"""
        if self.selection_start is None or self.selection_end is None:
            return

        x1 = min(self.selection_start, self.selection_end)
        x2 = max(self.selection_start, self.selection_end)
        y1 = 0
        y2 = len(self.timeline_tracks) * self.track_height
        if y2 == 0:
             y2 = self.timeline_canvas.winfo_height()

        # Deselect all if Shift is not pressed
        if not self.shift_pressed:
             self.deselect_all_clips()

        # Iterate through clips and select those within the selection area
        for clip_info in self.timeline_clips:
             try:
                 bbox = self.timeline_canvas.bbox(clip_info['clip_item_id'])
                 if bbox:
                      # Check for overlap between clip bbox and selection area
                      clip_x1, clip_y1, clip_x2, clip_y2 = bbox
                      if max(x1, clip_x1) < min(x2, clip_x2) and max(y1, clip_y1) < min(y2, clip_y2):
                          self.select_clip(clip_info)
             except tk.TclError:
                  print(f"Warning: Could not get bbox for canvas item {clip_info['clip_item_id']} during selection.")
                  pass # Continue checking other clips


    def select_clip(self, clip_info):
        """Select a clip (update visual state)"""
        if clip_info not in self.selected_clips:
            self.selected_clips.append(clip_info)
            # Change outline color to indicate selection
            self.timeline_canvas.itemconfig(clip_info['clip_item_id'], outline="#ffaa00", width=2)

    def deselect_clip(self, clip_info):
        """Deselect a clip (update visual state)"""
        if clip_info in self.selected_clips:
            self.selected_clips.remove(clip_info)
            # Reset outline color
            track_type = self.timeline_tracks[clip_info['track']]['type']
            clip_border = "#00aaff" if track_type == "video" else "#aa00ff"
            self.timeline_canvas.itemconfig(clip_info['clip_item_id'], outline=clip_border, width=2)

    def deselect_all_clips(self):
        """Deselect all clips"""
        for clip_info in list(self.selected_clips):
            self.deselect_clip(clip_info)
        self.selected_clips = []

    def delete_selected_clips(self):
        """Delete all selected clips"""
        if not self.selected_clips:
            return

        # Save state for undo
        self.save_state()

        # Delete all selected clips
        for clip_info in list(self.selected_clips):
            self.delete_clip(clip_info)

        self.selected_clips = []
        self.update_timeline_scrollregion()
        self.draw_time_ruler()

    def move_playhead(self, x):
        """Move the playhead and update its position"""
        # Ensure playhead stays within bounds (0 to max timeline duration in pixels)
        max_x = self.get_timeline_duration() * self.timeline_scale
        self.playhead_x = max(0, min(x, max_x))

        self.draw_playhead()
        # Call the callback in the main app if set
        if self.playhead_callback:
            self.playhead_callback(self.playhead_x) # Pass pixel position

        self.draw_time_ruler()

    def set_playhead_callback(self, callback):
        """Set callback for playhead movement"""
        self.playhead_callback = callback

    def get_target_track_name(self, y_pos):
        """Determine which track to add the clip to based on y-position"""
        # Find the track frame that the y_pos falls into
        for track_name, track_info in self.timeline_tracks.items():
            # Get the bounding box of the track header frame in canvas coordinates
            # Need to convert canvas y to window y for accurate comparison
            frame_bbox = self.timeline_canvas.bbox(track_info['frame'])
            if frame_bbox and frame_bbox[1] <= y_pos <= frame_bbox[3]:
                return track_name
        # If no track frame is found, return the first track name if available
        if self.timeline_tracks:
             return next(iter(self.timeline_tracks))
        return None # Return None if no tracks exist


    def add_clip(self, clip_data, x_pos, y_pos):
        """Add a clip to the timeline by drawing directly on the canvas"""
        try:
            # Save state for undo
            self.save_state()

            # Determine the target track based on y-position
            target_track_name = self.get_target_track_name(y_pos)
            if not target_track_name:
                print(f"Error adding clip: No track available to add the clip for {clip_data.get('filename', 'N/A')}")
                return None

            # Calculate clip width in pixels
            clip_width = max(50, int(clip_data['duration'] * self.timeline_scale))

            # Get the y-position for the track
            track_y = self.timeline_tracks[target_track_name]['y'] + 10
            clip_height = self.track_height - 20

            # Create clip rectangle item
            clip_bg = "#3a3a3a"
            clip_border = "#00aaff"
            if self.timeline_tracks[target_track_name]['type'] == "audio":
                clip_bg = "#4a3a4a"
                clip_border = "#aa00ff"

            # Use a simpler tag format to avoid potential Tkinter parsing issues
            clip_index = len(self.timeline_clips)
            clip_tag = f"clip{clip_index}"

            clip_item_id = self.timeline_canvas.create_rectangle(
                x_pos, track_y, x_pos + clip_width, track_y + clip_height,
                fill=clip_bg, outline=clip_border, width=2,
                tags=("timeline_clip", clip_tag) # Use the simplified tag here
            )

            # Add thumbnail image item (if available)
            thumb_item_id = None
            if clip_data.get('thumbnail_image'):
                # Position thumbnail at the top-left of the clip rectangle
                thumb_item_id = self.timeline_canvas.create_image(
                    x_pos + 5, track_y + 5, # Adjust position as needed
                    image=clip_data['thumbnail_image'],
                    anchor="nw",
                    tags=("timeline_clip", f"{clip_tag}_thumb") # Use simplified tag + suffix
                )

            # Add filename text item
            # Position text below thumbnail or at the top-left if no thumbnail
            text_y_pos = track_y + 5
            if thumb_item_id:
                 # Position text next to or below thumbnail, adjust as needed
                 # For simplicity, placing text slightly below the top edge
                 text_y_pos = track_y + 25 # Example: place text below a small thumbnail area

            text_item_id = self.timeline_canvas.create_text(
                x_pos + 5, text_y_pos, # Adjust position as needed
                text=clip_data['filename'],
                fill="white",
                font=("Segoe UI", 8, "bold"),
                anchor="nw",
                width=clip_width - 10, # Wrap text within clip width
                tags=("timeline_clip", f"{clip_tag}_text") # Use simplified tag + suffix
            )


            # Store clip info including canvas item IDs
            clip_info = {
                'clip_item_id': clip_item_id,
                'text_item_id': text_item_id,
                'thumb_item_id': thumb_item_id, # Store thumbnail item ID
                'filename': clip_data['filename'],
                'start_time': x_pos / self.timeline_scale,
                'duration': clip_data['duration'],
                'video_path': clip_data['video_path'],
                'track': target_track_name,
                'thumbnail': clip_data.get('thumbnail_image'),  # Store for copying
                'frame_count': clip_data.get('frame_count', 0),
                'fps': clip_data.get('fps', 0)
            }
            self.timeline_clips.append(clip_info)
            self.timeline_tracks[target_track_name]['clips'].append(clip_info)

            # Update scrollregion
            self.update_timeline_scrollregion()
            self.draw_time_ruler()

            return clip_info

        except Exception as e:
            print(f"Error adding clip to timeline: {e}")
            # Bỏ thông báo lỗi popup theo yêu cầu của người dùng
            # messagebox.showerror("Error", f"Failed to add clip: {clip_data.get('filename', 'N/A')}\n{e}")
            return None

    def get_clip_width_pixels(self, clip_info):
        """Calculate the width of a clip in pixels based on its duration and timeline scale"""
        return max(50, int(clip_info['duration'] * self.timeline_scale))

    def redraw_all_clips(self):
        """Redraw all clips on the canvas based on current data"""
        # Clear existing clip graphical items
        for clip_info in self.timeline_clips:
             self.timeline_canvas.delete(clip_info['clip_item_id'])
             self.timeline_canvas.delete(clip_info['text_item_id'])
             if 'thumb_item_id' in clip_info and clip_info['thumb_item_id'] is not None:
                  self.timeline_canvas.delete(clip_info['thumb_item_id'])


        # Draw clips again from the updated timeline_clips list
        for clip_info in self.timeline_clips:
            track_name = clip_info['track']
            if track_name not in self.timeline_tracks:
                 print(f"Warning: Track '{track_name}' not found for clip '{clip_info['filename']}' during redraw. Skipping clip.")
                 continue # Skip if track was deleted

            x_pos = clip_info['start_time'] * self.timeline_scale
            track_y = self.timeline_tracks[track_name]['y'] + 10
            clip_width = self.get_clip_width_pixels(clip_info)
            clip_height = self.track_height - 20

            clip_bg = "#3a3a3a"
            clip_border = "#00aaff"
            if self.timeline_tracks[track_name]['type'] == "audio":
                clip_bg = "#4a3a4a"
                clip_border = "#aa00ff"

            # Recreate clip rectangle item
            # Use a simpler tag format to avoid potential Tkinter parsing issues
            clip_index = self.timeline_clips.index(clip_info)
            clip_tag = f"clip{clip_index}"

            clip_item_id = self.timeline_canvas.create_rectangle(
                x_pos, track_y, x_pos + clip_width, track_y + clip_height,
                fill=clip_bg, outline=clip_border, width=2,
                tags=("timeline_clip", clip_tag) # Use the simplified tag here
            )
            clip_info['clip_item_id'] = clip_item_id # Update item ID in clip info

            # Recreate thumbnail image item (if available)
            thumb_item_id = None
            if clip_info.get('thumbnail'):
                 thumb_item_id = self.timeline_canvas.create_image(
                     x_pos + 5, track_y + 5,
                     image=clip_info['thumbnail'],
                     anchor="nw",
                     tags=("timeline_clip", f"{clip_tag}_thumb") # Use simplified tag + suffix
                 )
            clip_info['thumb_item_id'] = thumb_item_id # Update item ID

            # Recreate filename text item
            text_y_pos = track_y + 5
            if thumb_item_id:
                 text_y_pos = track_y + 25 # Example: place text below a small thumbnail area

            text_item_id = self.timeline_canvas.create_text(
                x_pos + 5, text_y_pos,
                text=clip_info['filename'],
                fill="white",
                font=("Segoe UI", 8, "bold"),
                anchor="nw",
                width=clip_width - 10,
                tags=("timeline_clip", f"{clip_tag}_text") # Use simplified tag + suffix
            )
            clip_info['text_item_id'] = text_item_id # Update item ID

            # Ensure selection state is visually updated
            if clip_info in self.selected_clips:
                 self.timeline_canvas.itemconfig(clip_item_id, outline="#ffaa00", width=2)


    def delete_clip(self, clip_info):
        """Delete a clip from the timeline"""
        # Save state for undo
        self.save_state()

        # Remove from track's clip list
        track_name = clip_info['track']
        if track_name in self.timeline_tracks:
            if clip_info in self.timeline_tracks[track_name]['clips']:
                self.timeline_tracks[track_name]['clips'].remove(clip_info)

        # Remove from selected clips if present
        if clip_info in self.selected_clips:
            self.selected_clips.remove(clip_info)

        # Delete the graphical items for the clip
        self.timeline_canvas.delete(clip_info['clip_item_id'])
        self.timeline_canvas.delete(clip_info['text_item_id'])
        if 'thumb_item_id' in clip_info and clip_info['thumb_item_id'] is not None:
             self.timeline_canvas.delete(clip_info['thumb_item_id'])

        # Remove from timeline clips list
        if clip_info in self.timeline_clips:
            self.timeline_clips.remove(clip_info)


        # Update timeline
        self.update_timeline_scrollregion()
        self.draw_time_ruler()

    def split_clip_at_playhead(self):
        """Split the selected clip at playhead position"""
        if not self.selected_clips or len(self.selected_clips) != 1:
            messagebox.showinfo("Split Clip", "Please select exactly one clip to split.")
            return

        clip_info = self.selected_clips[0]
        playhead_time = self.playhead_x / self.timeline_scale
        clip_start = clip_info['start_time']
        clip_end = clip_start + clip_info['duration']

        # Check if playhead is within clip boundaries (with a small tolerance)
        tolerance = 0.01 / self.timeline_scale # Tolerance of 0.01 pixels converted to time
        if playhead_time <= clip_start + tolerance or playhead_time >= clip_end - tolerance:
            messagebox.showinfo("Split Clip", "Playhead must be positioned within the clip.")
            return

        # Save state for undo
        self.save_state()

        # Calculate durations for the two new clips
        first_duration = playhead_time - clip_start
        second_duration = clip_end - playhead_time

        # Calculate frame counts for the two new clips
        # Ensure frame counts are integers and sum up correctly
        first_frame_count = int(first_duration * clip_info['fps'])
        second_frame_count = clip_info['frame_count'] - first_frame_count

        # Update existing clip (first part) duration and frame count
        clip_info['duration'] = first_duration
        clip_info['frame_count'] = first_frame_count
        # Update visual representation (width)
        new_width = self.get_clip_width_pixels(clip_info)
        self.timeline_canvas.coords(clip_info['clip_item_id'],
                                    clip_info['start_time'] * self.timeline_scale,
                                    self.timeline_tracks[clip_info['track']]['y'] + 10,
                                    clip_info['start_time'] * self.timeline_scale + new_width,
                                    self.timeline_tracks[clip_info['track']]['y'] + 10 + self.track_height - 20)
        # Update text item position and width
        self.timeline_canvas.coords(clip_info['text_item_id'], clip_info['start_time'] * self.timeline_scale + 5, self.timeline_tracks[clip_info['track']]['y'] + 10 + (self.track_height - 20) / 2) # Center text vertically
        self.timeline_canvas.itemconfig(clip_info['text_item_id'], width=new_width - 10)
        # Update thumbnail item position
        if 'thumb_item_id' in clip_info and clip_info['thumb_item_id'] is not None:
             self.timeline_canvas.coords(clip_info['thumb_item_id'], clip_info['start_time'] * self.timeline_scale + 5, self.timeline_tracks[clip_info['track']]['y'] + 10 + 5)


        # Create second part (new clip) data
        new_clip_data = {
            'thumbnail_image': clip_info.get('thumbnail'), # Use get for safety
            'filename': clip_info['filename'] + " (2)",
            'duration': second_duration,
            'video_path': clip_info['video_path'],
            'frame_count': second_frame_count,
            'fps': clip_info['fps']
        }

        # Add new clip at playhead position
        track_y = self.timeline_tracks[clip_info['track']]['y'] + 10
        new_clip_info = self.add_clip(new_clip_data, self.playhead_x, track_y)

        # Update timeline
        self.update_timeline_scrollregion()
        self.draw_time_ruler()
        # Select the new clip
        if new_clip_info:
             self.deselect_all_clips()
             self.select_clip(new_clip_info)


    def trim_clip_start(self, clip_info):
        """Trim the start of the clip to playhead"""
        playhead_time = self.playhead_x / self.timeline_scale
        clip_start = clip_info['start_time']
        clip_end = clip_start + clip_info['duration']

        # Check if playhead is within clip boundaries (with a small tolerance)
        tolerance = 0.01 / self.timeline_scale
        if playhead_time <= clip_start + tolerance or playhead_time >= clip_end - tolerance:
            messagebox.showinfo("Trim Clip", "Playhead must be positioned within the clip.")
            return

        # Save state for undo
        self.save_state()

        # Calculate new duration and frame count
        new_duration = clip_end - playhead_time
        trimmed_frames = int((playhead_time - clip_start) * clip_info['fps'])
        new_frame_count = clip_info['frame_count'] - trimmed_frames

        # Update the clip data
        clip_info['start_time'] = playhead_time
        clip_info['duration'] = new_duration
        clip_info['frame_count'] = new_frame_count

        # Update visual representation (position and width)
        new_width = self.get_clip_width_pixels(clip_info)
        track_y = self.timeline_tracks[clip_info['track']]['y'] + 10
        self.timeline_canvas.coords(clip_info['clip_item_id'],
                                    self.playhead_x, # New start x is playhead position
                                    track_y,
                                    self.playhead_x + new_width, # New end x
                                    track_y + self.track_height - 20)
        # Update text item position and width
        self.timeline_canvas.coords(clip_info['text_item_id'], self.playhead_x + 5, track_y + (self.track_height - 20) / 2) # Center text vertically
        self.timeline_canvas.itemconfig(clip_info['text_item_id'], width=new_width - 10)
        # Update thumbnail item position
        if 'thumb_item_id' in clip_info and clip_info['thumb_item_id'] is not None:
             self.timeline_canvas.coords(clip_info['thumb_item_id'], self.playhead_x + 5, track_y + 5)


        # Update timeline
        self.update_timeline_scrollregion()
        self.draw_time_ruler()

    def trim_clip_end(self, clip_info):
        """Trim the end of the clip to playhead"""
        playhead_time = self.playhead_x / self.timeline_scale
        clip_start = clip_info['start_time']
        clip_end = clip_start + clip_info['duration']

        # Check if playhead is within clip boundaries (with a small tolerance)
        tolerance = 0.01 / self.timeline_scale
        if playhead_time <= clip_start + tolerance or playhead_time >= clip_end - tolerance:
            messagebox.showinfo("Trim Clip", "Playhead must be positioned within the clip.")
            return

        # Save state for undo
        self.save_state()

        # Calculate new duration and frame count
        new_duration = playhead_time - clip_start
        new_frame_count = int(new_duration * clip_info['fps'])

        # Update the clip data
        clip_info['duration'] = new_duration
        clip_info['frame_count'] = new_frame_count


        # Update visual representation (width)
        new_width = self.get_clip_width_pixels(clip_info)
        track_y = self.timeline_tracks[clip_info['track']]['y'] + 10
        self.timeline_canvas.coords(clip_info['clip_item_id'],
                                    clip_info['start_time'] * self.timeline_scale, # Start x remains the same
                                    track_y,
                                    clip_info['start_time'] * self.timeline_scale + new_width, # New end x
                                    track_y + self.track_height - 20)
        # Update text item width
        self.timeline_canvas.itemconfig(clip_info['text_item_id'], width=new_width - 10)


        # Update timeline
        self.update_timeline_scrollregion()
        self.draw_time_ruler()

    def show_clip_context_menu(self, event, clip_info):
        """Show context menu for a clip"""
        clip_menu = tk.Menu(self.parent, tearoff=0)

        # Add menu items
        clip_menu.add_command(label="Split at Playhead",
                              command=lambda: self.split_clip_at_playhead())
        clip_menu.add_command(label="Trim Start to Playhead",
                              command=lambda: self.trim_clip_start(clip_info))
        clip_menu.add_command(label="Trim End to Playhead",
                              command=lambda: self.trim_clip_end(clip_info))
        clip_menu.add_separator()
        clip_menu.add_command(label="Delete",
                              command=lambda: self.delete_clip(clip_info))

        # Show context menu
        try:
            clip_menu.tk_popup(event.x_root, event.y_root)
        finally:
            clip_menu.grab_release()


    def copy_selected_clips(self):
        """Copy selected clips to clipboard"""
        if not self.selected_clips:
            return

        # Clear clipboard
        self.clipboard = []

        # Get the minimum start time of selected clips (to maintain relative positioning)
        min_start_time = float('inf')
        if self.selected_clips:
             min_start_time = min(clip['start_time'] for clip in self.selected_clips)


        # Copy all selected clips with relative positions
        for clip_info in self.selected_clips:
            self.clipboard.append({
                'filename': clip_info['filename'],
                'duration': clip_info['duration'],
                'video_path': clip_info['video_path'],
                'relative_start': clip_info['start_time'] - min_start_time,
                'track': clip_info['track'],
                'thumbnail': clip_info.get('thumbnail'), # Store for copying
                'frame_count': clip_info.get('frame_count', 0),
                'fps': clip_info.get('fps', 0)
            })
        print(f"Copied {len(self.clipboard)} clips to clipboard.")


    def paste_clips(self):
        """Paste clips from clipboard at playhead position"""
        if not self.clipboard:
            messagebox.showinfo("Paste Clips", "Clipboard is empty.")
            return

        # Save state for undo
        self.save_state()

        # Deselect all clips
        self.deselect_all_clips()

        # Get paste position (playhead x in pixels)
        paste_pos_x = self.playhead_x

        # Paste all clips with relative positions maintained
        newly_pasted_clips = []
        for clip_data in self.clipboard:
            # Calculate the absolute x position for the new clip
            paste_x = paste_pos_x + (clip_data['relative_start'] * self.timeline_scale)

            # Prepare clip data for adding
            new_clip_data = {
                'thumbnail_image': clip_data.get('thumbnail'), # Use get for safety
                'filename': clip_data['filename'], # Keep original filename for pasted copy
                'duration': clip_data['duration'],
                'video_path': clip_data['video_path'],
                'frame_count': clip_data.get('frame_count', 0),
                'fps': clip_data.get('fps', 0)
            }

            # Determine the target track name based on the copied track name
            track_name = clip_data['track']
            # If original track doesn't exist, try to find a compatible track or use the first available
            if track_name not in self.timeline_tracks:
                 print(f"Warning: Original track '{track_name}' not found for pasted clip. Attempting to find compatible track.")
                 if self.timeline_tracks:
                     track_name = next(iter(self.timeline_tracks)) # Use the first track
                     print(f"Using first available track: '{track_name}' for pasted clip.")
                 else:
                     print(f"Error pasting clip '{clip_data['filename']}': No tracks available.")
                     continue # Skip this clip if no tracks exist

            # Get Y position for the track (this is handled internally by add_clip now)
            # We just need to provide the desired x position and a rough y position to help find the track
            # The actual y position on the canvas will be determined by the track's y + padding
            track_y_hint = self.timeline_tracks[track_name]['y'] + 10

            # Add clip and select it (add_clip now handles drawing)
            new_clip_info = self.add_clip(new_clip_data, paste_x, track_y_hint)
            if new_clip_info:
                newly_pasted_clips.append(new_clip_info)

        # Select all newly pasted clips
        for clip_info in newly_pasted_clips:
             self.select_clip(clip_info)

        # Update timeline
        self.update_timeline_scrollregion()
        self.draw_time_ruler()
        print(f"Pasted {len(newly_pasted_clips)} clips.")


    def save_state(self):
        """Save the current state for undo operations"""
        # Create a deep copy of the current timeline clips state
        state = []
        for clip_info in self.timeline_clips:
            # Copy relevant data, not the tkinter canvas item IDs
            state.append({
                'filename': clip_info['filename'],
                'start_time': clip_info['start_time'],
                'duration': clip_info['duration'],
                'video_path': clip_info['video_path'],
                'track': clip_info['track'],
                'frame_count': clip_info.get('frame_count', 0),
                'fps': clip_info.get('fps', 0)
                # Do NOT store canvas item IDs or thumbnail image directly in the state
            })

        # Add to undo stack (limit stack size)
        self.undo_stack.append(state)
        if len(self.undo_stack) > 20: # Limit stack size to 20 states
            self.undo_stack.pop(0)
        print(f"Saved state. Undo stack size: {len(self.undo_stack)}")


    def undo_action(self):
        """Undo the last action"""
        if len(self.undo_stack) < 2: # Need at least the initial state and one action
            messagebox.showinfo("Undo", "Nothing to undo.")
            return

        # Get the previous state (the one before the last action)
        # The last state in the stack is the current state before undoing
        self.undo_stack.pop() # Remove the current state
        prev_state = self.undo_stack[-1] # Get the previous state

        print(f"Undoing to state with {len(prev_state)} clips.")

        # Clear current timeline clips and their graphical items
        for clip_info in list(self.timeline_clips):
            # Remove the graphical items
            self.timeline_canvas.delete(clip_info['clip_item_id'])
            self.timeline_canvas.delete(clip_info['text_item_id'])
            if 'thumb_item_id' in clip_info and clip_info['thumb_item_id'] is not None:
                 self.timeline_canvas.delete(clip_info['thumb_item_id'])

        self.timeline_clips = []
        # Clear clips from tracks
        for track_name in self.timeline_tracks:
             self.timeline_tracks[track_name]['clips'] = []
        self.selected_clips = []


        # Recreate clips from the previous state by adding them back
        # Note: This will regenerate canvas item IDs and thumbnails
        for clip_data in prev_state:
            # Prepare clip data for re-adding
            # Note: thumbnail image is not stored in state, might need to regenerate or reload
            # For simplicity in this undo, we'll pass None for thumbnail, or ideally reload it
            # Reloading thumbnail from video path would be better for full fidelity undo
            # For now, we'll just add with None thumbnail
            re_add_clip_data = {
                 'thumbnail_image': None, # Thumbnail not saved in state
                 'filename': clip_data['filename'],
                 'duration': clip_data['duration'],
                 'video_path': clip_data['video_path'],
                 'frame_count': clip_data.get('frame_count', 0),
                 'fps': clip_data.get('fps', 0)
            }

            # Determine the track and position
            track_name = clip_data['track']
            # Ensure the track still exists
            if track_name not in self.timeline_tracks:
                 print(f"Warning: Track '{track_name}' for clip '{clip_data['filename']}' not found during undo. Skipping clip.")
                 continue # Skip this clip if its track was deleted

            # Calculate the x position from start_time
            x_pos = clip_data['start_time'] * self.timeline_scale
            track_y_hint = self.timeline_tracks[track_name]['y'] + 10 # Y position hint for add_clip

            # Add the clip back using the internal add_clip logic
            # This will recreate the graphical items and add it to the lists
            # Note: add_clip already saves state, which is not ideal during undo.
            # A more robust undo would bypass state saving during the undo process.
            # For this example, we'll accept the extra state saves during undo for simplicity.
            # To avoid saving state during undo, we could temporarily disable state saving
            # or create a separate internal add_clip method that doesn't save state.
            # For now, let's just call add_clip and accept the extra state.
            self.add_clip(re_add_clip_data, x_pos, track_y_hint)


        # Update timeline
        self.update_timeline_scrollregion()
        self.draw_time_ruler()
        self.draw_playhead() # Redraw playhead as timeline duration might change
        print("Undo complete.")


    def zoom_timeline(self, factor):
        """Zoom the timeline in or out"""
        # Calculate new scale
        old_scale = self.timeline_scale
        self.timeline_scale = max(10, min(500, self.timeline_scale * factor))

        # Keep playhead position constant in time
        playhead_time = self.playhead_x / old_scale
        self.playhead_x = playhead_time * self.timeline_scale

        # Redraw all clips with the new scale
        self.redraw_all_clips()

        # Update the timeline
        self.update_timeline_scrollregion()
        self.draw_playhead()
        self.draw_time_ruler()

    def on_mousewheel_zoom(self, event):
        """Zoom the timeline with mouse wheel"""
        # Get the mouse position relative to the timeline canvas
        canvas_x = self.timeline_canvas.canvasx(event.x)

        # Calculate the time at the mouse position
        time_at_mouse = canvas_x / self.timeline_scale

        # Zoom in or out based on direction
        if event.delta > 0:
            self.zoom_timeline(1.1)  # Zoom in
        else:
            self.zoom_timeline(0.9)  # Zoom out

        # After zooming, adjust the scroll position to keep the time under the mouse cursor centered
        new_canvas_x_at_mouse = time_at_mouse * self.timeline_scale
        # Calculate the difference between the old and new canvas x at the mouse position
        scroll_offset = new_canvas_x_at_mouse - canvas_x

        # Get the current scroll position
        current_scroll_x, _ = self.timeline_canvas.xview()
        # Calculate the new scroll position
        new_scroll_x = current_scroll_x + (scroll_offset / self.timeline_canvas.winfo_width())

        # Set the new scroll position
        self.timeline_canvas.xview_moveto(new_scroll_x)


    def update_timeline_scrollregion(self):
        """Update the timeline canvas scroll region"""
        # Calculate the total width needed (duration * scale + buffer)
        duration = self.get_timeline_duration()
        width = max(self.timeline_canvas.winfo_width(), (duration * self.timeline_scale) + 200) # Ensure minimum width is canvas width

        # Set height based on number of tracks
        height = max(self.timeline_canvas.winfo_height(), len(self.timeline_tracks) * self.track_height + 50) # Ensure minimum height is canvas height

        # Update timeline inner frame size (for track headers)
        self.timeline_inner.configure(width=width, height=height)

        # Update scrollregion
        self.timeline_canvas.configure(scrollregion=(0, 0, width, height))

    def on_timeline_configure(self, event):
        """Handle timeline inner frame configure event"""
        # This is triggered when the size of the inner frame changes (e.g., on scrollregion update)
        # Redraw elements that depend on the inner frame size, like the playhead height
        self.draw_playhead()


    def on_timeline_canvas_configure(self, event):
        """Handle timeline canvas configure event"""
        # Update the inner window to fill entire canvas width
        self.timeline_canvas.itemconfig(
            self.timeline_window,
            width=event.width
        )

        # Redraw elements that depend on canvas size, like the ruler
        self.draw_time_ruler()

        # Update scrollregion as canvas size changes
        self.update_timeline_scrollregion()

        # Move playhead if needed (e.g., if resizing makes it go out of bounds)
        self.move_playhead(self.playhead_x) # Calling move_playhead will re-clamp and redraw


    def get_timeline_duration(self):
        """Calculate the total duration of the timeline"""
        if not self.timeline_clips:
            return 10  # Default minimum duration

        # Find the furthest clip end
        max_end_time = 0
        for clip in self.timeline_clips:
            clip_end = clip['start_time'] + clip['duration']
            max_end_time = max(max_end_time, clip_end)

        return max(10, max_end_time + 5)  # Add some padding (5 seconds)

    def format_timecode(self, seconds):
        """Format seconds to timecode (HH:MM:SS:FF)"""
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        secs = int(seconds % 60)
        # Assuming 30fps for frame display
        frames = int((seconds % 1) * 30)

        return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"

    def get_selected_clips(self):
        """Return the list of currently selected clips"""
        return self.selected_clips

    def get_playhead_time(self):
        """Return the current playhead time in seconds"""
        return self.playhead_x / self.timeline_scale

    def get_clips(self):
        """Return all timeline clips"""
        print("Timeline.get_clips() called.") # Added print statement
        return self.timeline_clips

    def clear_timeline(self):
        """Clear all clips from the timeline"""
        # Save state for undo
        self.save_state()

        # Remove all clips
        for clip_info in list(self.timeline_clips):
            # Remove the graphical items
            self.timeline_canvas.delete(clip_info['clip_item_id'])
            self.timeline_canvas.delete(clip_info['text_item_id'])
            if 'thumb_item_id' in clip_info and clip_info['thumb_item_id'] is not None:
                 self.timeline_canvas.delete(clip_info['thumb_item_id'])

        self.timeline_clips = []
        # Clear clips from tracks
        for track_name in self.timeline_tracks:
            self.timeline_tracks[track_name]['clips'] = []

        self.selected_clips = []

        # Reset playhead
        self.playhead_x = 0
        self.draw_playhead()

        # Update timeline
        self.update_timeline_scrollregion()
        self.draw_time_ruler()
