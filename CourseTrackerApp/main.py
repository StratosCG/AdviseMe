"""
Course Tracker - Desktop Advisement Tool
Main entry point.

Usage:
    python main.py
"""
import os
import sys

# Ensure the app directory is on the path
app_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, app_dir)

# Try CustomTkinter first for modern UI, fall back to plain tkinter
try:
    import customtkinter as ctk
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    HAS_CTK = True
except ImportError:
    HAS_CTK = False

from gui.app import CourseTrackerApp


def main():
    if HAS_CTK:
        root = ctk.CTk()
    else:
        import tkinter as tk
        root = tk.Tk()

    # Set app icon if available
    icon_path = os.path.join(app_dir, "assets", "icon.ico")
    if os.path.exists(icon_path):
        root.iconbitmap(icon_path)

    app = CourseTrackerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
