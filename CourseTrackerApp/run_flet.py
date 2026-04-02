"""Launch the Flet-based AdviseMe application."""
import os
import sys
import ssl

# Ensure the app directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Fix SSL certificate verification for corporate networks / bundled exe.
# Must run BEFORE flet imports trigger any network calls.
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass

try:
    ssl.create_default_context()
except ssl.SSLError:
    ssl._create_default_https_context = ssl.create_unverified_context

import flet as ft
from gui.flet_app import app

if __name__ == "__main__":
    ft.run(main=app)
