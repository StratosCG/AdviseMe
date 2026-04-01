"""
Course Tracker GUI Application — Dashboard-style UI with CustomTkinter.

RBSD branded interface with card-based layout, visual analytics,
and Human Mode for manual course status editing.
"""
import os
import sys
import math
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import customtkinter as ctk
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    HAS_CTK = True
except ImportError:
    HAS_CTK = False

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import (
    GridHighlight, CourseStatus, StudentRecord, ProgramGrid, SemesterPlan
)
from core.evaluation_parser import parse_evaluation_pdf
from core.grid_loader import (
    load_program_grid, list_available_programs, get_programs_dir,
    load_faculty, get_faculty_for_department
)
from core.course_matcher import (
    match_courses, detect_current_semester, find_gap_courses,
    get_next_semester_courses, get_completion_stats,
    get_unmatched_courses, get_free_elective_courses,
    get_all_remaining_grid_courses, get_transfer_courses
)
from core.semester_planner import (
    generate_plan, auto_detect_semester_label, auto_detect_semester_index,
    get_strategy_options, get_available_semesters,
    STRATEGY_CAP_18, STRATEGY_ADVISOR_PICKS, STRATEGY_SWAP
)
from core.pdf_generator import generate_grid_pdf, generate_semester_plan_pdf
from core.updater import check_for_updates
from version import __version__


# ── Brand Colors  (dark dashboard theme) ────────────────────────
NAVY       = "#15293F"       # brand accent
NAVY_LIGHT = "#1E3A5F"       # buttons / active elements
NAVY_MID   = "#2A4A6B"
GRAY       = "#64748B"
GRAY_LIGHT = "#475569"
BLUE       = "#8FC3E9"       # highlight accent
BLUE_DARK  = "#5BA3D9"       # CTA accent
WHITE      = "#FFFFFF"

# Dark surfaces
BG             = "#0B1120"       # deep page background
CARD_BG        = "#111B2E"       # card / panel surface
SIDEBAR_BG     = "#1B2B44"       # sidebar surface (slate blue)
SIDEBAR_GRAD_TOP    = "#1B2B44"
SIDEBAR_GRAD_BOTTOM = "#152238"
BORDER         = "#1E2D42"       # subtle separator
TEXT_PRIMARY   = "#E2E8F0"       # light text on dark
TEXT_SECONDARY = "#94A3B8"
TEXT_MUTED     = "#64748B"

# Header (stays light — white banner with logo)
HDR_BG_COLOR       = "#FFFFFF"
HDR_TEXT_DARK      = "#1A202C"   # dark text on white header
HDR_BORDER         = "#E2E8F0"   # header-specific border
HDR_SHADOW_1       = "#C8D4E0"
HDR_SHADOW_2       = "#E2E8F0"

# Status colors (vibrant on dark backgrounds)
GREEN      = "#48BB78"
GREEN_BG   = "#1A3A2A"
ORANGE     = "#ED8936"
ORANGE_BG  = "#2D2415"
RED        = "#FC8181"
RED_BG     = "#2D1A1A"
BLUE_STATUS = "#63B3ED"
BLUE_BG    = "#1A2840"
PURPLE     = "#9F7AEA"
PURPLE_BG  = "#251A3A"

# Grid cell colors — kept LIGHT for readability
GRID_GREEN    = "#C6F6D5"
GRID_TRANSFER = "#E9D8FD"
GRID_ORANGE   = "#F9C96A"
GRID_RED      = "#FCA5A5"
GRID_BLUE     = "#BEE3F8"
GRID_WHITE    = "#FFFFFF"
GRID_TEXT     = "#1A202C"       # dark text on light grid cells
GRID_BG       = "#E8EDF2"       # very light navy-blue behind the grid

# Fonts
F_TITLE   = ("Segoe UI", 18, "bold")
F_HEADING = ("Segoe UI", 13, "bold")
F_LABEL   = ("Segoe UI", 11)
F_BODY    = ("Segoe UI", 11)
F_SMALL   = ("Segoe UI", 10)
F_TINY    = ("Segoe UI", 10)
F_GRID    = ("Segoe UI", 9)
F_GRID_B  = ("Segoe UI", 8, "bold")
F_METRIC  = ("Segoe UI", 22, "bold")
F_METRIC_LABEL = ("Segoe UI", 9)


def _asset_path(filename: str) -> str:
    """Resolve path to bundled assets — works in dev and PyInstaller."""
    base = getattr(sys, '_MEIPASS', None)
    if base:
        return os.path.join(base, 'assets', filename)
    # Dev: assets/ sits next to gui/ (one level up from this file)
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'assets', filename)


