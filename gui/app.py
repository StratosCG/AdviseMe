"""
Course Tracker GUI Application — Dashboard-style UI with CustomTkinter.

Kean University branded interface with card-based layout, visual analytics,
and Human Mode for manual course status editing.
"""
import os
import sys
import math
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime

try:
    import customtkinter as ctk
    ctk.set_appearance_mode("light")
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
    STRATEGY_CAP_18, STRATEGY_ADVISOR_PICKS, STRATEGY_SWAP, STRATEGY_MANUAL
)
from core.pdf_generator import generate_grid_pdf, generate_semester_plan_pdf
from core.updater import check_for_updates
from version import __version__


# ── Brand Colors ─────────────────────────────────────────────────
NAVY       = "#15293F"
NAVY_LIGHT = "#1E3A5F"
NAVY_MID   = "#2A4A6B"
GRAY       = "#959CA1"
GRAY_LIGHT = "#C5CAD0"
BLUE       = "#8FC3E9"
BLUE_DARK  = "#5BA3D9"
WHITE      = "#FFFFFF"
BG         = "#F0F4F8"       # page background
CARD_BG    = "#FFFFFF"
SIDEBAR_BG = "#F7F9FC"
BORDER     = "#E2E8F0"
TEXT_PRIMARY   = "#1A202C"
TEXT_SECONDARY = "#718096"
TEXT_MUTED     = "#A0AEC0"

# Status colors
GREEN      = "#48BB78"
GREEN_BG   = "#C6F6D5"
ORANGE     = "#ED8936"
ORANGE_BG  = "#FEEBC8"
RED        = "#FC8181"
RED_BG     = "#FED7D7"
BLUE_STATUS = "#63B3ED"
BLUE_BG    = "#BEE3F8"
PURPLE     = "#9F7AEA"
PURPLE_BG  = "#E9D8FD"

# Grid cell colors
GRID_GREEN   = "#C6F6D5"
GRID_TRANSFER = "#E9D8FD"   # Purple tint for transfers
GRID_ORANGE  = "#FEEBC8"
GRID_RED     = "#FED7D7"
GRID_BLUE    = "#BEE3F8"
GRID_WHITE   = "#FFFFFF"

# Fonts
F_TITLE   = ("Segoe UI", 16, "bold")
F_HEADING = ("Segoe UI", 12, "bold")
F_LABEL   = ("Segoe UI", 10)
F_BODY    = ("Segoe UI", 10)
F_SMALL   = ("Segoe UI", 9)
F_TINY    = ("Segoe UI", 8)
F_GRID    = ("Segoe UI", 8)
F_GRID_B  = ("Segoe UI", 8, "bold")
F_METRIC  = ("Segoe UI", 22, "bold")
F_METRIC_LABEL = ("Segoe UI", 9)


def _card(parent, **kw):
    """Create a card-like frame with border."""
    f = tk.Frame(parent, bg=CARD_BG, highlightbackground=BORDER,
                 highlightthickness=1, **kw)
    return f


