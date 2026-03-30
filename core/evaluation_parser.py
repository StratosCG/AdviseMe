"""
Parse Kean University program evaluation PDFs to extract course statuses.

The evaluation PDF has a structured format with sections like:
- GE Foundation Requirements
- GE Distribution Requirements
- Additional Required Courses
- Academic Major (Foundation Core, Major Required, Major Elective, etc.)
- Free Electives
- Other Courses

Each course entry has a status (Completed, Transfer Equivalency, In-Progress,
Not Started, Fulfilled, Fully Planned, Dropped) and a course code.
"""
import re
from typing import Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from core.models import EvalCourse, CourseStatus, StudentRecord


# Status keywords found in evaluation PDFs
STATUS_MAP = {
    "completed": CourseStatus.COMPLETED,
    "transfer equivalency": CourseStatus.TRANSFER,
    "transfer": CourseStatus.TRANSFER,
    "in-progress": CourseStatus.IN_PROGRESS,
    "in progress": CourseStatus.IN_PROGRESS,
    "not started": CourseStatus.NOT_STARTED,
    "fulfilled": CourseStatus.FULFILLED,
    "fully planned": CourseStatus.FULLY_PLANNED,
    "dropped": CourseStatus.DROPPED,
}

# Regex to match course codes like GD*3010, DSN*1103, ENG*1030, etc.
COURSE_CODE_RE = re.compile(r'\b([A-Z]{2,4})\*(\d{4})\b')

# Regex for grade patterns
GRADE_RE = re.compile(r'^([A-F][+-]?)$')


def parse_evaluation_pdf(pdf_path: str) -> StudentRecord:
    """
    Parse a Kean University program evaluation PDF and extract all course data.

    Args:
        pdf_path: Path to the evaluation PDF file.

    Returns:
        StudentRecord with extracted student info and course list.
    """
    if fitz is None:
        raise ImportError("PyMuPDF (fitz) is required. Install with: pip install PyMuPDF")

    doc = fitz.open(pdf_path)
    record = StudentRecord()
    all_text_lines = []

    # Extract all text from every page
    for page in doc:
        text = page.get_text("text")
        lines = text.split("\n")
        all_text_lines.extend(lines)

    doc.close()

    # Parse student header info
    _parse_header(all_text_lines, record)

    # Parse all courses with their statuses
    record.eval_courses = _parse_courses(all_text_lines)

    return record


def _parse_header(lines: list, record: StudentRecord):
    """Extract student name, ID, GPA, program info from the header."""
    full_text = "\n".join(lines[:50])  # Header is in the first ~50 lines

    # Student name and ID: "Cassondra Fortuna (1320437)"
    name_match = re.search(r'^([A-Za-z\s]+)\s*\((\d+)\)', full_text, re.MULTILINE)
    if name_match:
        record.student_name = name_match.group(1).strip()
        record.student_id = name_match.group(2).strip()

    # GPA: "Cumulative GPA: 3.315"
    gpa_match = re.search(r'Cumulative GPA:\s*([\d.]+)', full_text)
    if gpa_match:
        try:
            record.gpa = float(gpa_match.group(1))
        except ValueError:
            pass

    # Total credits: "Total Credits  101 of 120"
    credits_match = re.search(r'Total Credits\s+(\d+)\s+of\s+(\d+)', full_text)
    if credits_match:
        try:
            record.total_credits_earned = int(credits_match.group(1))
            record.total_credits_required = int(credits_match.group(2))
        except ValueError:
            pass

    # Program name from page header
    if "Graphic Design, BFA" in full_text or "Graphic Design, BFA" in full_text:
        record.program_name = "BFA Graphic Design"
    else:
        # Try to find it from the degree line
        degree_match = re.search(r'Degree:\s*(.+)', full_text)
        major_match = re.search(r'Majors:.*?([A-Za-z\s]+)', full_text, re.DOTALL)
        if degree_match and major_match:
            record.program_name = f"{major_match.group(1).strip()}"


