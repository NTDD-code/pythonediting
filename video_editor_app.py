import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from PIL import Image, ImageTk
import cv2
import os

class VideoEditorApp:
    def __init__(self, root):
        self.project_path = os.path.dirname(os.path.abspath(__file__))
        self.root = root
        self.root.title("Simple Video Editor")
        self.root.geometry("1280x720")
        self.root.configure(bg="#232323")
        self.root.minsize(1100, 600)
        
        # Initialize collections
        self.thumbnails = []
        self.thumbnail_labels = []
        self.timeline_clips = []
        self.timeline_scale = 100  # pixels per second

        # Video playback variables
        self.current_video = None
        self.video_playing = False
        self.current_frame = None
        self.frame_count = 0
        self.current_frame_pos = 0
        self.fps = 0
        
        # Top menu bar (dark)
        menu_bar = tk.Menu(root, bg="#181818", fg="#fff", activebackground="#2d2d2d", activeforeground="#fff", bd=0, relief="flat")
        root.config(menu=menu_bar)
        file_menu = tk.Menu(menu_bar, tearoff=0, bg="#181818", fg="#fff", activebackground="#2d2d2d", activeforeground="#fff")
        file_menu.add_command(label="Import Video", command=self.import_video)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=root.quit)
        menu_bar.add_cascade(label="File", menu=file_menu)
        menu_bar.add_command(label="Reload", command=self.reload_thumbnails)

        # Main layout: 3x2 grid (media | preview+timeline | effects)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(1, weight=2)
        self.root.grid_columnconfigure(2, weight=1)

        # --- Left: Project/Media Panel ---
        self.media_panel = tk.Frame(root, bg="#181818", bd=0, highlightbackground="#333", highlightthickness=1)
        self.media_panel.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.media_panel.grid_propagate(False)
        self.media_panel.config(width=260)
        tk.Label(self.media_panel, text="Project", font=("Segoe UI", 12, "bold"), bg="#181818", fg="#fff").pack(anchor="w", padx=12, pady=(10, 2))
        self.media_canvas = tk.Canvas(self.media_panel, bg="#232323", highlightthickness=0)
        self.media_scroll = tk.Scrollbar(self.media_panel, orient=tk.VERTICAL, command=self.media_canvas.yview)
        self.media_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.media_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=(0,8))
        self.media_canvas.configure(yscrollcommand=self.media_scroll.set)
        self.media_inner = tk.Frame(self.media_canvas, bg="#232323")
        self.media_canvas.create_window((0,0), window=self.media_inner, anchor="nw")
        self.media_inner.bind("<Configure>", lambda e: self.media_canvas.configure(scrollregion=self.media_canvas.bbox("all")))

        # --- Center Top: Program/Preview Panel ---
        self.preview_panel = tk.Frame(root, bg="#181818", bd=0, highlightbackground="#333", highlightthickness=1)
        self.preview_panel.grid(row=0, column=1, sticky="nsew")
        tk.Label(self.preview_panel, text="Program", font=("Segoe UI", 12, "bold"), bg="#181818", fg="#fff").pack(anchor="w", padx=12, pady=(10, 2))
        self.preview_canvas = tk.Canvas(self.preview_panel, bg="#000", width=480, height=270, highlightthickness=0)
        self.preview_canvas.pack(padx=16, pady=16, fill=tk.BOTH, expand=True)
        self.preview_canvas.create_text(240, 135, text="Preview", fill="#888", font=("Segoe UI", 20, "bold"))

        # --- Center Bottom: Timeline Panel ---
        self.timeline_panel = tk.Frame(root, bg="#232323", bd=0, highlightbackground="#333", highlightthickness=1, height=140)
        self.timeline_panel.grid(row=1, column=1, sticky="nsew")
        self.timeline_panel.grid_propagate(False)
        
        # Timeline header
        tk.Label(self.timeline_panel, text="Timeline", font=("Segoe UI", 12, "bold"), bg="#232323", fg="#fff").pack(anchor="w", padx=12, pady=(10, 2))
        
        # Timeline canvas and scrollbar
        self.timeline_canvas = tk.Canvas(self.timeline_panel, bg="#181818", height=80, highlightthickness=0)
        self.timeline_scroll = tk.Scrollbar(self.timeline_panel, orient=tk.HORIZONTAL, command=self.timeline_canvas.xview)
        
        # Pack scrollbar and canvas
        self.timeline_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.timeline_canvas.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)
        
        # Configure canvas scroll
        self.timeline_canvas.configure(xscrollcommand=self.timeline_scroll.set)
        
        # Create timeline inner frame
        self.timeline_inner = tk.Frame(self.timeline_canvas, bg="#181818")
        self.timeline_window = self.timeline_canvas.create_window(
            (0, 0), 
            window=self.timeline_inner, 
            anchor="nw",
            width=self.timeline_canvas.winfo_width(),
            height=self.timeline_canvas.winfo_height()
        )
        
        # Bind timeline events
        self.timeline_inner.bind("<Configure>", self.on_timeline_configure)
        self.timeline_canvas.bind("<Configure>", self.on_timeline_canvas_configure)
        
        # Enable drag from thumbnails
        for container in self.thumbnail_labels:
            self.enable_drag(container)

        # Create preview controls
        self.preview_controls = tk.Frame(self.preview_panel, bg="#181818")
        self.preview_controls.pack(fill=tk.X, padx=16, pady=8)
        
        # Create play/pause button
        self.play_button = tk.Button(self.preview_controls, text="▶", command=self.toggle_play,
                                   bg="#2d2d2d", fg="white", width=3, relief="flat")
        self.play_button.pack(side=tk.LEFT, padx=5)
        
        # Create time slider
        self.time_slider = ttk.Scale(self.preview_controls, from_=0, to=100,
                                   orient=tk.HORIZONTAL, command=self.on_slider_change)
        self.time_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        
        # Create time label
        self.time_label = tk.Label(self.preview_controls, text="00:00 / 00:00",
                                 bg="#181818", fg="white")
        self.time_label.pack(side=tk.LEFT, padx=5)
        
        # Schedule the first frame update
        self.root.after(33, self.update_video_frame)  # ~30 FPS

    def enable_drag(self, container):
        """Enable drag and drop for a thumbnail container"""
        container.bind('<ButtonPress-1>', self.on_drag_start_thumbnail)
        container.bind('<B1-Motion>', self.on_drag_motion_thumbnail)
        container.bind('<ButtonRelease-1>', self.on_drag_stop_thumbnail)
        
        # Enable for all child widgets too
        for child in container.winfo_children():
            child.bind('<ButtonPress-1>', self.on_drag_start_thumbnail)
            child.bind('<B1-Motion>', self.on_drag_motion_thumbnail)
            child.bind('<ButtonRelease-1>', self.on_drag_stop_thumbnail)

    def on_drag_start_thumbnail(self, event):
        """Start dragging a thumbnail"""
        if not hasattr(self, 'dragging_thumbnail'):
            widget = event.widget
            # Get the container if we clicked a child widget
            if not widget in self.thumbnail_labels:
                widget = widget.master
            if widget in self.thumbnail_labels:
                self.dragging_thumbnail = widget
                self.drag_start_x = event.x_root
                self.drag_start_y = event.y_root
                
                # Create drag preview
                self.drag_preview = tk.Toplevel(self.root)
                self.drag_preview.overrideredirect(1)
                self.drag_preview.attributes('-alpha', 0.7)
                
                # Copy thumbnail image to preview
                image_label = widget.winfo_children()[0]
                preview_label = tk.Label(self.drag_preview, image=image_label.image)
                preview_label.pack()
                
                # Position preview at mouse
                self.drag_preview.geometry(f"+{event.x_root}+{event.y_root}")

    def on_drag_motion_thumbnail(self, event):
        """Update drag preview position"""
        if hasattr(self, 'drag_preview') and self.drag_preview:
            # Move preview with mouse
            x = event.x_root
            y = event.y_root
            self.drag_preview.geometry(f"+{x}+{y}")
            
            # Check if we're over the timeline
            timeline_bbox = self.timeline_canvas.bbox("all")
            if timeline_bbox:
                tx = self.timeline_canvas.winfo_rootx()
                ty = self.timeline_canvas.winfo_rooty()
                if tx <= x <= tx + self.timeline_canvas.winfo_width() and \
                   ty <= y <= ty + self.timeline_canvas.winfo_height():
                    self.timeline_canvas.configure(bg="#2a2a2a")  # Highlight drop zone
                else:
                    self.timeline_canvas.configure(bg="#181818")  # Reset background

    def on_drag_stop_thumbnail(self, event):
        """Handle dropping a thumbnail"""
        if hasattr(self, 'drag_preview') and self.drag_preview:
            try:
                # Check if we're over the timeline
                x = event.x_root
                y = event.y_root
                tx = self.timeline_canvas.winfo_rootx()
                ty = self.timeline_canvas.winfo_rooty()
                
                if (tx <= x <= tx + self.timeline_canvas.winfo_width() and
                    ty <= y <= ty + self.timeline_canvas.winfo_height()):
                    # Convert screen coordinates to canvas coordinates
                    canvas_x = self.timeline_canvas.canvasx(x - tx)
                    self.add_clip_to_timeline(self.dragging_thumbnail, canvas_x)
                    print(f"Dropped at canvas_x: {canvas_x}")  # Debug info
            except Exception as e:
                print(f"Error in on_drag_stop_thumbnail: {e}")  # Debug info
                
            # Clean up
            self.drag_preview.destroy()
            del self.drag_preview
            self.timeline_canvas.configure(bg="#181818")
            if hasattr(self, 'dragging_thumbnail'):
                del self.dragging_thumbnail

    def add_clip_to_timeline(self, thumbnail_container, x_pos):
        """Add video clip to timeline"""
        try:
            # Get video info
            name_label = thumbnail_container.winfo_children()[1]
            filename = name_label.cget("text")
            video_path = os.path.join(self.project_path, filename)
            
            # Create clip container
            clip_frame = tk.Frame(self.timeline_inner, bg="#2d2d2d", bd=1, relief="solid")
            
            # Get video duration
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = frame_count / fps if fps > 0 else 0
            cap.release()
            
            # Set minimum width for very short clips
            clip_width = max(100, int(duration * self.timeline_scale))
            clip_frame.configure(width=clip_width)
            
            # Add thumbnail
            image_label = thumbnail_container.winfo_children()[0]
            clip_thumb = tk.Label(clip_frame, image=image_label.image, bg="#2d2d2d")
            clip_thumb.image = image_label.image  # Keep reference
            clip_thumb.pack(side=tk.LEFT, padx=2, pady=2)
            
            # Add filename label
            clip_label = tk.Label(clip_frame, text=filename, bg="#2d2d2d", fg="white")
            clip_label.pack(side=tk.LEFT, padx=2)
            
            # Calculate grid-snapped position
            grid_size = 10
            x_pos = max(0, round(x_pos / grid_size) * grid_size)
            
            # Position clip in timeline
            clip_frame.place(x=x_pos, y=10, height=60)
            
            # Store clip info
            clip_info = {
                'widget': clip_frame,
                'filename': filename,
                'start_time': x_pos / self.timeline_scale,
                'duration': duration,
                'path': video_path
            }
            self.timeline_clips.append(clip_info)
            
            # Enable dragging within timeline
            clip_frame.bind('<Button-1>', lambda e, c=clip_frame: self.start_clip_drag(e, c))
            clip_frame.bind('<B1-Motion>', lambda e, c=clip_frame: self.drag_clip(e, c))
            clip_frame.bind('<ButtonRelease-1>', lambda e, c=clip_frame: self.stop_clip_drag(e, c))
            
            # Update scrollregion
            self.update_timeline_scrollregion()
            
            print(f"Added clip: {filename} at x={x_pos}")  # Debug info
            
        except Exception as e:
            print(f"Error adding clip to timeline: {e}")  # Debug info
            messagebox.showerror("Error", f"Failed to add clip to timeline: {e}")

    def start_clip_drag(self, event, clip):
        """Start dragging a timeline clip"""
        clip.drag_start_x = event.x_root
        clip.drag_start_y = event.y_root
        clip.original_x = clip.winfo_x()
        clip.lift()  # Bring to front

    def drag_clip(self, event, clip):
        """Drag a timeline clip"""
        if hasattr(clip, 'drag_start_x'):
            dx = event.x_root - clip.drag_start_x
            new_x = max(0, clip.original_x + dx)
            
            # Snap to grid
            grid_size = 10
            new_x = round(new_x / grid_size) * grid_size
            
            clip.place(x=new_x)
            
            # Update timeline scroll region while dragging
            self.update_timeline_scrollregion()

    def stop_clip_drag(self, event, clip):
        """Stop dragging a timeline clip"""
        if hasattr(clip, 'drag_start_x'):
            # Update clip info with new position
            new_x = clip.winfo_x()
            for clip_info in self.timeline_clips:
                if clip_info['widget'] == clip:
                    clip_info['start_time'] = new_x / self.timeline_scale
                    break
                    
            # Clean up drag attributes
            del clip.drag_start_x
            del clip.drag_start_y
            del clip.original_x
            
            self.update_timeline_scrollregion()

    def update_timeline_scrollregion(self):
        """Update the timeline canvas scroll region"""
        if not self.timeline_clips:
            return
            
        # Find rightmost edge of all clips
        max_x = 0
        for clip_info in self.timeline_clips:
            clip = clip_info['widget']
            clip_right = clip.winfo_x() + clip.winfo_width()
            max_x = max(max_x, clip_right)
        
        # Add some padding
        max_x += 100
        
        # Update scroll region
        self.timeline_canvas.configure(scrollregion=(0, 0, max_x, self.timeline_canvas.winfo_height()))

    def on_timeline_configure(self, event):
        """Handle timeline canvas resize"""
        self.update_timeline_scrollregion()

    def on_timeline_canvas_configure(self, event):
        """Handle timeline canvas resize"""
        # Update timeline window size when canvas is resized
        self.timeline_canvas.itemconfig(
            self.timeline_window,
            width=max(self.timeline_canvas.winfo_width(), 
                     self.timeline_inner.winfo_reqwidth()),
            height=max(self.timeline_canvas.winfo_height(),
                      self.timeline_inner.winfo_reqheight())
        )
        # Update scroll region
        self.update_timeline_scrollregion()

    def update_overlay_size(self, event=None):
        """Update the selection overlay size when media_inner size changes"""
        if hasattr(self, 'selection_overlay'):
            self.selection_overlay.configure(
                width=self.media_inner.winfo_width(),
                height=self.media_inner.winfo_height()
            )

    def arrange_thumbnails(self, event=None):
        if not self.thumbnail_labels:
            return
        # Get the width of the canvas
        canvas_width = self.media_canvas.winfo_width()
        if canvas_width == 1:
            return
        # Thumbnail size + padding
        thumb_width = 150 + 10  # 150 width + 5 padding each side
        # Calculate number of columns that fit
        cols = max(1, canvas_width // thumb_width)
        # Arrange thumbnails in grid
        for index, label in enumerate(self.thumbnail_labels):
            row = index // cols
            col = index % cols
            label.grid_configure(row=row, column=col, padx=5, pady=5)

    def get_columns(self):
        canvas_width = self.media_canvas.winfo_width()
        thumb_width = 150 + 10
        return max(1, canvas_width // thumb_width)

    def import_video(self):
        filetypes = (
            ("Video files", "*.mp4 *.avi *.mov *.mkv"),
            ("All files", "*.*")
        )
        filepaths = filedialog.askopenfilenames(title="Open Video Files", filetypes=filetypes)
        if filepaths:
            for filepath in filepaths:
                self.add_thumbnail(filepath)
        else:
            messagebox.showinfo("Import Cancelled", "No video file was selected.")

    def show_control_context_menu(self, event):
        pass

    def create_new_folder_in_project(self):
        # Prompt user for folder name
        folder_name = tk.simpledialog.askstring("Create New Folder", "Enter folder name:")
        if folder_name:
            folder_path = os.path.join(self.project_path, folder_name)
            try:
                os.makedirs(folder_path, exist_ok=True)
                messagebox.showinfo("Success", f"Folder '{folder_name}' created successfully.")

                # Add folder icon to the UI
                self.add_folder_icon(folder_name, folder_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create folder: {e}")

    def add_folder_icon(self, folder_name, folder_path):
        # Load folder icon
        folder_icon_path = os.path.join("icons", "folder_icon (64x64).png")
        try:
            folder_image = Image.open(folder_icon_path)
            folder_image = folder_image.resize((32, 32), Image.LANCZOS)
            folder_icon = ImageTk.PhotoImage(folder_image)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load folder icon: {e}")
            return

        # Create folder container in media_inner
        container = tk.Frame(self.media_inner, bg="#232323", bd=2, relief="solid")
        row = len(self.thumbnail_labels) // self.get_columns()
        col = len(self.thumbnail_labels) % self.get_columns()
        container.grid(row=row, column=col, padx=5, pady=5, sticky="nw")

        # Add folder icon
        icon_label = tk.Label(container, image=folder_icon, bg="#232323")
        icon_label.image = folder_icon  # Keep reference
        icon_label.pack()

        # Add editable folder name label
        name_var = tk.StringVar(value=folder_name)
        name_entry = tk.Entry(container, textvariable=name_var, bg="#232323", fg="white", justify="center", bd=0)
        name_entry.pack()

        # Bind events to handle renaming
        name_entry.bind("<Return>", lambda e: self.rename_folder(name_var, folder_path))
        name_entry.bind("<FocusOut>", lambda e: self.rename_folder(name_var, folder_path))

        self.thumbnail_labels.append(container)
        container.selected = False

    def rename_folder(self, name_var, folder_path):
        new_name = name_var.get().strip()
        if new_name and new_name != os.path.basename(folder_path):
            new_path = os.path.join(os.path.dirname(folder_path), new_name)
            try:
                os.rename(folder_path, new_path)
                # Sau khi đổi tên thành công, unbind các sự kiện để tránh gọi lại
                entry_widget = None
                for container in self.thumbnail_labels:
                    for child in container.winfo_children():
                        if isinstance(child, tk.Entry) and child.get() == new_name:
                            entry_widget = child
                            break
                if entry_widget:
                    entry_widget.unbind("<Return>")
                    entry_widget.unbind("<FocusOut>")
                # Cập nhật lại folder_path nếu cần dùng tiếp
                folder_path = new_path
            except Exception as e:
                messagebox.showerror("Error", f"Failed to rename folder: {e}")

    def add_thumbnail(self, video_path):
        # Extract the first frame of the video using OpenCV
        cap = cv2.VideoCapture(video_path)
        
        success, frame = cap.read()
        if success:
            frame = cv2.resize(frame, (150, 100))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame)
            thumbnail_image = ImageTk.PhotoImage(image)
        else:
            image = Image.new('RGB', (150, 100), color='gray')
            thumbnail_image = ImageTk.PhotoImage(image)
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration_sec = frame_count / fps if fps > 0 else 0
        cap.release()

        # Create thumbnail container with border
        container = tk.Frame(self.media_inner, bg="#232323", bd=2, relief="solid")

        # Add the container using grid
        row = len(self.thumbnail_labels) // self.get_columns()
        col = len(self.thumbnail_labels) % self.get_columns()
        container.grid(row=row, column=col, padx=5, pady=5, sticky="nw")

        # Thumbnail image label
        label = tk.Label(container, image=thumbnail_image, bg="#232323")
        label.image = thumbnail_image  # Keep reference
        label.pack()

        # Video filename label
        filename = os.path.basename(video_path)
        name_label = tk.Label(container, text=filename, bg="#232323", fg="white", wraplength=150)
        name_label.pack()

        # Duration label
        minutes = int(duration_sec // 60)
        seconds = int(duration_sec % 60)
        duration_str = f"{minutes}:{seconds:02d}"
        duration_label = tk.Label(container, text=duration_str, bg="#232323", fg="yellow", font=("Arial", 9))
        duration_label.pack()

        self.thumbnails.append(thumbnail_image)
        self.thumbnail_labels.append(container)
        container.selected = False

        # Configure thumbnail interactions
        container.bind("<Button-1>", self.on_thumbnail_click)
        container.bind("<B1-Motion>", self.on_thumbnail_drag)
        container.bind("<ButtonRelease-1>", self.on_thumbnail_release)
        
        # Enable for child widgets too
        for child in container.winfo_children():
            child.bind("<Button-1>", self.on_thumbnail_click)
            child.bind("<B1-Motion>", self.on_thumbnail_drag)
            child.bind("<ButtonRelease-1>", self.on_thumbnail_release)
        
        # Configure hover and selection effects
        container.bind("<Enter>", lambda e, c=container: self.on_hover_enter(e, c))
        container.bind("<Leave>", lambda e, c=container: self.on_hover_leave(e, c))
        container.bind("<Button-3>", lambda e, c=container: self.show_context_menu(e, c))

        self.arrange_thumbnails()

    def show_empty_space_context_menu(self, event):
        # Check if click is in empty space in media_canvas
        clicked_widget = self.media_canvas.find_closest(
            self.media_canvas.canvasx(event.x),
            self.media_canvas.canvasy(event.y)
        )
        if not clicked_widget or not self.media_canvas.gettags(clicked_widget[0]):
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="Create New Folder", command=self.create_new_folder_in_project)
            menu.tk_popup(event.x_root, event.y_root)

    def select_all_items(self, event=None):
        """Select all thumbnails"""
        for container in self.thumbnail_labels:
            if not container.selected:
                self.toggle_selection(container)

    def sort_items(self, by="name"):
        if not self.thumbnail_labels:
            return
            
        if by == "name":
            sorted_items = sorted(self.thumbnail_labels, 
                key=lambda x: x.winfo_children()[1].cget("text").lower())
        else:  # by date
            sorted_items = sorted(self.thumbnail_labels,
                key=lambda x: os.path.getmtime(x.winfo_children()[1].cget("text")))

        # Reorder items
        for idx, container in enumerate(sorted_items):
            row = idx // self.get_columns()
            col = idx % self.get_columns() 
            container.grid(row=row, column=col, padx=5, pady=5)
            
        self.thumbnail_labels = sorted_items

    def paste_items(self):
        # Implement clipboard paste functionality
        pass

    def on_canvas_configure(self, event):
        self.arrange_thumbnails(event)

    def on_mousewheel(self, event):
        self.media_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def on_hover_enter(self, event, container):
        if not container.selected:
            container.configure(bg='#202020')  # Slightly lighter background on hover
            for child in container.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(bg='#202020')

    def on_hover_leave(self, event, container):
        if not container.selected:
            container.configure(bg='#232323')  # Reset to default background
            for child in container.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(bg='#232323')

    def on_drag_start(self, event):
        """Start drawing selection rectangle"""
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.dragging = True
        
        # Clear previous selection if Ctrl is not pressed
        if not self.ctrl_pressed:
            for container in self.thumbnail_labels:
                if container.selected:
                    self.toggle_selection(container)

    def on_drag_motion(self, event):
        """Update selection rectangle as mouse moves"""
        if not self.dragging:
            return

        # Delete previous selection rectangle
        if self.selection_rect:
            self.selection_overlay.delete(self.selection_rect)

        # Draw new selection rectangle
        self.selection_rect = self.selection_overlay.create_rectangle(
            self.drag_start_x, self.drag_start_y,
            event.x, event.y,
            outline='#00a2ff',
            fill='#00a2ff20'
        )

        # Check which thumbnails are in the selection
        selection_bbox = (
            min(self.drag_start_x, event.x),
            min(self.drag_start_y, event.y),
            max(self.drag_start_x, event.x),
            max(self.drag_start_y, event.y)
        )

        for container in self.thumbnail_labels:
            container_bbox = (
                container.winfo_x(),
                container.winfo_y(),
                container.winfo_x() + container.winfo_width(),
                container.winfo_y() + container.winfo_height()
            )
            
            if self.rectangles_overlap(selection_bbox, container_bbox):
                if not container.selected:
                    self.toggle_selection(container)
            elif not self.ctrl_pressed and container.selected:
                self.toggle_selection(container)

    def on_drag_release(self, event):
        """Clean up after selection is complete"""
        if self.selection_rect:
            self.selection_overlay.delete(self.selection_rect)
        self.selection_rect = None
        self.dragging = False

    def on_ctrl_press(self, event):
        """Handle Ctrl key press"""
        self.ctrl_pressed = True

    def on_ctrl_release(self, event):
        """Handle Ctrl key release"""
        self.ctrl_pressed = False

    def get_widget_bbox(self, widget):
        """Get the bounding box of a widget relative to the selection overlay"""
        x = widget.winfo_x()
        y = widget.winfo_y()
        width = widget.winfo_width()
        height = widget.winfo_height()
        return (x, y, x + width, y + height)

    def rectangles_overlap(self, rect1, rect2):
        """Check if two rectangles overlap"""
        return not (rect1[2] < rect2[0] or  # r1 right < r2 left
                   rect1[0] > rect2[2] or  # r1 left > r2 right
                   rect1[3] < rect2[1] or  # r1 bottom < r2 top
                   rect1[1] > rect2[3])    # r1 top > r2 bottom

    def toggle_selection(self, container):
        """Toggle selection state of a thumbnail container"""
        if not hasattr(container, 'selected'):
            container.selected = False
        container.selected = not container.selected
        
        if container.selected:
            container.configure(bg='#404040')  # Darker background when selected
            for child in container.winfo_children():
                if isinstance(child, (tk.Label, tk.Entry)):
                    child.configure(bg='#404040')
        else:
            container.configure(bg='#232323')  # Reset to default background
            for child in container.winfo_children():
                if isinstance(child, (tk.Label, tk.Entry)):
                    child.configure(bg='#232323')

    def reload_thumbnails(self):
        # Xóa toàn bộ thumbnail hiện tại
        for container in self.thumbnail_labels:
            container.destroy()
        self.thumbnail_labels.clear()
        self.thumbnails.clear()
        # Reload lại các folder trong project
        if self.project_path and os.path.isdir(self.project_path):
            for name in os.listdir(self.project_path):
                path = os.path.join(self.project_path, name)
                if os.path.isdir(path):
                    self.add_folder_icon(name, path)
        # Reload lại các video (nếu muốn, có thể lọc theo đuôi file video)
        if self.project_path and os.path.isdir(self.project_path):
            for name in os.listdir(self.project_path):
                path = os.path.join(self.project_path, name)
                if os.path.isfile(path) and name.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
                    self.add_thumbnail(path)
        self.arrange_thumbnails()

    def show_context_menu(self, event, container):
        """Show context menu for thumbnail items"""
        # Select the item if not already selected
        if not getattr(container, 'selected', False):
            self.toggle_selection(container)

        menu = tk.Menu(self.root, tearoff=0)
        menu.configure(bg='#2d2d2d', fg='white', activebackground='#404040', activeforeground='white')
        
        # Count selected items
        selected_count = sum(1 for c in self.thumbnail_labels if getattr(c, 'selected', False))
        
        if selected_count > 1:
            menu.add_command(label=f"Delete {selected_count} items", 
                           command=lambda: self.delete_selected_items())
        else:
            name_label = container.winfo_children()[1]
            filename = name_label.cget("text")
            menu.add_command(label=f"Preview {filename}", 
                           command=lambda: self.open_video_preview(filename))
            menu.add_command(label=f"Open {filename}", 
                           command=lambda: self.open_media(filename))
            menu.add_command(label="Rename", 
                           command=lambda: self.rename_media(container))
            menu.add_separator()
            menu.add_command(label="Delete", 
                           command=lambda: self.delete_media(container))
        
        menu.add_separator()
        menu.add_command(label="Select All", command=self.select_all_items)
        
        menu.tk_popup(event.x_root, event.y_root)

    def delete_media(self, container):
        """Delete a media item (folder or video)"""
        # If it's a folder, delete the folder and its contents
        name_label = container.winfo_children()[1]
        folder_name = name_label.cget("text")
        folder_path = os.path.join(self.project_path, folder_name)
        if os.path.isdir(folder_path):
            if messagebox.askyesno("Confirm Delete", f"Delete folder '{folder_name}' and all its contents?"):
                import shutil
                shutil.rmtree(folder_path)
                self.reload_thumbnails()
        else:
            # Otherwise, delete the video file
            if messagebox.askyesno("Confirm Delete", f"Delete video '{folder_name}'?"):
                os.remove(folder_path)
                self.reload_thumbnails()

    def open_media(self, filename):
        """Open the media file with the default application"""
        file_path = os.path.join(self.project_path, filename)
        if os.path.isfile(file_path):
            os.startfile(file_path)

    def rename_media(self, container):
        """Rename a media item (folder or video)"""
        name_label = container.winfo_children()[1]
        current_name = name_label.cget("text")
        new_name = simpledialog.askstring("Rename", "Enter new name:", initialvalue=current_name)
        if new_name and new_name != current_name:
            # Rename logic here (update both UI and filesystem)
            pass

    def delete_selected_items(self):
        """Delete all selected items"""
        selected = [c for c in self.thumbnail_labels if getattr(c, 'selected', False)]
        if not selected:
            return
            
        if messagebox.askyesno("Confirm Delete", f"Delete {len(selected)} items?"):
            for container in selected[:]:
                self.delete_media(container)

    def on_thumbnail_click(self, event):
        """Handle click on thumbnail"""
        widget = event.widget
        # Get container if clicked on child widget
        if widget not in self.thumbnail_labels:
            widget = widget.master
        
        if widget in self.thumbnail_labels:
            self.drag_data = {
                'widget': widget,
                'start_x': event.x_root,
                'start_y': event.y_root,
                'dragging': False
            }
            
            # Handle selection
            if not event.state & 0x0004:  # If Ctrl not pressed
                # Deselect others if not dragging
                for container in self.thumbnail_labels:
                    if container != widget and container.selected:
                        self.toggle_selection(container)
                self.toggle_selection(widget)
                
                # Open video in preview
                filename = widget.winfo_children()[1].cget("text")
                self.open_video_preview(filename)
            else:
                self.toggle_selection(widget)

    def on_thumbnail_drag(self, event):
        """Handle dragging thumbnail"""
        if not hasattr(self, 'drag_data') or not self.drag_data:
            return
            
        # Calculate distance moved
        dx = event.x_root - self.drag_data['start_x']
        dy = event.y_root - self.drag_data['start_y']
        distance = (dx ** 2 + dy ** 2) ** 0.5
        
        # Start dragging if moved more than 5 pixels
        if not self.drag_data['dragging'] and distance > 5:
            self.drag_data['dragging'] = True
            self.start_drag_preview(event)
        
        # Update preview position if dragging
        if self.drag_data['dragging'] and hasattr(self, 'drag_preview') and self.drag_preview:
            self.drag_preview.geometry(f"+{event.x_root}+{event.y_root}")
            
            # Check if over timeline
            timeline_bbox = self.timeline_canvas.bbox("all")
            if timeline_bbox:
                tx = self.timeline_canvas.winfo_rootx()
                ty = self.timeline_canvas.winfo_rooty()
                if (tx <= event.x_root <= tx + self.timeline_canvas.winfo_width() and
                    ty <= event.y_root <= ty + self.timeline_canvas.winfo_height()):
                    self.timeline_canvas.configure(bg="#2a2a2a")  # Highlight drop zone
                else:
                    self.timeline_canvas.configure(bg="#181818")  # Reset background

    def on_thumbnail_release(self, event):
        """Handle releasing thumbnail"""
        if not hasattr(self, 'drag_data') or not self.drag_data or not self.drag_data.get('dragging'):
            return
            
        try:
            # Check if released over timeline
            timeline_bbox = self.timeline_canvas.bbox("all")
            if timeline_bbox:
                tx = self.timeline_canvas.winfo_rootx()
                ty = self.timeline_canvas.winfo_rooty()
                if (tx <= event.x_root <= tx + self.timeline_canvas.winfo_width() and
                    ty <= event.y_root <= ty + self.timeline_canvas.winfo_height()):
                    # Convert screen coordinates to canvas coordinates
                    canvas_x = event.x_root - tx
                    self.add_clip_to_timeline(self.drag_data['widget'], canvas_x)
                    print(f"Dropped at canvas_x: {canvas_x}")  # Debug info
            
            # Clean up drag preview
            if hasattr(self, 'drag_preview') and self.drag_preview:
                self.drag_preview.destroy()
                delattr(self, 'drag_preview')
            self.timeline_canvas.configure(bg="#181818")
            
        except Exception as e:
            print(f"Error in on_thumbnail_release: {e}")  # Debug info
        
        finally:
            self.drag_data = {}

    def start_drag_preview(self, event):
        """Create and show drag preview"""
        if not hasattr(self, 'drag_data') or not self.drag_data:
            return
            
        widget = self.drag_data['widget']
        
        # Create preview window
        self.drag_preview = tk.Toplevel(self.root)
        self.drag_preview.overrideredirect(1)
        self.drag_preview.attributes('-alpha', 0.7)
        self.drag_preview.attributes('-topmost', True)
        
        # Copy thumbnail image to preview
        image_label = widget.winfo_children()[0]
        preview = tk.Label(self.drag_preview, image=image_label.image,
                         bg=widget.cget('bg'))
        preview.pack()
        
        # Position preview at mouse
        self.drag_preview.geometry(f"+{event.x_root}+{event.y_root}")

    def toggle_play(self):
        """Toggle video playback"""
        if self.current_video is None:
            return
            
        self.video_playing = not self.video_playing
        self.play_button.configure(text="⏸" if self.video_playing else "▶")

    def on_slider_change(self, value):
        """Handle time slider change"""
        if self.current_video is None:
            return
            
        # Convert slider value (0-100) to frame position
        frame_pos = int(float(value) * self.frame_count / 100)
        self.current_video.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
        self.current_frame_pos = frame_pos
        
        # Update time label
        self.update_time_label()
        
        # Read and display the frame
        success, frame = self.current_video.read()
        if success:
            self.show_frame(frame)

    def update_time_label(self):
        """Update the time label with current/total duration"""
        if self.current_video is None or self.fps == 0:
            return
            
        current_time = self.current_frame_pos / self.fps
        total_time = self.frame_count / self.fps
        
        current_min = int(current_time // 60)
        current_sec = int(current_time % 60)
        total_min = int(total_time // 60)
        total_sec = int(total_time % 60)
        
        self.time_label.configure(
            text=f"{current_min:02d}:{current_sec:02d} / {total_min:02d}:{total_sec:02d}"
        )

    def update_video_frame(self):
        """Update video frame in preview"""
        if self.current_video is not None and self.video_playing:
            success, frame = self.current_video.read()
            if success:
                self.show_frame(frame)
                self.current_frame_pos += 1
                
                # Update slider position
                if self.frame_count > 0:
                    slider_value = (self.current_frame_pos / self.frame_count) * 100
                    self.time_slider.set(slider_value)
                
                # Update time label
                self.update_time_label()
                
                # Loop video if at end
                if self.current_frame_pos >= self.frame_count:
                    self.current_video.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self.current_frame_pos = 0
            else:
                # Reset video if we couldn't read a frame
                self.current_video.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.current_frame_pos = 0
        
        # Schedule next frame update
        self.root.after(33, self.update_video_frame)  # ~30 FPS

    def show_frame(self, frame):
        """Display a frame in the preview canvas"""
        if frame is None:
            return
            
        # Resize frame to fit preview canvas while maintaining aspect ratio
        canvas_width = self.preview_canvas.winfo_width()
        canvas_height = self.preview_canvas.winfo_height()
        
        frame_height, frame_width = frame.shape[:2]
        scale = min(canvas_width/frame_width, canvas_height/frame_height)
        
        if scale < 1:
            new_width = int(frame_width * scale)
            new_height = int(frame_height * scale)
            frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        # Convert frame to PhotoImage
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame)
        photo = ImageTk.PhotoImage(image=image)
        
        # Update canvas
        self.preview_canvas.delete("all")
        self.current_frame = photo  # Keep a reference!
        
        # Center the frame in canvas
        x = (canvas_width - frame.shape[1]) // 2
        y = (canvas_height - frame.shape[0]) // 2
        self.preview_canvas.create_image(x, y, image=photo, anchor="nw")

    def open_video_preview(self, filename):
        """Open a video file in the preview panel"""
        video_path = os.path.join(self.project_path, filename)
        
        # Close current video if one is open
        if self.current_video is not None:
            self.current_video.release()
            self.video_playing = False
            self.play_button.configure(text="▶")
        
        # Open new video
        self.current_video = cv2.VideoCapture(video_path)
        if self.current_video.isOpened():
            # Get video properties
            self.frame_count = int(self.current_video.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.current_video.get(cv2.CAP_PROP_FPS)
            self.current_frame_pos = 0
            
            # Read first frame
            success, frame = self.current_video.read()
            if success:
                self.show_frame(frame)
                self.update_time_label()
            
            # Reset slider
            self.time_slider.set(0)
        else:
            messagebox.showerror("Error", f"Could not open video: {filename}")
            self.current_video = None

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoEditorApp(root)
    root.mainloop()