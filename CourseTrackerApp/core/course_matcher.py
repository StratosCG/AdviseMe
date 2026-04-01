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

    # Fifth pass: handle course substitutions
    # e.g. "FEX*1000 replaces AH*3740" means AH*3740 slot is satisfied
    _match_by_substitution(grid, record, matched_ids)

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
    Use section-level "X of Y Completed" markers to fill GE category slots.

    When GE sections are collapsed (Show Details not clicked), individual course
    codes aren't visible, but the section header says e.g. "1 of 1 Completed".
    We use this to mark the corresponding grid slot as completed.

    This maps GE category definitions' eval_section names to parser section names
    and checks if the section is fully completed.
    """
    if not hasattr(record, 'section_completions') or not record.section_completions:
        return

    # Build mapping from ge_category -> eval section keywords
    # The grid's ge_category_definitions have eval_section like "D. Soc Science Ele"
    # The parser's section names are like "GE Soc Science Ele"
    ge_section_map = {}
    for ge_cat, ge_def in grid.ge_category_definitions.items():
        eval_section = ge_def.get("eval_section", "")
        if eval_section:
            # Map both the raw eval_section key and the parser section name
            ge_section_map[ge_cat] = eval_section

    for semester in grid.semesters:
        for course in semester.courses:
            if not course.is_ge_category:
                continue
            if course.status != GridHighlight.NONE:
                continue  # Already matched

            ge_cat = course.ge_category
            eval_section_key = ge_section_map.get(ge_cat, "")
            if not eval_section_key:
                continue

            # Check if any section completion marker matches
            for section_name, (completed, total) in record.section_completions.items():
                # Match by checking if the eval_section substring appears
                # in the parser's section name (e.g. "Soc Science Ele" in
                # "GE Soc Science Ele")
                section_keyword = eval_section_key.split(". ", 1)[-1].lower()
                if section_keyword in section_name.lower() and completed >= total:
                    # Section is fully completed — create a synthetic course
                    synthetic = EvalCourse(
                        code=course.code,
                        status=CourseStatus.FULFILLED,
                        grade="",
                        section=section_name,
                    )
                    course.status = GridHighlight.GREEN
                    course.matched_eval_course = synthetic
                    course.eval_status = CourseStatus.FULFILLED
                    break


def _match_by_substitution(
    grid: ProgramGrid,
    record: StudentRecord,
    matched_ids: set
):
    """
    Handle course substitutions found in the evaluation PDF.

    When the PDF says "FEX*1000 replaces AH*3740", the AH*3740 grid slot
    should be marked as completed using the replacement course's status.
    """
    if not hasattr(record, 'substitutions') or not record.substitutions:
        return

    for semester in grid.semesters:
        for course in semester.courses:
            if course.status != GridHighlight.NONE:
                continue  # Already matched

            # Check if any of this course's match codes has a substitution
            for match_code in course.match_codes:
                if match_code in record.substitutions:
                    replacement_code = record.substitutions[match_code]
                    # Find the replacement course in eval_courses
                    for ec in record.eval_courses:
                        if ec.code == replacement_code and ec.status in DONE_STATUSES:
                            synthetic = EvalCourse(
                                code=match_code,
                                status=ec.status,
                                grade=ec.grade,
                                is_transfer=ec.is_transfer,
                                section=ec.section,
                            )
                            course.status = _done_highlight(ec)
                            course.matched_eval_course = synthetic
                            course.eval_status = ec.status
                            break
                    if course.status != GridHighlight.NONE:
                        break


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
