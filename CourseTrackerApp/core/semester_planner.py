"""
Semester planner with out-of-sequence course handling.

Determines the next semester's course plan, identifies gaps,
and provides options for handling credit overload when a student
is behind schedule.
"""
from datetime import datetime
from typing import Optional

from core.models import (
    ProgramGrid, SemesterPlan, GridCourse, GridHighlight, CourseStatus
)
from core.course_matcher import (
    detect_current_semester, find_gap_courses, get_next_semester_courses
)


# Strategy options for handling out-of-sequence courses
STRATEGY_CAP_18 = "cap_18"
STRATEGY_ADVISOR_PICKS = "advisor_picks"
STRATEGY_SWAP = "swap"

MAX_CREDITS_CAP = 18


def auto_detect_semester_label(credits_earned: int) -> str:
    """
    Guess the upcoming semester based on current date and credits.

    Returns a label like "Fall 2026", "Spring 2027", or "Summer 2026".

    Academic calendar heuristic:
      Jan–Apr  → currently in Spring  → next is Summer (same year)
      May–Jul  → currently in Summer  → next is Fall   (same year)
      Aug–Dec  → currently in Fall    → next is Spring (next year)
    """
    now = datetime.now()
    month = now.month

    if month <= 4:
        # Spring semester → next is Summer
        return f"Summer {now.year}"
    elif month <= 7:
        # Summer → next is Fall
        return f"Fall {now.year}"
    else:
        # Fall → next is Spring of next year
        return f"Spring {now.year + 1}"


def auto_detect_semester_index(grid: ProgramGrid, credits_earned: int = 0) -> int:
    """
    Detect which semester index the student should be planning for next.
    """
    return detect_current_semester(grid, credits_earned)


def generate_plan(
    grid: ProgramGrid,
    semester_idx: int,
    semester_label: str,
    strategy: str = STRATEGY_CAP_18,
    advisor_selected_courses: list = None,
) -> SemesterPlan:
    """
    Generate a next-semester course plan.

    Args:
        grid: Program grid with course statuses filled in.
        semester_idx: Index of the semester to plan for.
        semester_label: Human-readable label (e.g., "Fall 2026").
        strategy: How to handle out-of-sequence courses.
        advisor_selected_courses: If strategy is advisor_picks, the courses
                                   the advisor chose to include.

    Returns:
        SemesterPlan with scheduled and makeup courses.
    """
    plan = SemesterPlan(semester_label=semester_label)

    # Get the courses normally scheduled for this semester
    scheduled = get_next_semester_courses(grid, semester_idx)

    # Find gap courses from earlier semesters
    gaps = find_gap_courses(grid, semester_idx)
    gap_courses = [course for (_, course) in gaps]

    if strategy == STRATEGY_CAP_18:
        plan = _plan_with_cap(scheduled, gap_courses, semester_label)
    elif strategy == STRATEGY_SWAP:
        plan = _plan_with_swap(scheduled, gap_courses, semester_label)
    elif strategy == STRATEGY_ADVISOR_PICKS:
        if advisor_selected_courses:
            plan = _plan_advisor_picks(
                scheduled, gap_courses, advisor_selected_courses, semester_label
            )
        else:
            # Return all options for the advisor to choose from
            plan = _plan_show_all(scheduled, gap_courses, semester_label)
    else:
        plan = _plan_with_cap(scheduled, gap_courses, semester_label)

    # Mark planned courses as orange on the grid
    # Never overwrite in-progress courses
    for course in plan.courses + plan.makeup_courses:
        if course.eval_status not in (CourseStatus.IN_PROGRESS, CourseStatus.FULLY_PLANNED):
            course.status = GridHighlight.ORANGE

    plan.compute_total()
    return plan


def _plan_with_cap(
    scheduled: list,
    gap_courses: list,
    semester_label: str
) -> SemesterPlan:
    """
    Strategy: Add missed courses + cap at 18 credits.
    Prioritize gap courses, then fill with scheduled courses.
    """
    plan = SemesterPlan(semester_label=semester_label)
    running_credits = 0

    # First, add gap courses (prioritize catching up)
    for course in gap_courses:
        if running_credits + course.credits <= MAX_CREDITS_CAP:
            plan.makeup_courses.append(course)
            running_credits += course.credits

    # Then add normally scheduled courses
    for course in scheduled:
        if running_credits + course.credits <= MAX_CREDITS_CAP:
            plan.courses.append(course)
            running_credits += course.credits

    if len(gap_courses) > len(plan.makeup_courses):
        remaining_gaps = len(gap_courses) - len(plan.makeup_courses)
        plan.notes.append(
            f"{remaining_gaps} additional gap course(s) could not fit within "
            f"{MAX_CREDITS_CAP} credit limit and should be scheduled in a "
            f"subsequent semester."
        )

    if len(scheduled) > len(plan.courses):
        deferred = len(scheduled) - len(plan.courses)
        plan.notes.append(
            f"{deferred} scheduled course(s) were deferred to make room for "
            f"makeup courses."
        )

    return plan


