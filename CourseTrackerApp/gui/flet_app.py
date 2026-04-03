"""
AdviseMe — Flet-based GUI.

Modern glassmorphic dashboard with card-based layout,
micro-interactions, and smooth transitions.
"""
import os
import sys
import math
import json
import urllib.request

import flet as ft

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import (
    GridHighlight, CourseStatus, StudentRecord, ProgramGrid, SemesterPlan
)
from core.evaluation_parser import parse_evaluation_pdf
from core.grid_loader import (
    load_program_grid, list_available_programs, get_programs_dir,
    load_faculty,
)
from core.course_matcher import (
    match_courses, detect_current_semester, find_gap_courses,
    get_next_semester_courses, get_completion_stats,
    get_unmatched_courses, get_free_elective_courses,
    get_all_remaining_grid_courses, get_transfer_courses,
)
from core.semester_planner import (
    generate_plan, auto_detect_semester_label, auto_detect_semester_index,
    get_strategy_options, get_available_semesters,
    STRATEGY_ADVISOR_PICKS,
)
from core.pdf_generator import generate_grid_pdf, generate_semester_plan_pdf
from version import __version__

GITHUB_REPO = "StratosCG/AdviseMe"


def _check_for_update() -> tuple:
    """Check GitHub for a newer release. Returns (latest_version, url) or (None, None)."""
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        latest = data.get("tag_name", "").lstrip("v")
        html_url = data.get("html_url", "")
        if latest and latest != __version__:
            # Simple version comparison: split by dots
            current_parts = [int(x) for x in __version__.split(".")]
            latest_parts = [int(x) for x in latest.split(".")]
            if latest_parts > current_parts:
                return latest, html_url
    except Exception:
        pass
    return None, None


# ── Brand Colors ──
NAVY          = "#15293F"
NAVY_LIGHT    = "#1E3A5F"
NAVY_MID      = "#2A4A6B"
GRAY          = "#64748B"
GRAY_LIGHT    = "#475569"
BLUE          = "#8FC3E9"
BLUE_DARK     = "#5BA3D9"
WHITE         = "#FFFFFF"

BG            = "#0B1120"
CARD_BG       = "#111B2E"
CARD_HOVER    = "#152238"
SIDEBAR_BG    = "#0E1728"
BORDER        = "#1E2D42"
TEXT_PRIMARY   = "#E2E8F0"
TEXT_SECONDARY = "#94A3B8"
TEXT_MUTED     = "#64748B"

GREEN         = "#48BB78"
GREEN_BG      = "#1A3A2A"
ORANGE        = "#ED8936"
ORANGE_BG     = "#2D2415"
RED           = "#FC8181"
RED_BG        = "#2D1A1A"
BLUE_STATUS   = "#63B3ED"
BLUE_BG       = "#1A2840"
PURPLE        = "#9F7AEA"
PURPLE_BG     = "#251A3A"

# Grid cell colors
GRID_GREEN    = "#C6F6D5"
GRID_TRANSFER = "#E9D8FD"
GRID_ORANGE   = "#F9C96A"
GRID_RED      = "#FCA5A5"
GRID_BLUE     = "#BEE3F8"
GRID_WHITE    = "#FFFFFF"
GRID_TEXT     = "#1A202C"
GRID_BG       = "#E8EDF2"

# ── Theme Palettes ──
# Each theme defines the key surface/accent colors used by _apply_theme().
# Keys: bg, card_bg, sidebar_bg, navy, navy_light, border,
#       text_primary, text_secondary, text_muted, accent, mode

THEME_MODERN = {
    "bg": "#0B1120", "card_bg": "#111B2E", "sidebar_bg": "#0E1728",
    "navy": "#15293F", "navy_light": "#1E3A5F", "border": "#1E2D42",
    "text_primary": "#E2E8F0", "text_secondary": "#94A3B8",
    "text_muted": "#64748B", "accent": "#5BA3D9", "mode": "dark",
}

THEME_FLAT = {
    "bg": "#F0F2F5", "card_bg": "#FFFFFF", "sidebar_bg": "#E8ECF1",
    "navy": "#2C3E50", "navy_light": "#34495E", "border": "#D1D9E0",
    "text_primary": "#1A202C", "text_secondary": "#4A5568",
    "text_muted": "#718096", "accent": "#3182CE", "mode": "light",
}

THEME_PRIVATE = {
    "bg": "#120E0E", "card_bg": "#1C1517", "sidebar_bg": "#150F11",
    "navy": "#2D1F23", "navy_light": "#3D2A30", "border": "#3A2630",
    "text_primary": "#E2E8F0", "text_secondary": "#94A3B8",
    "text_muted": "#64748B", "accent": "#C97070", "mode": "dark",
}

THEME_PURPLE = {
    "bg": "#F5F0FA", "card_bg": "#FFFFFF", "sidebar_bg": "#EDE5F4",
    "navy": "#5B2C8E", "navy_light": "#7B4DAA", "border": "#D4C4E3",
    "text_primary": "#1A102C", "text_secondary": "#5A4570",
    "text_muted": "#8A7399", "accent": "#7C3AED", "mode": "light",
}

THEME_ORANGE = {
    "bg": "#FFF7ED", "card_bg": "#FFFFFF", "sidebar_bg": "#FEF0DC",
    "navy": "#9A3412", "navy_light": "#C2410C", "border": "#FDDCAB",
    "text_primary": "#1C1007", "text_secondary": "#78501E",
    "text_muted": "#A07745", "accent": "#EA580C", "mode": "light",
}

THEME_BLUE = {
    "bg": "#EFF6FF", "card_bg": "#FFFFFF", "sidebar_bg": "#DBEAFE",
    "navy": "#1E3A5F", "navy_light": "#2563EB", "border": "#BFDBFE",
    "text_primary": "#0F172A", "text_secondary": "#334155",
    "text_muted": "#6B7FA3", "accent": "#2563EB", "mode": "light",
}

THEME_GREEN = {
    "bg": "#F0FDF4", "card_bg": "#FFFFFF", "sidebar_bg": "#DCFCE7",
    "navy": "#14532D", "navy_light": "#166534", "border": "#BBF7D0",
    "text_primary": "#052E16", "text_secondary": "#3B6B4F",
    "text_muted": "#6B9A7E", "accent": "#16A34A", "mode": "light",
}

BUILT_IN_THEMES = {
    "Midnight": THEME_MODERN, "Slate": THEME_FLAT,
    "Amethyst": THEME_PURPLE, "Ember": THEME_ORANGE,
    "Ocean": THEME_BLUE, "Forest": THEME_GREEN,
}


def _asset_path(filename: str) -> str:
    base = getattr(sys, '_MEIPASS', None)
    if base:
        return os.path.join(base, 'assets', filename)
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'assets', filename)


def _config_path() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'config.json')
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'config.json')


def _load_config() -> dict:
    try:
        with open(_config_path(), 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(data: dict):
    try:
        cfg = _load_config()
        cfg.update(data)
        with open(_config_path(), 'w') as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────

def _cell_color(course) -> str:
    if course.eval_status == CourseStatus.IN_PROGRESS:
        return GRID_BLUE
    return {
        GridHighlight.GREEN: GRID_GREEN,
        GridHighlight.TRANSFER: GRID_TRANSFER,
        GridHighlight.ORANGE: GRID_ORANGE,
        GridHighlight.LIGHT_RED: GRID_RED,
        GridHighlight.NONE: GRID_WHITE,
    }.get(course.status, GRID_WHITE)


def _cell_accent(course) -> str:
    if course.eval_status == CourseStatus.IN_PROGRESS:
        return BLUE_STATUS
    return {
        GridHighlight.GREEN: GREEN,
        GridHighlight.TRANSFER: PURPLE,
        GridHighlight.ORANGE: ORANGE,
        GridHighlight.LIGHT_RED: RED,
        GridHighlight.NONE: GRAY_LIGHT,
    }.get(course.status, GRAY_LIGHT)


# Mutable theme colors for module-level card helpers
_card_theme = {
    "bg": CARD_BG, "accent": BLUE_DARK, "border_tint": WHITE, "mode": "dark",
    "text_primary": TEXT_PRIMARY, "text_secondary": TEXT_SECONDARY,
    "text_muted": TEXT_MUTED, "navy_light": NAVY_LIGHT,
}


def _glass_card(content, padding=16, border_radius=12, expand=False,
                width=None, height=None, elevation="medium"):
    """Create a glassmorphic card container with layered shadows."""
    is_light = _card_theme["mode"] == "light"
    card_bg = _card_theme["bg"]
    accent = _card_theme["accent"]
    tint = _card_theme["border_tint"]

    shadow_opacity = 0.06 if is_light else 0.12
    shadow_presets = {
        "low": [
            ft.BoxShadow(spread_radius=0, blur_radius=4,
                         color=ft.Colors.with_opacity(shadow_opacity * 0.7, "#000000"),
                         offset=ft.Offset(0, 1)),
        ],
        "medium": [
            ft.BoxShadow(spread_radius=0, blur_radius=4,
                         color=ft.Colors.with_opacity(shadow_opacity, "#000000"),
                         offset=ft.Offset(0, 1)),
            ft.BoxShadow(spread_radius=0, blur_radius=12,
                         color=ft.Colors.with_opacity(shadow_opacity, "#000000"),
                         offset=ft.Offset(0, 4)),
        ],
        "high": [
            ft.BoxShadow(spread_radius=0, blur_radius=6,
                         color=ft.Colors.with_opacity(shadow_opacity, "#000000"),
                         offset=ft.Offset(0, 2)),
            ft.BoxShadow(spread_radius=0, blur_radius=20,
                         color=ft.Colors.with_opacity(shadow_opacity * 1.2, "#000000"),
                         offset=ft.Offset(0, 8)),
        ],
    }
    shadows = shadow_presets.get(elevation, shadow_presets["medium"])

    gradient_opacity = 0.02 if is_light else 0.03

    return ft.Container(
        content=content,
        padding=padding,
        border_radius=border_radius,
        bgcolor=card_bg,
        border=ft.border.all(1, ft.Colors.with_opacity(0.06 if is_light else 0.08, tint)),
        expand=expand,
        width=width,
        height=height,
        shadow=shadows,
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1, -1),
            end=ft.Alignment(1, 1),
            colors=[
                ft.Colors.with_opacity(gradient_opacity, accent),
                ft.Colors.with_opacity(0.00, accent),
            ],
        ),
    )