class CourseTrackerApp:
    """Dashboard-style application."""

    def __init__(self, root):
        self.root = root
        self.root.title("Course Tracker — Kean University")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)
        self.root.configure(bg=BG)

        # State
        self.grid: ProgramGrid = None
        self.record: StudentRecord = None
        self.plan: SemesterPlan = None
        self.current_semester_idx: int = -1
        self.programs_dir = get_programs_dir()

        # Human-mode manual student info
        self._human_name_var = tk.StringVar()
        self._human_id_var = tk.StringVar()
        self._human_gpa_var = tk.StringVar()
        self._human_credits_var = tk.StringVar()

        # Build UI
        self._build_header()
        self._build_body()
        self._build_status_bar()
        self._refresh_programs()

        # Check for updates in background (non-blocking)
        check_for_updates(self.root, __version__)

    # ================================================================
    #  HEADER
    # ================================================================

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=NAVY, height=56)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        # Left: branding
        left = tk.Frame(hdr, bg=NAVY)
        left.pack(side=tk.LEFT, padx=24, pady=8)
        tk.Label(left, text="KEAN UNIVERSITY", font=("Segoe UI", 9, "bold"),
                 fg=BLUE, bg=NAVY).pack(anchor=tk.W)
        tk.Label(left, text="Course Tracker", font=("Segoe UI", 15, "bold"),
                 fg=WHITE, bg=NAVY).pack(anchor=tk.W)

        # Center-right: Reset button
        reset_btn = tk.Button(
            hdr, text="⟳  RESET", font=("Segoe UI", 9, "bold"),
            bg="#C53030", fg=WHITE, activebackground="#9B2C2C",
            activeforeground=WHITE, relief=tk.FLAT, padx=14, pady=6,
            cursor="hand2", bd=0, command=self._confirm_reset)
        reset_btn.pack(side=tk.RIGHT, padx=(0, 16), pady=12)

        # Right: program selector
        right = tk.Frame(hdr, bg=NAVY)
        right.pack(side=tk.RIGHT, padx=(16, 0), pady=10)
        tk.Label(right, text="Program", font=F_SMALL, fg=BLUE,
                 bg=NAVY).pack(side=tk.LEFT, padx=(0, 8))

        self.program_var = tk.StringVar()
        if HAS_CTK:
            self.program_combo = ctk.CTkComboBox(
                right, variable=self.program_var, values=[], width=260,
                height=30, font=F_SMALL, dropdown_font=F_SMALL,
                fg_color=WHITE, border_color=NAVY_MID,
                button_color=NAVY_LIGHT, button_hover_color=BLUE,
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
        sidebar_outer = tk.Frame(body, bg=SIDEBAR_BG, width=290)
        sidebar_outer.pack(side=tk.LEFT, fill=tk.Y)
        sidebar_outer.pack_propagate(False)

        sb_canvas = tk.Canvas(sidebar_outer, bg=SIDEBAR_BG, highlightthickness=0, width=274)
        sb_scroll = tk.Scrollbar(sidebar_outer, orient=tk.VERTICAL, command=sb_canvas.yview)
        sb_canvas.configure(yscrollcommand=sb_scroll.set)
        sb_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        sb_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._sb = tk.Frame(sb_canvas, bg=SIDEBAR_BG, padx=16, pady=10)
        sb_canvas.create_window((0, 0), window=self._sb, anchor="nw")
        self._sb.bind("<Configure>",
                      lambda e: sb_canvas.configure(scrollregion=sb_canvas.bbox("all")))

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
        # ── Upload ──
        self._sidebar_label(sb, "UPLOAD EVALUATION")
        self._make_button(sb, "Upload PDF", NAVY, WHITE, self._upload_eval, h=36)

        self.eval_label = tk.Label(sb, text="No file loaded", font=F_TINY,
                                   fg=TEXT_MUTED, bg=SIDEBAR_BG, anchor=tk.W)
        self.eval_label.pack(fill=tk.X, pady=(2, 0))

        # ── Student Info (read-only card from PDF) ──
        self._sidebar_label(sb, "STUDENT INFO")
        card = _card(sb)
        card.pack(fill=tk.X, pady=(2, 6))
        self.info_text = tk.Text(card, height=5, width=28, state=tk.DISABLED,
                                 font=F_TINY, bg=CARD_BG, fg=TEXT_PRIMARY,
                                 relief=tk.FLAT, padx=10, pady=8, borderwidth=0)
        self.info_text.pack(fill=tk.X)

        # ── Faculty Advisor ──
        self._sidebar_label(sb, "FACULTY ADVISOR")
        self.advisor_var = tk.StringVar(value="")
        if HAS_CTK:
            self.advisor_combo = ctk.CTkComboBox(
                sb, variable=self.advisor_var,
                values=["Select advisor..."], width=250, height=28,
                font=F_TINY, dropdown_font=F_TINY,
                fg_color=WHITE, border_color=BORDER,
                button_color=NAVY_LIGHT, button_hover_color=BLUE)
        else:
            from tkinter import ttk
            self.advisor_combo = ttk.Combobox(
                sb, textvariable=self.advisor_var,
                values=["Select advisor..."], width=28)
        self.advisor_combo.pack(fill=tk.X, pady=(2, 8))
        self._faculty_data = load_faculty()

        # ── Semester Plan ──
        self._sidebar_label(sb, "SEMESTER PLAN")
        tk.Label(sb, text="Target Semester", font=F_TINY, fg=TEXT_SECONDARY,
                 bg=SIDEBAR_BG, anchor=tk.W).pack(fill=tk.X)

        self.semester_var = tk.StringVar()
        if HAS_CTK:
            self.semester_combo = ctk.CTkComboBox(
                sb, variable=self.semester_var,
                values=get_available_semesters(), width=250, height=28,
                font=F_TINY, dropdown_font=F_TINY,
                fg_color=WHITE, border_color=BORDER,
                button_color=NAVY_LIGHT, button_hover_color=BLUE)
        else:
            from tkinter import ttk
            self.semester_combo = ttk.Combobox(
                sb, textvariable=self.semester_var,
                values=get_available_semesters(), width=28)
        self.semester_combo.pack(fill=tk.X, pady=(2, 8))

        tk.Label(sb, text="Strategy", font=F_TINY, fg=TEXT_SECONDARY,
                 bg=SIDEBAR_BG, anchor=tk.W).pack(fill=tk.X, pady=(0, 2))

        self.strategy_var = tk.StringVar(value=STRATEGY_CAP_18)
        for val, label in [
            (STRATEGY_CAP_18, "Cap at 18 credits"),
            (STRATEGY_ADVISOR_PICKS, "Advisor picks courses"),
            (STRATEGY_SWAP, "Swap on-track for missed"),
            (STRATEGY_MANUAL, "Use manual edits"),
        ]:
            rb = tk.Radiobutton(sb, text=label, variable=self.strategy_var,
                                value=val, font=F_TINY, bg=SIDEBAR_BG,
                                fg=TEXT_PRIMARY, anchor=tk.W,
                                activebackground=SIDEBAR_BG, selectcolor=SIDEBAR_BG)
            rb.pack(fill=tk.X, padx=(8, 0), pady=0)

        self._make_button(sb, "Generate Plan", BLUE_DARK, WHITE,
                          self._generate_plan, h=36, pady=(8, 4))

        # ── Human Mode ──
        self._sidebar_label(sb, "HUMAN MODE")
        tk.Label(sb, text="Click grid cells to manually set status",
                 font=F_TINY, fg=TEXT_SECONDARY, bg=SIDEBAR_BG,
                 anchor=tk.W, wraplength=240).pack(fill=tk.X, pady=(0, 4))

        self.manual_mode_var = tk.BooleanVar(value=False)
        if HAS_CTK:
            self.manual_toggle = ctk.CTkSwitch(
                sb, text="Enable Human Mode", variable=self.manual_mode_var,
                font=F_SMALL, fg_color=GRAY_LIGHT, progress_color=GREEN,
                button_color=WHITE, button_hover_color=BLUE,
                command=self._on_manual_mode_toggle)
        else:
            self.manual_toggle = tk.Checkbutton(
                sb, text="Enable Human Mode", variable=self.manual_mode_var,
                font=F_SMALL, bg=SIDEBAR_BG, anchor=tk.W,
                command=self._on_manual_mode_toggle)
        self.manual_toggle.pack(fill=tk.X, pady=(0, 6))

        # Color picker
        self.manual_color_var = tk.StringVar(value="green")
        color_frame = tk.Frame(sb, bg=SIDEBAR_BG)
        color_frame.pack(fill=tk.X, pady=(0, 4))
        for val, lbl, clr in [
            ("green", "Completed", GREEN),
            ("transfer", "Transfer", PURPLE),
            ("orange", "Next Sem.", ORANGE),
            ("light_red", "Gap", RED),
            ("none", "Not Started", GRAY_LIGHT),
            ("in_progress", "In Progress", BLUE_STATUS),
        ]:
            rf = tk.Frame(color_frame, bg=SIDEBAR_BG)
            rf.pack(fill=tk.X, pady=1)
            tk.Radiobutton(rf, text=lbl, variable=self.manual_color_var,
                           value=val, font=F_TINY, bg=SIDEBAR_BG,
                           fg=TEXT_PRIMARY, anchor=tk.W,
                           activebackground=SIDEBAR_BG,
                           selectcolor=SIDEBAR_BG).pack(side=tk.LEFT)
            tk.Frame(rf, bg=clr, width=18, height=12,
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
                                     height=28, font=F_TINY, fg_color=WHITE,
                                     border_color=BORDER, corner_radius=4)
            else:
                entry = tk.Entry(self._human_info_frame, textvariable=var,
                                 font=F_TINY, relief=tk.SOLID, bd=1)
            entry.pack(fill=tk.X, pady=(1, 6))

        # ── Export ──
        self._sidebar_label(sb, "EXPORT")
        self._make_button(sb, "Export Grid PDF", CARD_BG, TEXT_PRIMARY,
                          self._export_grid_pdf, h=30, border=True)
        self._make_button(sb, "Export Plan PDF", CARD_BG, TEXT_PRIMARY,
                          self._export_plan_pdf, h=30, border=True, pady=(4, 2))

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

        grid_card = _card(grid_frame)
        grid_card.pack(fill=tk.BOTH, expand=True)

        self.grid_canvas = tk.Canvas(grid_card, bg=CARD_BG, highlightthickness=0)
        gv = tk.Scrollbar(grid_card, orient=tk.VERTICAL, command=self.grid_canvas.yview)
        gh = tk.Scrollbar(grid_card, orient=tk.HORIZONTAL, command=self.grid_canvas.xview)
        self.grid_canvas.configure(yscrollcommand=gv.set, xscrollcommand=gh.set)
        gv.pack(side=tk.RIGHT, fill=tk.Y)
        gh.pack(side=tk.BOTTOM, fill=tk.X)
        self.grid_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.grid_inner_frame = tk.Frame(self.grid_canvas, bg=CARD_BG)
        self.grid_canvas.create_window((0, 0), window=self.grid_inner_frame, anchor="nw")
        self.grid_inner_frame.bind("<Configure>",
            lambda e: self.grid_canvas.configure(scrollregion=self.grid_canvas.bbox("all")))

        # ── Plan tab ──
        plan_frame = tk.Frame(self.tab_container, bg=BG)
        self.tab_frames["plan"] = plan_frame
        plan_card = _card(plan_frame)
        plan_card.pack(fill=tk.BOTH, expand=True)
        self.plan_text = tk.Text(plan_card, wrap=tk.WORD, font=("Consolas", 10),
                                 bg=CARD_BG, fg=TEXT_PRIMARY, relief=tk.FLAT,
                                 padx=20, pady=16, borderwidth=0)
        ps = tk.Scrollbar(plan_card, orient=tk.VERTICAL, command=self.plan_text.yview)
        self.plan_text.configure(yscrollcommand=ps.set)
        ps.pack(side=tk.RIGHT, fill=tk.Y)
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

        # Scrollable cards area
        stats_scroll_canvas = tk.Canvas(stats_frame, bg=BG, highlightthickness=0)
        stats_scrollbar = tk.Scrollbar(stats_frame, orient=tk.VERTICAL,
                                       command=stats_scroll_canvas.yview)
        stats_scroll_canvas.configure(yscrollcommand=stats_scrollbar.set)
        stats_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        stats_scroll_canvas.pack(fill=tk.BOTH, expand=True)

        self.stats_inner = tk.Frame(stats_scroll_canvas, bg=BG)
        stats_scroll_canvas.create_window((0, 0), window=self.stats_inner, anchor="nw")
        self.stats_inner.bind("<Configure>",
            lambda e: stats_scroll_canvas.configure(
                scrollregion=stats_scroll_canvas.bbox("all")))

        self._switch_tab("grid")

    # ================================================================
    #  HELPERS
    # ================================================================

    def _sidebar_label(self, parent, text):
        f = tk.Frame(parent, bg=parent.cget("bg"))
        f.pack(fill=tk.X, pady=(12, 3))
        tk.Label(f, text=text, font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED,
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
                btn.configure(bg=NAVY, fg=WHITE, font=("Segoe UI", 10, "bold"))
            else:
                btn.configure(bg="#E2E8F0", fg=TEXT_PRIMARY, font=F_LABEL)

    def _build_status_bar(self):
        self.status_var = tk.StringVar(
            value="Ready — Select a program and upload an evaluation to begin.")
        tk.Label(self.root, textvariable=self.status_var, font=F_TINY,
                 fg=TEXT_MUTED, bg="#E2E8F0", anchor=tk.W,
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
        self.manual_mode_var.set(False)
        if hasattr(self, '_human_info_frame'):
            self._human_info_frame.pack_forget()

        # Clear Human Mode inputs
        for attr in ('_human_name_var', '_human_id_var',
                     '_human_gpa_var', '_human_credits_var'):
            if hasattr(self, attr):
                getattr(self, attr).set("")

        # Refresh grid display and stats
        if self.grid:
            self._display_grid()
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
        if self.manual_mode_var.get():
            self._human_info_frame.pack(fill=tk.X, after=self.manual_toggle.master
                                        if hasattr(self.manual_toggle, 'master')
                                        else self._sb)
            self.status_var.set(
                "Human Mode ON — Click any course cell to set its status.")
        else:
            self._human_info_frame.pack_forget()
            self.status_var.set("Human Mode OFF.")
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
        if not self.grid:
            return

        max_c = max(len(s.courses) for s in self.grid.semesters)

        # Header
        headers = ["Year", "Term"] + [f"Course {i+1}" for i in range(max_c)] + ["Cr"]
        for col, h in enumerate(headers):
            tk.Label(self.grid_inner_frame, text=h, bg=NAVY, fg=WHITE,
                     font=F_GRID_B, padx=6, pady=5).grid(
                         row=0, column=col, sticky="nsew")

        row = 1
        cur_year = None
        for sem in self.grid.semesters:
            ytxt = f"Year {sem.year}" if sem.year != cur_year else ""
            cur_year = sem.year

            for col, txt in enumerate([ytxt, sem.term]):
                tk.Label(self.grid_inner_frame, text=txt, bg=NAVY_LIGHT,
                         fg=WHITE, font=F_GRID_B, padx=6,
                         pady=5).grid(row=row, column=col, sticky="nsew")

            for col, course in enumerate(sem.courses):
                bg = self._cell_color(course)
                if course.is_elective_slot or course.is_ge_category:
                    txt = f"{course.name}\n({course.credits} cr)"
                else:
                    txt = f"{course.code}\n{course.name}\n({course.credits} cr)"
                if course.matched_eval_course and course.matched_eval_course.grade:
                    txt += f"\n[{course.matched_eval_course.grade}]"

                cursor = "hand2" if self.manual_mode_var.get() else ""
                lbl = tk.Label(self.grid_inner_frame, text=txt, bg=bg,
                               fg=TEXT_PRIMARY, font=F_GRID, padx=5, pady=5,
                               wraplength=130, justify=tk.CENTER,
                               highlightbackground=BORDER,
                               highlightthickness=1, cursor=cursor)
                lbl.grid(row=row, column=col + 2, sticky="nsew")
                lbl.bind("<Button-1>",
                         lambda e, c=course: self._on_grid_cell_click(c))

            for col in range(len(sem.courses), max_c):
                tk.Label(self.grid_inner_frame, text="", bg=CARD_BG,
                         highlightbackground=BORDER,
                         highlightthickness=1).grid(
                             row=row, column=col + 2, sticky="nsew")

            cr = sum(c.credits for c in sem.courses)
            tk.Label(self.grid_inner_frame, text=str(cr), bg=NAVY_LIGHT,
                     fg=WHITE, font=F_GRID_B, padx=6, pady=5).grid(
                         row=row, column=max_c + 2, sticky="nsew")
            row += 1

        # Legend
        row += 1
        for i, (txt, clr) in enumerate([
            ("Completed", GRID_GREEN), ("Transfer", GRID_TRANSFER),
            ("Next Semester", GRID_ORANGE), ("Gap", GRID_RED),
            ("In Progress", GRID_BLUE), ("Not Scheduled", GRID_WHITE),
        ]):
            tk.Label(self.grid_inner_frame, text=f"  {txt}  ", bg=clr,
                     fg=TEXT_PRIMARY, font=F_TINY, highlightbackground=BORDER,
                     highlightthickness=1, padx=6, pady=3).grid(
                         row=row, column=i + 1, sticky="nsew", padx=1, pady=4)

        for col in range(max_c + 3):
            self.grid_inner_frame.columnconfigure(col, weight=1)

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

    # ================================================================
    #  PLAN GENERATION
    # ================================================================

    def _generate_plan(self):
        if not self.grid:
            messagebox.showwarning("Warning", "Please select a program first.")
            return
        try:
            strategy = self.strategy_var.get()
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

            if strategy == STRATEGY_ADVISOR_PICKS:
                self._show_advisor_pick_dialog(semester_idx, semester_label)
                return

            self.plan = generate_plan(self.grid, semester_idx, semester_label,
                                      strategy)
            self._display_grid()
            self._update_stats()
            self._display_plan()
            self._switch_tab("plan")
            self.status_var.set(
                f"Plan generated for {semester_label}: "
                f"{self.plan.total_credits} credits")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate plan:\n{e}")
            import traceback; traceback.print_exc()

    def _show_advisor_pick_dialog(self, semester_idx, semester_label):
        if HAS_CTK:
            dialog = ctk.CTkToplevel(self.root)
        else:
            dialog = tk.Toplevel(self.root)
        dialog.title("Select Courses — Advisor Selection")
        dialog.geometry("720x640")
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

        # Scrollable list
        canvas = tk.Canvas(dialog, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(dialog, orient=tk.VERTICAL, command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(fill=tk.BOTH, expand=True, padx=20)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        check_vars = {}
        key_map = {}

        def update_count(*_):
            total = sum(cr for k, (v, cr) in check_vars.items() if v.get())
            color = GREEN if total <= 18 else RED
            credit_var.set(f"Selected: {total} credits" +
                           (" — over 18!" if total > 18 else ""))
            counter_lbl.configure(fg=color)

        def add_cb(parent, text, key, code, credits, checked, accent):
            var = tk.BooleanVar(value=checked)
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
        if other:
            tk.Label(inner, text="All Other Remaining Courses",
                     font=("Segoe UI", 10, "bold"), fg=TEXT_MUTED,
                     bg=BG).pack(anchor=tk.W, pady=(12, 2))
            tk.Label(inner, text="Select any for special scheduling needs",
                     font=F_TINY, fg=TEXT_MUTED, bg=BG).pack(
                         anchor=tk.W, padx=12, pady=(0, 4))
            for sl, c in other:
                add_cb(inner,
                       f"{c.code} — {c.name} ({c.credits} cr) [{sl}]",
                       f"o_{c.code}_{sl}", c.code, c.credits, False, GRAY)

        update_count()

        def confirm():
            sel = [key_map[k] for k, (v, _) in check_vars.items() if v.get()]
            self.plan = generate_plan(self.grid, semester_idx, semester_label,
                                      STRATEGY_ADVISOR_PICKS, sel)
            self._display_grid()
            self._update_stats()
            self._display_plan()
            self._switch_tab("plan")
            dialog.destroy()
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

    def _display_plan(self):
        self.plan_text.delete("1.0", tk.END)
        if not self.plan:
            self.plan_text.insert(tk.END,
                "No plan generated yet.\n\n"
                "Upload an evaluation and click 'Generate Plan'.")
            return

        name = self._get_student_name()
        sid = self._get_student_id()
        lines = []
        if name:
            lines.append(f"  Student: {name}    ID: {sid}")
            lines.append("")
        lines.append(f"{'━' * 64}")
        lines.append(f"  SEMESTER PLAN: {self.plan.semester_label}")
        lines.append(f"{'━' * 64}\n")

        if self.plan.courses:
            lines.append("  SCHEDULED COURSES")
            lines.append(f"  {'─' * 58}")
            for c in self.plan.courses:
                lines.append(f"    {c.code:<18} {c.name:<34} {c.credits} cr")
            lines.append(f"  {'─' * 58}")
            lines.append(f"    {'Subtotal':<52} "
                         f"{sum(c.credits for c in self.plan.courses)} cr\n")

        if self.plan.makeup_courses:
            lines.append("  MAKEUP COURSES (Out of Sequence)")
            lines.append(f"  {'─' * 58}")
            for c in self.plan.makeup_courses:
                lines.append(f"    {c.code:<18} {c.name:<34} {c.credits} cr")
            lines.append(f"  {'─' * 58}")
            lines.append(f"    {'Subtotal':<52} "
                         f"{sum(c.credits for c in self.plan.makeup_courses)} cr\n")

        self.plan.compute_total()
        lines.append(f"{'━' * 64}")
        lines.append(f"  TOTAL CREDITS: {self.plan.total_credits}")
        lines.append(f"{'━' * 64}")

        if self.plan.notes:
            lines.append("\n  NOTES:")
            for n in self.plan.notes:
                lines.append(f"    {n}")

        self.plan_text.insert(tk.END, "\n".join(lines))

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

        # Student info card
        stu_card = _card(row2)
        stu_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        stu_inner = tk.Frame(stu_card, bg=CARD_BG, padx=20, pady=16)
        stu_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(stu_inner, text="Student", font=F_HEADING,
                 fg=TEXT_PRIMARY, bg=CARD_BG).pack(anchor=tk.W, pady=(0, 8))

        # Initials avatar
        av_frame = tk.Frame(stu_inner, bg=CARD_BG)
        av_frame.pack(anchor=tk.W, pady=(0, 10))
        initials = "".join(w[0].upper() for w in name.split()[:2]) if name != "—" else "?"
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
            bar_bg = tk.Frame(rf, bg="#EDF2F7", height=8)
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

    def _draw_progress_ring(self, canvas, size, percent):
        """Draw a donut-style progress ring on a Canvas."""
        pad = 12
        width = 14
        x0, y0 = pad, pad
        x1, y1 = size - pad, size - pad

        # Background ring
        canvas.create_oval(x0, y0, x1, y1, outline="#EDF2F7", width=width)

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
        name = self._get_student_name()
        sid = self._get_student_id()
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
        name = self._get_student_name()
        sid = self._get_student_id()
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
