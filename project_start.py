import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from PIL import Image, ImageTk
import os
import subprocess
import sys

class ProjectStartApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Start Video Editor Project")
        self.root.geometry("420x260")
        self.root.configure(bg="#f7f7fa")
        self.root.resizable(False, False)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', font=("Segoe UI", 12), padding=8, borderwidth=0, relief="flat", background="#ffffff", foreground="#222", focuscolor="#e0e0e0")
        style.map('TButton', background=[('active', '#e6e6f2')])

        label = tk.Label(root, text="Xin Chào!", font=("Segoe UI", 18, "bold"), bg="#f7f7fa", fg="#222")
        label.pack(pady=(32, 18))

        # Load icons
        icon_new = Image.open(os.path.join("icons", "create_new_project (64 x 64 px).png"))
        icon_new = icon_new.resize((36, 36), Image.LANCZOS)
        self.icon_new_img = ImageTk.PhotoImage(icon_new)

        icon_open = Image.open(os.path.join("icons", "open_folder (64 x 64 px).png"))
        icon_open = icon_open.resize((36, 36), Image.LANCZOS)
        self.icon_open_img = ImageTk.PhotoImage(icon_open)

        btn_new = ttk.Button(root, text="  Create New Project", image=self.icon_new_img, compound="left", command=self.create_new_project, style='TButton')
        btn_new.pack(pady=10, ipadx=8, ipady=2)

        btn_open = ttk.Button(root, text="  Open Existing Project", image=self.icon_open_img, compound="left", command=self.open_existing_project, style='TButton')
        btn_open.pack(pady=10, ipadx=8, ipady=2)

    def create_new_project(self):
        folder = filedialog.askdirectory(title="Select or Create New Project Folder")
        if folder:
            if not os.path.exists(folder):
                if not os.access(os.path.dirname(folder), os.W_OK):
                    messagebox.showerror("Error", "The selected location is not writable.")
                    return
                try:
                    os.makedirs(folder)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create folder: {e}")
                    return
        self.launch_editor(folder)

    def open_existing_project(self):
        folder = filedialog.askdirectory(title="Select Existing Project Folder")
        if folder:
            if not os.path.exists(folder):
                messagebox.showerror("Error", "The selected folder does not exist.")
                return
            try:
                editor_path = os.path.join(os.path.dirname(__file__), "video_editor_app.py")
                project_path = folder
                if not os.path.exists(editor_path):
                    messagebox.showerror("Error", f"Editor file not found: {editor_path}")
                    return
                subprocess.Popen([sys.executable, editor_path, project_path])
                self.root.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to launch editor: {e}")

    def launch_editor(self, folder):
        try:
            editor_path = os.path.join(os.path.dirname(__file__), "video_editor_app.py")
            if not os.path.exists(editor_path):
                messagebox.showerror("Error", f"Editor file not found: {editor_path}")
                return
            subprocess.Popen([sys.executable, editor_path, folder])
            self.root.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch editor: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ProjectStartApp(root)
    root.mainloop()
