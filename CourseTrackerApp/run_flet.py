"""Launch the Flet-based AdviseMe application."""
import os
import sys

# Ensure the app directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flet as ft
from gui.flet_app import app

if __name__ == "__main__":
    ft.app(target=app)
