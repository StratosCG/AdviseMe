"""
AdviseMe — Flet-based GUI.

Dark glassmorphic dashboard with card-based layout,
matching the existing brand colors from the Tkinter version.
"""
import os
import sys
import math
import json

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
from version import __version__

# ── Brand Colors (dark dashboard theme — kept from Tkinter version) ──
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

# Grid cell colors — light for readability
GRID_GREEN    = "#C6F6D5"
GRID_TRANSFER = "#E9D8FD"
GRID_ORANGE   = "#F9C96A"
GRID_RED      = "#FCA5A5"
GRID_BLUE     = "#BEE3F8"
GRID_WHITE    = "#FFFFFF"
GRID_TEXT     = "#1A202C"
GRID_BG       = "#E8EDF2"


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


def _glass_card(content, padding=16, border_radius=12, expand=False,
                width=None, height=None):
    """Create a glassmorphic card container."""
    return ft.Container(
        content=content,
        padding=padding,
        border_radius=border_radius,
        bgcolor=CARD_BG,
        border=ft.border.all(1, BORDER),
        expand=expand,
        width=width,
        height=height,
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=20,
            color=ft.Colors.with_opacity(0.15, "#000000"),
            offset=ft.Offset(0, 4),
        ),
    )


# ─────────────────────────────────────────────────────────
#  Main Application
# ─────────────────────────────────────────────────────────

