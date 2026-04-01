"""
Data models for the Course Tracker application.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CourseStatus(Enum):
    COMPLETED = "completed"
    TRANSFER = "transfer"
    IN_PROGRESS = "in_progress"
    NOT_STARTED = "not_started"
    FULFILLED = "fulfilled"
    FULLY_PLANNED = "fully_planned"
    DROPPED = "dropped"


class GridHighlight(Enum):
    GREEN = "green"         # Completed
    TRANSFER = "transfer"   # Transfer / TE credit
    ORANGE = "orange"       # Planned for next semester
    LIGHT_RED = "light_red" # Gap / out of sequence
    NONE = "none"           # Future / not yet relevant


@dataclass
class EvalCourse:
    """A course extracted from the program evaluation PDF."""
    code: str                      # e.g. "GD*3010"
    status: CourseStatus
    grade: str = ""
    is_transfer: bool = False
    section: str = ""              # Which section of the eval it came from
    credits: int = 3

    @property
    def normalized_code(self) -> str:
        """Convert GD*3010 -> GD 3010 for matching."""
        return self.code.replace("*", " ")

    @property
    def department(self) -> str:
        """Extract department prefix: GD*3010 -> GD"""
        return self.code.split("*")[0] if "*" in self.code else self.code.split(" ")[0]

    @property
    def course_number(self) -> int:
        """Extract course number: GD*3010 -> 3010"""
        try:
            parts = self.code.replace("*", " ").split()
            if len(parts) >= 2:
                return int(parts[1])
        except (ValueError, IndexError):
            pass
        return 0


@dataclass
class GridCourse:
    """A course slot in the program's 4-year grid."""
    code: str
    name: str
    credits: int
    category: str
    match_codes: list = field(default_factory=list)
    is_choice: bool = False
    is_elective_slot: bool = False
    is_ge_category: bool = False
    elective_group: str = ""
    ge_category: str = ""
    slot_number: int = 0
    note: str = ""
    credits_range: list = field(default_factory=list)

    # Matching results (filled in by matcher)
    status: GridHighlight = GridHighlight.NONE
    matched_eval_course: Optional[EvalCourse] = None
    eval_status: Optional[CourseStatus] = None


@dataclass
class Semester:
    """A semester in the 4-year grid."""
    year: int
    term: str       # "Fall", "Spring", "Summer"
    target_credits: int
    courses: list = field(default_factory=list)  # List[GridCourse]

    @property
    def label(self) -> str:
        return f"Year {self.year} - {self.term}"

    @property
    def sort_key(self) -> tuple:
        term_order = {"Fall": 0, "Spring": 1, "Summer": 2}
        return (self.year, term_order.get(self.term, 3))


@dataclass
class ProgramGrid:
    """The full program grid configuration."""
    program_name: str
    program_code: str
    school: str
    university: str
    total_credits: int
    semesters: list = field(default_factory=list)  # List[Semester]
    elective_definitions: dict = field(default_factory=dict)
    ge_category_definitions: dict = field(default_factory=dict)
    department: str = ""


@dataclass
class SemesterPlan:
    """A recommended next-semester course plan."""
    semester_label: str       # e.g. "Fall 2026"
    courses: list = field(default_factory=list)       # List[GridCourse]
    makeup_courses: list = field(default_factory=list) # Courses from earlier semesters
    total_credits: int = 0
    notes: list = field(default_factory=list)

    def compute_total(self):
        self.total_credits = sum(c.credits for c in self.courses) + \
                             sum(c.credits for c in self.makeup_courses)


@dataclass
class StudentRecord:
    """Complete student analysis."""
    student_name: str = ""
    student_id: str = ""
    gpa: float = 0.0
    total_credits_earned: int = 0
    total_credits_required: int = 120
    program_name: str = ""
    eval_courses: list = field(default_factory=list)     # List[EvalCourse]
    grid: Optional[ProgramGrid] = None
    current_semester_index: int = -1
    semester_plan: Optional[SemesterPlan] = None
    gap_courses: list = field(default_factory=list)      # Out-of-sequence courses
    # Section-level completion markers: section_name -> (completed, total)
    # e.g. {"GE Soc Science Ele": (1, 1), "GE Science & Math": (2, 2)}
    section_completions: dict = field(default_factory=dict)
    # Course substitutions: original_code -> replacement_code
    # e.g. {"AH*3740": "FEX*1000"}
    substitutions: dict = field(default_factory=dict)
