"""
Auto-update checker for AdviseMe.
Checks GitHub Releases API on startup and prompts the user if a newer version exists.
"""

import threading
import webbrowser
import tkinter as tk
from tkinter import messagebox
import urllib.request
import urllib.error
import json

GITHUB_OWNER = "StratosCG"
GITHUB_REPO  = "AdviseMe"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
DOWNLOAD_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"


def _parse_version(tag: str) -> tuple:
    """Convert 'v1.2.3' or '1.2.3' to (1, 2, 3) for comparison."""
    tag = tag.lstrip("v").strip()
    try:
        return tuple(int(x) for x in tag.split("."))
    except ValueError:
        return (0,)


def _fetch_latest_version() -> tuple[str, str] | None:
    """
    Returns (latest_tag, release_name) or None if the check fails.
    Runs in a background thread — must not touch Tkinter widgets directly.
    """
    try:
        req = urllib.request.Request(
            RELEASES_URL,
            headers={"User-Agent": "AdviseMe-updater/1.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        tag  = data.get("tag_name", "")
        name = data.get("name", tag)
        return (tag, name) if tag else None
    except Exception:
        # No internet, rate-limited, or repo has no releases yet — silently ignore
        return None


def _show_update_dialog(current: str, latest_tag: str, release_name: str) -> None:
    """Shows a Tkinter messagebox on the main thread."""
    answer = messagebox.askyesno(
        "Update Available",
        f"A new version of AdviseMe is available!\n\n"
        f"  Current version : {current}\n"
        f"  Latest version  : {latest_tag}  ({release_name})\n\n"
        f"Would you like to open the download page?",
        icon="info",
    )
    if answer:
        webbrowser.open(DOWNLOAD_URL)


def check_for_updates(root: tk.Tk, current_version: str) -> None:
    """
    Entry point — call this once from app startup.
    Spawns a background thread so it never blocks the UI.
    """

    def _worker():
        result = _fetch_latest_version()
        if result is None:
            return  # No release found or no internet

        latest_tag, release_name = result
        if _parse_version(latest_tag) > _parse_version(current_version):
            # Schedule the dialog on the main Tkinter thread
            root.after(0, lambda: _show_update_dialog(current_version, latest_tag, release_name))

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
