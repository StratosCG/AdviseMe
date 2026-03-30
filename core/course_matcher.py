"""
Course matching engine.

Matches courses from the program evaluation against the 4-year grid
to determine which grid slots have been completed, are in progress,
or are gaps (out of sequence).
"""
from typing import Optional

from core.models import (
    EvalCourse, GridCourse, StudentRecord, ProgramGrid,
    CourseStatus, GridHighlight, Semester
)


# Statuses that count as "done"
DONE_STATUSES = {CourseStatus.COMPLETED, CourseStatus.TRANSFER, CourseStatus.FULFILLED}
ACTIVE_STATUSES = {CourseStatus.IN_PROGRESS, CourseStatus.FULLY_PLANNED}


def _done_highlight(eval_course: 'EvalCourse') -> GridHighlight:
    """Return the correct highlight for a completed/transfer course."""
    if eval_course.status == CourseStatus.TRANSFER:
        return GridHighlight.TRANSFER
    return GridHighlight.GREEN


def match_courses(record: StudentRecord, grid: ProgramGrid) -> ProgramGrid:
    """
    Match evaluation courses against the program grid.

    Sets the status and matched_eval_course on each GridCourse in the grid.

    Args:
        record: Student record with parsed evaluation courses.
        grid: Program grid to match against.

    Returns:
        The grid with match results filled in.
    """
    # Build lookup structures from evaluation
    # Exclude "fulfilled" courses from direct matching — they are just markers
    # that a requirement is satisfied by another course
    done_courses = [
        c for c in record.eval_courses
        if c.status in DONE_STATUSES and c.status != CourseStatus.FULFILLED
    ]
    # Sort active courses so IN_PROGRESS comes before FULLY_PLANNED.
    # This ensures that when a course appears in multiple eval sections
    # (e.g. once as fully_planned and once as in_progress), the matcher
    # picks the in_progress instance first — which is more informative.
    _STATUS_PRIORITY = {CourseStatus.IN_PROGRESS: 0, CourseStatus.FULLY_PLANNED: 1}
    active_courses = sorted(
        [c for c in record.eval_courses if c.status in ACTIVE_STATUSES],
        key=lambda c: _STATUS_PRIORITY.get(c.status, 9),
    )
    not_started = [c for c in record.eval_courses if c.status == CourseStatus.NOT_STARTED]

    # Track matched eval courses by object identity (id()) to avoid
    # double-counting while supporting same-code courses in different lists
    matched_ids = set()

    # Track elective counts per group
    elective_counts = {}

    # First pass: match specific courses (non-elective, non-GE-category)
    for semester in grid.semesters:
        for course in semester.courses:
            if course.is_elective_slot or course.is_ge_category:
                continue  # Handle these in second pass

            match = _find_match(course, done_courses, matched_ids)
            if match:
                course.status = _done_highlight(match)
                course.matched_eval_course = match
                course.eval_status = match.status
                matched_ids.add(id(match))
                continue

            match = _find_match(course, active_courses, matched_ids)
            if match:
                course.status = GridHighlight.NONE  # Will be set later by planner
                course.matched_eval_course = match
                course.eval_status = match.status
                matched_ids.add(id(match))

    # Second pass: match elective slots
    for semester in grid.semesters:
        for course in semester.courses:
            if not course.is_elective_slot:
                continue

            group = course.elective_group
            if group not in elective_counts:
                elective_counts[group] = 0

            elective_def = grid.elective_definitions.get(group, {})
            match = _find_elective_match(
                course, done_courses, matched_ids, elective_def
            )
            if match:
                course.status = _done_highlight(match)
                course.matched_eval_course = match
                course.eval_status = match.status
                matched_ids.add(id(match))
                elective_counts[group] = elective_counts.get(group, 0) + 1

    # Third pass: match GE category slots
    for semester in grid.semesters:
        for course in semester.courses:
            if not course.is_ge_category:
                continue

            match = _find_ge_category_match(
                course, done_courses, matched_ids,
                grid.ge_category_definitions, record
            )
            if match:
                course.status = _done_highlight(match)
                course.matched_eval_course = match
                course.eval_status = match.status
                matched_ids.add(id(match))

    # Fourth pass: detect section-level completion for GE categories
    # Some evaluation PDFs have collapsed details, so we check if the
    # section shows as completed even without individual course codes
    _match_by_section_completion(grid, record, matched_ids)

    return grid


def _find_match(
    grid_course: GridCourse,
    eval_courses: list,
    matched_ids: set
) -> Optional[EvalCourse]:
    """
    Find an evaluation course that matches a grid course slot.

    Returns the matching EvalCourse or None.
    """
    for eval_course in eval_courses:
        if id(eval_course) in matched_ids:
            continue

        # Check against explicit match codes
        if eval_course.code in grid_course.match_codes:
            return eval_course

        # Also check normalized form
        if eval_course.normalized_code in grid_course.match_codes:
            return eval_course

        # Check if grid code matches directly (with * replacement)
        grid_code_star = grid_course.code.replace(" ", "*")
        if eval_course.code == grid_code_star:
            return eval_course

    return None


