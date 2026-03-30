"""
Generate highlighted 4-year grid PDFs and semester plan PDFs.

Uses reportlab to create clean, color-coded grid documents.
Color coding:
  - Green: Completed courses
  - Orange: Planned for next semester
  - Light Red: Gaps (out of sequence / missed)
  - White: Future courses (not yet relevant)
"""
import os
from datetime import datetime

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.units import inch, mm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
except ImportError:
    raise ImportError("reportlab is required. Install with: pip install reportlab")

from core.models import ProgramGrid, GridHighlight, CourseStatus, SemesterPlan

# Color definitions
COLOR_GREEN = colors.Color(0.6, 0.9, 0.6)       # Completed
COLOR_TRANSFER = colors.Color(0.78, 0.66, 0.92)  # Transfer (purple tint)
COLOR_ORANGE = colors.Color(1.0, 0.8, 0.4)       # Next semester planned
COLOR_LIGHT_RED = colors.Color(1.0, 0.7, 0.7)    # Gap / out of sequence
COLOR_WHITE = colors.Color(1.0, 1.0, 1.0)         # Normal / future
COLOR_HEADER = colors.Color(0.85, 0.85, 0.85)     # Header row
COLOR_YEAR_LABEL = colors.Color(0.75, 0.75, 0.75) # Year label column
COLOR_IN_PROGRESS = colors.Color(0.4, 0.65, 1.0)     # In progress (bold blue)

HIGHLIGHT_COLORS = {
    GridHighlight.GREEN: COLOR_GREEN,
    GridHighlight.TRANSFER: COLOR_TRANSFER,
    GridHighlight.ORANGE: COLOR_ORANGE,
    GridHighlight.LIGHT_RED: COLOR_LIGHT_RED,
    GridHighlight.NONE: COLOR_WHITE,
}