def _parse_courses(lines: list) -> list:
    """
    Parse all course entries from the evaluation text.

    The evaluation format typically shows:
        Status keyword (e.g., "Completed", "Transfer Equivalency")
        Course code (e.g., "GD*3010")
        Grade (e.g., "A", "B+")

    These appear on consecutive lines.
    """
    courses = []
    current_section = ""
    current_status = None
    seen_codes = set()
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Track which section we're in
        section = _detect_section(line)
        if section:
            current_section = section

        # Check if this line indicates a status
        status = _detect_status(line)
        if status is not None:
            current_status = status
            # Look ahead for course code on the next line(s)
            for j in range(1, 4):  # Check next 3 lines
                if i + j < len(lines):
                    next_line = lines[i + j].strip()
                    code_match = COURSE_CODE_RE.search(next_line)
                    if code_match:
                        course_code = f"{code_match.group(1)}*{code_match.group(2)}"

                        # Look for grade on the line after the code
                        grade = ""
                        if i + j + 1 < len(lines):
                            grade_line = lines[i + j + 1].strip()
                            if GRADE_RE.match(grade_line):
                                grade = grade_line

                        # Allow duplicates for elective codes (GDX, FEX, etc.)
                        # but avoid exact duplicates (same code + section + status)
                        unique_key = f"{course_code}_{current_section}_{current_status.value}_{grade}"
                        is_generic = course_code.split("*")[0].endswith("X") or course_code.split("*")[0] in ("FEX", "FA")
                        if unique_key not in seen_codes or is_generic:
                            is_transfer = (current_status == CourseStatus.TRANSFER)
                            course = EvalCourse(
                                code=course_code,
                                status=current_status,
                                grade=grade,
                                is_transfer=is_transfer,
                                section=current_section,
                            )
                            courses.append(course)
                        break

        # Also check for course codes on this line directly
        # (sometimes status and code are on the same or nearby lines)
        code_match = COURSE_CODE_RE.search(line)
        if code_match and current_status is None:
            # Check previous lines for status
            for j in range(1, 4):
                if i - j >= 0:
                    prev_status = _detect_status(lines[i - j].strip())
                    if prev_status is not None:
                        current_status = prev_status
                        break

        i += 1

    # Post-process: remove dropped courses from the active list
    # but keep them for reference
    return courses


def _detect_status(line: str) -> Optional[CourseStatus]:
    """Check if a line contains a course status keyword."""
    line_lower = line.lower().strip()
    for keyword, status in STATUS_MAP.items():
        if line_lower == keyword or line_lower.startswith(keyword):
            return status
    return None


def _detect_section(line: str) -> str:
    """Detect which section of the evaluation we're in."""
    line_lower = line.lower().strip()

    section_markers = {
        "ge foundation requirements": "GE Foundation",
        "ge distribution requirements": "GE Distribution",
        "additional required courses": "Additional Required",
        "a. found. core": "Foundation Core",
        "b. major required": "Major Required",
        "c. major elective": "Major Elective",
        "d. intern/pract": "Internship/Practicum",
        "e. major capstone": "Major Capstone",
        "free electives": "Free Electives",
        "other courses": "Other Courses",
        "a. humanities req": "GE Humanities Req",
        "b. humanities elec": "GE Humanities Elec",
        "c. soc science req": "GE Soc Science Req",
        "d. soc science ele": "GE Soc Science Ele",
        "e. science & math": "GE Science & Math",
        "a. ge*1000/3000": "GE Transition",
        "b. composition": "GE Composition",
        "c. mathematics": "GE Mathematics",
        "d. communication": "GE Communication",
        "e. research/technology": "GE Research/Tech",
        "a. add'l required": "Additional Required",
        "academic major": "Academic Major",
        "a. upper level": "Free Elective Upper",
        "b. lower level": "Free Elective Lower",
    }

    for marker, section in section_markers.items():
        if marker in line_lower:
            return section

    return ""


def get_completed_codes(record: StudentRecord) -> set:
    """Get all course codes that count as 'done' (completed, transfer, fulfilled)."""
    done_statuses = {
        CourseStatus.COMPLETED,
        CourseStatus.TRANSFER,
        CourseStatus.FULFILLED,
    }
    return {
        c.code for c in record.eval_courses
        if c.status in done_statuses
    }


def get_in_progress_codes(record: StudentRecord) -> set:
    """Get all course codes currently in progress."""
    return {
        c.code for c in record.eval_courses
        if c.status == CourseStatus.IN_PROGRESS
    }


def get_not_started_codes(record: StudentRecord) -> set:
    """Get all course codes not yet started."""
    return {
        c.code for c in record.eval_courses
        if c.status == CourseStatus.NOT_STARTED
    }


def get_courses_by_section(record: StudentRecord, section: str) -> list:
    """Get all courses in a specific section of the evaluation."""
    return [c for c in record.eval_courses if c.section == section]