def _find_elective_match(
    grid_course: GridCourse,
    eval_courses: list,
    matched_ids: set,
    elective_def: dict
) -> Optional[EvalCourse]:
    """
    Find an evaluation course that fills an elective slot.

    Returns the matching EvalCourse or None.
    """
    prefixes = elective_def.get("match_prefixes", [])
    min_level = elective_def.get("min_level", 0)

    for eval_course in eval_courses:
        if id(eval_course) in matched_ids:
            continue

        # Check if course matches any of the elective prefixes
        for prefix in prefixes:
            prefix_clean = prefix.rstrip("*")
            if eval_course.department == prefix_clean:
                # Check level requirement
                if eval_course.course_number >= min_level:
                    return eval_course

    return None


def _find_ge_category_match(
    grid_course: GridCourse,
    eval_courses: list,
    matched_ids: set,
    ge_definitions: dict,
    record: StudentRecord
) -> Optional[EvalCourse]:
    """
    Find an evaluation course that fills a GE category slot.

    Returns the matching EvalCourse or None.
    """
    ge_cat = grid_course.ge_category
    ge_def = ge_definitions.get(ge_cat, {})
    eval_section = ge_def.get("eval_section", "")

    # Try to match by section from the evaluation
    if eval_section:
        for eval_course in eval_courses:
            if id(eval_course) in matched_ids:
                continue
            if eval_section.lower() in eval_course.section.lower():
                return eval_course

    # Fallback: try matching by common GE course prefixes
    # But be strict — only match courses that are clearly in GE sections
    ge_prefixes = {
        "social_science": ["PSY", "ECO", "SOC", "POL", "GEO", "ANT", "IDS", "PUB", "GLS"],
        "science_math": ["BIO", "CHE", "PHY", "ESC", "ENV", "CPS"],
    }

    if ge_cat in ge_prefixes:
        for eval_course in eval_courses:
            if id(eval_course) in matched_ids:
                continue
            if "GE" in eval_course.section or "Science" in eval_course.section:
                if eval_course.department in ge_prefixes[ge_cat]:
                    return eval_course

    return None


def _match_by_section_completion(
    grid: ProgramGrid,
    record: StudentRecord,
    matched_ids: set
):
    """
    Detect section-level completion from the evaluation PDF text.

    Some evaluations have collapsed details (Show Details links), so
    individual course codes aren't available. We parse completion markers
    like 'X of Y Completed' to determine if a GE category is satisfied.
    """
    import re
    import fitz

    # We need to re-read the PDF to find section completion markers
    # This is done as a fallback for unmatched GE slots
    unmatched_ge = []
    for semester in grid.semesters:
        for course in semester.courses:
            if course.is_ge_category and course.status != GridHighlight.GREEN:
                unmatched_ge.append(course)

    if not unmatched_ge:
        return  # All GE categories matched

    # Check section completion patterns in the evaluation text
    # Map GE categories to their section headers in the evaluation
    ge_section_patterns = {
        "social_science": [
            r"d\.\s*soc\s*science\s*ele.*?(\d+)\s+of\s+(\d+)\s+completed",
            r"soc\s*science.*?(\d+)\s+of\s+(\d+)\s+completed",
        ],
        "science_math": [
            r"e\.\s*science\s*&\s*math.*?(\d+)\s+of\s+(\d+)\s+completed",
            r"science\s*&\s*math.*?(\d+)\s+of\s+(\d+)\s+completed",
        ],
    }

    # Read evaluation PDF text
    # We'll check if the student's record has the PDF path
    # For now, just mark based on credit progress
    # The section completion is detected by looking at "X of Y Completed" patterns

    # Simple heuristic: if total credits > threshold, assume GE is done
    # This can be refined when we have full PDF text access
    for course in unmatched_ge:
        ge_cat = course.ge_category
        # If the student has 101+ credits out of 120, GE requirements are likely met
        if record.total_credits_earned >= 90:
            # Create a synthetic eval course to mark it
            from core.models import EvalCourse
            synthetic = EvalCourse(
                code=f"[{course.name}]",
                status=CourseStatus.COMPLETED,
                grade="",
                section=f"GE {ge_cat}",
            )
            course.status = GridHighlight.GREEN
            course.matched_eval_course = synthetic
            course.eval_status = CourseStatus.COMPLETED


def detect_current_semester(grid: ProgramGrid, credits_earned: int = 0) -> int:
    """
    Determine which semester the student should be planning NEXT,
    based on a combination of credit progress and completion patterns.

    Uses credits to estimate year, then finds the first semester in
    that year (or later) that has incomplete courses.

    Returns the index of the semester to plan for.
    """
    # Estimate year based on credits (roughly 30 per year)
    if credits_earned >= 90:
        estimated_year = 4
    elif credits_earned >= 60:
        estimated_year = 3
    elif credits_earned >= 30:
        estimated_year = 2
    else:
        estimated_year = 1

    # Find the first semester at or after the estimated year with incomplete courses
    # (courses that are done or currently in progress don't count as incomplete)
    for i, semester in enumerate(grid.semesters):
        if semester.year < estimated_year:
            continue
        has_incomplete = any(
            not _is_done_or_active(c)
            for c in semester.courses
        )
        if has_incomplete:
            return i

    # Check earlier semesters as fallback (all later semesters done somehow)
    for i, semester in enumerate(grid.semesters):
        has_incomplete = any(
            not _is_done_or_active(c)
            for c in semester.courses
        )
        if has_incomplete:
            return i

    return len(grid.semesters) - 1