def main(page: ft.Page):
    page.title = "AdviseMe — RBSD | Internal Tool"
    page.bgcolor = BG
    page.window.width = 1600
    page.window.height = 1000
    page.window.min_width = 1200
    page.window.min_height = 800
    page.padding = 0
    page.fonts = {"Segoe UI": "Segoe UI"}
    page.theme = ft.Theme(
        color_scheme_seed=BLUE_DARK,
    )
    page.theme_mode = ft.ThemeMode.DARK

    # ── State ──
    grid: list = [None]  # ProgramGrid (mutable ref)
    record: list = [None]  # StudentRecord
    plan: list = [None]  # SemesterPlan
    last_advisor_picks: list = [set()]
    current_semester_idx: list = [-1]
    programs_dir = get_programs_dir()
    programs = list_available_programs(programs_dir)
    program_paths = {name: path for path, name in programs}
    program_names = [name for _, name in programs]
    faculty_data = load_faculty()
    private_view: list = [_load_config().get("private_view", False)]
    manual_mode: list = [private_view[0]]  # ON in private view
    manual_color: list = ["green"]

    # ── File picker ──
    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)

    # ──────────────────────────────────────────
    #  Sidebar widgets (built first, referenced later)
    # ──────────────────────────────────────────

    eval_label = ft.Text("No file loaded", size=11, color=TEXT_MUTED)

    info_text = ft.Text("", size=10, color=TEXT_PRIMARY, font_family="Consolas",
                        selectable=True)

    advisor_dropdown = ft.Dropdown(
        label="Faculty Advisor",
        options=[],
        text_size=12, height=44,
        bgcolor=CARD_BG, color=TEXT_PRIMARY,
        border_color=BORDER, focused_border_color=BLUE_DARK,
        border_radius=8, content_padding=ft.padding.symmetric(8, 12),
        label_style=ft.TextStyle(size=10, color=TEXT_MUTED),
    )

    semester_dropdown = ft.Dropdown(
        label="Target Semester",
        options=[ft.dropdown.Option(s) for s in get_available_semesters()],
        text_size=12, height=44,
        bgcolor=CARD_BG, color=TEXT_PRIMARY,
        border_color=BORDER, focused_border_color=BLUE_DARK,
        border_radius=8, content_padding=ft.padding.symmetric(8, 12),
        label_style=ft.TextStyle(size=10, color=TEXT_MUTED),
    )

    program_dropdown = ft.Dropdown(
        options=[ft.dropdown.Option(n) for n in program_names],
        value=program_names[0] if program_names else None,
        text_size=12, height=42, width=280,
        bgcolor=CARD_BG, color=TEXT_PRIMARY,
        border_color=BORDER, focused_border_color=BLUE_DARK,
        border_radius=8, content_padding=ft.padding.symmetric(8, 12),
    )

    # Status bar
    status_text = ft.Text(
        "Ready — Select a program and upload an evaluation to begin.",
        size=11, color=TEXT_MUTED)

    # ──────────────────────────────────────────
    #  Content area refs
    # ──────────────────────────────────────────
    grid_content = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=6)
    plan_content = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=8)
    stats_content = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=10)

    # ──────────────────────────────────────────
    #  Tab management
    # ──────────────────────────────────────────
    current_tab = ["grid"]
    tab_buttons = {}
    tab_views = {}

    def _switch_tab(tab_id):
        current_tab[0] = tab_id
        for tid, view in tab_views.items():
            view.visible = (tid == tab_id)
        for tid, btn in tab_buttons.items():
            if tid == tab_id:
                btn.bgcolor = BLUE_DARK
                btn.content.color = WHITE
            else:
                btn.bgcolor = CARD_BG
                btn.content.color = TEXT_SECONDARY
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
                status_text.value = f"Loaded program: {name}"
                _display_grid()
                _update_advisor_dropdown()
                page.update()
            except Exception as ex:
                page.open(ft.AlertDialog(title=ft.Text("Error"),
                                          content=ft.Text(str(ex))))

    program_dropdown.on_change = _on_program_selected

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

    def _on_file_picked(e: ft.FilePickerResultEvent):
        if not e.files:
            return
        filepath = e.files[0].path
        try:
            status_text.value = "Parsing evaluation PDF..."
            page.update()
            record[0] = parse_evaluation_pdf(filepath)
            filename = os.path.basename(filepath)
            eval_label.value = f"  {filename}"
            eval_label.color = GREEN
            _update_student_info()

            if grid[0]:
                name = program_dropdown.value
                grid[0] = load_program_grid(program_paths[name])
                grid[0] = match_courses(record[0], grid[0])
                current_semester_idx[0] = auto_detect_semester_index(
                    grid[0], record[0].total_credits_earned)
                semester_dropdown.value = auto_detect_semester_label(
                    record[0].total_credits_earned)
                _display_grid()
                _update_stats()

            status_text.value = (
                f"Loaded evaluation for {record[0].student_name} — "
                f"{len(record[0].eval_courses)} courses parsed")
            page.update()
        except Exception as ex:
            page.open(ft.AlertDialog(
                title=ft.Text("Error"),
                content=ft.Text(f"Failed to parse evaluation:\n{ex}")))
            import traceback; traceback.print_exc()

    file_picker.on_result = _on_file_picked

    def _upload_eval(e):
        file_picker.pick_files(
            dialog_title="Select Program Evaluation PDF",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["pdf"])

    # ── Grid cell click (Human Mode) ──
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
        _display_grid()
        _update_stats()
        status_text.value = (
            f"Set {course.code or course.name} → "
            f"{manual_color[0].replace('_', ' ').title()}")
        page.update()

    # ── Grid display ──
    def _display_grid():
        grid_content.controls.clear()
        if not grid[0]:
            return

        # Legend
        legend_items = [
            ("Completed", GREEN), ("Transfer", PURPLE),
            ("Next Sem.", ORANGE), ("Gap", RED),
            ("In Progress", BLUE_STATUS), ("Not Started", GRAY_LIGHT),
        ]
        legend_row = ft.Row(spacing=16, wrap=True)
        for txt, clr in legend_items:
            legend_row.controls.append(ft.Row([
                ft.Container(width=10, height=10, bgcolor=clr,
                             border_radius=2),
                ft.Text(txt, size=10, color=TEXT_MUTED),
            ], spacing=4))
        grid_content.controls.append(
            ft.Container(content=legend_row, padding=ft.padding.only(
                left=12, right=12, top=8, bottom=4)))
        grid_content.controls.append(
            ft.Divider(height=1, color="#CBD5E0"))

        # Semesters
        year_accents = {1: NAVY_LIGHT, 2: BLUE_DARK, 3: NAVY_LIGHT, 4: BLUE_DARK}
        prev_year = None

        for sem in grid[0].semesters:
            accent = year_accents.get(sem.year, NAVY_LIGHT)

            if sem.year != prev_year and prev_year is not None:
                grid_content.controls.append(
                    ft.Divider(height=1, color="#CBD5E0"))
            prev_year = sem.year

            # Semester header
            sem_cr = sum(c.credits for c in sem.courses)
            header = ft.Container(
                content=ft.Row([
                    ft.Text(f"Year {sem.year}", size=12, weight=ft.FontWeight.BOLD,
                            color=WHITE),
                    ft.Text("·", size=12, color=BLUE),
                    ft.Text(sem.term, size=12, weight=ft.FontWeight.BOLD,
                            color=WHITE),
                    ft.Container(expand=True),
                    ft.Text(f"{sem_cr} credits", size=10, color=BLUE),
                ], spacing=6),
                bgcolor=accent,
                padding=ft.padding.symmetric(8, 12),
                border_radius=6,
                margin=ft.margin.only(left=12, right=12, top=6),
            )
            grid_content.controls.append(header)

            # Course cards row
            cards = []
            for course in sem.courses:
                cell_bg = _cell_color(course)
                accent_clr = _cell_accent(course)
                cursor = "pointer" if manual_mode[0] else None

                # Card content
                card_items = []
                if not course.is_elective_slot and not course.is_ge_category:
                    card_items.append(ft.Text(
                        course.code, size=11, weight=ft.FontWeight.BOLD,
                        color=GRID_TEXT))
                card_items.append(ft.Text(
                    course.name, size=9, color="#4A5568",
                    max_lines=2, overflow=ft.TextOverflow.ELLIPSIS))
                meta = f"{course.credits} cr"
                if course.matched_eval_course and course.matched_eval_course.grade:
                    meta += f"  ·  {course.matched_eval_course.grade}"
                card_items.append(ft.Text(meta, size=8, color="#718096"))

                card = ft.Container(
                    content=ft.Container(
                        content=ft.Column(card_items, spacing=2),
                        bgcolor=cell_bg,
                        padding=ft.padding.all(10),
                        border_radius=ft.border_radius.only(
                            top_right=8, bottom_right=8),
                    ),
                    bgcolor=accent_clr,
                    border_radius=8,
                    padding=ft.padding.only(left=4),
                    expand=True,
                    on_click=lambda e, c=course: _on_cell_click(c),
                    ink=manual_mode[0],
                )
                cards.append(card)

            cards_row = ft.Row(cards, spacing=6,
                               alignment=ft.MainAxisAlignment.START)
            grid_content.controls.append(
                ft.Container(content=cards_row,
                             padding=ft.padding.only(left=12, right=12)))

    # ── Plan display ──
    def _build_plan_text() -> str:
        if not plan[0]:
            return ""
        lines = []
        if not private_view[0]:
            name = record[0].student_name if record[0] else ""
            sid = record[0].student_id if record[0] else ""
            if name:
                lines.append(f"Student: {name}")
                if sid:
                    lines.append(f"ID: {sid}")
                lines.append("")
        lines.append(f"Advising Plan — {plan[0].semester_label}")
        lines.append("─" * 48)
        lines.append("")
        if plan[0].courses:
            lines.append("Scheduled Courses:")
            for c in plan[0].courses:
                lines.append(f"  • {c.code} — {c.name} ({c.credits} cr)")
            sub = sum(c.credits for c in plan[0].courses)
            lines.append(f"  Subtotal: {sub} credits")
            lines.append("")
        if plan[0].makeup_courses:
            lines.append("Makeup Courses (Out of Sequence):")
            for c in plan[0].makeup_courses:
                lines.append(f"  • {c.code} — {c.name} ({c.credits} cr)")
            sub = sum(c.credits for c in plan[0].makeup_courses)
            lines.append(f"  Subtotal: {sub} credits")
            lines.append("")
        plan[0].compute_total()
        lines.append("─" * 48)
        lines.append(f"Total Credits: {plan[0].total_credits}")
        lines.append("─" * 48)
        if plan[0].notes:
            lines.append("")
            lines.append("Notes:")
            for n in plan[0].notes:
                lines.append(f"  - {n}")
        return "\n".join(lines)

    def _display_plan():
        plan_content.controls.clear()
        if not plan[0]:
            plan_content.controls.append(
                _glass_card(ft.Column([
                    ft.Text("No plan generated yet.", size=14,
                            color=TEXT_SECONDARY),
                    ft.Text("Upload an evaluation and click 'Generate Plan'.",
                            size=12, color=TEXT_MUTED),
                ], spacing=8), expand=True))
            return

        plan_text_display = ft.Text(
            _build_plan_text(), size=12, color=TEXT_PRIMARY,
            font_family="Consolas", selectable=True)

        def _copy_plan(e):
            page.set_clipboard(_build_plan_text())
            status_text.value = "Plan copied to clipboard!"
            copy_btn.text = "Copied!"
            page.update()
            import threading
            def _reset():
                import time; time.sleep(1.5)
                copy_btn.text = "Copy to Clipboard"
                page.update()
            threading.Thread(target=_reset, daemon=True).start()

        copy_btn = ft.ElevatedButton(
            "Copy to Clipboard", icon=ft.Icons.COPY,
            bgcolor=NAVY, color=WHITE,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=_copy_plan)

        plan_content.controls.append(
            ft.Row([ft.Container(expand=True), copy_btn], spacing=8))
        plan_content.controls.append(
            _glass_card(plan_text_display, expand=True))

    # ── Stats display ──
    def _update_stats():
        stats_content.controls.clear()
        if not grid[0]:
            return

        stats = get_completion_stats(grid[0])

        # Row 1: Metric cards
        metrics = [
            (str(stats['completed']), "Completed", GREEN, GREEN_BG),
            (str(stats['transfer']), "Transfer", PURPLE, PURPLE_BG),
            (str(stats['in_progress']), "In Progress", BLUE_STATUS, BLUE_BG),
            (str(stats['gaps']), "Gaps", RED, RED_BG),
            (str(stats['remaining']), "Remaining", ORANGE, ORANGE_BG),
        ]
        metric_cards = []
        for val, label, accent, bg_c in metrics:
            metric_cards.append(_glass_card(
                ft.Column([
                    ft.Container(height=3, bgcolor=accent,
                                 border_radius=2),
                    ft.Text(val, size=28, weight=ft.FontWeight.BOLD,
                            color=accent),
                    ft.Text(label, size=10, color=TEXT_SECONDARY),
                ], spacing=6),
                expand=True,
            ))
        stats_content.controls.append(
            ft.Row(metric_cards, spacing=8))

        # Row 2: Progress + Student + Breakdown
        pct = stats['percent_complete']

        # Progress ring (using a stack with arc)
        ring_size = 140
        ring = ft.Stack([
            ft.Container(
                width=ring_size, height=ring_size,
                border_radius=ring_size // 2,
                border=ft.border.all(12, BORDER),
            ),
            ft.Container(
                width=ring_size, height=ring_size,
                content=ft.Column([
                    ft.Text(f"{pct:.0f}%", size=24,
                            weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                    ft.Text("complete", size=10, color=TEXT_MUTED),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                   alignment=ft.MainAxisAlignment.CENTER,
                   spacing=0),
            ),
        ], width=ring_size, height=ring_size)

        ring_card = _glass_card(ft.Column([
            ft.Text("Completion", size=14, weight=ft.FontWeight.BOLD,
                    color=TEXT_PRIMARY),
            ft.Container(content=ring, alignment=ft.alignment.center,
                         padding=ft.padding.symmetric(12, 0)),
            ft.Text(f"{stats['completed']+stats['transfer']} of {stats['total']} courses",
                    size=11, color=TEXT_SECONDARY),
        ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=200)

        # Student card
        if private_view[0]:
            stu_items = [
                ft.Text("Private View", size=14, weight=ft.FontWeight.BOLD,
                        color=TEXT_SECONDARY),
                ft.Icon(ft.Icons.LOCK, size=36, color=GRAY_LIGHT),
                ft.Text("Student identity is\nhidden in this mode.",
                        size=11, color=TEXT_MUTED),
                ft.Text(f"Program: {grid[0].program_name}",
                        size=11, color=TEXT_SECONDARY),
            ]
        else:
            name = (record[0].student_name if record[0] else "") or "—"
            gpa_str = f"{record[0].gpa:.3f}" if record[0] else "—"
            credits_str = (f"{record[0].total_credits_earned} / "
                           f"{record[0].total_credits_required}") if record[0] else "—"
            initials = "".join(w[0].upper() for w in name.split()[:2]) \
                       if name != "—" else "?"

            avatar = ft.CircleAvatar(
                content=ft.Text(initials, size=16, weight=ft.FontWeight.BOLD),
                bgcolor=BLUE, radius=22)

            stu_items = [
                ft.Text("Student", size=14, weight=ft.FontWeight.BOLD,
                        color=TEXT_PRIMARY),
                ft.Row([avatar, ft.Text(name, size=14,
                        weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY)],
                       spacing=12),
                ft.Row([ft.Text("Program", size=11, color=TEXT_MUTED, width=80),
                        ft.Text(grid[0].program_name, size=11,
                                weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY)]),
                ft.Row([ft.Text("GPA", size=11, color=TEXT_MUTED, width=80),
                        ft.Text(gpa_str, size=11, weight=ft.FontWeight.BOLD,
                                color=TEXT_PRIMARY)]),
                ft.Row([ft.Text("Credits", size=11, color=TEXT_MUTED, width=80),
                        ft.Text(credits_str, size=11, weight=ft.FontWeight.BOLD,
                                color=TEXT_PRIMARY)]),
            ]
        stu_card = _glass_card(ft.Column(stu_items, spacing=8), expand=True)

        # Breakdown card
        total = stats['total'] or 1
        bar_items = [ft.Text("Breakdown", size=14, weight=ft.FontWeight.BOLD,
                             color=TEXT_PRIMARY)]
        for lbl, cnt, clr in [
            ("Completed", stats['completed'], GREEN),
            ("Transfer", stats['transfer'], PURPLE),
            ("In Progress", stats['in_progress'], BLUE_STATUS),
            ("Gaps", stats['gaps'], RED),
            ("Remaining", stats['remaining'], ORANGE),
        ]:
            pct_w = max(0.02, cnt / total)
            bar_items.append(ft.Column([
                ft.Text(f"{lbl}  ({cnt})", size=11, color=TEXT_PRIMARY),
                ft.Container(
                    content=ft.Container(
                        bgcolor=clr, border_radius=4,
                        width=180 * pct_w, height=8),
                    bgcolor=BORDER, border_radius=4, height=8, width=180),
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
            page.open(ft.SnackBar(ft.Text("Please select a program first."),
                                   bgcolor=ORANGE))
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

            # Snapshot picks before clearing
            human_picks = set()
            for sem in grid[0].semesters:
                for c in sem.courses:
                    if c.status in (GridHighlight.ORANGE, GridHighlight.LIGHT_RED):
                        human_picks.add(c.code)

            _clear_plan_highlights()
            _show_advisor_pick_dialog(sem_idx, sem_label, human_picks)
        except Exception as ex:
            page.open(ft.AlertDialog(
                title=ft.Text("Error"),
                content=ft.Text(f"Failed to generate plan:\n{ex}")))
            import traceback; traceback.print_exc()

    def _show_advisor_pick_dialog(semester_idx, semester_label, human_picks=None):
        pre_checked = (human_picks or set()) | last_advisor_picks[0]
        check_vars = {}
        key_map = {}

        credit_text = ft.Text("Selected: 0 credits", size=13,
                               weight=ft.FontWeight.BOLD, color=GREEN)

        def update_count():
            total_cr = sum(cr for k, (cb, cr) in check_vars.items() if cb.value)
            color = GREEN if total_cr <= 18 else RED
            warn = " ⚠ Over 18 credits!" if total_cr > 18 else ""
            credit_text.value = f"Selected: {total_cr} credits{warn}"
            credit_text.color = color

        def on_check_change(e):
            update_count()
            page.update()

        def add_checkbox(parent, text, key, code, credits, checked, accent):
            is_checked = checked or (code in pre_checked)
            cb = ft.Checkbox(
                label=text, value=is_checked,
                active_color=accent, check_color=WHITE,
                label_style=ft.TextStyle(size=12, color=TEXT_PRIMARY),
                on_change=on_check_change)
            check_vars[key] = (cb, credits)
            key_map[key] = code
            parent.append(cb)

        items = []

        # Scheduled
        scheduled = get_next_semester_courses(grid[0], semester_idx)
        if scheduled:
            items.append(ft.Text("Scheduled Courses (This Semester)", size=12,
                                 weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY))
            for c in scheduled:
                add_checkbox(items,
                    f"{c.code} — {c.name} ({c.credits} cr)",
                    f"s_{c.code}", c.code, c.credits, True, NAVY_LIGHT)

        # Gaps
        gaps = find_gap_courses(grid[0], semester_idx)
        if gaps:
            items.append(ft.Text("Makeup Courses (Out of Sequence)", size=12,
                                 weight=ft.FontWeight.BOLD, color=RED))
            for sl, c in gaps:
                add_checkbox(items,
                    f"{c.code} — {c.name} ({c.credits} cr) [{sl}]",
                    f"g_{c.code}_{sl}", c.code, c.credits, True, RED)

        # Other remaining
        shown = {c.code for c in scheduled} | {c.code for _, c in gaps}
        other = [(sl, c) for sl, c in get_all_remaining_grid_courses(grid[0])
                 if c.code not in shown]
        human_only = [(sl, c) for sl, c in other if c.code in pre_checked]
        non_human = [(sl, c) for sl, c in other if c.code not in pre_checked]

        if human_only:
            items.append(ft.Text("Your Selections", size=12,
                                 weight=ft.FontWeight.BOLD, color=ORANGE))
            for sl, c in human_only:
                add_checkbox(items,
                    f"{c.code} — {c.name} ({c.credits} cr) [{sl}]",
                    f"h_{c.code}_{sl}", c.code, c.credits, True, ORANGE)

        if non_human:
            items.append(ft.Text("All Other Remaining Courses", size=12,
                                 weight=ft.FontWeight.BOLD, color=TEXT_MUTED))
            for sl, c in non_human:
                add_checkbox(items,
                    f"{c.code} — {c.name} ({c.credits} cr) [{sl}]",
                    f"o_{c.code}_{sl}", c.code, c.credits, False, GRAY)

        update_count()

        def confirm(e):
            sel_codes = set(key_map[k] for k, (cb, _) in check_vars.items()
                           if cb.value)
            last_advisor_picks[0] = set(sel_codes)
            page.close(dlg)

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
            status_text.value = f"Plan generated: {plan[0].total_credits} credits"
            page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Select courses for {semester_label}",
                          weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    credit_text,
                    ft.Divider(color=BORDER),
                    ft.Column(items, scroll=ft.ScrollMode.AUTO, height=500,
                              spacing=2),
                ], spacing=8),
                width=700, height=600,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton("Confirm Selection", bgcolor=NAVY,
                                   color=WHITE, on_click=confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=BG,
            shape=ft.RoundedRectangleBorder(radius=16),
        )
        page.open(dlg)

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
        status_text.value = "Session reset."
        page.update()

    def _confirm_reset(e):
        def _do_reset(e):
            page.close(dlg)
            _reset_app()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Reset Session"),
            content=ft.Text(
                "Are you sure you want to reset?\n\n"
                "This will clear the loaded student evaluation, all grid\n"
                "highlights, the semester plan, and any manual edits.\n\n"
                "This action cannot be undone."),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton("Reset", bgcolor="#C53030", color=WHITE,
                                   on_click=_do_reset),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=BG,
        )
        page.open(dlg)

    # ── Private View ──
    pv_btn_ref = [None]

    def _toggle_private_view(e):
        private_view[0] = not private_view[0]
        _save_config({"private_view": private_view[0]})
        if private_view[0]:
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

        # Rebuild sidebar visibility
        _rebuild_sidebar()
        _update_stats()
        status_text.value = ("Private View ON — Human Mode only, "
                             "student identity hidden." if private_view[0]
                             else "Private View OFF.")
        page.update()

    # ── Human Mode toggle ──
    human_mode_switch = ft.Switch(
        label="Enable Human Mode", value=manual_mode[0],
        active_color=GREEN, inactive_thumb_color=GRAY_LIGHT,
        label_style=ft.TextStyle(size=12, color=TEXT_PRIMARY),
    )
    pv_human_label = ft.Text("Human Mode  ·  Always On", size=12,
                              weight=ft.FontWeight.BOLD, color=GREEN)

    # Color picker for Human Mode
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
            ft.Row([
                ft.Radio(value=val, active_color=dot_clr,
                         label=lbl,
                         label_style=ft.TextStyle(size=11, color=TEXT_PRIMARY)),
                ft.Container(width=24, height=12, bgcolor=cell_clr,
                             border_radius=3,
                             border=ft.border.all(1, BORDER)),
            ], spacing=4)
            for val, lbl, cell_clr, dot_clr in color_options
        ], spacing=0),
    )

    def _on_color_change(e):
        manual_color[0] = color_radio.value
    color_radio.on_change = _on_color_change

    def _on_manual_toggle(e):
        if not human_mode_switch.value and private_view[0]:
            human_mode_switch.value = True
            status_text.value = "Human Mode cannot be disabled in Private View."
            page.update()
            return
        manual_mode[0] = human_mode_switch.value
        _rebuild_sidebar()
        if grid[0]:
            _display_grid()
        status_text.value = ("Human Mode ON — Click any course cell."
                             if manual_mode[0] else "Human Mode OFF.")
        page.update()
    human_mode_switch.on_change = _on_manual_toggle

    # ── Sidebar sections ──
    upload_section = ft.Column([
        ft.Text("UPLOAD EVALUATION", size=10, weight=ft.FontWeight.BOLD,
                color=TEXT_MUTED),
        ft.Divider(height=1, color=BORDER),
        ft.ElevatedButton("Upload PDF", icon=ft.Icons.UPLOAD_FILE,
                           bgcolor=NAVY_LIGHT, color=WHITE,
                           style=ft.ButtonStyle(
                               shape=ft.RoundedRectangleBorder(radius=8)),
                           on_click=_upload_eval, width=280),
        eval_label,
        ft.Text("STUDENT INFO", size=10, weight=ft.FontWeight.BOLD,
                color=TEXT_MUTED),
        ft.Divider(height=1, color=BORDER),
        _glass_card(info_text, padding=10, border_radius=8),
    ], spacing=6)

    advisor_section = ft.Column([
        ft.Text("FACULTY ADVISOR", size=10, weight=ft.FontWeight.BOLD,
                color=TEXT_MUTED),
        ft.Divider(height=1, color=BORDER),
        advisor_dropdown,
    ], spacing=6)

    semester_section = ft.Column([
        ft.Text("SEMESTER PLAN", size=10, weight=ft.FontWeight.BOLD,
                color=TEXT_MUTED),
        ft.Divider(height=1, color=BORDER),
        semester_dropdown,
    ], spacing=6)

    generate_btn = ft.ElevatedButton(
        "Generate Plan", icon=ft.Icons.AUTO_AWESOME,
        bgcolor=BLUE_DARK, color=WHITE, width=280,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
        on_click=_generate_plan)

    manual_options = ft.Column([
        ft.Text("Click grid cells to set course status",
                size=10, color=TEXT_SECONDARY),
        color_radio,
    ], spacing=6, visible=manual_mode[0])

    human_mode_section = ft.Column([
        ft.Text("HUMAN MODE", size=10, weight=ft.FontWeight.BOLD,
                color=TEXT_MUTED),
        ft.Divider(height=1, color=BORDER),
    ], spacing=6)

    # Export buttons
    export_section = ft.Column([
        ft.Divider(height=1, color=BORDER),
        ft.ElevatedButton("Export Grid PDF", icon=ft.Icons.PICTURE_AS_PDF,
                           bgcolor=NAVY, color=WHITE, width=280,
                           style=ft.ButtonStyle(
                               shape=ft.RoundedRectangleBorder(radius=8))),
        ft.OutlinedButton("Export Plan PDF", icon=ft.Icons.DESCRIPTION,
                           width=280,
                           style=ft.ButtonStyle(
                               shape=ft.RoundedRectangleBorder(radius=8),
                               side=ft.BorderSide(1, BORDER),
                               color=TEXT_PRIMARY)),
    ], spacing=6)

    # Sidebar container
    sidebar_items = ft.Column(spacing=12, expand=True,
                               scroll=ft.ScrollMode.AUTO)

    def _rebuild_sidebar():
        sidebar_items.controls.clear()
        if not private_view[0]:
            sidebar_items.controls.append(upload_section)
            sidebar_items.controls.append(advisor_section)
            sidebar_items.controls.append(semester_section)
        sidebar_items.controls.append(generate_btn)

        # Human mode section
        hm = ft.Column(spacing=6)
        hm.controls.append(ft.Text("HUMAN MODE", size=10,
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
        width=320,
        bgcolor=SIDEBAR_BG,
        padding=16,
        border=ft.border.only(right=ft.BorderSide(1, BORDER)),
    )

    # ──────────────────────────────────────────
    #  Tab bar + content area
    # ──────────────────────────────────────────

    def make_tab_btn(tab_id, label, icon):
        is_active = (tab_id == current_tab[0])
        btn = ft.Container(
            content=ft.Text(label, size=12,
                            weight=ft.FontWeight.BOLD if is_active else None,
                            color=WHITE if is_active else TEXT_SECONDARY),
            bgcolor=BLUE_DARK if is_active else CARD_BG,
            padding=ft.padding.symmetric(8, 16),
            border_radius=8,
            on_click=lambda e, t=tab_id: _switch_tab(t),
            ink=True,
        )
        tab_buttons[tab_id] = btn
        return btn

    tab_bar = ft.Row([
        make_tab_btn("grid", "4-Year Grid", ft.Icons.GRID_VIEW),
        make_tab_btn("plan", "Semester Plan", ft.Icons.CALENDAR_MONTH),
        make_tab_btn("stats", "Dashboard", ft.Icons.DASHBOARD),
    ], spacing=4)

    # Wrap each content area in a container for visibility toggling
    grid_view = ft.Container(
        content=ft.Container(
            content=grid_content,
            bgcolor=GRID_BG, border_radius=12,
            border=ft.border.all(1, BORDER),
            padding=8,
        ),
        expand=True, visible=True)
    plan_view = ft.Container(content=plan_content, expand=True, visible=False)
    stats_view = ft.Container(content=stats_content, expand=True, visible=False)

    tab_views["grid"] = grid_view
    tab_views["plan"] = plan_view
    tab_views["stats"] = stats_view

    content_area = ft.Column([
        tab_bar,
        ft.Stack([grid_view, plan_view, stats_view], expand=True),
    ], spacing=8, expand=True)

    # ──────────────────────────────────────────
    #  Header
    # ──────────────────────────────────────────

    # Logo
    logo_path = _asset_path('logo_transparent.png')
    logo_exists = os.path.exists(logo_path)

    header_left = ft.Row([
        ft.Image(src=logo_path, width=36, height=36) if logo_exists
        else ft.Icon(ft.Icons.SCHOOL, size=36, color=BLUE_DARK),
        ft.Column([
            ft.Text("RBSD | Internal Tool", size=9,
                    weight=ft.FontWeight.BOLD, color=BLUE_DARK),
            ft.Text("AdviseMe", size=17, weight=ft.FontWeight.BOLD,
                    color=WHITE),
        ], spacing=0),
    ], spacing=12)

    pv_btn = ft.ElevatedButton(
        "🔒  Private View",
        bgcolor=NAVY_LIGHT if private_view[0] else CARD_BG,
        color=WHITE if private_view[0] else TEXT_MUTED,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
        on_click=_toggle_private_view)
    pv_btn_ref[0] = pv_btn

    reset_btn = ft.ElevatedButton(
        "⟳  RESET", bgcolor="#C53030", color=WHITE,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
        on_click=_confirm_reset)

    header = ft.Container(
        content=ft.Row([
            header_left,
            ft.VerticalDivider(width=1, color=BORDER),
            ft.Text("Program", size=11, color=TEXT_MUTED),
            program_dropdown,
            ft.Container(expand=True),
            pv_btn,
            reset_btn,
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=NAVY,
        padding=ft.padding.symmetric(10, 16),
        border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
    )

    # ──────────────────────────────────────────
    #  Status bar
    # ──────────────────────────────────────────
    status_bar = ft.Container(
        content=status_text,
        bgcolor=CARD_BG,
        padding=ft.padding.symmetric(6, 24),
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
    page.bgcolor = BG
    page.window.width = 1440
    page.window.height = 804
    page.window.resizable = False
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK

    def _launch_main(e):
        page.controls.clear()
        page.window.width = 1600
        page.window.height = 1000
        page.window.min_width = 1200
        page.window.min_height = 800
        page.window.resizable = True
        main(page)

    # Logo
    logo_path = _asset_path('logo_transparent.png')
    logo_exists = os.path.exists(logo_path)

    # Welcome background — gradient fallback
    welcome_bg = ft.Container(
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
            colors=[NAVY_LIGHT, BLUE_DARK, NAVY],
        ),
        expand=True,
        border_radius=0,
    )

    # Check if welcome bg image exists
    bg_path = _asset_path('welcome_bg.png')
    if os.path.exists(bg_path):
        welcome_bg = ft.Container(
            content=ft.Image(src=bg_path, fit=ft.ImageFit.COVER,
                             expand=True),
            expand=True,
        )

    left_panel = ft.Container(
        content=ft.Column([
            ft.Container(expand=True),
            ft.Image(src=logo_path, width=64, height=64)
            if logo_exists else ft.Container(),
            ft.Text("AdviseMe", size=36, weight=ft.FontWeight.BOLD,
                    color=TEXT_PRIMARY),
            ft.Text("RBSD | Internal Tool", size=12,
                    weight=ft.FontWeight.BOLD, color=BLUE_DARK),
            ft.Container(height=20),
            ft.Text("Course tracking and advising\nmade simple for faculty.",
                    size=14, color=TEXT_SECONDARY, text_align=ft.TextAlign.CENTER),
            ft.Container(height=30),
            ft.ElevatedButton(
                "Let's Get Started  →",
                bgcolor=BLUE_DARK, color=WHITE,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    text_style=ft.TextStyle(size=16, weight=ft.FontWeight.BOLD)),
                height=52, width=260,
                on_click=_launch_main),
            ft.Container(expand=True),
            ft.Text(f"v{__version__}", size=10, color=TEXT_MUTED),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
           spacing=4),
        width=600,
        padding=40,
    )

    page.add(
        ft.Row([
            left_panel,
            welcome_bg,
        ], spacing=0, expand=True)
    )
    page.update()


if __name__ == "__main__":
    ft.app(target=app)