def _plan_with_swap(
    scheduled: list,
    gap_courses: list,
    semester_label: str
) -> SemesterPlan:
    """
    Strategy: Push on-track courses back and add missed courses.
    Replace scheduled courses with gap courses to maintain similar credit load.
    """
    plan = SemesterPlan(semester_label=semester_label)

    # Calculate the target credit load from the scheduled semester
    target_credits = sum(c.credits for c in scheduled)

    # Start with gap courses
    running_credits = 0
    for course in gap_courses:
        if running_credits + course.credits <= target_credits:
            plan.makeup_courses.append(course)
            running_credits += course.credits

    # Fill remaining with scheduled courses
    for course in scheduled:
        if running_credits + course.credits <= target_credits:
            plan.courses.append(course)
            running_credits += course.credits

    deferred_scheduled = len(scheduled) - len(plan.courses)
    if deferred_scheduled > 0:
        plan.notes.append(
            f"{deferred_scheduled} on-track course(s) were pushed to the next "
            f"semester to accommodate {len(plan.makeup_courses)} makeup course(s)."
        )

    return plan


def _plan_advisor_picks(
    scheduled: list,
    gap_courses: list,
    selected_codes: list,
    semester_label: str
) -> SemesterPlan:
    """
    Strategy: Advisor manually selected which courses to include.
    """
    plan = SemesterPlan(semester_label=semester_label)

    selected_set = set(selected_codes)

    for course in scheduled:
        if course.code in selected_set:
            plan.courses.append(course)

    for course in gap_courses:
        if course.code in selected_set:
            plan.makeup_courses.append(course)

    return plan


def _plan_show_all(
    scheduled: list,
    gap_courses: list,
    semester_label: str
) -> SemesterPlan:
    """
    Return all available courses for the advisor to choose from.
    """
    plan = SemesterPlan(semester_label=semester_label)
    plan.courses = list(scheduled)
    plan.makeup_courses = list(gap_courses)
    plan.notes.append(
        "All available courses shown. Please select which courses "
        "to include in the final plan."
    )
    return plan



def get_strategy_options() -> list:
    """Return the available planning strategy options for the GUI."""
    return [
        (STRATEGY_CAP_18, "Add missed courses + cap at 18 credits",
         "Prioritize catching up on missed courses, but never exceed "
         "18 credit hours. Push remaining courses to next semester."),
        (STRATEGY_ADVISOR_PICKS, "Advisor picks courses manually",
         "View all available courses (scheduled + missed) and "
         "manually select which ones to include."),
        (STRATEGY_SWAP, "Swap: replace on-track with missed courses",
         "Push on-track scheduled courses back to accommodate missed "
         "courses, maintaining a similar credit load."),
    ]


def get_available_semesters(current_year: int = None) -> list:
    """
    Get a list of upcoming semester labels for the dropdown.

    Starts from the NEXT upcoming semester (not one already in progress)
    and returns about 2–3 years of options.

    Returns labels like ["Fall 2026", "Spring 2027", "Summer 2027", ...].
    """
    now = datetime.now()
    if current_year is None:
        current_year = now.year

    month = now.month

    # Determine the first upcoming semester (not currently in progress)
    # Jan–Apr → Summer is next  (Spring is current)
    # May–Jul → Fall is next    (Summer is current)
    # Aug–Dec → Spring is next  (Fall is current)
    if month <= 4:
        # Start from Summer of the current year
        start = ("Summer", current_year)
    elif month <= 7:
        # Start from Fall of the current year
        start = ("Fall", current_year)
    else:
        # Start from Spring of the next year
        start = ("Spring", current_year + 1)

    term_order = ["Spring", "Summer", "Fall"]
    semesters = []

    # Generate the next ~2.5 years of semesters starting from start
    term, year = start
    for _ in range(8):  # 8 entries ≈ 2.67 years
        semesters.append(f"{term} {year}")
        idx = term_order.index(term)
        if idx + 1 < len(term_order):
            term = term_order[idx + 1]
        else:
            term = term_order[0]
            year += 1

    return semesters