def generate_grid_pdf(
    grid: ProgramGrid,
    student_name: str,
    student_id: str,
    output_path: str,
    semester_plan: SemesterPlan = None,
    advisor_name: str = "",
):
    """
    Generate a highlighted 4-year grid PDF.

    Args:
        grid: Program grid with highlight statuses set.
        student_name: Student's name for the header.
        student_id: Student's ID for the header.
        output_path: Where to save the PDF.
        semester_plan: Optional semester plan (to mark orange courses).
        advisor_name: Optional faculty advisor name for the header.
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(letter),
        leftMargin=0.4 * inch,
        rightMargin=0.4 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.4 * inch,
    )

    styles = getSampleStyleSheet()
    elements = []

    # ── Modern header ──
    navy = colors.Color(0.08, 0.16, 0.25)
    title_style = ParagraphStyle(
        'GridTitle', parent=styles['Title'],
        fontSize=16, spaceAfter=2, textColor=navy,
    )
    subtitle_style = ParagraphStyle(
        'GridSubtitle', parent=styles['Normal'],
        fontSize=10, alignment=TA_CENTER, spaceAfter=2,
        textColor=colors.Color(0.4, 0.4, 0.4),
    )
    info_style = ParagraphStyle(
        'GridInfo', parent=styles['Normal'],
        fontSize=9, alignment=TA_LEFT, spaceAfter=4,
        textColor=colors.Color(0.3, 0.3, 0.3),
    )

    elements.append(Paragraph(f"{grid.university} - {grid.school}", subtitle_style))
    elements.append(Paragraph(f"<b>{grid.program_name}</b>", title_style))

    info_parts = [
        f"Student: <b>{student_name}</b> ({student_id})",
        f"Generated: {datetime.now().strftime('%m/%d/%Y')}",
        f"Total Required: {grid.total_credits} SH",
    ]
    if advisor_name:
        info_parts.insert(1, f"Advisor: <b>{advisor_name}</b>")
    elements.append(Paragraph("  |  ".join(info_parts), info_style))
    elements.append(Spacer(1, 6))

    # Build the grid table
    table_data, cell_colors = _build_grid_table(grid)

    # Fixed column layout: Year | Term | Course1..N | Cr
    # All rows are padded to the same number of columns in _build_grid_table
    total_cols = len(table_data[0])  # All rows now have the same length
    num_course_cols = total_cols - 3  # Subtract Year, Term, Cr

    available_width = landscape(letter)[0] - 0.8 * inch
    year_col_width = 0.75 * inch
    term_col_width = 0.5 * inch
    credits_col_width = 0.4 * inch
    course_col_width = (
        available_width - year_col_width - term_col_width - credits_col_width
    ) / max(num_course_cols, 1)

    col_widths = (
        [year_col_width, term_col_width]
        + [course_col_width] * num_course_cols
        + [credits_col_width]
    )

    # Create table
    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    # Modern styling
    style_commands = [
        # Outer border
        ('BOX', (0, 0), (-1, -1), 1, colors.Color(0.4, 0.4, 0.4)),
        # Inner grid — light lines
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.Color(0.78, 0.78, 0.78)),
        # Typography
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        # Header row — dark navy
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.08, 0.16, 0.25)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        # Credits column — subtle background
        ('BACKGROUND', (-1, 1), (-1, -1), colors.Color(0.95, 0.95, 0.95)),
        ('FONTNAME', (-1, 1), (-1, -1), 'Helvetica-Bold'),
    ]

    # Apply cell colors (course cells + year/term labels)
    for (row, col), color in cell_colors.items():
        style_commands.append(('BACKGROUND', (col, row), (col, row), color))

    table.setStyle(TableStyle(style_commands))
    elements.append(table)

    # Add legend
    elements.append(Spacer(1, 10))
    elements.append(_create_legend(styles))

    # Build PDF
    doc.build(elements)


def _build_grid_table(grid: ProgramGrid) -> tuple:
    """
    Build the table data and cell color map for the grid.

    All rows are normalized to the same column count:
      [Year, Term, Course_1 .. Course_N, Cr]

    Returns (table_data, cell_colors).
    """
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    cell_style = ParagraphStyle(
        'CellStyle', fontSize=6.5, leading=8,
        alignment=TA_CENTER, wordWrap='CJK',
    )
    bold_cell = ParagraphStyle(
        'BoldCell', parent=cell_style, fontName='Helvetica-Bold',
    )
    year_style = ParagraphStyle(
        'YearCell', parent=cell_style, fontName='Helvetica-Bold',
        fontSize=7, leading=9,
    )

    max_courses = max(
        len(sem.courses) for sem in grid.semesters
    ) if grid.semesters else 6

    total_cols = 2 + max_courses + 1  # Year + Term + courses + Cr

    # ── Header row (white text for dark navy background) ──
    header_style = ParagraphStyle(
        'HeaderCell', parent=bold_cell,
        textColor=colors.white,
    )
    header = [
        Paragraph("<b>Year</b>", header_style),
        Paragraph("<b>Term</b>", header_style),
    ]
    for i in range(max_courses):
        header.append(Paragraph(f"<b>Course {i + 1}</b>", header_style))
    header.append(Paragraph("<b>Cr</b>", header_style))

    table_data = [header]
    cell_colors = {}

    # Year label styling
    YEAR_BG = colors.Color(0.2, 0.3, 0.42)   # dark navy for year col
    TERM_BG = colors.Color(0.88, 0.9, 0.93)   # light gray for term col

    current_year = None

    for sem in grid.semesters:
        row_idx = len(table_data)

        if sem.year != current_year:
            year_label = _year_label(sem.year)
            current_year = sem.year
        else:
            year_label = ""

        row = [
            Paragraph(f"<b><font color='white'>{year_label}</font></b>", year_style),
            Paragraph(f"<b>{sem.term}</b>", bold_cell),
        ]

        # Add course cells
        for i, course in enumerate(sem.courses):
            lines = []
            if not course.is_elective_slot and not course.is_ge_category:
                lines.append(f"<b>{course.code}</b>")
            name = course.name
            if len(name) > 40:
                name = name[:38] + "..."
            lines.append(name)
            lines.append(f"({course.credits} cr)")

            if course.matched_eval_course and course.matched_eval_course.grade:
                grade = course.matched_eval_course.grade
                lines.append(f"<br/><b><font color='#2D3748' size='7'>Grade: {grade}</font></b>")

            cell_text = "<br/>".join(lines)
            row.append(Paragraph(cell_text, cell_style))

            col_idx = i + 2
            if course.status in HIGHLIGHT_COLORS:
                cell_colors[(row_idx, col_idx)] = HIGHLIGHT_COLORS[course.status]
            if course.eval_status == CourseStatus.IN_PROGRESS:
                cell_colors[(row_idx, col_idx)] = COLOR_IN_PROGRESS

        # Pad empty course cells so Cr is always in the last column
        while len(row) < total_cols - 1:
            row.append("")

        # Cr column — always last
        total_credits = sum(c.credits for c in sem.courses)
        row.append(Paragraph(f"<b>{total_credits}</b>", bold_cell))

        # Year and Term column colors
        cell_colors[(row_idx, 0)] = YEAR_BG
        cell_colors[(row_idx, 1)] = TERM_BG

        table_data.append(row)

    return table_data, cell_colors


def _year_label(year_num: int) -> str:
    """Convert year number to label."""
    labels = {
        1: "FIRST YEAR",
        2: "SECOND YEAR",
        3: "THIRD YEAR",
        4: "FOURTH YEAR",
    }
    return labels.get(year_num, f"YEAR {year_num}")


def _create_legend(styles) -> Table:
    """Create a clean two-row color legend."""
    from reportlab.lib.styles import ParagraphStyle

    lbl = ParagraphStyle('LegendLabel', fontSize=7, leading=9)
    hdr = ParagraphStyle('LegendHdr', fontSize=7, leading=9, fontName='Helvetica-Bold')

    # Layout: Legend label | swatch+label | swatch+label | swatch+label
    swatch_w = 0.18 * inch
    label_w  = 1.25 * inch

    legend_data = [
        [
            Paragraph("<b>Legend:</b>", hdr),
            "", Paragraph("Completed", lbl),
            "", Paragraph("Transfer", lbl),
            "", Paragraph("Next Semester", lbl),
        ],
        [
            "",
            "", Paragraph("Gap (Out of Sequence)", lbl),
            "", Paragraph("In Progress", lbl),
            "", Paragraph("Not Yet Scheduled", lbl),
        ],
    ]

    col_widths = [0.6 * inch] + [swatch_w, label_w] * 3
    legend_table = Table(legend_data, colWidths=col_widths)

    border_color = colors.Color(0.7, 0.7, 0.7)
    legend_commands = [
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        # Row 1 swatches (cols 1, 3, 5)
        ('BOX', (1, 0), (1, 0), 0.5, border_color),
        ('BOX', (3, 0), (3, 0), 0.5, border_color),
        ('BOX', (5, 0), (5, 0), 0.5, border_color),
        ('BACKGROUND', (1, 0), (1, 0), COLOR_GREEN),
        ('BACKGROUND', (3, 0), (3, 0), COLOR_TRANSFER),
        ('BACKGROUND', (5, 0), (5, 0), COLOR_ORANGE),
        # Row 2 swatches
        ('BOX', (1, 1), (1, 1), 0.5, border_color),
        ('BOX', (3, 1), (3, 1), 0.5, border_color),
        ('BOX', (5, 1), (5, 1), 0.5, border_color),
        ('BACKGROUND', (1, 1), (1, 1), COLOR_LIGHT_RED),
        ('BACKGROUND', (3, 1), (3, 1), COLOR_IN_PROGRESS),
        ('BACKGROUND', (5, 1), (5, 1), COLOR_WHITE),
    ]

    legend_table.setStyle(TableStyle(legend_commands))
    return legend_table


def generate_semester_plan_pdf(
    plan: SemesterPlan,
    student_name: str,
    student_id: str,
    program_name: str,
    output_path: str
):
    """
    Generate a clean one-page PDF for the next semester course plan.

    Args:
        plan: The semester plan with courses.
        student_name: Student's name.
        student_id: Student's ID.
        program_name: Name of the program.
        output_path: Where to save the PDF.
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    elements = []

    # Header
    title_style = ParagraphStyle(
        'PlanTitle', parent=styles['Title'],
        fontSize=16, spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        'PlanSubtitle', parent=styles['Normal'],
        fontSize=11, spaceAfter=6,
    )
    note_style = ParagraphStyle(
        'PlanNote', parent=styles['Normal'],
        fontSize=9, textColor=colors.grey, spaceAfter=8,
    )

    elements.append(Paragraph(f"<b>Next Semester Course Plan</b>", title_style))
    elements.append(Paragraph(f"{plan.semester_label}", subtitle_style))
    elements.append(Paragraph(
        f"Student: {student_name} ({student_id})  |  Program: {program_name}  |  "
        f"Generated: {datetime.now().strftime('%m/%d/%Y')}",
        subtitle_style
    ))
    elements.append(Spacer(1, 12))

    # Scheduled courses table
    if plan.courses:
        elements.append(Paragraph("<b>Scheduled Courses:</b>", styles['Heading3']))
        course_data = [["Course Code", "Course Name", "Credits", "Category"]]
        for c in plan.courses:
            course_data.append([
                c.code, c.name, str(c.credits), c.category.replace("_", " ").title()
            ])

        # Total row
        total_credits = sum(c.credits for c in plan.courses)
        course_data.append(["", "", str(total_credits), ""])

        table = Table(course_data, colWidths=[1.5 * inch, 3 * inch, 1 * inch, 1.5 * inch])
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_HEADER),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    # Makeup courses (out of sequence)
    if plan.makeup_courses:
        elements.append(Paragraph(
            "<b>Makeup Courses (Out of Sequence):</b>", styles['Heading3']
        ))
        elements.append(Paragraph(
            "These courses should have been completed earlier and need to be scheduled.",
            note_style
        ))

        makeup_data = [["Course Code", "Course Name", "Credits", "Originally Scheduled"]]
        for c in plan.makeup_courses:
            makeup_data.append([
                c.code, c.name, str(c.credits), c.category.replace("_", " ").title()
            ])

        makeup_total = sum(c.credits for c in plan.makeup_courses)
        makeup_data.append(["", "", str(makeup_total), ""])

        table = Table(makeup_data, colWidths=[1.5 * inch, 3 * inch, 1 * inch, 1.5 * inch])
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_LIGHT_RED),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    # Total credits summary
    plan.compute_total()
    elements.append(Paragraph(
        f"<b>Total Credits This Semester: {plan.total_credits}</b>",
        styles['Heading3']
    ))

    # Notes
    if plan.notes:
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("<b>Notes:</b>", styles['Heading3']))
        for note in plan.notes:
            elements.append(Paragraph(f"  - {note}", styles['Normal']))

    # Signature lines
    elements.append(Spacer(1, 40))
    sig_data = [
        ["_" * 40, "", "_" * 40],
        ["Student Signature", "", "Advisor Signature"],
        ["", "", ""],
        ["_" * 40, "", "_" * 40],
        ["Date", "", "Date"],
    ]
    sig_table = Table(sig_data, colWidths=[2.5 * inch, 1.5 * inch, 2.5 * inch])
    sig_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(sig_table)

    doc.build(elements)
