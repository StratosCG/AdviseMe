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

# Regex for section completion markers like "1 of 1 Completed" or "5 of 5 Completed. Show Details"
SECTION_COMPLETION_RE = re.compile(
    r'(\d+)\s+of\s+(\d+)\s+Completed',
    re.IGNORECASE
)

# Regex for course substitution lines like "FEX*1000 replaces AH*3740 as per ..."
SUBSTITUTION_RE = re.compile(
    r'([A-Z]{2,4}\*\d{4})\s+replaces\s+([A-Z]{2,4}\*\d{4})',
    re.IGNORECASE
)

# Page header/footer junk patterns to filter out before parsing
# These are injected at page boundaries in browser-printed PDFs and break
# the lookahead that pairs statuses with course codes.
_PAGE_JUNK_RE = re.compile(
    r'^(?:'
    r'\d{1,2}/\d{1,2}/\d{2,4},?\s*\d{1,2}:\d{2}\s*[AP]M'  # date/time header
    r'|about:blank'                                           # browser origin
    r'|\d+/\d+$'                                              # page number "4/6"
    r')$',
    re.IGNORECASE
)

def _detect_page_title(raw_lines: list) -> str:
    """Auto-detect the repeated page title from raw PDF lines.

    Browser-printed PDFs repeat the document title at the top of every page.
    We find it by looking for a short string that appears 3+ times and
    sits near date/time header lines.
    """
    from collections import Counter
    candidates = Counter()
    for i, line in enumerate(raw_lines):
        s = line.strip()
        # Title is short, contains a comma or space, and isn't a status keyword
        if 10 < len(s) < 60 and not COURSE_CODE_RE.search(s):
            lower = s.lower()
            if not any(lower == kw or lower.startswith(kw) for kw in STATUS_MAP):
                candidates[s] += 1
    # The page title repeats once per page (typically 4-8 times)
    for text, count in candidates.most_common(5):
        if count >= 3:
            return text
    return ""


def _is_page_junk(line: str, page_title: str = "") -> bool:
    """Return True if the line is a page header/footer artifact."""
    s = line.strip()
    if not s:
        return False
    if _PAGE_JUNK_RE.match(s):
        return True
    if page_title and s == page_title:
        return True
    return False


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
    raw_lines = []

    # Extract all text from every page
    for page in doc:
        text = page.get_text("text")
        lines = text.split("\n")
        raw_lines.extend(lines)

    doc.close()

    # Parse student header info (from raw lines — junk doesn't affect header)
    _parse_header(raw_lines, record)

    # Filter out page header/footer junk that breaks status→code pairing
    page_title = _detect_page_title(raw_lines)
    all_text_lines = [ln for ln in raw_lines if not _is_page_junk(ln, page_title)]

    # Parse all courses with their statuses
    record.eval_courses = _parse_courses(all_text_lines)

    # Parse section-level completion markers (for collapsed GE sections)
    record.section_completions = _parse_section_completions(all_text_lines)

    # Parse course substitution lines
    record.substitutions = _parse_substitutions(all_text_lines)

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
            gpa = float(gpa_match.group(1))
            if 0.0 <= gpa <= 4.0:
                record.gpa = gpa
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

    # Program name detection
    # Map of PDF text patterns -> app program names
    _PROGRAM_MAP = {
        "Graphic Design, BFA": "BFA Graphic Design",
        "Interior Design, BFA": "BFA Interior Design",
        "Industrial Design, BID": "BID Industrial Design",
        "Advertising, BFA": "BFA Advertising",
    }

    # Try exact match first
    matched = False
    for pdf_text, program_name in _PROGRAM_MAP.items():
        if pdf_text in full_text:
            record.program_name = program_name
            matched = True
            break

    if not matched:
        # Try parsing Degree + Major lines generically
        degree_match = re.search(r'Degree:\s*(.+)', full_text)
        major_match = re.search(r'Majors?:\s*([A-Za-z\s/]+)', full_text)
        if degree_match and major_match:
            degree = degree_match.group(1).strip()
            major = major_match.group(1).strip()
            # Extract degree abbreviation (e.g. "Bachelor of Fine Arts" -> "BFA")
            abbrev_match = re.search(r'\(([A-Z]{2,4})\)', degree)
            if abbrev_match:
                abbrev = abbrev_match.group(1)
            else:
                # Build from initials: "Bachelor of Fine Arts" -> "BFA"
                words = [w for w in degree.split() if w[0].isupper()]
                abbrev = "".join(w[0] for w in words) if words else ""
            if abbrev and major:
                record.program_name = f"{abbrev} {major}"
            elif major:
                record.program_name = major