def _is_done_or_active(course) -> bool:
    """Check if a course is completed, transferred, or currently in progress."""
    _DONE = {GridHighlight.GREEN, GridHighlight.TRANSFER}
    _ACTIVE = {CourseStatus.IN_PROGRESS, CourseStatus.FULLY_PLANNED}
    return course.status in _DONE or course.eval_status in _ACTIVE


def find_gap_courses(grid: ProgramGrid, current_semester_idx: int) -> list:
    """
    Find courses from earlier semesters that should have been completed
    but weren't (out-of-sequence gaps).

    Returns list of (semester_label, GridCourse) tuples for gap courses.
    Excludes courses that are currently in progress or fully planned.
    """
    gaps = []
    for i, semester in enumerate(grid.semesters):
        if i >= current_semester_idx:
            break
        for course in semester.courses:
            if not _is_done_or_active(course):
                # This is a gap — should have been done by now
                course.status = GridHighlight.LIGHT_RED
                gaps.append((semester.label, course))
    return gaps


def get_next_semester_courses(grid: ProgramGrid, semester_idx: int) -> list:
    """
    Get the courses scheduled for a specific semester in the grid.

    Returns only courses that haven't been completed and aren't in progress.
    """
    if semester_idx < 0 or semester_idx >= len(grid.semesters):
        return []

    semester = grid.semesters[semester_idx]
    return [c for c in semester.courses if not _is_done_or_active(c)]


def get_completion_stats(grid: ProgramGrid) -> dict:
    """Calculate completion statistics across the entire grid."""
    total_courses = 0
    completed = 0
    transfer = 0
    in_progress = 0
    gaps = 0
    remaining = 0

    for semester in grid.semesters:
        for course in semester.courses:
            total_courses += 1
            if course.status == GridHighlight.GREEN:
                completed += 1
            elif course.status == GridHighlight.TRANSFER:
                transfer += 1
            elif course.eval_status == CourseStatus.IN_PROGRESS:
                # Check eval_status early — in-progress courses may have
                # their grid status changed to ORANGE by the planner
                in_progress += 1
            elif course.eval_status == CourseStatus.FULLY_PLANNED:
                in_progress += 1
            elif course.status == GridHighlight.LIGHT_RED:
                gaps += 1
            else:
                remaining += 1

    done_total = completed + transfer
    return {
        "total": total_courses,
        "completed": completed,
        "transfer": transfer,
        "in_progress": in_progress,
        "gaps": gaps,
        "remaining": remaining,
        "percent_complete": round(done_total / total_courses * 100, 1) if total_courses > 0 else 0,
    }


def get_unmatched_courses(record: StudentRecord, grid: ProgramGrid) -> list:
    """
    Find eval courses that did NOT match any grid slot — 'other courses'.

    These represent credits the student has that don't fit the program grid,
    such as free electives, extra courses, or courses from a different program.

    Returns list of EvalCourse objects not matched to the grid.
    """
    # Collect all matched eval courses from the grid by identity
    matched_ids = set()
    for semester in grid.semesters:
        for course in semester.courses:
            if course.matched_eval_course is not None:
                matched_ids.add(id(course.matched_eval_course))

    unmatched = []
    for ec in record.eval_courses:
        if id(ec) not in matched_ids:
            unmatched.append(ec)

    return unmatched


def get_free_elective_courses(record: StudentRecord) -> list:
    """
    Get courses that are in the 'Free Elective' section of the evaluation.

    Returns list of EvalCourse objects from the free electives section.
    """
    free_elective_keywords = ["free elective", "free elect", "free elec"]
    return [
        ec for ec in record.eval_courses
        if any(kw in ec.section.lower() for kw in free_elective_keywords)
    ]


def get_all_remaining_grid_courses(grid: ProgramGrid) -> list:
    """
    Get ALL grid courses that are not yet completed and not in progress.

    Returns list of (semester_label, GridCourse) tuples for every incomplete
    course in the entire grid. Useful for the advisor picks dialog to show
    every available option.
    """
    remaining = []
    for semester in grid.semesters:
        for course in semester.courses:
            if not _is_done_or_active(course):
                remaining.append((semester.label, course))
    return remaining


def get_transfer_courses(record: StudentRecord) -> list:
    """
    Get all courses with Transfer / TE status from the evaluation.

    Returns list of EvalCourse objects that are transfers.
    """
    return [
        ec for ec in record.eval_courses
        if ec.status == CourseStatus.TRANSFER
    ]