def _plan_course_card(course, accent_color):
    """Create a single course card for the plan display."""
    card_content = ft.Row([
        ft.Text(course.code, size=14, weight=ft.FontWeight.BOLD,
                color=_card_theme["text_primary"]),
        ft.Text(f"— {course.name}", size=13, color=_card_theme["text_secondary"],
                expand=True, max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS),
        ft.Container(
            content=ft.Text(f"{course.credits} cr", size=11,
                            weight=ft.FontWeight.W_600, color=accent_color),
            bgcolor=ft.Colors.with_opacity(0.12, accent_color),
            border_radius=6,
            padding=ft.padding.symmetric(4, 10),
        ),
    ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def on_hover(e):
        card.scale = 1.02 if e.data == "true" else 1.0
        card.update()

    card = ft.Container(
        content=ft.Container(
            content=card_content,
            padding=ft.padding.symmetric(12, 16),
            border_radius=ft.border_radius.only(top_right=10, bottom_right=10),
            bgcolor=_card_theme["bg"],
        ),
        bgcolor=accent_color,
        padding=ft.padding.only(left=4),
        border_radius=10,
        border=ft.border.all(1, ft.Colors.with_opacity(0.08, WHITE)),
        on_hover=on_hover,
        animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        scale=1.0,
    )
    return card


def _show_toast(page, message, icon=None, color=GREEN, duration=3000):
    """Show a floating toast notification."""
    row_controls = []
    if icon:
        row_controls.append(ft.Icon(icon, color=WHITE, size=16))
    row_controls.append(
        ft.Text(message, color=WHITE, size=12, weight=ft.FontWeight.W_500))

    snack = ft.SnackBar(
        content=ft.Row(row_controls, spacing=8),
        bgcolor=color,
        behavior=ft.SnackBarBehavior.FLOATING,
        shape=ft.RoundedRectangleBorder(radius=8),
        duration=duration,
        margin=ft.Margin(left=0, top=0, right=0, bottom=4),
        width=400,
    )
    page.show_dialog(snack)


# ─────────────────────────────────────────────────────────
#  Main Application
# ─────────────────────────────────────────────────────────

def main(page: ft.Page):
    # Debug: log unhandled errors
    import logging
    _log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'crash.log')
    logging.basicConfig(filename=_log_path, level=logging.ERROR, force=True)
    def _on_error(e):
        logging.error(f"Unhandled error: {e.data}")
        print(f"UNHANDLED ERROR: {e.data}", flush=True)
    page.on_error = _on_error

    page.title = "AdviseMe — RBSD | Internal Tool"
    page.bgcolor = BG
    page.window.width = 1600
    page.window.height = 1000
    page.window.min_width = 1200
    page.window.min_height = 800
    page.padding = 0
    page.theme = ft.Theme(color_scheme_seed=BLUE_DARK)
    page.theme_mode = ft.ThemeMode.DARK

    # ── State ──
    grid: list = [None]
    record: list = [None]
    plan: list = [None]
    last_advisor_picks: list = [set()]
    current_semester_idx: list = [-1]
    programs_dir = get_programs_dir()
    programs = list_available_programs(programs_dir)
    program_paths = {name: path for path, name in programs}
    program_names = [name for _, name in programs]
    faculty_data = load_faculty()
    private_view: list = [_load_config().get("private_view", False)]
    manual_mode: list = [private_view[0]]
    manual_color: list = ["green"]

    # ── Services ──
    file_picker = ft.FilePicker()
    clipboard = ft.Clipboard()

    # ──────────────────────────────────────────
    #  Sidebar widgets
    # ──────────────────────────────────────────

    eval_label = ft.Text("No file loaded", size=12, color=TEXT_MUTED)

    info_text = ft.Text("", size=12, color=TEXT_PRIMARY, font_family="Consolas",
                        selectable=True)

    advisor_dropdown = ft.Dropdown(
        label="Faculty Advisor",
        options=[],
        text_size=13, height=48,
        bgcolor=CARD_BG, color=TEXT_PRIMARY,
        border_color=BORDER, focused_border_color=BLUE_DARK,
        border_radius=8, content_padding=ft.padding.symmetric(8, 12),
        label_style=ft.TextStyle(size=11, color=TEXT_MUTED),
    )

    semester_dropdown = ft.Dropdown(
        label="Target Semester",
        options=[ft.dropdown.Option(s) for s in get_available_semesters()],
        text_size=13, height=48,
        bgcolor=CARD_BG, color=TEXT_PRIMARY,
        border_color=BORDER, focused_border_color=BLUE_DARK,
        border_radius=8, content_padding=ft.padding.symmetric(8, 12),
        label_style=ft.TextStyle(size=11, color=TEXT_MUTED),
    )

    program_dropdown = ft.Dropdown(
        options=[ft.dropdown.Option(n) for n in program_names],
        value=program_names[0] if program_names else None,
        text_size=13, height=46, width=280,
        bgcolor=CARD_BG, color=TEXT_PRIMARY,
        border_color=BORDER, focused_border_color=BLUE_DARK,
        border_radius=8, content_padding=ft.padding.symmetric(8, 12),
    )

    # Status bar
    status_text = ft.Text(
        "Ready — Select a program and upload an evaluation to begin.",
        size=12, color=TEXT_MUTED)

    # Loading bar
    loading_bar = ft.ProgressBar(
        visible=False, color=BLUE_DARK, bgcolor=BORDER,
        bar_height=3, width=280, border_radius=2,
    )

    # ──────────────────────────────────────────
    #  Content area refs
    # ──────────────────────────────────────────
    grid_content = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=8)
    plan_content = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=12)
    stats_content = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)

    # ──────────────────────────────────────────
    #  Tab management with AnimatedSwitcher
    # ──────────────────────────────────────────
    current_tab = ["grid"]
    tab_buttons = {}

    def _tab_hover(e):
        c = e.control
        if c.data != current_tab[0]:
            t = _get_theme_palette()
            c.bgcolor = t["navy_light"] if e.data == "true" else t["card_bg"]
            c.update()

    def make_tab_btn(tab_id, label, icon):
        is_active = (tab_id == current_tab[0])
        btn = ft.Container(
            content=ft.Row([
                ft.Icon(icon, size=16,
                        color=WHITE if is_active else TEXT_SECONDARY),
                ft.Text(label, size=13,
                        weight=ft.FontWeight.BOLD if is_active else None,
                        color=WHITE if is_active else TEXT_SECONDARY),
            ], spacing=6),
            bgcolor=BLUE_DARK if is_active else CARD_BG,
            padding=ft.padding.symmetric(10, 18),
            border_radius=8,
            on_click=lambda e, t=tab_id: _switch_tab(t),
            on_hover=_tab_hover,
            data=tab_id,
            ink=True,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )
        tab_buttons[tab_id] = btn
        return btn

    tab_bar = ft.Row([
        make_tab_btn("grid", "4-Year Grid", ft.Icons.GRID_VIEW),
        make_tab_btn("plan", "Semester Plan", ft.Icons.CALENDAR_MONTH),
        make_tab_btn("stats", "Dashboard", ft.Icons.DASHBOARD),
    ], spacing=4)

    # Tab views
    grid_bg_container = ft.Container(
        content=grid_content,
        bgcolor=GRID_BG, border_radius=12,
        border=ft.border.all(1, BORDER),
        padding=8,
    )
    grid_view = ft.Container(
        key="grid",
        content=grid_bg_container,
        expand=True,
    )
    plan_view = ft.Container(key="plan", content=plan_content, expand=True)
    stats_view = ft.Container(key="stats", content=stats_content, expand=True)

    tab_view_map = {
        "grid": grid_view,
        "plan": plan_view,
        "stats": stats_view,
    }

    tab_container = ft.Container(content=grid_view, expand=True)

    def _switch_tab(tab_id):
        current_tab[0] = tab_id
        t = _get_theme_palette()
        for tid, btn in tab_buttons.items():
            if tid == tab_id:
                btn.bgcolor = t["accent"]
                btn.content.controls[0].color = WHITE
                btn.content.controls[1].color = WHITE
                btn.content.controls[1].weight = ft.FontWeight.BOLD
            else:
                btn.bgcolor = t["card_bg"]
                btn.content.controls[0].color = t["text_secondary"]
                btn.content.controls[1].color = t["text_secondary"]
                btn.content.controls[1].weight = None
            btn.data = tid
        tab_container.content = tab_view_map[tab_id]
        page.update()

    # ──────────────────────────────────────────
    #  Core actions
    # ──────────────────────────────────────────

    def _update_advisor_dropdown():
        if not grid[0] or not grid[0].department:
            advisors = ["No advisors available"]
        else:
            advisors = faculty_data.get(grid[0].department, [])
            if not advisors:
                advisors = ["No advisors available"]
        advisor_dropdown.options = [ft.dropdown.Option(a) for a in advisors]
        advisor_dropdown.value = advisors[0]

    def _on_program_selected(e):
        name = program_dropdown.value
        if name and name in program_paths:
            try:
                grid[0] = load_program_grid(program_paths[name])
                # Re-apply evaluation if one is loaded
                if record[0]:
                    grid[0] = match_courses(record[0], grid[0])
                    current_semester_idx[0] = auto_detect_semester_index(
                        grid[0], record[0].total_credits_earned)
                    semester_dropdown.value = auto_detect_semester_label(
                        record[0].total_credits_earned)
                    _update_student_info()
                    _update_stats()
                # Clear stale plan from previous program
                plan[0] = None
                last_advisor_picks[0] = set()
                _display_plan()
                _show_toast(page, f"Loaded program: {name}",
                            ft.Icons.CHECK_CIRCLE, GREEN)
                status_text.value = f"Program: {name}"
                _display_grid()
                _update_advisor_dropdown()
                page.update()
            except Exception as ex:
                page.show_dialog(ft.AlertDialog(
                    title=ft.Text("Error"), content=ft.Text(str(ex)),
                    bgcolor=BG, shape=ft.RoundedRectangleBorder(radius=16)))

    program_dropdown.on_select = _on_program_selected

    def _update_student_info():
        if record[0]:
            r = record[0]
            transfers = get_transfer_courses(r)
            if grid[0]:
                te_credits = sum(
                    gc.credits for sem in grid[0].semesters
                    for gc in sem.courses
                    if gc.status == GridHighlight.TRANSFER)
            else:
                te_credits = sum(ec.credits for ec in transfers)
            lines = [
                f"Name:      {r.student_name}",
                f"ID:        {r.student_id}",
                f"GPA:       {r.gpa:.3f}",
                f"Credits:   {r.total_credits_earned} / {r.total_credits_required}",
                f"Program:   {r.program_name}",
                f"Courses:   {len(r.eval_courses)} parsed",
            ]
            if transfers:
                lines.append(f"Transfer:  {len(transfers)} courses ({te_credits} cr)")
            info_text.value = "\n".join(lines)
        else:
            info_text.value = ""

    async def _upload_eval(e):
        result = await file_picker.pick_files(
            dialog_title="Select Program Evaluation PDF",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["pdf"])
        if not result:
            return
        filepath = result[0].path
        try:
            loading_bar.visible = True
            loading_bar.value = None  # indeterminate
            status_text.value = "Parsing evaluation PDF..."
            page.update()

            record[0] = parse_evaluation_pdf(filepath)
            filename = os.path.basename(filepath)
            eval_label.value = f"  {filename}"
            eval_label.color = GREEN

            # Auto-select matching program from evaluation
            if record[0] and record[0].program_name:
                eval_prog = record[0].program_name.lower().strip()
                matched_name = None
                for pname in program_names:
                    if pname.lower().strip() == eval_prog:
                        matched_name = pname
                        break
                if not matched_name:
                    # Fuzzy: check if eval program name is contained in dropdown name or vice versa
                    for pname in program_names:
                        plow = pname.lower()
                        if eval_prog in plow or plow in eval_prog:
                            matched_name = pname
                            break
                if matched_name and matched_name != program_dropdown.value:
                    program_dropdown.value = matched_name
                    grid[0] = load_program_grid(program_paths[matched_name])
                    _update_advisor_dropdown()

            _update_student_info()

            if record[0] and grid[0]:
                name = program_dropdown.value
                grid[0] = load_program_grid(program_paths[name])
                grid[0] = match_courses(record[0], grid[0])
                current_semester_idx[0] = auto_detect_semester_index(
                    grid[0], record[0].total_credits_earned)
                semester_dropdown.value = auto_detect_semester_label(
                    record[0].total_credits_earned)
                _display_grid()
                _update_stats()

            loading_bar.visible = False
            if record[0]:
                _show_toast(page,
                    f"Loaded evaluation for {record[0].student_name} — "
                    f"{len(record[0].eval_courses)} courses parsed",
                    ft.Icons.CHECK_CIRCLE, GREEN)
                status_text.value = f"Student: {record[0].student_name}"
            else:
                _show_toast(page, "Could not parse evaluation PDF.",
                    ft.Icons.WARNING, ORANGE)
                status_text.value = "Ready"
            page.update()
        except Exception as ex:
            import traceback; traceback.print_exc()
            loading_bar.visible = False
            try:
                page.show_dialog(ft.AlertDialog(
                    title=ft.Text("Upload Error"),
                    content=ft.Text(
                        "Could not read this PDF. Please upload a program "
                        "evaluation PDF from the Registrar (Banner/DegreeWorks)."),
                    bgcolor=BG, shape=ft.RoundedRectangleBorder(radius=16)))
            except Exception:
                pass

    # ── Grid cell click (Human Mode) ──
    # Map course objects to their card containers for in-place updates
    _card_refs: dict = {}

    def _on_cell_click(course):
        if not manual_mode[0] or not grid[0]:
            return
        mapping = {
            "green":       (GridHighlight.GREEN, CourseStatus.COMPLETED),
            "transfer":    (GridHighlight.TRANSFER, CourseStatus.TRANSFER),
            "orange":      (GridHighlight.ORANGE, None),
            "light_red":   (GridHighlight.LIGHT_RED, None),
            "none":        (GridHighlight.NONE, CourseStatus.NOT_STARTED),
            "in_progress": (GridHighlight.NONE, CourseStatus.IN_PROGRESS),
        }
        highlight, eval_stat = mapping.get(manual_color[0],
                                           (GridHighlight.NONE, None))
        course.status = highlight
        course.eval_status = eval_stat

        # Update card in-place instead of rebuilding entire grid
        card = _card_refs.get(id(course))
        if card:
            new_bg = _cell_color(course)
            new_accent = _cell_accent(course)
            card.bgcolor = new_accent                # left accent strip
            card.content.bgcolor = new_bg            # main card bg
            card.update()

        _update_stats()
        status_text.value = (
            f"{course.code or course.name} → "
            f"{manual_color[0].replace('_', ' ').title()}")
        page.update()

    # ── Grid display ──
    def _display_grid():
        grid_content.controls.clear()
        _card_refs.clear()
        if not grid[0]:
            return

        t = _get_theme_palette()

        # Legend — modern circular dots in a glass card
        legend_items = [
            ("Completed", GREEN), ("Transfer", PURPLE),
            ("Next Sem.", ORANGE), ("Gap", RED),
            ("In Progress", BLUE_STATUS), ("Not Started", GRAY_LIGHT),
        ]
        legend_row = ft.Row([
            ft.Text("Legend", size=12, weight=ft.FontWeight.W_600,
                    color=t.get("text_muted", TEXT_MUTED)),
            ft.VerticalDivider(width=1, color=t["border"]),
        ] + [
            ft.Row([
                ft.Container(width=12, height=12, bgcolor=clr,
                             border_radius=6,
                             border=ft.border.all(1, t["border"])),
                ft.Text(txt, size=11, color=t.get("text_secondary", TEXT_SECONDARY)),
            ], spacing=8)
            for txt, clr in legend_items
        ], spacing=16, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        grid_content.controls.append(
            ft.Container(content=legend_row,
                         padding=ft.padding.symmetric(8, 16),
                         bgcolor=t["card_bg"],
                         border_radius=10,
                         border=ft.border.all(1, t["border"])))

        # Semesters
        prev_year = None

        for sem in grid[0].semesters:
            if sem.year != prev_year and prev_year is not None:
                grid_content.controls.append(
                    ft.Divider(height=1, color=t["border"]))
            prev_year = sem.year

            # Semester header — clean white bar
            sem_cr = sum(c.credits for c in sem.courses)
            header = ft.Container(
                content=ft.Row([
                    ft.Text(f"Year {sem.year}", size=13,
                            weight=ft.FontWeight.W_600, color="#4A5568"),
                    ft.Text("·", size=13, color="#A0AEC0"),
                    ft.Text(sem.term, size=13, weight=ft.FontWeight.W_600,
                            color="#4A5568"),
                    ft.Container(expand=True),
                    ft.Text(f"{sem_cr} credits", size=12,
                            weight=ft.FontWeight.W_500, color="#718096"),
                ], spacing=6),
                bgcolor="#FFFFFF",
                padding=ft.padding.symmetric(8, 14),
                border_radius=8,
                border=ft.border.all(1, "#E2E8F0"),
                margin=ft.Margin(left=12, top=8, right=12, bottom=0),
            )
            grid_content.controls.append(header)

            # Course cards row
            cards = []
            for course in sem.courses:
                cell_bg = _cell_color(course)
                accent_clr = _cell_accent(course)

                # Card content
                card_items = []
                if not course.is_elective_slot and not course.is_ge_category:
                    card_items.append(ft.Text(
                        course.code, size=13, weight=ft.FontWeight.W_600,
                        color=GRID_TEXT))
                card_items.append(ft.Text(
                    course.name, size=11, color="#4A5568",
                    max_lines=2, overflow=ft.TextOverflow.ELLIPSIS))
                meta = f"{course.credits} cr"
                if course.matched_eval_course and course.matched_eval_course.grade:
                    meta += f"  ·  {course.matched_eval_course.grade}"
                card_items.append(ft.Text(meta, size=9, color="#718096"))

                def make_hover(container):
                    def on_hover(e):
                        container.scale = 1.03 if e.data == "true" else 1.0
                        container.update()
                    return on_hover

                card = ft.Container(
                    content=ft.Container(
                        content=ft.Column(card_items, spacing=3),
                        bgcolor=cell_bg,
                        padding=ft.padding.all(14),
                        border_radius=ft.border_radius.only(
                            top_right=10, bottom_right=10),
                    ),
                    bgcolor=accent_clr,
                    border_radius=10,
                    padding=ft.padding.only(left=5),
                    expand=True,
                    on_click=lambda e, c=course: _on_cell_click(c),
                    ink=True,
                    animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
                    scale=1.0,
                )
                card.on_hover = make_hover(card)
                _card_refs[id(course)] = card
                cards.append(card)

            cards_row = ft.Row(cards, spacing=8,
                               alignment=ft.MainAxisAlignment.START)
            grid_content.controls.append(
                ft.Container(content=cards_row,
                             padding=ft.padding.only(left=12, right=12)))

    # ── Plan display ──
    def _build_plan_email() -> str:
        if not plan[0]:
            return ""
        p = plan[0]
        p.compute_total()
        semester = p.semester_label or "Upcoming Semester"
        student_name = (record[0].student_name if record[0] else "Student")
        # Use first name for greeting
        first_name = student_name.split()[0] if student_name else "Student"

        # Combine all courses into one list
        all_courses = list(p.courses or [])
        all_courses.extend(p.makeup_courses or [])

        course_lines = ""
        for c in all_courses:
            course_lines += f"{c.code} — {c.name} ({c.credits} cr)\n\n"

        notes_section = ""
        if p.notes:
            notes_section = "\nAdditional Notes:\n"
            for n in p.notes:
                notes_section += f"- {n}\n"
            notes_section += "\n"

        email = (
            f"Subject: Academic Advising Plan - {semester}\n\n"
            f"Dear {first_name},\n\n"
            f"I hope you're doing well.\n\n"
            f"I have reviewed your academic progress and prepared your advising "
            f"plan for the upcoming {semester} term. Based on your degree "
            f"requirements, here is the schedule we have outlined for you:\n\n"
            f"Planned Course Schedule\n"
            f"{course_lines}"
            f"Total Credits: {p.total_credits}\n\n"
            f"Please review these selections in your student portal. If these "
            f"courses align with your goals and graduation timeline, you can "
            f"proceed with registration once your enrollment window opens.\n\n"
            f"Important Reminders:\n\n"
            f"Ensure you have met any necessary prerequisites for the courses "
            f"listed above.\n\n"
            f"If you are planning on an Internship/Practicum, please ensure all "
            f"departmental paperwork is submitted by the deadline.\n\n"
            f"If you wish to make any changes to this plan, please reach out to "
            f"me so we can ensure you stay on track for graduation.\n\n"
            f"Feel free to schedule a brief follow-up meeting if you have any "
            f"specific questions about these electives or your long-term grid.\n"
            f"{notes_section}"
        )
        return email

    def _display_plan():
        plan_content.controls.clear()
        tp = _card_theme["text_primary"]
        ts = _card_theme["text_secondary"]
        tm = _card_theme["text_muted"]
        acc = _card_theme["accent"]

        if not plan[0]:
            plan_content.controls.append(
                _glass_card(ft.Column([
                    ft.Icon(ft.Icons.CALENDAR_MONTH, size=48, color=tm),
                    ft.Text("No plan generated yet.", size=16,
                            color=ts, weight=ft.FontWeight.W_500),
                    ft.Text("Upload an evaluation and click 'Generate Plan'.",
                            size=13, color=tm),
                ], spacing=10,
                   horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                   expand=True))
            return

        p = plan[0]
        p.compute_total()

        # Copy email button
        async def _copy_plan(e):
            try:
                await clipboard.set(_build_plan_email())
                _show_toast(page, "Advising email copied to clipboard!",
                            ft.Icons.EMAIL, GREEN)
            except Exception:
                _show_toast(page, "Could not copy to clipboard.",
                            ft.Icons.ERROR_OUTLINE, ORANGE)

        copy_btn = ft.Button(
            "Copy Email", icon=ft.Icons.EMAIL,
            bgcolor=_card_theme.get("navy_light", NAVY_LIGHT), color=WHITE,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=_copy_plan)

        plan_content.controls.append(
            ft.Row([ft.Container(expand=True), copy_btn], spacing=8))

        # Header card
        plan_content.controls.append(
            _glass_card(ft.Row([
                ft.Column([
                    ft.Text("Advising Plan", size=18,
                            weight=ft.FontWeight.BOLD, color=tp),
                    ft.Text(p.semester_label, size=14, color=ts),
                ], spacing=4),
                ft.Container(expand=True),
                ft.Container(
                    content=ft.Text(f"{p.total_credits} cr", size=18,
                                    weight=ft.FontWeight.BOLD, color=acc),
                    bgcolor=ft.Colors.with_opacity(0.12, acc),
                    border_radius=10, padding=ft.padding.symmetric(8, 16)),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                elevation="high"))

        # Student info (if not private)
        if not private_view[0] and record[0]:
            plan_content.controls.append(
                _glass_card(ft.Row([
                    ft.Icon(ft.Icons.PERSON, size=18, color=acc),
                    ft.Text(record[0].student_name, size=14,
                            weight=ft.FontWeight.W_500, color=tp),
                    ft.Text(f"·  {record[0].student_id}", size=12,
                            color=ts),
                ], spacing=10), padding=12, elevation="low"))

        # Scheduled courses
        if p.courses:
            plan_content.controls.append(
                ft.Text("Scheduled Courses", size=15,
                        weight=ft.FontWeight.W_600, color=tp))
            for c in p.courses:
                plan_content.controls.append(_plan_course_card(c, ORANGE))
            sub = sum(c.credits for c in p.courses)
            plan_content.controls.append(
                ft.Container(
                    content=ft.Text(f"Subtotal: {sub} credits", size=12,
                                    weight=ft.FontWeight.W_600,
                                    color=ts),
                    alignment=ft.Alignment(1, 0),
                    padding=ft.padding.only(right=8, bottom=8)))

        # Makeup courses
        if p.makeup_courses:
            plan_content.controls.append(
                ft.Row([
                    ft.Icon(ft.Icons.REPLAY, size=16, color=RED),
                    ft.Text("Makeup Courses (Out of Sequence)", size=15,
                            weight=ft.FontWeight.W_600, color=tp),
                ], spacing=8))
            for c in p.makeup_courses:
                plan_content.controls.append(_plan_course_card(c, RED))
            sub = sum(c.credits for c in p.makeup_courses)
            plan_content.controls.append(
                ft.Container(
                    content=ft.Text(f"Subtotal: {sub} credits", size=12,
                                    weight=ft.FontWeight.W_600,
                                    color=ts),
                    alignment=ft.Alignment(1, 0),
                    padding=ft.padding.only(right=8, bottom=8)))

        # Notes
        if p.notes:
            plan_content.controls.append(
                _glass_card(ft.Row([
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=18, color=ORANGE),
                    ft.Column([ft.Text(n, size=13, color=ts)
                               for n in p.notes], spacing=4, expand=True),
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
                    padding=14, elevation="low"))

    # ── Stats display ──
    def _update_stats():
        stats_content.controls.clear()
        if not grid[0]:
            return

        tp = _card_theme["text_primary"]
        ts = _card_theme["text_secondary"]
        tm = _card_theme["text_muted"]

        stats = get_completion_stats(grid[0])

        # Metric cards with hover + icons
        metrics = [
            (str(stats['completed']), "Completed", GREEN, GREEN_BG, ft.Icons.CHECK_CIRCLE),
            (str(stats['transfer']), "Transfer", PURPLE, PURPLE_BG, ft.Icons.SWAP_HORIZ),
            (str(stats['in_progress']), "In Progress", BLUE_STATUS, BLUE_BG, ft.Icons.SCHEDULE),
            (str(stats['gaps']), "Gaps", RED, RED_BG, ft.Icons.WARNING),
            (str(stats['remaining']), "Remaining", ORANGE, ORANGE_BG, ft.Icons.PENDING),
        ]

        def _metric_hover(e):
            c = e.control
            c.scale = 1.03 if e.data == "true" else 1.0
            c.update()

        metric_cards = []
        for val, label, accent, bg_c, icon in metrics:
            card = ft.Container(
                content=_glass_card(
                    ft.Column([
                        ft.Container(height=4, bgcolor=accent, border_radius=2),
                        ft.Row([
                            ft.Icon(icon, size=20, color=accent),
                            ft.Text(val, size=36, weight=ft.FontWeight.BOLD,
                                    color=accent),
                        ], spacing=8, alignment=ft.MainAxisAlignment.CENTER),
                        ft.Text(label, size=12, color=ts),
                    ], spacing=6,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    expand=True,
                ),
                expand=True,
                on_hover=_metric_hover,
                animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
                scale=1.0,
            )
            metric_cards.append(card)

        stats_content.controls.append(ft.Row(metric_cards, spacing=8))

        # Row 2: Progress + Student + Breakdown
        pct = stats['percent_complete']

        ring_size = 160
        ring = ft.Stack([
            ft.Container(
                width=ring_size, height=ring_size,
                border_radius=ring_size // 2,
                border=ft.border.all(14, _card_theme["bg"]),
            ),
            ft.Container(
                width=ring_size, height=ring_size,
                content=ft.Column([
                    ft.Text(f"{pct:.0f}%", size=28,
                            weight=ft.FontWeight.BOLD, color=tp),
                    ft.Text("complete", size=11, color=tm),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                   alignment=ft.MainAxisAlignment.CENTER, spacing=0),
            ),
        ], width=ring_size, height=ring_size)

        ring_card = _glass_card(ft.Column([
            ft.Text("Completion", size=14, weight=ft.FontWeight.BOLD,
                    color=tp),
            ft.Container(content=ring, alignment=ft.Alignment(0, 0),
                         padding=ft.padding.symmetric(12, 0)),
            ft.Text(f"{stats['completed']+stats['transfer']} of {stats['total']} courses",
                    size=13, color=ts),
        ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=220)

        # Student card
        if private_view[0]:
            stu_items = [
                ft.Text("Private Mode", size=16, weight=ft.FontWeight.BOLD,
                        color=ts),
                ft.Icon(ft.Icons.LOCK, size=40, color=GRAY_LIGHT),
                ft.Text("Student identity is\nhidden in this mode.",
                        size=13, color=tm),
                ft.Text(f"Program: {grid[0].program_name}",
                        size=13, color=ts),
            ]
        else:
            name = (record[0].student_name if record[0] else "") or "—"
            gpa_str = f"{record[0].gpa:.3f}" if record[0] else "—"
            credits_str = (f"{record[0].total_credits_earned} / "
                           f"{record[0].total_credits_required}") if record[0] else "—"
            initials = "".join(w[0].upper() for w in name.split()[:2]) \
                       if name != "—" else "?"

            avatar = ft.CircleAvatar(
                content=ft.Text(initials, size=18, weight=ft.FontWeight.BOLD),
                bgcolor=BLUE, radius=26)

            stu_items = [
                ft.Text("Student", size=16, weight=ft.FontWeight.BOLD,
                        color=tp),
                ft.Row([avatar, ft.Text(name, size=16,
                        weight=ft.FontWeight.BOLD, color=tp)],
                       spacing=14),
                ft.Row([ft.Text("Program", size=13, color=tm, width=80),
                        ft.Text(grid[0].program_name, size=13,
                                weight=ft.FontWeight.BOLD, color=tp)]),
                ft.Row([ft.Text("GPA", size=13, color=tm, width=80),
                        ft.Text(gpa_str, size=13, weight=ft.FontWeight.BOLD,
                                color=tp)]),
                ft.Row([ft.Text("Credits", size=13, color=tm, width=80),
                        ft.Text(credits_str, size=13, weight=ft.FontWeight.BOLD,
                                color=tp)]),
            ]
        stu_card = _glass_card(ft.Column(stu_items, spacing=10), expand=True)

        # Breakdown card
        total = stats['total'] or 1
        bar_items = [ft.Text("Breakdown", size=14, weight=ft.FontWeight.BOLD,
                             color=tp)]
        for lbl, cnt, clr in [
            ("Completed", stats['completed'], GREEN),
            ("Transfer", stats['transfer'], PURPLE),
            ("In Progress", stats['in_progress'], BLUE_STATUS),
            ("Gaps", stats['gaps'], RED),
            ("Remaining", stats['remaining'], ORANGE),
        ]:
            pct_w = max(0.02, cnt / total)
            bar_items.append(ft.Column([
                ft.Text(f"{lbl}  ({cnt})", size=12, color=tp),
                ft.Container(
                    content=ft.Container(
                        bgcolor=clr, border_radius=4,
                        width=200 * pct_w, height=8),
                    bgcolor=_card_theme["bg"], border_radius=4, height=8, width=200),
            ], spacing=2))
        breakdown_card = _glass_card(ft.Column(bar_items, spacing=6))

        stats_content.controls.append(
            ft.Row([ring_card, stu_card, breakdown_card], spacing=8,
                   vertical_alignment=ft.CrossAxisAlignment.START))

    # ── Generate Plan ──
    def _clear_plan_highlights():
        if not grid[0]:
            return
        for sem in grid[0].semesters:
            for course in sem.courses:
                if course.status in (GridHighlight.ORANGE, GridHighlight.LIGHT_RED):
                    if course.eval_status != CourseStatus.IN_PROGRESS:
                        course.status = GridHighlight.NONE

    def _generate_plan(e):
        if not grid[0]:
            _show_toast(page, "Please select a program first.",
                        ft.Icons.WARNING, ORANGE)
            return
        try:
            sem_label = semester_dropdown.value or ""
            if not sem_label:
                credits = (record[0].total_credits_earned if record[0] else 0)
                sem_label = auto_detect_semester_label(credits)

            if current_semester_idx[0] >= 0:
                sem_idx = current_semester_idx[0]
            else:
                credits = (record[0].total_credits_earned if record[0] else 0)
                sem_idx = detect_current_semester(grid[0], credits)

            human_picks = set()
            for sem in grid[0].semesters:
                for c in sem.courses:
                    if c.status in (GridHighlight.ORANGE, GridHighlight.LIGHT_RED):
                        human_picks.add(c.code)

            _clear_plan_highlights()
            _show_advisor_pick_dialog(sem_idx, sem_label, human_picks)
        except Exception as ex:
            page.show_dialog(ft.AlertDialog(
                title=ft.Text("Error"),
                content=ft.Text(f"Failed to generate plan:\n{ex}"),
                bgcolor=BG, shape=ft.RoundedRectangleBorder(radius=16)))
            import traceback; traceback.print_exc()

    def _show_advisor_pick_dialog(semester_idx, semester_label, human_picks=None):
        pre_checked = (human_picks or set()) | last_advisor_picks[0]
        check_vars = {}
        key_map = {}

        credit_text = ft.Text("Selected: 0 credits", size=16,
                               weight=ft.FontWeight.BOLD, color=GREEN)
        credit_container = ft.Container(
            content=credit_text,
            bgcolor=ft.Colors.with_opacity(0.08, GREEN),
            border_radius=10,
            padding=ft.padding.symmetric(8, 16),
        )

        def update_count():
            total_cr = sum(cr for k, (cb, cr) in check_vars.items() if cb.value)
            color = GREEN if total_cr <= 18 else RED
            warn = " ⚠ Over 18 credits!" if total_cr > 18 else ""
            credit_text.value = f"Selected: {total_cr} credits{warn}"
            credit_text.color = color
            credit_container.bgcolor = ft.Colors.with_opacity(0.08, color)

        def on_check_change(e):
            update_count()
            page.update()

        def add_checkbox(parent, text, key, code, credits, checked, accent):
            is_checked = checked or (code in pre_checked)
            cb = ft.Checkbox(
                label=text, value=is_checked,
                active_color=accent, check_color=WHITE,
                label_style=ft.TextStyle(size=13, color=TEXT_PRIMARY),
                on_change=on_check_change)
            check_vars[key] = (cb, credits)
            key_map[key] = code
            parent.append(cb)

        def _category_header(text, dot_color):
            return ft.Row([
                ft.Container(width=10, height=10, bgcolor=dot_color,
                             border_radius=5),
                ft.Text(text, size=14, weight=ft.FontWeight.BOLD,
                        color=TEXT_PRIMARY),
            ], spacing=8)

        items = []

        scheduled = get_next_semester_courses(grid[0], semester_idx)
        if scheduled:
            items.append(_category_header("Scheduled Courses (This Semester)", NAVY_LIGHT))
            for c in scheduled:
                add_checkbox(items,
                    f"{c.code} — {c.name} ({c.credits} cr)",
                    f"s_{c.code}", c.code, c.credits, True, NAVY_LIGHT)

        gaps = find_gap_courses(grid[0], semester_idx)
        if gaps:
            items.append(_category_header("Makeup Courses (Out of Sequence)", RED))
            for sl, c in gaps:
                add_checkbox(items,
                    f"{c.code} — {c.name} ({c.credits} cr) [{sl}]",
                    f"g_{c.code}_{sl}", c.code, c.credits, True, RED)

        shown = {c.code for c in scheduled} | {c.code for _, c in gaps}
        other = [(sl, c) for sl, c in get_all_remaining_grid_courses(grid[0])
                 if c.code not in shown]
        human_only = [(sl, c) for sl, c in other if c.code in pre_checked]
        non_human = [(sl, c) for sl, c in other if c.code not in pre_checked]

        if human_only:
            items.append(_category_header("Your Selections", ORANGE))
            for sl, c in human_only:
                add_checkbox(items,
                    f"{c.code} — {c.name} ({c.credits} cr) [{sl}]",
                    f"h_{c.code}_{sl}", c.code, c.credits, True, ORANGE)

        if non_human:
            items.append(_category_header("All Other Remaining Courses", TEXT_MUTED))
            for sl, c in non_human:
                add_checkbox(items,
                    f"{c.code} — {c.name} ({c.credits} cr) [{sl}]",
                    f"o_{c.code}_{sl}", c.code, c.credits, False, GRAY)

        update_count()

        def confirm(e):
            sel_codes = set(key_map[k] for k, (cb, _) in check_vars.items()
                           if cb.value)
            last_advisor_picks[0] = set(sel_codes)
            page.pop_dialog()

            _clear_plan_highlights()
            new_plan = SemesterPlan(semester_label=semester_label)
            for sem in grid[0].semesters:
                for course in sem.courses:
                    if course.code in sel_codes:
                        if course.eval_status != CourseStatus.IN_PROGRESS:
                            course.status = GridHighlight.ORANGE
                        new_plan.courses.append(course)

            total_cr = sum(c.credits for c in new_plan.courses)
            if total_cr > 18:
                new_plan.notes.append(
                    f"⚠ Total selected credits ({total_cr}) exceeds 18.")
            new_plan.compute_total()
            plan[0] = new_plan

            _display_grid()
            _update_stats()
            _display_plan()
            _switch_tab("plan")
            _show_toast(page, f"Plan generated: {plan[0].total_credits} credits",
                        ft.Icons.AUTO_AWESOME, GREEN)
            page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Select courses for {semester_label}",
                          size=18, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            content=ft.Container(
                content=ft.Column([
                    credit_container,
                    ft.Divider(color=BORDER),
                    ft.Column(items, scroll=ft.ScrollMode.AUTO, height=520,
                              spacing=2),
                ], spacing=10),
                width=850, height=700,
                padding=24,
            ),
            actions=[
                ft.TextButton("Cancel",
                              style=ft.ButtonStyle(color=TEXT_SECONDARY),
                              on_click=lambda e: page.pop_dialog()),
                ft.Button("Confirm Selection",
                                   icon=ft.Icons.CHECK,
                                   bgcolor=NAVY, color=WHITE,
                                   style=ft.ButtonStyle(
                                       shape=ft.RoundedRectangleBorder(radius=10),
                                       padding=ft.padding.symmetric(14, 28)),
                                   on_click=confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=BG,
            shape=ft.RoundedRectangleBorder(radius=20),
        )
        page.show_dialog(dlg)

    # ── Reset ──
    def _reset_app(e=None):
        record[0] = None
        plan[0] = None
        last_advisor_picks[0] = set()
        current_semester_idx[0] = -1
        name = program_dropdown.value
        if name and name in program_paths:
            try:
                grid[0] = load_program_grid(program_paths[name])
            except Exception:
                grid[0] = None
        else:
            grid[0] = None
        eval_label.value = "No file loaded"
        eval_label.color = TEXT_MUTED
        advisor_dropdown.value = None
        semester_dropdown.value = None
        if not private_view[0]:
            manual_mode[0] = False
        _update_student_info()
        if grid[0]:
            _display_grid()
        _display_plan()
        _update_stats()
        _show_toast(page, "Session reset.", ft.Icons.REFRESH, BLUE_DARK)
        status_text.value = "Ready"
        page.update()

    def _confirm_reset(e):
        def _do_reset(e):
            page.pop_dialog()
            _reset_app()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=48, color=ORANGE),
                ft.Text("Reset Session", size=18, weight=ft.FontWeight.BOLD,
                        color=TEXT_PRIMARY),
            ], spacing=12),
            content=ft.Text(
                "Are you sure you want to reset?\n\n"
                "This will clear the loaded student evaluation, all grid\n"
                "highlights, the semester plan, and any manual edits.\n\n"
                "This action cannot be undone.",
                size=13, color=TEXT_SECONDARY),
            actions=[
                ft.TextButton("Cancel",
                              style=ft.ButtonStyle(color=TEXT_SECONDARY),
                              on_click=lambda e: page.pop_dialog()),
                ft.Button("Reset",
                                   icon=ft.Icons.RESTART_ALT,
                                   bgcolor="#C53030", color=WHITE,
                                   style=ft.ButtonStyle(
                                       shape=ft.RoundedRectangleBorder(radius=10)),
                                   on_click=_do_reset),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=BG,
            shape=ft.RoundedRectangleBorder(radius=20),
        )
        page.show_dialog(dlg)

    # ── Private Mode ──
    pv_btn_ref = [None]
    _apply_theme_ref = [None]   # set after containers are built

    def _toggle_private_view(e):
        # Turning OFF private view — no confirmation needed
        if private_view[0]:
            private_view[0] = False
            _save_config({"private_view": False})
            _rebuild_sidebar()
            _update_stats()
            if _apply_theme_ref[0]:
                _apply_theme_ref[0]()
            _show_toast(page, "Private Mode OFF.",
                        ft.Icons.LOCK_OPEN, BLUE_DARK)
            status_text.value = "Ready"
            page.update()
            return

        # Turning ON — ask for confirmation first
        def _confirm_private(ev):
            dlg.open = False
            page.update()
            private_view[0] = True
            _save_config({"private_view": True})
            manual_mode[0] = True
            if record[0]:
                record[0] = None
                plan[0] = None
                last_advisor_picks[0] = set()
                name = program_dropdown.value
                if name and name in program_paths:
                    try:
                        grid[0] = load_program_grid(program_paths[name])
                    except Exception:
                        pass
                eval_label.value = "No file loaded"
                eval_label.color = TEXT_MUTED
                _update_student_info()
                if grid[0]:
                    _display_grid()
                _display_plan()
            _rebuild_sidebar()
            _update_stats()
            if _apply_theme_ref[0]:
                _apply_theme_ref[0]()
            _show_toast(page, "Private Mode ON — Human Mode only, student identity hidden.",
                        ft.Icons.LOCK, THEME_PRIVATE["accent"])
            status_text.value = "Private Mode"
            page.update()

        def _cancel_private(ev):
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Enable Private Mode?", color=WHITE,
                          weight=ft.FontWeight.BOLD),
            content=ft.Text(
                "This will hide student identity and clear uploaded data.",
                color=TEXT_SECONDARY),
            actions=[
                ft.Button("Yes", on_click=_confirm_private,
                          color=WHITE, bgcolor=GREEN),
                ft.Button("No", on_click=_cancel_private,
                          color=WHITE, bgcolor=GRAY_LIGHT),
            ],
            bgcolor=CARD_BG, shape=ft.RoundedRectangleBorder(radius=16),
        )
        page.show_dialog(dlg)

    # ── Human Mode toggle ──
    human_mode_switch = ft.Switch(
        label="Enable Human Mode", value=manual_mode[0],
        active_color=GREEN, inactive_thumb_color=GRAY_LIGHT,
        label_text_style=ft.TextStyle(size=13, color=TEXT_PRIMARY),
    )
    pv_human_label = ft.Text("Human Mode  ·  Always On", size=13,
                              weight=ft.FontWeight.BOLD, color=GREEN)

    # Color picker
    color_options = [
        ("green", "Completed", GRID_GREEN, GREEN),
        ("transfer", "Transfer", GRID_TRANSFER, PURPLE),
        ("orange", "Next Sem.", GRID_ORANGE, ORANGE),
        ("light_red", "Gap", GRID_RED, RED),
        ("none", "Not Started", GRID_WHITE, GRAY_LIGHT),
        ("in_progress", "In Progress", GRID_BLUE, BLUE_STATUS),
    ]
    color_radio = ft.RadioGroup(
        value="green",
        content=ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.Radio(value=val, active_color=dot_clr,
                             label=lbl,
                             label_style=ft.TextStyle(size=12, color=TEXT_PRIMARY)),
                    ft.Container(width=32, height=20, bgcolor=cell_clr,
                                 border_radius=6,
                                 border=ft.border.all(1, BORDER)),
                ], spacing=4),
                height=36,
                padding=ft.padding.symmetric(4, 8),
            )
            for val, lbl, cell_clr, dot_clr in color_options
        ], spacing=4),
    )

    def _on_color_change(e):
        manual_color[0] = color_radio.value
    color_radio.on_change = _on_color_change

    def _on_manual_toggle(e):
        if not human_mode_switch.value and private_view[0]:
            human_mode_switch.value = True
            _show_toast(page, "Human Mode cannot be disabled in Private Mode.",
                        ft.Icons.LOCK, ORANGE)
            page.update()
            return
        manual_mode[0] = human_mode_switch.value
        _rebuild_sidebar()
        if grid[0]:
            _display_grid()
        status_text.value = ("Human Mode ON" if manual_mode[0] else "Ready")
        page.update()
    human_mode_switch.on_change = _on_manual_toggle

    # ── Sidebar sections ──
    # Track section headers for theme updates
    _hdr_upload = ft.Text("UPLOAD EVALUATION", size=11, weight=ft.FontWeight.BOLD, color=TEXT_MUTED)
    _hdr_info = ft.Text("STUDENT INFO", size=11, weight=ft.FontWeight.BOLD, color=TEXT_MUTED)
    _hdr_advisor = ft.Text("FACULTY ADVISOR", size=11, weight=ft.FontWeight.BOLD, color=TEXT_MUTED)
    _hdr_semester = ft.Text("SEMESTER PLAN", size=11, weight=ft.FontWeight.BOLD, color=TEXT_MUTED)
    _hdr_manual = ft.Text("Click grid cells to set course status", size=11, color=TEXT_SECONDARY)
    _section_headers = [_hdr_upload, _hdr_info, _hdr_advisor, _hdr_semester, _hdr_manual]

    upload_btn = ft.Button("Upload PDF", icon=ft.Icons.UPLOAD_FILE,
                       bgcolor=NAVY_LIGHT, color=WHITE,
                       style=ft.ButtonStyle(
                           shape=ft.RoundedRectangleBorder(radius=8)),
                       on_click=_upload_eval, width=280)

    upload_section = ft.Column([
        _hdr_upload,
        ft.Divider(height=1, color=BORDER),
        upload_btn,
        loading_bar,
        eval_label,
        _hdr_info,
        ft.Divider(height=1, color=BORDER),
        _glass_card(info_text, padding=10, border_radius=8, elevation="low"),
    ], spacing=8)

    advisor_section = ft.Column([
        _hdr_advisor,
        ft.Divider(height=1, color=BORDER),
        advisor_dropdown,
    ], spacing=8)

    semester_section = ft.Column([
        _hdr_semester,
        ft.Divider(height=1, color=BORDER),
        semester_dropdown,
    ], spacing=8)

    generate_btn = ft.Button(
        "Generate Plan", icon=ft.Icons.AUTO_AWESOME,
        bgcolor=BLUE_DARK, color=WHITE, width=280,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
        on_click=_generate_plan)

    manual_options = ft.Column([
        _hdr_manual,
        color_radio,
    ], spacing=6, visible=manual_mode[0])

    # ── Export handlers ──
    async def _export_grid_pdf(e):
        if not grid[0]:
            _show_toast(page, "No program grid loaded.", ft.Icons.WARNING, ORANGE)
            return
        student_name = record[0].student_name if record[0] else "Manual"
        student_id = record[0].student_id if record[0] else ""
        filepath = await file_picker.save_file(
            dialog_title="Save Highlighted Grid PDF",
            file_name=f"grid_{student_name.replace(' ', '_')}.pdf",
            allowed_extensions=["pdf"])
        if not filepath:
            return
        if not filepath.endswith(".pdf"):
            filepath += ".pdf"
        try:
            advisor = advisor_dropdown.value or ""
            if advisor in ("No advisors available",):
                advisor = ""
            generate_grid_pdf(grid[0], student_name, student_id, filepath,
                              plan[0], advisor_name=advisor)
            _show_toast(page, f"Grid PDF saved!", ft.Icons.CHECK_CIRCLE, GREEN)
            status_text.value = f"Exported: {os.path.basename(filepath)}"
            page.update()
        except Exception as ex:
            page.show_dialog(ft.AlertDialog(
                title=ft.Text("Export Error"),
                content=ft.Text(f"Failed to export grid PDF:\n{ex}"),
                bgcolor=BG, shape=ft.RoundedRectangleBorder(radius=16)))

    async def _export_plan_pdf(e):
        if not plan[0]:
            _show_toast(page, "No plan generated yet.", ft.Icons.WARNING, ORANGE)
            return
        adv_val = advisor_dropdown.value
        if not adv_val or adv_val in ("No advisors available",):
            _show_toast(page, "Please select an advisor before exporting the plan.",
                        ft.Icons.WARNING, ORANGE)
            return
        student_name = record[0].student_name if record[0] else "Manual"
        student_id = record[0].student_id if record[0] else ""
        prog_name = grid[0].program_name if grid[0] else ""
        filepath = await file_picker.save_file(
            dialog_title="Save Semester Plan PDF",
            file_name=f"plan_{student_name.replace(' ', '_')}.pdf",
            allowed_extensions=["pdf"])
        if not filepath:
            return
        if not filepath.endswith(".pdf"):
            filepath += ".pdf"
        try:
            advisor = advisor_dropdown.value or ""
            if advisor in ("No advisors available",):
                advisor = ""
            generate_semester_plan_pdf(plan[0], student_name, student_id,
                                       prog_name, filepath,
                                       advisor_name=advisor)
            _show_toast(page, f"Plan PDF saved!", ft.Icons.CHECK_CIRCLE, GREEN)
            status_text.value = f"Exported: {os.path.basename(filepath)}"
            page.update()
        except Exception as ex:
            page.show_dialog(ft.AlertDialog(
                title=ft.Text("Export Error"),
                content=ft.Text(f"Failed to export plan PDF:\n{ex}"),
                bgcolor=BG, shape=ft.RoundedRectangleBorder(radius=16)))

    # Export buttons
    export_grid_btn = ft.Button("Export Grid PDF", icon=ft.Icons.PICTURE_AS_PDF,
                       bgcolor=NAVY, color=WHITE, width=280,
                       tooltip="Export 4-year program grid with course status",
                       style=ft.ButtonStyle(
                           shape=ft.RoundedRectangleBorder(radius=8)),
                       on_click=_export_grid_pdf)
    export_plan_btn = ft.OutlinedButton("Export Plan PDF", icon=ft.Icons.DESCRIPTION,
                       width=280,
                       tooltip="Export semester advising plan with advisor signature",
                       style=ft.ButtonStyle(
                           shape=ft.RoundedRectangleBorder(radius=8),
                           side=ft.BorderSide(1, BORDER),
                           color=TEXT_PRIMARY),
                       on_click=_export_plan_pdf)
    export_section = ft.Column([
        ft.Divider(height=1, color=BORDER),
        export_grid_btn,
        export_plan_btn,
    ], spacing=6)

    # ── Theme system ──
    _theme_names = list(BUILT_IN_THEMES.keys())
    _saved_theme = _load_config().get("theme", "Ocean")
    if _saved_theme not in BUILT_IN_THEMES:
        _saved_theme = "Midnight"
    current_theme = [_saved_theme]

    def _get_theme_palette():
        if private_view[0]:
            return THEME_PRIVATE
        return BUILT_IN_THEMES.get(current_theme[0], THEME_MODERN)

    theme_dropdown = ft.Dropdown(
        label="Theme",
        options=[ft.dropdown.Option(t) for t in _theme_names],
        value=current_theme[0],
        text_size=13, height=48, width=260,
        bgcolor=CARD_BG, color=TEXT_PRIMARY,
        border_color=BORDER, focused_border_color=BLUE_DARK,
        border_radius=8, content_padding=ft.padding.symmetric(8, 12),
        label_style=ft.TextStyle(size=11, color=TEXT_MUTED),
    )

    def _on_theme_selected(e):
        name = e.control.value
        current_theme[0] = name
        _save_config({"theme": name})
        page.theme_mode = (ft.ThemeMode.LIGHT
                           if _get_theme_palette().get("mode") == "light"
                           else ft.ThemeMode.DARK)
        _apply_theme_ref[0]()
        page.update()

    theme_dropdown.on_select = _on_theme_selected

    # Sidebar container
    sidebar_items = ft.Column(spacing=16, expand=True,
                               scroll=ft.ScrollMode.AUTO)

    def _rebuild_sidebar():
        sidebar_items.controls.clear()
        if not private_view[0]:
            sidebar_items.controls.append(upload_section)
            sidebar_items.controls.append(advisor_section)
            sidebar_items.controls.append(semester_section)
        sidebar_items.controls.append(generate_btn)

        hm = ft.Column(spacing=6)
        hm.controls.append(ft.Text("HUMAN MODE", size=11,
                                    weight=ft.FontWeight.BOLD, color=TEXT_MUTED))
        hm.controls.append(ft.Divider(height=1, color=BORDER))
        if private_view[0]:
            hm.controls.append(pv_human_label)
        else:
            hm.controls.append(human_mode_switch)
        sidebar_items.controls.append(hm)

        manual_options.visible = manual_mode[0]
        sidebar_items.controls.append(manual_options)

    _rebuild_sidebar()

    sidebar = ft.Container(
        content=ft.Column([
            sidebar_items,
            export_section,
        ], spacing=0, expand=True),
        width=340,
        bgcolor=SIDEBAR_BG,
        padding=16,
        border=ft.border.only(right=ft.BorderSide(1, BORDER)),
    )

    # ──────────────────────────────────────────
    #  Content area
    # ──────────────────────────────────────────
    content_area = ft.Column([
        tab_bar,
        tab_container,
    ], spacing=8, expand=True)

    # ──────────────────────────────────────────
    #  Header
    # ──────────────────────────────────────────
    logo_path = _asset_path('icon_128.png')
    logo_exists = os.path.exists(logo_path)

    logo_widget = ft.Container(
        content=ft.Image(src=logo_path, width=34, height=34,
                         fit=ft.BoxFit.CONTAIN),
        width=38, height=38,
        border_radius=10,
        bgcolor=WHITE,
        padding=2,
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=6,
                             color="rgba(0,0,0,0.25)", offset=ft.Offset(0, 2)),
    ) if logo_exists else ft.Icon(ft.Icons.SCHOOL, size=36, color=BLUE_DARK)

    header_left = ft.Row([
        logo_widget,
        ft.Column([
            ft.Text("RBSD | Internal Tool", size=10,
                    weight=ft.FontWeight.BOLD, color=BLUE_DARK),
            ft.Text("AdviseMe", size=20, weight=ft.FontWeight.BOLD,
                    color=WHITE),
        ], spacing=0),
    ], spacing=12)

    def _btn_hover(e):
        c = e.control
        c.scale = 1.05 if e.data == "true" else 1.0
        c.update()

    pv_btn = ft.Container(
        content=ft.Button(
            "🔒  Private Mode",
            bgcolor=NAVY_LIGHT if private_view[0] else CARD_BG,
            color=WHITE if private_view[0] else TEXT_MUTED,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=_toggle_private_view),
        on_hover=_btn_hover,
        animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        scale=1.0,
    )
    pv_btn_ref[0] = pv_btn

    reset_btn = ft.Container(
        content=ft.Button(
            "⟳  RESET", bgcolor="#C53030", color=WHITE,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=_confirm_reset),
        on_hover=_btn_hover,
        animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        scale=1.0,
    )

    header = ft.Container(
        content=ft.Row([
            header_left,
            ft.VerticalDivider(width=1, color=BORDER),
            ft.Text("Program", size=11, color="#94A3B8"),
            program_dropdown,
            ft.Container(expand=True),
            pv_btn,
            reset_btn,
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1, 0),
            end=ft.Alignment(1, 0),
            colors=[NAVY, NAVY_LIGHT, NAVY],
        ),
        padding=ft.padding.symmetric(10, 16),
        border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
    )

    # ──────────────────────────────────────────
    #  Status bar
    # ──────────────────────────────────────────
    # Compact theme selector for status bar
    theme_label_text = ft.Text(current_theme[0], size=11, color=TEXT_PRIMARY)

    def _on_compact_theme_click(e):
        name = e.control.data
        current_theme[0] = name
        theme_dropdown.value = name
        theme_label_text.value = name
        _save_config({"theme": name})
        page.theme_mode = (ft.ThemeMode.LIGHT
                           if _get_theme_palette().get("mode") == "light"
                           else ft.ThemeMode.DARK)
        _apply_theme_ref[0]()
        page.update()

    theme_compact = ft.PopupMenuButton(
        content=ft.Row([
            ft.Text("Theme:", size=11, color=TEXT_MUTED),
            theme_label_text,
            ft.Icon(ft.Icons.ARROW_DROP_UP, size=14, color=TEXT_MUTED),
        ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        items=[
            ft.PopupMenuItem(
                content=ft.Text(name, size=12),
                on_click=_on_compact_theme_click,
                data=name,
            )
            for name in _theme_names
        ],
        menu_position=ft.PopupMenuPosition.OVER,
    )

    status_bar = ft.Container(
        content=ft.Row([
            ft.Container(content=status_text, padding=ft.padding.only(left=8)),
            ft.Container(expand=True),
            theme_compact,
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=CARD_BG,
        padding=ft.padding.symmetric(10, 16),
        border=ft.border.only(top=ft.BorderSide(1, BORDER)),
    )

    # ──────────────────────────────────────────
    #  Main layout
    # ──────────────────────────────────────────
    body = ft.Row([
        sidebar,
        ft.Container(content=content_area, expand=True,
                     padding=ft.padding.all(16)),
    ], spacing=0, expand=True)

    # ── Theme switcher for Private Mode ──
    def _apply_theme():
        t = _get_theme_palette()
        tp = t["text_primary"]
        ts = t["text_secondary"]
        tm = t.get("text_muted", TEXT_MUTED)
        brd = t["border"]
        cbg = t["card_bg"]
        acc = t["accent"]

        # Update module-level card theme for _glass_card / _plan_course_card
        _card_theme["bg"] = cbg
        _card_theme["accent"] = acc
        _card_theme["border_tint"] = "#000000" if t.get("mode") == "light" else WHITE
        _card_theme["mode"] = t.get("mode", "dark")
        _card_theme["text_primary"] = tp
        _card_theme["text_secondary"] = ts
        _card_theme["text_muted"] = tm
        _card_theme["navy_light"] = t["navy_light"]

        # Page
        page.bgcolor = t["bg"]
        page.theme_mode = (ft.ThemeMode.LIGHT if t.get("mode") == "light"
                           else ft.ThemeMode.DARK)
        # Header
        header.gradient = ft.LinearGradient(
            begin=ft.Alignment(-1, 0),
            end=ft.Alignment(1, 0),
            colors=[t["navy"], t["navy_light"], t["navy"]],
        )
        header.border = ft.border.only(bottom=ft.BorderSide(1, brd))
        # Sidebar
        sidebar.bgcolor = t["sidebar_bg"]
        sidebar.border = ft.border.only(right=ft.BorderSide(1, brd))
        # Status bar
        status_bar.bgcolor = cbg
        status_bar.border = ft.border.only(top=ft.BorderSide(1, brd))
        # Private Mode button
        btn = pv_btn_ref[0].content
        if private_view[0]:
            btn.bgcolor = t["navy_light"]
            btn.color = acc
        else:
            btn.bgcolor = cbg
            btn.color = tm
        # Update dropdowns/widgets text colors for theme
        # Sidebar dropdowns — theme-aware
        for dd in (advisor_dropdown, semester_dropdown, theme_dropdown):
            dd.bgcolor = cbg
            dd.color = tp
            dd.border_color = brd
            dd.focused_border_color = acc
            dd.label_style = ft.TextStyle(size=11, color=tm)
        # Header dropdown — lighter bg with white text
        program_dropdown.bgcolor = t["navy_light"]
        program_dropdown.color = "#FFFFFF"
        program_dropdown.border_color = t["navy"]
        program_dropdown.focused_border_color = "#FFFFFF"
        program_dropdown.menu_style = ft.MenuStyle(bgcolor=t["navy_light"])
        # Rebuild options with white text for dark menu
        program_dropdown.options = [
            ft.dropdown.Option(
                key=n, content=ft.Text(n, size=13, color="#FFFFFF"))
            for n in program_names
        ]
        # Status text & theme menu
        status_text.color = tm
        theme_label_text.color = tp
        # Hide theme selector in Private Mode
        theme_compact.visible = not private_view[0]
        # Export buttons
        export_grid_btn.bgcolor = t["navy"]
        export_plan_btn.style = ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
            side=ft.BorderSide(1, brd),
            color=tp)
        # Upload button
        upload_btn.bgcolor = t["navy_light"]
        generate_btn.bgcolor = acc
        # Section headers
        for h in _section_headers:
            h.color = tm
        _hdr_manual.color = ts
        # Switch label
        human_mode_switch.label_text_style = ft.TextStyle(size=13, color=tp)
        # Radio labels
        for radio_row in color_radio.content.controls:
            radio = radio_row.content.controls[0]
            radio.label_style = ft.TextStyle(size=12, color=tp)
            radio_row.content.controls[1].border = ft.border.all(1, brd)
        # Info text
        info_text.color = tp
        # Grid container
        grid_bg_container.border = ft.border.all(1, brd)
        # Tab buttons
        _switch_tab(current_tab[0])
        # Rebuild grid and plan with new colors
        if grid[0]:
            _display_grid()
        _display_plan()

    _apply_theme_ref[0] = _apply_theme

    # Apply theme on startup
    _apply_theme()

    page.services.append(file_picker)
    page.services.append(clipboard)
    page.add(
        ft.Column([
            header,
            body,
            status_bar,
        ], spacing=0, expand=True)
    )

    # ── Initialize ──
    if program_names:
        _on_program_selected(None)
    _display_plan()
    _update_stats()
    if private_view[0]:
        _rebuild_sidebar()
    page.update()


# ─────────────────────────────────────────────────────────
#  Welcome screen wrapper
# ─────────────────────────────────────────────────────────

def app(page: ft.Page):
    """Entry point — shows welcome screen, then transitions to main app."""
    page.title = "AdviseMe — RBSD | Internal Tool"
    # Try .ico first (Windows), fall back to .png
    _ico = _asset_path('AdviseMe.ico')
    if os.path.exists(_ico):
        page.window.icon = _ico
    else:
        page.window.icon = _asset_path('icon_128.png')
    page.bgcolor = BG
    page.window.width = 1440
    page.window.height = 804
    page.window.resizable = False
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK

    def _launch_main(e):
        try:
            page.controls.clear()
            page.window.width = 1600
            page.window.height = 1000
            page.window.min_width = 1200
            page.window.min_height = 800
            page.window.resizable = True
            main(page)
        except Exception as ex:
            import traceback
            traceback.print_exc()
            _crash = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'crash.log')
            with open(_crash, 'w', encoding='utf-8') as _f:
                traceback.print_exc(file=_f)
            try:
                page.add(ft.Text(f"Error: {ex}", color="red", size=16))
                page.update()
            except Exception:
                pass

    # Logo
    logo_path = _asset_path('icon_128.png')
    logo_exists = os.path.exists(logo_path)

    # Welcome background
    bg_path = _asset_path('welcome_bg.png')
    if os.path.exists(bg_path):
        welcome_bg = ft.Container(
            content=ft.Image(src=bg_path, fit=ft.BoxFit.COVER,
                             width=2000, height=2000),
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )
    else:
        welcome_bg = ft.Container(
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=["#0A1628", "#122A4A", "#1A3A5C", "#0F2844"],
            ),
            expand=True,
        )

    # Animated elements
    welcome_logo = ft.Container(
        content=ft.Container(
            content=ft.Image(src=logo_path, width=64, height=64,
                             fit=ft.BoxFit.CONTAIN),
            width=72, height=72,
            border_radius=16,
            bgcolor=WHITE,
            padding=4,
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=12,
                                 color="rgba(0,0,0,0.3)", offset=ft.Offset(0, 4)),
        ) if logo_exists else ft.Container(),
        opacity=0,
        animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
        scale=ft.Scale(0.8),
        animate_scale=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
    )

    title_widget = ft.Container(
        content=ft.Text("AdviseMe", size=42, weight=ft.FontWeight.BOLD,
                        color=TEXT_PRIMARY),
        opacity=0,
        animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
        offset=ft.Offset(0, 0.15),
        animate_offset=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
    )

    subtitle_widget = ft.Container(
        content=ft.Column([
            ft.Text("RBSD | Internal Tool", size=12,
                    weight=ft.FontWeight.BOLD, color=BLUE_DARK),
            ft.Container(height=12),
            ft.Text("Course tracking and advising\nmade simple for faculty.",
                    size=16, color=TEXT_SECONDARY,
                    text_align=ft.TextAlign.CENTER),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
        opacity=0,
        animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
        offset=ft.Offset(0, 0.15),
        animate_offset=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
    )

    btn_container = ft.Container(
        content=ft.Button(
            "Let's Get Started  →",
            bgcolor=BLUE_DARK, color=WHITE,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                text_style=ft.TextStyle(size=16, weight=ft.FontWeight.BOLD)),
            height=52, width=260,
            on_click=_launch_main),
        opacity=0,
        animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
        scale=ft.Scale(0.95),
        animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        offset=ft.Offset(0, 0.15),
        animate_offset=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
    )

    def _btn_hover(e):
        btn_container.scale = ft.Scale(
            1.05 if e.data == "true" else 1.0)
        btn_container.update()
    btn_container.on_hover = _btn_hover

    version_widget = ft.Container(
        content=ft.Text(f"v{__version__}", size=11, color=TEXT_MUTED),
        opacity=0,
        animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
    )

    update_banner = ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.SYSTEM_UPDATE, size=14, color=BLUE_DARK),
            ft.Text("", size=12, color=BLUE_DARK, weight=ft.FontWeight.W_500),
        ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
        opacity=0,
        animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
        padding=ft.padding.symmetric(6, 12),
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.1, BLUE_DARK),
    )

    left_panel = ft.Container(
        content=ft.Column([
            ft.Container(expand=True),
            welcome_logo,
            ft.Container(height=16),
            title_widget,
            ft.Container(height=8),
            subtitle_widget,
            ft.Container(height=30),
            btn_container,
            ft.Container(expand=True),
            update_banner,
            version_widget,
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
        width=600,
        padding=40,
    )

    page.add(
        ft.Row([left_panel, welcome_bg], spacing=0, expand=True)
    )
    page.update()

    # Staggered fade-in
    async def _animate():
        import asyncio
        elements = [welcome_logo, title_widget, subtitle_widget,
                     btn_container, version_widget]
        for ctrl in elements:
            await asyncio.sleep(0.15)
            ctrl.opacity = 1
            if hasattr(ctrl, 'scale') and ctrl.scale is not None:
                ctrl.scale = ft.Scale(1.0)
            if hasattr(ctrl, 'offset') and ctrl.offset is not None:
                ctrl.offset = ft.Offset(0, 0)
            page.update()

        # Check for updates in background
        import concurrent.futures
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            latest, url = await loop.run_in_executor(pool, _check_for_update)
        if latest:
            update_banner.content.controls[1].value = (
                f"Update available: v{latest} — download from GitHub Releases")
            update_banner.opacity = 1
            page.update()

    page.run_task(_animate)


if __name__ == "__main__":
    ft.app(target=app)