def _parse_courses(lines: list) -> list:
    """
    Parse all course entries from the evaluation text.

    Uses a two-pass approach for robustness against page-boundary reordering:

    Pass 1 — Index: Walk through all lines and record the position of every
    status keyword and every course code (with its grade on the next line).

    Pass 2 — Pair: For each course code, find its status.  First check if a
    status was found in the forward-lookahead window (the standard pattern:
    status on line N, code on line N+1/N+2).  If not, look for the nearest
    status keyword that appeared *before* this code and hasn't been consumed
    yet.  This handles the page-boundary case where fitz reorders content.
    """
    # ── Pass 1: Build indexes ──
    # status_entries: [(line_idx, CourseStatus)]
    # code_entries:   [(line_idx, course_code, grade, section)]
    status_entries = []
    code_entries = []
    current_section = ""

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()

        # Track section
        section = _detect_section(line)
        if section:
            current_section = section

        # Record status keywords — but skip section-summary lines.
        # Section summaries look like:
        #   " 0 of 1 Completed. Fully Planned Hide Details"
        #   " Fully Planned "        <-- preceded by "X of Y Completed"
        #   " 25 of 27 Credits Completed. Hide Details"
        # These are NOT per-course statuses; they describe the section header.
        st = _detect_status(line)
        if st is not None:
            is_section_summary = False
            # Check: is the previous line a section-level completion indicator?
            if i > 0:
                prev = lines[i - 1].strip().lower()
                if ("completed" in prev or "hide details" in prev
                        or "show details" in prev) and "of" in prev:
                    is_section_summary = True
            # Check: does this line itself contain "Hide Details" / "Show Details"?
            if "hide details" in line.lower() or "show details" in line.lower():
                is_section_summary = True
            if not is_section_summary:
                status_entries.append((i, st))

        # Record course codes
        # Skip lines that are clearly section headers or long descriptions
        # but allow moderately long lines that contain a course code
        if len(line) < 80 and not _detect_section(line):
            code_match = COURSE_CODE_RE.search(line)
            if code_match:
                course_code = f"{code_match.group(1)}*{code_match.group(2)}"
                # Look for grade on the next line
                grade = ""
                if i + 1 < len(lines):
                    grade_line = lines[i + 1].strip()
                    if GRADE_RE.match(grade_line):
                        grade = grade_line
                code_entries.append((i, course_code, grade, current_section))

    # ── Pass 2: Forward pairing (natural status→code) ──
    # For each status, find the FIRST course code within 6 lines forward.
    # This handles the normal case: status line, then code line, then grade.
    paired_codes = set()    # code entry indices already paired
    paired_statuses = set() # status entry indices already paired
    pairs = []              # (status_val, code_idx, course_code, grade, section)

    # Build code lookup by line index for fast access
    code_by_line = {}
    for ci, (c_idx, ccode, cgrade, csection) in enumerate(code_entries):
        code_by_line.setdefault(c_idx, []).append(ci)

    for si, (s_idx, s_val) in enumerate(status_entries):
        # Look forward up to 6 lines for a course code
        for offset in range(1, 7):
            target = s_idx + offset
            if target in code_by_line:
                for ci in code_by_line[target]:
                    if ci not in paired_codes:
                        c_idx, ccode, cgrade, csection = code_entries[ci]
                        pairs.append((s_val, c_idx, ccode, cgrade, csection))
                        paired_codes.add(ci)
                        paired_statuses.add(si)
                        break
                if si in paired_statuses:
                    break

    # ── Pass 3: Orphan matching ──
    # Codes not paired in pass 2 need a status.  Search for the nearest
    # unpaired status *anywhere* before the code (no distance limit).
    orphan_statuses = [
        (si, s_idx, s_val) for si, (s_idx, s_val) in enumerate(status_entries)
        if si not in paired_statuses
    ]

    for ci, (c_idx, ccode, cgrade, csection) in enumerate(code_entries):
        if ci in paired_codes:
            continue
        # Find nearest unpaired status before this code
        best = None
        for osi, (si, s_idx, s_val) in enumerate(orphan_statuses):
            if s_idx < c_idx:
                if best is None or s_idx > best[1]:
                    best = (osi, s_idx, s_val)
        if best is not None:
            osi, _, s_val = best
            pairs.append((s_val, c_idx, ccode, cgrade, csection))
            paired_codes.add(ci)
            orphan_statuses.pop(osi)

    # ── Build final course list ──
    # Allow repeated courses (e.g. topics courses like GD*4007 taken multiple
    # times count as separate elective completions).  Use a counter to cap at
    # MAX_REPEATS to guard against PDF extraction artifacts.
    from collections import Counter
    courses = []
    seen_counts = Counter()
    MAX_REPEATS = 4  # Topics courses can be taken up to 4 times

    for status_val, code_idx, course_code, grade, code_section in pairs:
        unique_key = f"{course_code}_{status_val.value}_{grade}"
        is_generic = (course_code.split("*")[0].endswith("X")
                      or course_code.split("*")[0] in ("FEX", "FA"))
        seen_counts[unique_key] += 1
        if seen_counts[unique_key] > MAX_REPEATS and not is_generic:
            continue

        is_transfer = (status_val == CourseStatus.TRANSFER)
        courses.append(EvalCourse(
            code=course_code,
            status=status_val,
            grade=grade,
            is_transfer=is_transfer,
            section=code_section,
        ))

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


def _parse_section_completions(lines: list) -> dict:
    """
    Parse section-level completion markers from the evaluation text.

    Looks for patterns like "X of Y Completed" within tracked GE sections.
    Returns dict mapping section name -> (completed_count, total_count).

    This is critical for collapsed sections where "Show Details" wasn't clicked
    and no individual course codes are visible.
    """
    completions = {}
    current_section = ""

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()

        # Track section changes
        section = _detect_section(line)
        if section:
            current_section = section

        # Look for "X of Y Completed" markers
        match = SECTION_COMPLETION_RE.search(line)
        if match and current_section:
            completed = int(match.group(1))
            total = int(match.group(2))
            # Only record if fully completed and it's a GE-type section
            # Avoid overwriting with sub-section counts (keep the first/highest)
            if current_section not in completions:
                completions[current_section] = (completed, total)

    return completions


def _parse_substitutions(lines: list) -> dict:
    """
    Parse course substitution lines from the evaluation text.

    Looks for patterns like "FEX*1000 replaces AH*3740 as per Edward Johnston".
    Returns dict mapping original_code -> replacement_code.
    """
    substitutions = {}

    for raw_line in lines:
        line = raw_line.strip()
        match = SUBSTITUTION_RE.search(line)
        if match:
            replacement = match.group(1).upper()
            original = match.group(2).upper()
            substitutions[original] = replacement

    return substitutions


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