def _load_tk_image(filename: str, size: tuple = None):
    """Load an image as a Tkinter-compatible PhotoImage. Returns None on failure."""
    if not HAS_PIL:
        return None
    try:
        path = _asset_path(filename)
        img = Image.open(path).convert('RGBA')
        if size:
            img = img.resize(size, Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


def _ctk_combo(parent, entry_fg=None, **kw) -> "ctk.CTkComboBox":
    """
    Create a CTkComboBox with a white dropdown arrow on the navy button.

    CTK uses the same `text_color` for both the entry text AND the arrow
    fill polygon. Setting text_color=WHITE gives a white arrow, but also
    makes the entry text invisible on the entry background. After creation
    we patch the internal Entry widget to use the correct text color.

    Pass entry_fg to override the entry text color (e.g. dark text on
    a white-background combo in the header).
    """
    combo = ctk.CTkComboBox(parent, text_color=WHITE, **kw)
    _fg = entry_fg or TEXT_PRIMARY
    try:
        combo._entry.configure(
            fg=_fg,
            disabledforeground=TEXT_MUTED,
            insertbackground=_fg,
        )
    except Exception:
        pass
    return combo


def _card(parent, bg=None, **kw):
    """Create a card-like frame with subtle border."""
    _bg = bg or CARD_BG
    f = tk.Frame(parent, bg=_bg, highlightbackground=BORDER,
                 highlightthickness=1, **kw)
    return f


class CourseTrackerApp:
    """Dashboard-style application."""

    def __init__(self, root):
        self.root = root
        self.root.title("AdviseMe — RBSD | Internal Tool")
        self.root.configure(bg=BG)

        # State
        self.grid: ProgramGrid = None
        self.record: StudentRecord = None
        self.plan: SemesterPlan = None
        self._last_advisor_picks: set = set()   # course codes from last dialog confirm
        self.current_semester_idx: int = -1
        self.programs_dir = get_programs_dir()

        # Private View — load persisted state before building UI
        self._private_view: bool = self._load_config().get("private_view", False)

        # Human-mode manual student info
        self._human_name_var = tk.StringVar()
        self._human_id_var = tk.StringVar()
        self._human_gpa_var = tk.StringVar()
        self._human_credits_var = tk.StringVar()

        # Set window icon (taskbar + title bar)
        self._set_window_icon()

        # Show welcome splash screen first
        self._show_welcome_screen()

    def _launch_main_app(self):
        """Transition from welcome screen to the main application."""
        # Destroy splash screen and restore resizability
        if hasattr(self, '_welcome_frame'):
            self._welcome_frame.destroy()
        self.root.resizable(True, True)
        self.root.geometry("1600x1000")
        self.root.minsize(1400, 950)

        # Build main UI
        self._build_header()
        self._build_body()
        self._build_status_bar()
        self._refresh_programs()

        # Apply Private View visibility AFTER sidebar is fully built
        if self._private_view:
            self._apply_private_view(True)

        # Check for updates in background (non-blocking)
        check_for_updates(self.root, __version__)

    # ================================================================
    #  WELCOME SCREEN
    # ================================================================

    def _show_welcome_screen(self):
        """Display a branded splash / welcome screen on launch."""
        # Lock window to match the welcome background image ratio (5504×3072 ≈ 16:9)
        self.root.geometry("1440x804")
        self.root.resizable(False, False)

        self._welcome_frame = tk.Frame(self.root, bg=BG)
        self._welcome_frame.pack(fill=tk.BOTH, expand=True)

        # ── Right panel: background image ──
        right_panel = tk.Canvas(self._welcome_frame, highlightthickness=0, bd=0, bg=BG)
        right_panel.place(relx=0.42, rely=0, relwidth=0.58, relheight=1)

        self._welcome_bg_source = None
        self._welcome_bg_tk = None

        if HAS_PIL:
            try:
                bg_path = _asset_path('welcome_bg.png')
                self._welcome_bg_source = Image.open(bg_path).convert('RGBA')
            except Exception:
                pass

        def _draw_welcome_bg(event=None):
            w = right_panel.winfo_width() or 800
            h = right_panel.winfo_height() or 1000
            if self._welcome_bg_source:
                # "Cover" crop — scale to fill panel, then center-crop excess
                src_w, src_h = self._welcome_bg_source.size
                scale = max(w / src_w, h / src_h)
                new_w = int(src_w * scale)
                new_h = int(src_h * scale)
                resized = self._welcome_bg_source.resize((new_w, new_h), Image.LANCZOS)
                # Crop from center to exact panel size
                left = (new_w - w) // 2
                top = (new_h - h) // 2
                cropped = resized.crop((left, top, left + w, top + h))
                self._welcome_bg_tk = ImageTk.PhotoImage(cropped)
                right_panel.delete("all")
                right_panel.create_image(0, 0, image=self._welcome_bg_tk, anchor="nw")
            else:
                # Fallback gradient if image not available
                right_panel.delete("all")
                r1, g1, b1 = 0x1E, 0x3A, 0x5F
                r2, g2, b2 = 0x5B, 0xA3, 0xD9
                steps = 60
                for i in range(steps):
                    t = i / steps
                    r = int(r1 + (r2 - r1) * t)
                    g = int(g1 + (g2 - g1) * t)
                    b = int(b1 + (b2 - b1) * t)
                    y0 = int(h * i / steps)
                    y1 = int(h * (i + 1) / steps) + 1
                    right_panel.create_rectangle(
                        0, y0, w, y1,
                        fill=f"#{r:02x}{g:02x}{b:02x}", outline="")

        right_panel.bind("<Configure>", _draw_welcome_bg)
        self._welcome_frame.after(100, _draw_welcome_bg)

        # ── Left panel: branding + CTA ──
        left_panel = tk.Frame(self._welcome_frame, bg=BG)
        left_panel.place(relx=0, rely=0, relwidth=0.42, relheight=1)

        # Center content vertically
        center = tk.Frame(left_panel, bg=BG)
        center.place(relx=0.5, rely=0.45, anchor="center")

        # App name
        tk.Label(center, text="AdviseMe", font=("Segoe UI", 32, "bold"),
                 fg=TEXT_PRIMARY, bg=BG).pack(pady=(0, 4))
        tk.Label(center, text="RBSD | Internal Tool", font=("Segoe UI", 11, "bold"),
                 fg=BLUE_DARK, bg=BG).pack(pady=(0, 24))

        # Subtitle
        tk.Label(center,
                 text="Course tracking and advising\nmade simple for faculty.",
                 font=("Segoe UI", 12), fg=TEXT_SECONDARY, bg=BG,
                 justify=tk.CENTER).pack(pady=(0, 36))

        # Get Started button
        if HAS_CTK:
            ctk.CTkButton(
                center, text="Let's Get Started  →",
                font=("Segoe UI", 14, "bold"), height=48,
                fg_color=BLUE_DARK, hover_color=BLUE,
                text_color=WHITE, corner_radius=8, width=240,
                command=self._launch_main_app
            ).pack()
        else:
            tk.Button(
                center, text="Let's Get Started  →",
                font=("Segoe UI", 14, "bold"),
                bg=BLUE_DARK, fg=WHITE, activebackground=BLUE,
                activeforeground=WHITE, relief=tk.FLAT,
                padx=32, pady=12, cursor="hand2",
                command=self._launch_main_app
            ).pack()

        # Version tag at bottom
        tk.Label(left_panel, text=f"v{__version__}", font=F_TINY,
                 fg=TEXT_MUTED, bg=BG).place(relx=0.5, rely=0.92, anchor="center")

    # ================================================================
    #  CONFIG  (persists Private View preference)
    # ================================================================

    @staticmethod
    def _config_path() -> str:
        """Return path to config.json — next to EXE when frozen, app root in dev."""
        if getattr(sys, 'frozen', False):
            return os.path.join(os.path.dirname(sys.executable), 'config.json')
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config.json')

    def _load_config(self) -> dict:
        try:
            import json
            with open(self._config_path(), 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_config(self):
        try:
            import json
            cfg = self._load_config()
            cfg['private_view'] = self._private_view
            with open(self._config_path(), 'w') as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass

    def _set_window_icon(self):
        """Set the window/taskbar icon from the bundled assets."""
        try:
            ico_path = _asset_path('AdviseMe.ico')
            if os.path.exists(ico_path):
                self.root.iconbitmap(ico_path)
                return
        except Exception:
            pass
        # Fallback: use PNG via iconphoto
        img = _load_tk_image('icon_48.png')
        if img:
            self._icon_img = img   # keep reference so GC doesn't delete it
            self.root.iconphoto(True, img)

    # ================================================================
    #  PRIVATE VIEW
    # ================================================================

    def _toggle_private_view(self):
        """Toggle Private View on/off, save preference, and update the UI."""
        self._private_view = not self._private_view
        self._save_config()
        self._apply_private_view(self._private_view)

    def _rebuild_sidebar_order(self):
        """Re-pack all sidebar sections in the correct order based on current state."""
        # Forget everything first
        for attr in ('_pv_identity_frame', '_pv_advisor_frame',
                     '_pv_semester_frame', '_generate_plan_frame',
                     '_human_mode_frame', '_manual_options_frame',
                     '_human_info_frame'):
            try:
                getattr(self, attr).pack_forget()
            except Exception:
                pass

        if not self._private_view:
            # Normal mode: show identity/advisor/semester sections
            self._pv_identity_frame.pack(fill=tk.X, in_=self._sb)
            self._pv_advisor_frame.pack(fill=tk.X, in_=self._sb)
            self._pv_semester_frame.pack(fill=tk.X, in_=self._sb)

        # Generate Plan button always visible
        self._generate_plan_frame.pack(fill=tk.X, in_=self._sb)

        # Human Mode section — always visible, toggle vs static label inside
        self._human_mode_frame.pack(fill=tk.X, in_=self._sb)
        if self._private_view:
            self.manual_toggle.pack_forget()
            self._pv_human_label.pack(fill=tk.X, pady=(0, 6),
                                      in_=self._human_mode_frame)
        else:
            self._pv_human_label.pack_forget()
            self.manual_toggle.pack(fill=tk.X, pady=(0, 6),
                                    in_=self._human_mode_frame)

        # Manual options + human info depend on Human Mode toggle state
        if self.manual_mode_var.get():
            self._manual_options_frame.pack(fill=tk.X, in_=self._sb)
            if not self._private_view:
                self._human_info_frame.pack(fill=tk.X, in_=self._sb)

    def _apply_private_view(self, on: bool):
        """Show or hide all student-identifying elements based on Private View state."""
        # Update header button appearance
        if hasattr(self, '_pv_btn'):
            if on:
                self._pv_btn.config(
                    bg=NAVY_LIGHT, fg=WHITE,
                    activebackground=NAVY, activeforeground=WHITE)
            else:
                self._pv_btn.config(
                    bg=HDR_BG_COLOR, fg="#718096",
                    activebackground="#F0F4F8", activeforeground=NAVY)

        # Force Human Mode ON when entering Private View
        if on and hasattr(self, 'manual_mode_var'):
            if not self.manual_mode_var.get():
                self.manual_mode_var.set(True)
                # Pack manual options directly (don't call _on_manual_mode_toggle
                # which would trigger _rebuild_sidebar_order before we're ready)
                self._manual_options_frame.pack(fill=tk.X, in_=self._sb)

        # Rebuild the sidebar in correct order
        if hasattr(self, '_pv_identity_frame'):
            self._rebuild_sidebar_order()

        # Wipe loaded student record immediately when turning on
        if on and self.record is not None:
            self.record = None
            self.plan = None
            self._last_advisor_picks = set()
            self.current_semester_idx = -1
            program_name = self.program_var.get()
            if program_name and hasattr(self, '_program_paths') \
                    and program_name in self._program_paths:
                try:
                    from core.grid_loader import load_program_grid
                    self.grid = load_program_grid(self._program_paths[program_name])
                except Exception:
                    pass
            if hasattr(self, 'eval_label'):
                self.eval_label.config(text="No file loaded", fg=TEXT_MUTED)
            if self.grid:
                self._display_grid()
            self._display_plan()

        # Refresh dashboard to reflect visibility changes
        if hasattr(self, 'stats_inner'):
            self._update_stats()

        msg = "Private View ON — Human Mode only, student identity hidden." if on \
              else "Private View OFF."
        if hasattr(self, 'status_var'):
            self.status_var.set(msg)

    def _get_export_label(self) -> tuple:
        """
        In Private View, show a small dialog asking for an optional label
        (e.g. 'Student A'). Returns (label, student_id_label).
        Returns ('', '') if the user cancels or leaves it blank.
        Never stores the value anywhere after the dialog closes.
        """
        if not self._private_view:
            return self._get_student_name(), self._get_student_id()

        if HAS_CTK:
            dlg = ctk.CTkToplevel(self.root)
        else:
            dlg = tk.Toplevel(self.root)
        dlg.title("Export Label")
        dlg.geometry("420x190")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.configure(bg=BG)

        tk.Frame(dlg, bg=NAVY_LIGHT, height=40).pack(fill=tk.X)
        tk.Label(dlg, text="  Export Label  (Private View)",
                 font=F_HEADING, fg=WHITE, bg=NAVY_LIGHT).place(x=0, y=8)

        tk.Label(dlg,
                 text="Enter an optional label for this export (e.g. 'Student A').\n"
                      "This label is used only in the PDF and is not saved anywhere.",
                 font=F_TINY, fg=TEXT_SECONDARY, bg=BG,
                 justify=tk.LEFT).pack(padx=20, pady=(14, 6), anchor=tk.W)

        lbl_var = tk.StringVar()
        if HAS_CTK:
            ctk.CTkEntry(dlg, textvariable=lbl_var, placeholder_text="e.g. Student A",
                         height=30, font=F_SMALL, fg_color=CARD_BG,
                         border_color=BORDER, corner_radius=4,
                         text_color=TEXT_PRIMARY,
                         width=360).pack(padx=20, pady=(0, 12))
        else:
            tk.Entry(dlg, textvariable=lbl_var, font=F_SMALL,
                     relief=tk.SOLID, bd=1, width=40).pack(padx=20, pady=(0, 12))

        result = ['', '']

        def _confirm():
            result[0] = lbl_var.get().strip()
            dlg.destroy()

        bf = tk.Frame(dlg, bg=BG)
        bf.pack(fill=tk.X, padx=20)
        if HAS_CTK:
            ctk.CTkButton(bf, text="Export", command=_confirm,
                          fg_color=NAVY, height=32, corner_radius=6,
                          width=100).pack(side=tk.RIGHT, padx=(6, 0))
            ctk.CTkButton(bf, text="Skip / No Label",
                          command=dlg.destroy,
                          fg_color=CARD_BG, text_color=TEXT_PRIMARY,
                          border_color=BORDER, border_width=1,
                          height=32, corner_radius=6,
                          width=130).pack(side=tk.RIGHT)
        else:
            tk.Button(bf, text="Export", command=_confirm,
                      bg=NAVY, fg=WHITE, padx=12).pack(side=tk.RIGHT, padx=(4, 0))
            tk.Button(bf, text="Skip / No Label", command=dlg.destroy,
                      padx=12).pack(side=tk.RIGHT)

        dlg.wait_window()
        return result[0], ""

    # ================================================================
    #  HEADER
    # ================================================================

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=HDR_BG_COLOR, height=60)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        # Drop shadow — two thin strips below the header for a layered effect
        tk.Frame(self.root, bg=HDR_SHADOW_1, height=2).pack(fill=tk.X)
        tk.Frame(self.root, bg=HDR_SHADOW_2, height=2).pack(fill=tk.X)

        # Left: logo + branding
        left = tk.Frame(hdr, bg=HDR_BG_COLOR)
        left.pack(side=tk.LEFT, padx=16, pady=8)

        logo_img = _load_tk_image('logo_transparent.png', size=(40, 40))
        if logo_img:
            self._header_logo = logo_img   # keep reference
            tk.Label(left, image=logo_img, bg=HDR_BG_COLOR).pack(side=tk.LEFT, padx=(0, 10))

        text_stack = tk.Frame(left, bg=HDR_BG_COLOR)
        text_stack.pack(side=tk.LEFT)
        tk.Label(text_stack, text="RBSD | Internal Tool", font=("Segoe UI", 9, "bold"),
                 fg=BLUE_DARK, bg=HDR_BG_COLOR).pack(anchor=tk.W)
        tk.Label(text_stack, text="AdviseMe", font=("Segoe UI", 15, "bold"),
                 fg=NAVY, bg=HDR_BG_COLOR).pack(anchor=tk.W)

        # Thin vertical divider between branding and right controls
        tk.Frame(hdr, bg=HDR_BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y,
                                                     padx=(12, 0), pady=10)

        # Center-right: Reset button
        reset_btn = tk.Button(
            hdr, text="⟳  RESET", font=("Segoe UI", 9, "bold"),
            bg="#C53030", fg=WHITE, activebackground="#9B2C2C",
            activeforeground=WHITE, relief=tk.FLAT, padx=14, pady=6,
            cursor="hand2", bd=0, command=self._confirm_reset)
        reset_btn.pack(side=tk.RIGHT, padx=(0, 16), pady=14)

        # Private View toggle button
        pv_on  = dict(bg=NAVY_LIGHT, fg=WHITE,
                      activebackground=NAVY, activeforeground=WHITE)
        pv_off = dict(bg=HDR_BG_COLOR, fg="#718096",
                      activebackground="#F0F4F8", activeforeground=NAVY)
        self._pv_btn = tk.Button(
            hdr, text="🔒  Private View",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT, padx=12, pady=6, cursor="hand2", bd=0,
            highlightbackground=HDR_BORDER, highlightthickness=1,
            command=self._toggle_private_view,
            **(pv_on if self._private_view else pv_off))
        self._pv_btn.pack(side=tk.RIGHT, padx=(0, 8), pady=14)

        # Right: program selector
        right = tk.Frame(hdr, bg=HDR_BG_COLOR)
        right.pack(side=tk.RIGHT, padx=(16, 0), pady=12)
        tk.Label(right, text="Program", font=F_SMALL, fg="#718096",
                 bg=HDR_BG_COLOR).pack(side=tk.LEFT, padx=(0, 8))

        self.program_var = tk.StringVar()
        if HAS_CTK:
            self.program_combo = _ctk_combo(
                right, variable=self.program_var, values=[], width=260,
                height=30, font=F_SMALL, dropdown_font=F_SMALL,
                fg_color=WHITE, border_color=HDR_BORDER,
                button_color=NAVY_LIGHT, button_hover_color=BLUE,
                entry_fg="#1A202C",
                command=lambda _: self._on_program_selected(None))
        else:
            from tkinter import ttk
            self.program_combo = ttk.Combobox(
                right, textvariable=self.program_var, state="readonly", width=35)
            self.program_combo.bind("<<ComboboxSelected>>", self._on_program_selected)
        self.program_combo.pack(side=tk.LEFT)

    # ================================================================
    #  BODY  (sidebar + content)
    # ================================================================

    def _build_body(self):
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill=tk.BOTH, expand=True)

        # ── Sidebar (scrollable) ──
        sidebar_outer = tk.Frame(body, bg=SIDEBAR_GRAD_TOP, width=340)
        sidebar_outer.pack(side=tk.LEFT, fill=tk.Y)
        sidebar_outer.pack_propagate(False)

        # Gradient background canvas — drawn behind all sidebar content
        _grad_canvas = tk.Canvas(sidebar_outer, highlightthickness=0, bd=0)
        _grad_canvas.place(x=0, y=0, relwidth=1, relheight=1)

        def _draw_sidebar_gradient(event=None):
            _grad_canvas.delete("all")
            w = sidebar_outer.winfo_width() or 340
            h = sidebar_outer.winfo_height() or 1000
            r1, g1, b1 = 0x0E, 0x17, 0x28   # top  #0E1728
            r2, g2, b2 = 0x09, 0x12, 0x20   # bottom #091220
            steps = 80
            for i in range(steps):
                t = i / steps
                r = int(r1 + (r2 - r1) * t)
                g = int(g1 + (g2 - g1) * t)
                b = int(b1 + (b2 - b1) * t)
                y0 = int(h * i / steps)
                y1 = int(h * (i + 1) / steps) + 1
                _grad_canvas.create_rectangle(
                    0, y0, w, y1,
                    fill=f"#{r:02x}{g:02x}{b:02x}", outline="")
            _grad_canvas.lower()   # keep gradient behind all packed widgets

        sidebar_outer.bind("<Configure>", lambda e: _draw_sidebar_gradient())
        sidebar_outer.after(150, _draw_sidebar_gradient)

        # ── Fixed Export footer (always visible at bottom) ──
        export_footer = tk.Frame(sidebar_outer, bg=SIDEBAR_GRAD_BOTTOM, padx=16, pady=10)
        export_footer.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Frame(export_footer, bg=BORDER, height=1).pack(fill=tk.X, pady=(0, 8))
        self._make_button(export_footer, "Export Grid PDF", NAVY, WHITE,
                          self._export_grid_pdf, h=34, pady=(0, 4))
        self._make_button(export_footer, "Export Plan PDF", CARD_BG, TEXT_PRIMARY,
                          self._export_plan_pdf, h=34, border=True, pady=(0, 0))

        sb_canvas = tk.Canvas(sidebar_outer, bg=SIDEBAR_BG, highlightthickness=0, width=324)
        sb_canvas.pack(fill=tk.BOTH, expand=True)

        self._sb = tk.Frame(sb_canvas, bg=SIDEBAR_BG, padx=16, pady=10)
        sb_canvas.create_window((0, 0), window=self._sb, anchor="nw")
        self._sb.bind("<Configure>",
                      lambda e: sb_canvas.configure(scrollregion=sb_canvas.bbox("all")))

        # Enable mousewheel scrolling on the sidebar
        def _on_sidebar_scroll(event):
            sb_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_mousewheel(widget):
            widget.bind("<MouseWheel>", _on_sidebar_scroll)
            for child in widget.winfo_children():
                _bind_mousewheel(child)

        sb_canvas.bind("<MouseWheel>", _on_sidebar_scroll)
        self._sb.bind("<MouseWheel>", _on_sidebar_scroll)
        # Re-bind after sidebar is built so all child widgets are covered
        self.root.after(200, lambda: _bind_mousewheel(self._sb))

        self._build_sidebar(self._sb)

        # Thin divider between sidebar and content
        tk.Frame(body, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

        # ── Content area ──
        content = tk.Frame(body, bg=BG)
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_content(content)

    # ================================================================
    #  SIDEBAR
    # ================================================================

    def _build_sidebar(self, sb):
        # ── Upload + Student Info (hidden in Private View) ──
        # Wrap in a single frame so both can be shown/hidden together
        self._pv_identity_frame = tk.Frame(sb, bg=SIDEBAR_BG)
        self._pv_identity_frame.pack(fill=tk.X)

        pvf = self._pv_identity_frame   # shorthand

        self._sidebar_label(pvf, "UPLOAD EVALUATION")
        self._make_button(pvf, "Upload PDF", NAVY_LIGHT, WHITE, self._upload_eval, h=36)

        self.eval_label = tk.Label(pvf, text="No file loaded", font=F_TINY,
                                   fg=TEXT_MUTED, bg=SIDEBAR_BG, anchor=tk.W)
        self.eval_label.pack(fill=tk.X, pady=(2, 0))

        self._sidebar_label(pvf, "STUDENT INFO")
        card = _card(pvf)
        card.pack(fill=tk.X, pady=(2, 6))
        self.info_text = tk.Text(card, height=5, width=28, state=tk.DISABLED,
                                 font=F_TINY, bg=CARD_BG, fg=TEXT_PRIMARY,
                                 relief=tk.FLAT, padx=10, pady=8, borderwidth=0)
        self.info_text.pack(fill=tk.X)

        # ── Faculty Advisor (hidden in Private View) ──
        self._pv_advisor_frame = tk.Frame(sb, bg=SIDEBAR_BG)
        self._pv_advisor_frame.pack(fill=tk.X)
        self._sidebar_label(self._pv_advisor_frame, "FACULTY ADVISOR")
        self.advisor_var = tk.StringVar(value="")
        if HAS_CTK:
            self.advisor_combo = _ctk_combo(
                self._pv_advisor_frame, variable=self.advisor_var,
                values=["Select advisor..."], width=250, height=28,
                font=F_TINY, dropdown_font=F_TINY,
                fg_color=CARD_BG, border_color=BORDER,
                button_color=NAVY_LIGHT, button_hover_color=BLUE)
        else:
            from tkinter import ttk
            self.advisor_combo = ttk.Combobox(
                self._pv_advisor_frame, textvariable=self.advisor_var,
                values=["Select advisor..."], width=28)
        self.advisor_combo.pack(fill=tk.X, pady=(2, 8))
        self._faculty_data = load_faculty()

        # ── Semester Plan + Strategy (hidden in Private View) ──
        self._pv_semester_frame = tk.Frame(sb, bg=SIDEBAR_BG)
        self._pv_semester_frame.pack(fill=tk.X)
        self._sidebar_label(self._pv_semester_frame, "SEMESTER PLAN")
        tk.Label(self._pv_semester_frame, text="Target Semester", font=F_TINY,
                 fg=TEXT_SECONDARY, bg=SIDEBAR_BG, anchor=tk.W).pack(fill=tk.X)

        self.semester_var = tk.StringVar()
        if HAS_CTK:
            self.semester_combo = _ctk_combo(
                self._pv_semester_frame, variable=self.semester_var,
                values=get_available_semesters(), width=250, height=28,
                font=F_TINY, dropdown_font=F_TINY,
                fg_color=CARD_BG, border_color=BORDER,
                button_color=NAVY_LIGHT, button_hover_color=BLUE)
        else:
            from tkinter import ttk
            self.semester_combo = ttk.Combobox(
                self._pv_semester_frame, textvariable=self.semester_var,
                values=get_available_semesters(), width=28)
        self.semester_combo.pack(fill=tk.X, pady=(2, 8))

        # Strategy is always Advisor Picks
        self.strategy_var = tk.StringVar(value=STRATEGY_ADVISOR_PICKS)

        # Generate Plan button — in its own frame so it stays visible in Private View
        self._generate_plan_frame = tk.Frame(sb, bg=SIDEBAR_BG)
        self._generate_plan_frame.pack(fill=tk.X)
        self._make_button(self._generate_plan_frame, "Generate Plan", BLUE_DARK, WHITE,
                          self._generate_plan, h=36, pady=(8, 4))

        # ── Human Mode ──
        # Wrap everything in a frame so _rebuild_sidebar_order can position it
        self._human_mode_frame = tk.Frame(sb, bg=SIDEBAR_BG)
        self._human_mode_frame.pack(fill=tk.X)

        self._sidebar_label(self._human_mode_frame, "HUMAN MODE")

        # Static label shown in Private View (toggle hidden)
        self._pv_human_label = tk.Label(
            self._human_mode_frame, text="Human Mode  ·  Always On",
            font=("Segoe UI", 10, "bold"), fg=GREEN,
            bg=SIDEBAR_BG, anchor=tk.W)
        # (packed/unpacked by _rebuild_sidebar_order)

        self.manual_mode_var = tk.BooleanVar(value=False)
        if HAS_CTK:
            self.manual_toggle = ctk.CTkSwitch(
                self._human_mode_frame, text="Enable Human Mode",
                variable=self.manual_mode_var,
                font=F_SMALL, fg_color=GRAY_LIGHT, progress_color=GREEN,
                button_color=WHITE, button_hover_color=BLUE,
                command=self._on_manual_mode_toggle)
        else:
            self.manual_toggle = tk.Checkbutton(
                self._human_mode_frame, text="Enable Human Mode",
                variable=self.manual_mode_var,
                font=F_SMALL, bg=SIDEBAR_BG, anchor=tk.W,
                command=self._on_manual_mode_toggle)
        self.manual_toggle.pack(fill=tk.X, pady=(0, 6))

        # ── Manual mode options (hidden until toggle is on) ──
        self._manual_options_frame = tk.Frame(sb, bg=SIDEBAR_BG)
        # (shown/hidden by toggle — NOT packed yet)

        tk.Label(self._manual_options_frame,
                 text="Click grid cells to set course status",
                 font=F_TINY, fg=TEXT_SECONDARY, bg=SIDEBAR_BG,
                 anchor=tk.W, wraplength=280).pack(fill=tk.X, pady=(0, 6))

        # Color picker
        self.manual_color_var = tk.StringVar(value="green")
        color_frame = tk.Frame(self._manual_options_frame, bg=SIDEBAR_BG)
        color_frame.pack(fill=tk.X, pady=(0, 4))
        for val, lbl, clr, dot_clr in [
            ("green",      "Completed",   GRID_GREEN,    GREEN),
            ("transfer",   "Transfer",    GRID_TRANSFER, PURPLE),
            ("orange",     "Next Sem.",   GRID_ORANGE,   ORANGE),
            ("light_red",  "Gap",         GRID_RED,      RED),
            ("none",       "Not Started", GRID_WHITE,    GRAY_LIGHT),
            ("in_progress","In Progress", GRID_BLUE,     BLUE_STATUS),
        ]:
            rf = tk.Frame(color_frame, bg=SIDEBAR_BG)
            rf.pack(fill=tk.X, pady=2)
            if HAS_CTK:
                ctk.CTkRadioButton(
                    rf, text=lbl, variable=self.manual_color_var, value=val,
                    font=F_TINY, fg_color=dot_clr, hover_color=dot_clr,
                    border_color=BORDER, radiobutton_width=16, radiobutton_height=16
                ).pack(side=tk.LEFT)
            else:
                tk.Radiobutton(rf, text=lbl, variable=self.manual_color_var,
                               value=val, font=F_TINY, bg=SIDEBAR_BG,
                               fg=TEXT_PRIMARY, anchor=tk.W,
                               activebackground=SIDEBAR_BG,
                               selectcolor=SIDEBAR_BG).pack(side=tk.LEFT)
            # Swatch shows the actual grid cell color
            tk.Frame(rf, bg=clr, width=28, height=14,
                     highlightbackground=BORDER,
                     highlightthickness=1).pack(side=tk.RIGHT, padx=4)

        # ── Human Mode: Student Info Input ──
        self._human_info_frame = tk.Frame(sb, bg=SIDEBAR_BG)
        # (shown/hidden by toggle)
        self._sidebar_label(self._human_info_frame, "STUDENT INFO (MANUAL)")
        for lbl_text, var in [
            ("Name", self._human_name_var),
            ("Student ID", self._human_id_var),
            ("GPA", self._human_gpa_var),
            ("Credits Earned", self._human_credits_var),
        ]:
            tk.Label(self._human_info_frame, text=lbl_text, font=F_TINY,
                     fg=TEXT_SECONDARY, bg=SIDEBAR_BG, anchor=tk.W).pack(fill=tk.X)
            if HAS_CTK:
                entry = ctk.CTkEntry(self._human_info_frame, textvariable=var,
                                     height=28, font=F_TINY, fg_color=CARD_BG,
                                     text_color=TEXT_PRIMARY,
                                     border_color=BORDER, corner_radius=4)
            else:
                entry = tk.Entry(self._human_info_frame, textvariable=var,
                                 font=F_TINY, bg=CARD_BG, fg=TEXT_PRIMARY,
                                 relief=tk.SOLID, bd=1,
                                 insertbackground=TEXT_PRIMARY)
            entry.pack(fill=tk.X, pady=(1, 6))


    # ================================================================
    #  CONTENT AREA (tabs)
    # ================================================================

    def _build_content(self, parent):
        # Tab bar
        tab_bar = tk.Frame(parent, bg=BG, height=44)
        tab_bar.pack(fill=tk.X, padx=20, pady=(14, 0))

        self.tab_buttons = {}
        self.tab_frames = {}
        self.current_tab = tk.StringVar(value="grid")

        for tid, label in [("grid", "4-Year Grid"), ("plan", "Semester Plan"),
                           ("stats", "Dashboard")]:
            btn = tk.Label(tab_bar, text=f"  {label}  ", font=F_LABEL,
                           padx=16, pady=7, cursor="hand2")
            btn.pack(side=tk.LEFT, padx=(0, 4))
            btn.bind("<Button-1>", lambda e, t=tid: self._switch_tab(t))
            self.tab_buttons[tid] = btn

        # Content container
        self.tab_container = tk.Frame(parent, bg=BG)
        self.tab_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(8, 14))

        # ── Grid tab ──
        grid_frame = tk.Frame(self.tab_container, bg=BG)
        self.tab_frames["grid"] = grid_frame

        grid_card = _card(grid_frame, bg=GRID_BG)
        grid_card.pack(fill=tk.BOTH, expand=True)

        self.grid_canvas = tk.Canvas(grid_card, bg=GRID_BG, highlightthickness=0)
        self.grid_canvas.pack(fill=tk.BOTH, expand=True)

        self.grid_inner_frame = tk.Frame(self.grid_canvas, bg=GRID_BG)
        self.grid_canvas.create_window((0, 0), window=self.grid_inner_frame, anchor="nw")
        self.grid_inner_frame.bind("<Configure>",
            lambda e: self.grid_canvas.configure(scrollregion=self.grid_canvas.bbox("all")))

        # Mousewheel scrolling for grid (vertical + shift-horizontal)
        def _on_grid_scroll(event):
            self.grid_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_grid_scroll_h(event):
            self.grid_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_grid_mousewheel(widget):
            widget.bind("<MouseWheel>", _on_grid_scroll)
            widget.bind("<Shift-MouseWheel>", _on_grid_scroll_h)
            for child in widget.winfo_children():
                _bind_grid_mousewheel(child)

        self.grid_canvas.bind("<MouseWheel>", _on_grid_scroll)
        self.grid_canvas.bind("<Shift-MouseWheel>", _on_grid_scroll_h)
        self._bind_grid_mw = _bind_grid_mousewheel  # store ref for re-bind after grid redraw

        # ── Plan tab ──
        plan_frame = tk.Frame(self.tab_container, bg=BG)
        self.tab_frames["plan"] = plan_frame

        # Toolbar row with copy button
        plan_toolbar = tk.Frame(plan_frame, bg=BG)
        plan_toolbar.pack(fill=tk.X, pady=(0, 6))
        if HAS_CTK:
            self._copy_plan_btn = ctk.CTkButton(
                plan_toolbar, text="Copy to Clipboard", font=F_SMALL,
                height=30, fg_color=NAVY, hover_color=BLUE_DARK,
                corner_radius=6, width=170,
                command=self._copy_plan_to_clipboard)
            self._copy_plan_btn.pack(side=tk.RIGHT)
        else:
            self._copy_plan_btn = tk.Button(
                plan_toolbar, text="Copy to Clipboard", font=F_SMALL,
                bg=NAVY, fg=WHITE, relief=tk.FLAT, padx=12, pady=2,
                command=self._copy_plan_to_clipboard)
            self._copy_plan_btn.pack(side=tk.RIGHT)

        plan_card = _card(plan_frame)
        plan_card.pack(fill=tk.BOTH, expand=True)
        self.plan_text = tk.Text(plan_card, wrap=tk.WORD, font=("Consolas", 10),
                                 bg=CARD_BG, fg=TEXT_PRIMARY, relief=tk.FLAT,
                                 padx=20, pady=16, borderwidth=0)
        self.plan_text.pack(fill=tk.BOTH, expand=True)

        # ── Stats / Dashboard tab ──
        stats_frame = tk.Frame(self.tab_container, bg=BG)
        self.tab_frames["stats"] = stats_frame

        # Refresh button row
        refresh_row = tk.Frame(stats_frame, bg=BG)
        refresh_row.pack(fill=tk.X, pady=(0, 6))
        if HAS_CTK:
            ctk.CTkButton(refresh_row, text="Refresh Dashboard", font=F_SMALL,
                          height=30, fg_color=NAVY, hover_color=BLUE_DARK,
                          corner_radius=6, width=160,
                          command=self._update_stats).pack(side=tk.RIGHT)
        else:
            tk.Button(refresh_row, text="Refresh Dashboard", font=F_SMALL,
                      bg=NAVY, fg=WHITE, relief=tk.FLAT, padx=12, pady=2,
                      command=self._update_stats).pack(side=tk.RIGHT)

        # Scrollable cards area (no visible scrollbar — mousewheel only)
        stats_scroll_canvas = tk.Canvas(stats_frame, bg=BG, highlightthickness=0)
        stats_scroll_canvas.pack(fill=tk.BOTH, expand=True)

        self.stats_inner = tk.Frame(stats_scroll_canvas, bg=BG)
        stats_scroll_canvas.create_window((0, 0), window=self.stats_inner, anchor="nw")
        self.stats_inner.bind("<Configure>",
            lambda e: stats_scroll_canvas.configure(
                scrollregion=stats_scroll_canvas.bbox("all")))

        # Mousewheel scrolling for stats
        def _on_stats_scroll(event):
            stats_scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_stats_mousewheel(widget):
            widget.bind("<MouseWheel>", _on_stats_scroll)
            for child in widget.winfo_children():
                _bind_stats_mousewheel(child)

        stats_scroll_canvas.bind("<MouseWheel>", _on_stats_scroll)
        self.stats_inner.bind("<MouseWheel>", _on_stats_scroll)
        self._bind_stats_mw = _bind_stats_mousewheel  # store ref for re-bind after stats rebuild
        self.root.after(300, lambda: _bind_stats_mousewheel(self.stats_inner))

        self._switch_tab("grid")

    # ================================================================
    #  HELPERS
    # ================================================================

    def _sidebar_label(self, parent, text):
        f = tk.Frame(parent, bg=parent.cget("bg"))
        f.pack(fill=tk.X, pady=(12, 3))
        tk.Label(f, text=text, font=("Segoe UI", 10, "bold"), fg=TEXT_MUTED,
                 bg=parent.cget("bg"), anchor=tk.W).pack(fill=tk.X)
        tk.Frame(f, bg=BORDER, height=1).pack(fill=tk.X, pady=(2, 0))

    def _make_button(self, parent, text, bg_color, fg_color, cmd, h=34,
                     border=False, pady=(4, 2)):
        if HAS_CTK:
            btn = ctk.CTkButton(parent, text=text, font=F_SMALL, height=h,
                                fg_color=bg_color, hover_color=BLUE,
                                text_color=fg_color, corner_radius=6,
                                border_width=1 if border else 0,
                                border_color=BORDER, command=cmd)
        else:
            btn = tk.Button(parent, text=text, font=F_SMALL, bg=bg_color,
                            fg=fg_color, relief=tk.GROOVE if border else tk.FLAT,
                            padx=12, pady=4, command=cmd)
        btn.pack(fill=tk.X, pady=pady)
        return btn

    def _switch_tab(self, tab_id):
        self.current_tab.set(tab_id)
        for frame in self.tab_frames.values():
            frame.pack_forget()
        self.tab_frames[tab_id].pack(fill=tk.BOTH, expand=True)
        for tid, btn in self.tab_buttons.items():
            if tid == tab_id:
                btn.configure(bg=BLUE_DARK, fg=WHITE, font=("Segoe UI", 10, "bold"))
            else:
                btn.configure(bg=CARD_BG, fg=TEXT_SECONDARY, font=F_LABEL)

    def _build_status_bar(self):
        self.status_var = tk.StringVar(
            value="Ready — Select a program and upload an evaluation to begin.")
        tk.Label(self.root, textvariable=self.status_var, font=F_TINY,
                 fg=TEXT_MUTED, bg=CARD_BG, anchor=tk.W,
                 padx=24, pady=5).pack(side=tk.BOTTOM, fill=tk.X)

    # ================================================================
    #  ACTIONS
    # ================================================================

    def _confirm_reset(self):
        """Prompt the user to confirm a full reset of the current session."""
        confirmed = messagebox.askyesno(
            title="Reset Session",
            message=(
                "Are you sure you want to reset?\n\n"
                "This will clear the loaded student evaluation, all grid\n"
                "highlights, the semester plan, and any manual edits.\n\n"
                "This action cannot be undone."
            ),
            icon="warning",
        )
        if confirmed:
            self._reset_app()

    def _reset_app(self):
        """Clear all session data and return the app to its initial state."""
        # Clear data models
        self.record = None
        self.plan = None
        self._last_advisor_picks = set()
        self.current_semester_idx = -1

        # Reload a fresh copy of the grid (clears all highlights)
        program_name = self.program_var.get()
        if program_name and program_name in self._program_paths:
            try:
                self.grid = load_program_grid(self._program_paths[program_name])
            except Exception:
                self.grid = None
        else:
            self.grid = None

        # Reset UI labels and inputs
        self.eval_label.config(text="No file loaded", fg=TEXT_MUTED)
        self.advisor_var.set("")

        # Reset manual mode toggle and hide options (keep ON in Private View)
        if not self._private_view:
            self.manual_mode_var.set(False)
            if hasattr(self, '_manual_options_frame'):
                self._manual_options_frame.pack_forget()
            if hasattr(self, '_human_info_frame'):
                self._human_info_frame.pack_forget()

        # Reset strategy to default (Advisor Picks)
        self.strategy_var.set(STRATEGY_ADVISOR_PICKS)

        # Clear Human Mode inputs
        for attr in ('_human_name_var', '_human_id_var',
                     '_human_gpa_var', '_human_credits_var'):
            if hasattr(self, attr):
                getattr(self, attr).set("")

        # Clear semester selection
        self.semester_var.set("")

        # Refresh all tabs — including student info panel
        if self.grid:
            self._display_grid()
        self._display_plan()
        self._update_student_info()
        self._update_stats()
        self.status_var.set("Session reset.")

    def _refresh_programs(self):
        programs = list_available_programs(self.programs_dir)
        self._program_paths = {name: path for path, name in programs}
        names = [name for _, name in programs]
        if HAS_CTK:
            self.program_combo.configure(values=names)
            if names:
                self.program_combo.set(names[0])
                self._on_program_selected(None)
        else:
            self.program_combo['values'] = names
            if names:
                self.program_combo.current(0)
                self._on_program_selected(None)

    def _on_program_selected(self, event):
        name = self.program_var.get()
        if name and name in self._program_paths:
            try:
                self.grid = load_program_grid(self._program_paths[name])
                self.status_var.set(f"Loaded program: {name}")
                self._display_grid()
                self._update_advisor_dropdown()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load program: {e}")

    def _update_advisor_dropdown(self):
        """Update the advisor dropdown based on the current program's department."""
        if not self.grid or not self.grid.department:
            advisors = ["No advisors available"]
        else:
            advisors = self._faculty_data.get(self.grid.department, [])
            if not advisors:
                advisors = ["No advisors available"]
        if HAS_CTK:
            self.advisor_combo.configure(values=advisors)
        else:
            self.advisor_combo['values'] = advisors
        self.advisor_var.set(advisors[0])

    def _upload_eval(self):
        filepath = filedialog.askopenfilename(
            title="Select Program Evaluation PDF",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")])
        if not filepath:
            return
        try:
            self.status_var.set("Parsing evaluation PDF...")
            self.root.update()
            self.record = parse_evaluation_pdf(filepath)
            filename = os.path.basename(filepath)
            self.eval_label.config(text=f"  {filename}", fg=GREEN)
            self._update_student_info()

            if self.grid:
                self.grid = load_program_grid(
                    self._program_paths[self.program_var.get()])
                self.grid = match_courses(self.record, self.grid)
                self.current_semester_idx = auto_detect_semester_index(
                    self.grid, self.record.total_credits_earned)
                self.semester_var.set(
                    auto_detect_semester_label(self.record.total_credits_earned))
                self._display_grid()
                self._update_stats()

            self.status_var.set(
                f"Loaded evaluation for {self.record.student_name} — "
                f"{len(self.record.eval_courses)} courses parsed")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to parse evaluation:\n{e}")
            self.status_var.set("Error parsing evaluation")
            import traceback; traceback.print_exc()

    def _update_student_info(self):
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete("1.0", tk.END)
        if self.record:
            transfers = get_transfer_courses(self.record)
            # Use grid course credits (from program JSON) when available — more
            # accurate than EvalCourse.credits which always defaults to 3.
            if self.grid:
                te_credits = sum(
                    gc.credits
                    for sem in self.grid.semesters
                    for gc in sem.courses
                    if gc.status == GridHighlight.TRANSFER
                )
            else:
                te_credits = sum(ec.credits for ec in transfers)
            lines = [
                f"Name:      {self.record.student_name}",
                f"ID:        {self.record.student_id}",
                f"GPA:       {self.record.gpa:.3f}",
                f"Credits:   {self.record.total_credits_earned} / {self.record.total_credits_required}",
                f"Program:   {self.record.program_name}",
                f"Courses:   {len(self.record.eval_courses)} parsed",
            ]
            if transfers:
                lines.append(f"Transfer:  {len(transfers)} courses ({te_credits} cr)")
            self.info_text.insert(tk.END, "\n".join(lines))
        self.info_text.config(state=tk.DISABLED)

    def _get_student_name(self):
        """Get student name from record or human mode inputs."""
        if self.record:
            return self.record.student_name
        return self._human_name_var.get() or ""

    def _get_student_id(self):
        if self.record:
            return self.record.student_id
        return self._human_id_var.get() or ""

    # ================================================================
    #  HUMAN MODE
    # ================================================================

    def _on_manual_mode_toggle(self):
        # Prevent turning off Human Mode while in Private View
        if not self.manual_mode_var.get() and self._private_view:
            self.manual_mode_var.set(True)
            self.status_var.set(
                "Human Mode cannot be disabled while Private View is active.")
            return

        if self.manual_mode_var.get():
            self.status_var.set(
                "Human Mode ON — Click any course cell to set its status.")
        else:
            self.status_var.set("Human Mode OFF.")

        # Rebuild sidebar in correct order
        self._rebuild_sidebar_order()

        if self.grid:
            self._display_grid()

    def _on_grid_cell_click(self, course):
        if not self.manual_mode_var.get():
            return
        if not self.grid:
            return

        color_choice = self.manual_color_var.get()
        mapping = {
            "green":       (GridHighlight.GREEN, CourseStatus.COMPLETED),
            "transfer":    (GridHighlight.TRANSFER, CourseStatus.TRANSFER),
            "orange":      (GridHighlight.ORANGE, None),
            "light_red":   (GridHighlight.LIGHT_RED, None),
            "none":        (GridHighlight.NONE, CourseStatus.NOT_STARTED),
            "in_progress": (GridHighlight.NONE, CourseStatus.IN_PROGRESS),
        }
        highlight, eval_stat = mapping.get(color_choice,
                                           (GridHighlight.NONE, None))
        course.status = highlight
        course.eval_status = eval_stat

        # Update card colors in place (no full rebuild)
        key = id(course)
        if key in self._grid_card_widgets:
            card_outer, card_inner = self._grid_card_widgets[key]
            new_bg = self._cell_color(course)
            new_accent = self._cell_accent(course)
            card_outer.config(bg=new_accent)
            card_inner.config(bg=new_bg)
            for child in card_inner.winfo_children():
                try:
                    child.config(bg=new_bg)
                except Exception:
                    pass
        else:
            # Fallback: full rebuild if widget ref is missing
            self._display_grid()

        self._update_stats()
        self.status_var.set(
            f"Set {course.code or course.name} → "
            f"{color_choice.replace('_', ' ').title()}")

    # ================================================================
    #  GRID DISPLAY
    # ================================================================

    def _display_grid(self):
        for w in self.grid_inner_frame.winfo_children():
            w.destroy()
        self._grid_card_widgets = {}   # id(course) → (card_outer, card_inner)
        if not self.grid:
            return

        # ── Legend bar (top) ──
        legend_row = tk.Frame(self.grid_inner_frame, bg=GRID_BG)
        legend_row.pack(fill=tk.X, padx=12, pady=(10, 6))
        for txt, clr, accent in [
            ("Completed", GRID_GREEN, GREEN),
            ("Transfer", GRID_TRANSFER, PURPLE),
            ("Next Sem.", GRID_ORANGE, ORANGE),
            ("Gap", GRID_RED, RED),
            ("In Progress", GRID_BLUE, BLUE_STATUS),
            ("Not Started", GRID_WHITE, GRAY_LIGHT),
        ]:
            pill = tk.Frame(legend_row, bg=GRID_BG)
            pill.pack(side=tk.LEFT, padx=(0, 16))
            tk.Frame(pill, bg=accent, width=10, height=10).pack(side=tk.LEFT, padx=(0, 5))
            tk.Label(pill, text=txt, font=("Segoe UI", 8), fg="#4A5568",
                     bg=GRID_BG).pack(side=tk.LEFT)

        # Thin separator
        tk.Frame(self.grid_inner_frame, bg="#CBD5E0", height=1).pack(
            fill=tk.X, padx=12, pady=(0, 8))

        # ── Semester sections ──
        YEAR_ACCENTS = {1: NAVY_LIGHT, 2: BLUE_DARK, 3: NAVY_LIGHT, 4: BLUE_DARK}
        cur_year = None

        for sem in self.grid.semesters:
            year_accent = YEAR_ACCENTS.get(sem.year, NAVY_LIGHT)
            is_new_year = sem.year != cur_year

            # Year divider
            if is_new_year and cur_year is not None:
                tk.Frame(self.grid_inner_frame, bg="#CBD5E0", height=1).pack(
                    fill=tk.X, padx=12, pady=(12, 0))
            cur_year = sem.year

            # ── Semester header band ──
            sem_cr = sum(c.credits for c in sem.courses)
            hdr = tk.Frame(self.grid_inner_frame, bg=year_accent, height=30)
            hdr.pack(fill=tk.X, padx=12, pady=(10 if is_new_year else 6, 0))
            hdr.pack_propagate(False)

            tk.Label(hdr, text=f"Year {sem.year}", font=("Segoe UI", 9, "bold"),
                     fg=WHITE, bg=year_accent).pack(side=tk.LEFT, padx=(12, 0))
            tk.Label(hdr, text="·", font=("Segoe UI", 9),
                     fg=BLUE, bg=year_accent).pack(side=tk.LEFT, padx=6)
            tk.Label(hdr, text=sem.term, font=("Segoe UI", 9, "bold"),
                     fg=WHITE, bg=year_accent).pack(side=tk.LEFT)
            tk.Label(hdr, text=f"{sem_cr} credits", font=("Segoe UI", 8),
                     fg=BLUE, bg=year_accent).pack(side=tk.RIGHT, padx=(0, 12))

            # ── Course cards row ──
            cards_row = tk.Frame(self.grid_inner_frame, bg=GRID_BG)
            cards_row.pack(fill=tk.X, padx=12, pady=(4, 0))

            for i, course in enumerate(sem.courses):
                accent_clr = self._cell_accent(course)
                cell_bg = self._cell_color(course)
                cursor = "hand2" if self.manual_mode_var.get() else ""

                # Card outer: provides the accent bar
                card_outer = tk.Frame(cards_row, bg=accent_clr, cursor=cursor)
                card_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                                padx=(0 if i == 0 else 3, 0), pady=3)

                # Card inner: white/colored content area with left accent
                card = tk.Frame(card_outer, bg=cell_bg, padx=10, pady=8, cursor=cursor)
                card.pack(fill=tk.BOTH, expand=True, padx=(3, 0))  # 3px accent bar

                # Store refs for in-place color updates
                self._grid_card_widgets[id(course)] = (card_outer, card)

                # Course code (bold)
                if not course.is_elective_slot and not course.is_ge_category:
                    tk.Label(card, text=course.code, font=("Segoe UI", 9, "bold"),
                             fg="#1A202C", bg=cell_bg, anchor=tk.W,
                             cursor=cursor).pack(fill=tk.X)

                # Course name
                tk.Label(card, text=course.name, font=("Segoe UI", 8),
                         fg="#4A5568", bg=cell_bg, anchor=tk.W, wraplength=120,
                         justify=tk.LEFT, cursor=cursor).pack(fill=tk.X)

                # Credits + grade row
                meta = f"{course.credits} cr"
                if course.matched_eval_course and course.matched_eval_course.grade:
                    meta += f"  ·  {course.matched_eval_course.grade}"
                tk.Label(card, text=meta, font=("Segoe UI", 7),
                         fg="#718096", bg=cell_bg, anchor=tk.W,
                         cursor=cursor).pack(fill=tk.X, pady=(3, 0))

                # Bind clicks to all parts of the card
                for w in (card_outer, card) + tuple(card.winfo_children()):
                    w.bind("<Button-1>",
                           lambda e, c=course: self._on_grid_cell_click(c))

        # Bottom padding
        tk.Frame(self.grid_inner_frame, bg=GRID_BG, height=12).pack(fill=tk.X)

        # Re-bind mousewheel to new grid children
        if hasattr(self, '_bind_grid_mw'):
            self.root.after(50, lambda: self._bind_grid_mw(self.grid_inner_frame))

    def _cell_color(self, course):
        if course.eval_status == CourseStatus.IN_PROGRESS:
            return GRID_BLUE
        return {
            GridHighlight.GREEN: GRID_GREEN,
            GridHighlight.TRANSFER: GRID_TRANSFER,
            GridHighlight.ORANGE: GRID_ORANGE,
            GridHighlight.LIGHT_RED: GRID_RED,
            GridHighlight.NONE: GRID_WHITE,
        }.get(course.status, GRID_WHITE)

    def _cell_accent(self, course):
        """Return a bold accent color for the card's left bar."""
        if course.eval_status == CourseStatus.IN_PROGRESS:
            return BLUE_STATUS
        return {
            GridHighlight.GREEN: GREEN,
            GridHighlight.TRANSFER: PURPLE,
            GridHighlight.ORANGE: ORANGE,
            GridHighlight.LIGHT_RED: RED,
            GridHighlight.NONE: GRAY_LIGHT,
        }.get(course.status, GRAY_LIGHT)

    # ================================================================
    #  PLAN GENERATION
    # ================================================================

    def _clear_plan_highlights(self):
        """
        Reset all plan-generated highlights (orange, gap red) back to NONE
        before regenerating a plan. Permanent statuses (green, transfer,
        in-progress) are left untouched.
        """
        if not self.grid:
            return
        _PERMANENT = {GridHighlight.GREEN, GridHighlight.TRANSFER}
        _PLAN_SET   = {GridHighlight.ORANGE, GridHighlight.LIGHT_RED}
        for sem in self.grid.semesters:
            for course in sem.courses:
                if (course.status in _PLAN_SET
                        and course.status not in _PERMANENT
                        and course.eval_status != CourseStatus.IN_PROGRESS):
                    course.status = GridHighlight.NONE

    def _generate_plan(self):
        if not self.grid:
            messagebox.showwarning("Warning", "Please select a program first.")
            return
        try:
            semester_label = self.semester_var.get()
            if not semester_label:
                credits = (self.record.total_credits_earned if self.record
                           else int(self._human_credits_var.get() or 0))
                semester_label = auto_detect_semester_label(credits)

            if self.current_semester_idx >= 0:
                semester_idx = self.current_semester_idx
            else:
                credits = (self.record.total_credits_earned if self.record
                           else int(self._human_credits_var.get() or 0))
                semester_idx = detect_current_semester(self.grid, credits)

            # Snapshot all orange/red picks BEFORE clearing highlights
            # (covers both human mode clicks and prior plan highlights)
            human_picks = set()
            for sem in self.grid.semesters:
                for c in sem.courses:
                    if c.status in (GridHighlight.ORANGE, GridHighlight.LIGHT_RED):
                        human_picks.add(c.code)

            self._clear_plan_highlights()
            self._show_advisor_pick_dialog(semester_idx, semester_label,
                                           human_picks)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate plan:\n{e}")
            import traceback; traceback.print_exc()

    def _show_advisor_pick_dialog(self, semester_idx, semester_label,
                                     human_picks=None):
        if HAS_CTK:
            dialog = ctk.CTkToplevel(self.root)
        else:
            dialog = tk.Toplevel(self.root)
        dialog.title("Select Courses — Advisor Selection")

        # Larger dialog, centered on screen
        dlg_w, dlg_h = 880, 740
        screen_w = dialog.winfo_screenwidth()
        screen_h = dialog.winfo_screenheight()
        x = (screen_w - dlg_w) // 2
        y = (screen_h - dlg_h) // 2
        dialog.geometry(f"{dlg_w}x{dlg_h}+{x}+{y}")

        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=BG)

        # Header
        hdr = tk.Frame(dialog, bg=NAVY, height=44)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text=f"  Select courses for {semester_label}",
                 font=F_HEADING, fg=WHITE, bg=NAVY).pack(
                     side=tk.LEFT, padx=16, pady=8)

        # Credit counter
        credit_var = tk.StringVar(value="Selected: 0 credits")
        counter_lbl = tk.Label(dialog, textvariable=credit_var,
                               font=("Segoe UI", 11, "bold"), fg=GREEN,
                               bg=BG)
        counter_lbl.pack(padx=20, pady=(10, 4), anchor=tk.W)

        # Scrollable list (no visible scrollbar — mousewheel only)
        canvas = tk.Canvas(dialog, bg=BG, highlightthickness=0)
        inner = tk.Frame(canvas, bg=BG)
        canvas.pack(fill=tk.BOTH, expand=True, padx=20)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # Mousewheel scrolling for this dialog
        def _on_dialog_scroll(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_dialog_mousewheel(widget):
            widget.bind("<MouseWheel>", _on_dialog_scroll)
            for child in widget.winfo_children():
                _bind_dialog_mousewheel(child)

        canvas.bind("<MouseWheel>", _on_dialog_scroll)
        inner.bind("<MouseWheel>", _on_dialog_scroll)
        dialog.after(200, lambda: _bind_dialog_mousewheel(inner))

        check_vars = {}
        key_map = {}

        # Pre-check from: human mode cell clicks (passed in before clear)
        # + previous advisor pick dialog selections
        human_orange = human_picks or set()
        pre_checked = human_orange | self._last_advisor_picks

        def update_count(*_):
            total = sum(cr for k, (v, cr) in check_vars.items() if v.get())
            color = GREEN if total <= 18 else RED
            credit_var.set(f"Selected: {total} credits" +
                           (" ⚠ Over 18 credits!" if total > 18 else ""))
            counter_lbl.configure(fg=color)

        def add_cb(parent, text, key, code, credits, checked, accent):
            # Pre-check from: scheduled default, human mode clicks, or prior picks
            is_checked = checked or (code in pre_checked)
            var = tk.BooleanVar(value=is_checked)
            var.trace_add("write", update_count)
            check_vars[key] = (var, credits)
            key_map[key] = code
            if HAS_CTK:
                ctk.CTkCheckBox(parent, text=text, variable=var, font=F_SMALL,
                                fg_color=accent,
                                hover_color=BLUE).pack(anchor=tk.W, padx=12, pady=1)
            else:
                tk.Checkbutton(parent, text=text, variable=var, font=F_SMALL,
                               bg=BG, anchor=tk.W).pack(anchor=tk.W, padx=12, pady=1)

        # Section 1: Scheduled
        scheduled = get_next_semester_courses(self.grid, semester_idx)
        if scheduled:
            tk.Label(inner, text="Scheduled Courses (This Semester)",
                     font=("Segoe UI", 10, "bold"), fg=TEXT_PRIMARY,
                     bg=BG).pack(anchor=tk.W, pady=(8, 4))
            for c in scheduled:
                add_cb(inner, f"{c.code} — {c.name} ({c.credits} cr)",
                       f"s_{c.code}", c.code, c.credits, True, NAVY)

        # Section 2: Gaps
        gaps = find_gap_courses(self.grid, semester_idx)
        if gaps:
            tk.Label(inner, text="Makeup Courses (Out of Sequence)",
                     font=("Segoe UI", 10, "bold"), fg=RED,
                     bg=BG).pack(anchor=tk.W, pady=(12, 4))
            for sl, c in gaps:
                add_cb(inner, f"{c.code} — {c.name} ({c.credits} cr) [{sl}]",
                       f"g_{c.code}_{sl}", c.code, c.credits, True, RED)

        # Section 3: All other remaining
        shown = {c.code for c in scheduled} | {c.code for _, c in gaps}
        other = [(sl, c) for sl, c in get_all_remaining_grid_courses(self.grid)
                 if c.code not in shown]

        # Show pre-checked courses (human clicks + prior picks) at top of "other"
        human_only = [(sl, c) for sl, c in other if c.code in pre_checked]
        non_human  = [(sl, c) for sl, c in other if c.code not in pre_checked]

        if human_only:
            tk.Label(inner, text="Your Selections",
                     font=("Segoe UI", 10, "bold"), fg=ORANGE,
                     bg=BG).pack(anchor=tk.W, pady=(12, 4))
            for sl, c in human_only:
                add_cb(inner,
                       f"{c.code} — {c.name} ({c.credits} cr) [{sl}]",
                       f"h_{c.code}_{sl}", c.code, c.credits, True, ORANGE)

        if non_human:
            tk.Label(inner, text="All Other Remaining Courses",
                     font=("Segoe UI", 10, "bold"), fg=TEXT_MUTED,
                     bg=BG).pack(anchor=tk.W, pady=(12, 2))
            tk.Label(inner, text="Select any for special scheduling needs",
                     font=F_TINY, fg=TEXT_MUTED, bg=BG).pack(
                         anchor=tk.W, padx=12, pady=(0, 4))
            for sl, c in non_human:
                add_cb(inner,
                       f"{c.code} — {c.name} ({c.credits} cr) [{sl}]",
                       f"o_{c.code}_{sl}", c.code, c.credits, False, GRAY)

        update_count()

        def confirm():
            sel_codes = set(key_map[k] for k, (v, _) in check_vars.items() if v.get())

            # Remember picks so they persist into the next dialog open
            self._last_advisor_picks = set(sel_codes)

            # Destroy dialog first so the main window can repaint freely
            dialog.destroy()

            # Clear old plan highlights before applying new ones
            self._clear_plan_highlights()

            # Build the plan directly from the full grid so courses from
            # ANY section (scheduled, gaps, or "other") are included.
            # This avoids the bug where _plan_advisor_picks only searched
            # scheduled/gap lists and silently dropped "other" selections.
            from core.models import SemesterPlan
            new_plan = SemesterPlan(semester_label=semester_label)
            for sem in self.grid.semesters:
                for course in sem.courses:
                    if course.code in sel_codes:
                        from core.models import GridHighlight, CourseStatus
                        if course.eval_status != CourseStatus.IN_PROGRESS:
                            course.status = GridHighlight.ORANGE
                        new_plan.courses.append(course)

            # Warn if over 18 credits
            total = sum(c.credits for c in new_plan.courses)
            if total > 18:
                new_plan.notes.append(
                    f"⚠ Total selected credits ({total}) exceeds 18. "
                    "Consider reducing the course load.")

            new_plan.compute_total()
            self.plan = new_plan

            self._display_grid()
            self._update_stats()
            self._display_plan()
            self._switch_tab("plan")
            self.status_var.set(f"Plan generated: {self.plan.total_credits} credits")

        bf = tk.Frame(dialog, bg=BG)
        bf.pack(fill=tk.X, padx=20, pady=12)
        if HAS_CTK:
            ctk.CTkButton(bf, text="Confirm Selection", command=confirm,
                          fg_color=NAVY, height=36,
                          corner_radius=6).pack(side=tk.RIGHT, padx=4)
            ctk.CTkButton(bf, text="Cancel", command=dialog.destroy,
                          fg_color=CARD_BG, text_color=TEXT_PRIMARY,
                          border_color=BORDER, border_width=1, height=36,
                          corner_radius=6).pack(side=tk.RIGHT, padx=4)
        else:
            tk.Button(bf, text="Confirm Selection", command=confirm,
                      bg=NAVY, fg=WHITE, padx=16, pady=4).pack(
                          side=tk.RIGHT, padx=4)
            tk.Button(bf, text="Cancel", command=dialog.destroy,
                      padx=16, pady=4).pack(side=tk.RIGHT, padx=4)

    def _build_plan_text(self) -> str:
        """Build a clean, email-friendly plain-text version of the plan."""
        if not self.plan:
            return ""

        lines = []

        # Header
        if not self._private_view:
            name = self._get_student_name()
            sid = self._get_student_id()
            if name and name != "—":
                lines.append(f"Student: {name}")
                if sid and sid != "—":
                    lines.append(f"ID: {sid}")
                lines.append("")

        lines.append(f"Advising Plan — {self.plan.semester_label}")
        lines.append("─" * 48)
        lines.append("")

        # Scheduled courses
        if self.plan.courses:
            lines.append("Scheduled Courses:")
            for c in self.plan.courses:
                lines.append(f"  • {c.code} — {c.name} ({c.credits} cr)")
            sub = sum(c.credits for c in self.plan.courses)
            lines.append(f"  Subtotal: {sub} credits")
            lines.append("")

        # Makeup courses
        if self.plan.makeup_courses:
            lines.append("Makeup Courses (Out of Sequence):")
            for c in self.plan.makeup_courses:
                lines.append(f"  • {c.code} — {c.name} ({c.credits} cr)")
            sub = sum(c.credits for c in self.plan.makeup_courses)
            lines.append(f"  Subtotal: {sub} credits")
            lines.append("")

        # Total
        self.plan.compute_total()
        lines.append("─" * 48)
        lines.append(f"Total Credits: {self.plan.total_credits}")
        lines.append("─" * 48)

        # Notes
        if self.plan.notes:
            lines.append("")
            lines.append("Notes:")
            for n in self.plan.notes:
                lines.append(f"  - {n}")

        return "\n".join(lines)

    def _display_plan(self):
        self.plan_text.delete("1.0", tk.END)
        if not self.plan:
            self.plan_text.insert(tk.END,
                "No plan generated yet.\n\n"
                "Upload an evaluation and click 'Generate Plan'.")
            return
        self.plan_text.insert(tk.END, self._build_plan_text())

    def _copy_plan_to_clipboard(self):
        text = self._build_plan_text()
        if not text:
            self.status_var.set("No plan to copy.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set("Plan copied to clipboard!")
        # Flash the button text briefly
        if HAS_CTK:
            self._copy_plan_btn.configure(text="Copied!")
            self.root.after(1500,
                lambda: self._copy_plan_btn.configure(text="Copy to Clipboard"))
        else:
            self._copy_plan_btn.config(text="Copied!")
            self.root.after(1500,
                lambda: self._copy_plan_btn.config(text="Copy to Clipboard"))

    # ================================================================
    #  DASHBOARD / STATS   (visual card-based layout)
    # ================================================================

    def _update_stats(self):
        for w in self.stats_inner.winfo_children():
            w.destroy()

        if not self.grid:
            return

        stats = get_completion_stats(self.grid)
        name = self._get_student_name() or "—"
        gpa_str = ""
        credits_str = ""
        if self.record:
            gpa_str = f"{self.record.gpa:.3f}"
            credits_str = (f"{self.record.total_credits_earned} / "
                           f"{self.record.total_credits_required}")
        elif self._human_gpa_var.get():
            gpa_str = self._human_gpa_var.get()
            credits_str = self._human_credits_var.get()

        # ── Row 1: Metric cards ──
        row1 = tk.Frame(self.stats_inner, bg=BG)
        row1.pack(fill=tk.X, pady=(0, 10))

        metrics = [
            (str(stats['completed']), "Completed", GREEN, GREEN_BG),
            (str(stats['transfer']), "Transfer", PURPLE, PURPLE_BG),
            (str(stats['in_progress']), "In Progress", BLUE_STATUS, BLUE_BG),
            (str(stats['gaps']), "Gaps", RED, RED_BG),
            (str(stats['remaining']), "Remaining", ORANGE, ORANGE_BG),
        ]
        for val, label, accent, bg_c in metrics:
            c = _card(row1)
            c.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
            inner = tk.Frame(c, bg=CARD_BG, padx=16, pady=12)
            inner.pack(fill=tk.BOTH, expand=True)

            # Accent bar at top
            tk.Frame(inner, bg=accent, height=3).pack(fill=tk.X, pady=(0, 8))
            tk.Label(inner, text=val, font=F_METRIC, fg=accent,
                     bg=CARD_BG).pack(anchor=tk.W)
            tk.Label(inner, text=label, font=F_METRIC_LABEL, fg=TEXT_SECONDARY,
                     bg=CARD_BG).pack(anchor=tk.W)

        # ── Row 2: Progress ring + Student card + Grid summary ──
        row2 = tk.Frame(self.stats_inner, bg=BG)
        row2.pack(fill=tk.X, pady=(0, 10))

        # Progress ring card
        ring_card = _card(row2)
        ring_card.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 8))
        ring_inner = tk.Frame(ring_card, bg=CARD_BG, padx=20, pady=16)
        ring_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(ring_inner, text="Completion", font=F_HEADING,
                 fg=TEXT_PRIMARY, bg=CARD_BG).pack(anchor=tk.W, pady=(0, 8))

        ring_size = 150
        ring_canvas = tk.Canvas(ring_inner, width=ring_size, height=ring_size,
                                bg=CARD_BG, highlightthickness=0)
        ring_canvas.pack(pady=(0, 8))
        self._draw_progress_ring(ring_canvas, ring_size,
                                 stats['percent_complete'])

        tk.Label(ring_inner, text=f"{stats['completed']} of {stats['total']} courses",
                 font=F_SMALL, fg=TEXT_SECONDARY, bg=CARD_BG).pack()

        # Student info card (suppressed in Private View)
        stu_card = _card(row2)
        stu_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        stu_inner = tk.Frame(stu_card, bg=CARD_BG, padx=20, pady=16)
        stu_inner.pack(fill=tk.BOTH, expand=True)

        if self._private_view:
            tk.Label(stu_inner, text="Private View", font=F_HEADING,
                     fg=TEXT_SECONDARY, bg=CARD_BG).pack(anchor=tk.W, pady=(0, 12))
            lock_canvas = tk.Canvas(stu_inner, width=44, height=44,
                                    bg=CARD_BG, highlightthickness=0)
            lock_canvas.pack(anchor=tk.W, pady=(0, 8))
            lock_canvas.create_oval(2, 2, 42, 42, fill=GRAY_LIGHT, outline="")
            lock_canvas.create_text(22, 22, text="🔒", font=("Segoe UI", 16))
            tk.Label(stu_inner,
                     text="Student identity is\nhidden in this mode.",
                     font=F_TINY, fg=TEXT_MUTED, bg=CARD_BG,
                     justify=tk.LEFT).pack(anchor=tk.W)
            tk.Label(stu_inner, text=f"Program: {self.grid.program_name}",
                     font=F_SMALL, fg=TEXT_SECONDARY,
                     bg=CARD_BG).pack(anchor=tk.W, pady=(8, 0))
        else:
            tk.Label(stu_inner, text="Student", font=F_HEADING,
                     fg=TEXT_PRIMARY, bg=CARD_BG).pack(anchor=tk.W, pady=(0, 8))

            av_frame = tk.Frame(stu_inner, bg=CARD_BG)
            av_frame.pack(anchor=tk.W, pady=(0, 10))
            initials = "".join(w[0].upper() for w in name.split()[:2]) \
                       if name != "—" else "?"
            av = tk.Canvas(av_frame, width=44, height=44, bg=CARD_BG,
                           highlightthickness=0)
            av.pack(side=tk.LEFT, padx=(0, 12))
            av.create_oval(2, 2, 42, 42, fill=BLUE, outline="")
            av.create_text(22, 22, text=initials, fill=WHITE,
                           font=("Segoe UI", 14, "bold"))
            tk.Label(av_frame, text=name, font=("Segoe UI", 12, "bold"),
                     fg=TEXT_PRIMARY, bg=CARD_BG).pack(anchor=tk.W)

            for lbl, val in [("Program", self.grid.program_name),
                             ("GPA", gpa_str or "—"),
                             ("Credits", credits_str or "—")]:
                rf = tk.Frame(stu_inner, bg=CARD_BG)
                rf.pack(fill=tk.X, pady=2)
                tk.Label(rf, text=lbl, font=F_SMALL, fg=TEXT_MUTED,
                         bg=CARD_BG, width=10, anchor=tk.W).pack(side=tk.LEFT)
                tk.Label(rf, text=val, font=("Segoe UI", 10, "bold"),
                         fg=TEXT_PRIMARY, bg=CARD_BG, anchor=tk.W).pack(side=tk.LEFT)

        # Breakdown bar card
        bar_card = _card(row2)
        bar_card.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 0))
        bar_inner = tk.Frame(bar_card, bg=CARD_BG, padx=20, pady=16)
        bar_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(bar_inner, text="Breakdown", font=F_HEADING,
                 fg=TEXT_PRIMARY, bg=CARD_BG).pack(anchor=tk.W, pady=(0, 10))

        total = stats['total'] or 1
        for lbl, cnt, clr in [
            ("Completed", stats['completed'], GREEN),
            ("Transfer", stats['transfer'], PURPLE),
            ("In Progress", stats['in_progress'], BLUE_STATUS),
            ("Gaps", stats['gaps'], RED),
            ("Remaining", stats['remaining'], ORANGE),
        ]:
            rf = tk.Frame(bar_inner, bg=CARD_BG)
            rf.pack(fill=tk.X, pady=3)
            tk.Label(rf, text=f"{lbl}  ({cnt})", font=F_SMALL,
                     fg=TEXT_PRIMARY, bg=CARD_BG, anchor=tk.W).pack(fill=tk.X)
            bar_bg = tk.Frame(rf, bg=BORDER, height=8)
            bar_bg.pack(fill=tk.X, pady=(2, 0))
            bar_bg.update_idletasks()
            pct = cnt / total
            bar_fg = tk.Frame(bar_bg, bg=clr, height=8,
                              width=max(2, int(180 * pct)))
            bar_fg.place(x=0, y=0, relheight=1)

        # ── Row 3: Transfer Credits ──
        if self.record:
            transfers = get_transfer_courses(self.record)
            if transfers:
                row_te = tk.Frame(self.stats_inner, bg=BG)
                row_te.pack(fill=tk.X, pady=(0, 10))

                te_card = _card(row_te)
                te_card.pack(fill=tk.BOTH, expand=True)
                te_inner = tk.Frame(te_card, bg=CARD_BG, padx=20, pady=16)
                te_inner.pack(fill=tk.BOTH, expand=True)

                # Header row
                te_hdr = tk.Frame(te_inner, bg=CARD_BG)
                te_hdr.pack(fill=tk.X, pady=(0, 8))
                tk.Label(te_hdr, text="Transfer Credits", font=F_HEADING,
                         fg=TEXT_PRIMARY, bg=CARD_BG).pack(side=tk.LEFT)
                tk.Label(te_hdr,
                         text=f"{len(transfers)} courses",
                         font=F_SMALL, fg=PURPLE, bg=CARD_BG).pack(
                             side=tk.RIGHT)

                # Courses in a compact grid
                te_grid = tk.Frame(te_inner, bg=CARD_BG)
                te_grid.pack(fill=tk.X)
                col_count = 4  # courses per row
                for idx, ec in enumerate(transfers):
                    r, c_idx = divmod(idx, col_count)
                    cell = tk.Frame(te_grid, bg=PURPLE_BG,
                                    highlightbackground=BORDER,
                                    highlightthickness=1)
                    cell.grid(row=r, column=c_idx, sticky="nsew",
                              padx=2, pady=2)
                    tk.Label(cell, text=ec.code, font=("Segoe UI", 9, "bold"),
                             fg=TEXT_PRIMARY, bg=PURPLE_BG,
                             padx=8, pady=4).pack(anchor=tk.W)
                    tk.Label(cell, text=f"{ec.credits} cr", font=F_TINY,
                             fg=TEXT_SECONDARY, bg=PURPLE_BG,
                             padx=8).pack(anchor=tk.W)
                for ci in range(col_count):
                    te_grid.columnconfigure(ci, weight=1)

                tk.Frame(te_inner, bg=BORDER, height=1).pack(
                    fill=tk.X, pady=(8, 4))
                total_te = sum(ec.credits for ec in transfers)
                tk.Label(te_inner,
                         text=f"Total Transfer Credits: {total_te}",
                         font=("Segoe UI", 10, "bold"), fg=PURPLE,
                         bg=CARD_BG).pack(anchor=tk.W)

        # ── Row 4: Free Electives + Other Courses ──
        if self.record:
            row3 = tk.Frame(self.stats_inner, bg=BG)
            row3.pack(fill=tk.X, pady=(0, 10))

            # Free Electives card
            fe_card = _card(row3)
            fe_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
            fe_inner = tk.Frame(fe_card, bg=CARD_BG, padx=20, pady=16)
            fe_inner.pack(fill=tk.BOTH, expand=True)
            tk.Label(fe_inner, text="Free Electives", font=F_HEADING,
                     fg=TEXT_PRIMARY, bg=CARD_BG).pack(anchor=tk.W, pady=(0, 8))

            free_electives = get_free_elective_courses(self.record)
            if free_electives:
                total_fe = 0
                for ec in free_electives:
                    status_tag = ec.status.value.replace("_", " ").title()
                    grade_str = f"({ec.grade})" if ec.grade else ""
                    rf = tk.Frame(fe_inner, bg=CARD_BG)
                    rf.pack(fill=tk.X, pady=1)
                    tk.Label(rf, text=ec.code, font=("Segoe UI", 9, "bold"),
                             fg=TEXT_PRIMARY, bg=CARD_BG, width=14,
                             anchor=tk.W).pack(side=tk.LEFT)
                    tk.Label(rf, text=status_tag, font=F_TINY,
                             fg=TEXT_SECONDARY, bg=CARD_BG, width=12,
                             anchor=tk.W).pack(side=tk.LEFT)
                    tk.Label(rf, text=grade_str, font=F_TINY, fg=TEXT_MUTED,
                             bg=CARD_BG, width=6, anchor=tk.W).pack(side=tk.LEFT)
                    tk.Label(rf, text=f"{ec.credits} cr", font=F_TINY,
                             fg=TEXT_SECONDARY, bg=CARD_BG,
                             anchor=tk.E).pack(side=tk.RIGHT)
                    total_fe += ec.credits

                tk.Frame(fe_inner, bg=BORDER, height=1).pack(fill=tk.X, pady=(6, 4))
                tk.Label(fe_inner,
                         text=f"Total: {total_fe} credits  |  {len(free_electives)} courses",
                         font=("Segoe UI", 9, "bold"), fg=GREEN,
                         bg=CARD_BG).pack(anchor=tk.W)
            else:
                tk.Label(fe_inner, text="No free elective courses found.",
                         font=F_SMALL, fg=TEXT_MUTED, bg=CARD_BG).pack(anchor=tk.W)

            # Other Courses card
            oc_card = _card(row3)
            oc_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            oc_inner = tk.Frame(oc_card, bg=CARD_BG, padx=20, pady=16)
            oc_inner.pack(fill=tk.BOTH, expand=True)
            tk.Label(oc_inner, text="Other Courses (Unmatched)", font=F_HEADING,
                     fg=TEXT_PRIMARY, bg=CARD_BG).pack(anchor=tk.W, pady=(0, 8))

            unmatched = get_unmatched_courses(self.record, self.grid)
            fe_ids = {id(ec) for ec in free_electives} if free_electives else set()
            other_courses = [ec for ec in unmatched if id(ec) not in fe_ids]

            if other_courses:
                total_oc = 0
                for ec in other_courses:
                    status_tag = ec.status.value.replace("_", " ").title()
                    grade_str = f"({ec.grade})" if ec.grade else ""
                    section_short = ec.section[:18] if ec.section else ""
                    rf = tk.Frame(oc_inner, bg=CARD_BG)
                    rf.pack(fill=tk.X, pady=1)
                    tk.Label(rf, text=ec.code, font=("Segoe UI", 9, "bold"),
                             fg=TEXT_PRIMARY, bg=CARD_BG, width=14,
                             anchor=tk.W).pack(side=tk.LEFT)
                    tk.Label(rf, text=status_tag, font=F_TINY,
                             fg=TEXT_SECONDARY, bg=CARD_BG, width=12,
                             anchor=tk.W).pack(side=tk.LEFT)
                    tk.Label(rf, text=grade_str, font=F_TINY, fg=TEXT_MUTED,
                             bg=CARD_BG, width=6, anchor=tk.W).pack(side=tk.LEFT)
                    tk.Label(rf, text=section_short, font=F_TINY, fg=TEXT_MUTED,
                             bg=CARD_BG, anchor=tk.W).pack(side=tk.LEFT, padx=4)
                    tk.Label(rf, text=f"{ec.credits} cr", font=F_TINY,
                             fg=TEXT_SECONDARY, bg=CARD_BG,
                             anchor=tk.E).pack(side=tk.RIGHT)
                    total_oc += ec.credits

                tk.Frame(oc_inner, bg=BORDER, height=1).pack(fill=tk.X, pady=(6, 4))
                tk.Label(oc_inner,
                         text=f"Total: {total_oc} credits  |  {len(other_courses)} courses",
                         font=("Segoe UI", 9, "bold"), fg=ORANGE,
                         bg=CARD_BG).pack(anchor=tk.W)
            else:
                tk.Label(oc_inner,
                         text="All courses matched to the program grid.",
                         font=F_SMALL, fg=TEXT_MUTED, bg=CARD_BG).pack(anchor=tk.W)

        # Re-bind mousewheel to new stats children
        if hasattr(self, '_bind_stats_mw'):
            self.root.after(50, lambda: self._bind_stats_mw(self.stats_inner))

    def _draw_progress_ring(self, canvas, size, percent):
        """Draw a donut-style progress ring on a Canvas."""
        pad = 12
        width = 14
        x0, y0 = pad, pad
        x1, y1 = size - pad, size - pad

        # Background ring
        canvas.create_oval(x0, y0, x1, y1, outline=BORDER, width=width)

        # Progress arc
        if percent > 0:
            extent = 3.6 * percent
            canvas.create_arc(x0, y0, x1, y1, start=90, extent=-extent,
                              outline=GREEN, width=width, style=tk.ARC)

        # Center text
        cx, cy = size / 2, size / 2
        canvas.create_text(cx, cy - 6, text=f"{percent:.0f}%",
                           font=("Segoe UI", 18, "bold"), fill=TEXT_PRIMARY)
        canvas.create_text(cx, cy + 14, text="complete",
                           font=F_TINY, fill=TEXT_MUTED)

    # ================================================================
    #  EXPORT
    # ================================================================

    def _export_grid_pdf(self):
        if not self.grid:
            messagebox.showwarning("Warning", "No program grid loaded.")
            return
        name, sid = self._get_export_label()
        filepath = filedialog.asksaveasfilename(
            title="Save Highlighted Grid PDF", defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")],
            initialfile=f"grid_{name.replace(' ', '_') or 'output'}.pdf")
        if not filepath:
            return
        try:
            advisor = self.advisor_var.get()
            if advisor in ("Select advisor...", "No advisors available"):
                advisor = ""
            generate_grid_pdf(self.grid, name, sid, filepath, self.plan,
                              advisor_name=advisor)
            self.status_var.set(f"Grid PDF exported: {filepath}")
            messagebox.showinfo("Success", f"Grid PDF saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export:\n{e}")

    def _export_plan_pdf(self):
        if not self.plan:
            messagebox.showwarning("Warning", "No plan generated yet.")
            return
        name, sid = self._get_export_label()
        filepath = filedialog.asksaveasfilename(
            title="Save Semester Plan PDF", defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")],
            initialfile=f"plan_{name.replace(' ', '_') or 'output'}.pdf")
        if not filepath:
            return
        try:
            generate_semester_plan_pdf(
                self.plan, name, sid,
                self.grid.program_name if self.grid else "", filepath)
            self.status_var.set(f"Plan PDF exported: {filepath}")
            messagebox.showinfo("Success", f"Plan PDF saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export:\n{e}")
