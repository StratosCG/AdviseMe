"""
Load and manage program grid configurations from JSON files.
Handles loading pre-built configs and (future) auto-detection from PDFs.
"""
import json
import os
import sys
from typing import Optional

from core.models import ProgramGrid, Semester, GridCourse


def load_program_grid(json_path: str) -> ProgramGrid:
    """
    Load a program grid configuration from a JSON file.

    Args:
        json_path: Path to the program's JSON configuration file.

    Returns:
        ProgramGrid object with all semester and course data.
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    grid = ProgramGrid(
        program_name=data.get("program_name", ""),
        program_code=data.get("program_code", ""),
        school=data.get("school", ""),
        university=data.get("university", ""),
        total_credits=data.get("total_credits", 120),
        elective_definitions=data.get("elective_definitions", {}),
        ge_category_definitions=data.get("ge_category_definitions", {}),
    )
    grid.department = data.get("department", "")

    for sem_data in data.get("semesters", []):
        semester = Semester(
            year=sem_data["year"],
            term=sem_data["term"],
            target_credits=sem_data.get("target_credits", 15),
        )

        for course_data in sem_data.get("courses", []):
            course = GridCourse(
                code=course_data["code"],
                name=course_data["name"],
                credits=course_data.get("credits", 3),
                category=course_data.get("category", ""),
                match_codes=course_data.get("match_codes", []),
                is_choice=course_data.get("is_choice", False),
                is_elective_slot=course_data.get("is_elective_slot", False),
                is_ge_category=course_data.get("is_ge_category", False),
                elective_group=course_data.get("elective_group", ""),
                ge_category=course_data.get("ge_category", ""),
                slot_number=course_data.get("slot_number", 0),
                note=course_data.get("note", ""),
                credits_range=course_data.get("credits_range", []),
            )
            semester.courses.append(course)

        grid.semesters.append(semester)

    return grid


def list_available_programs(programs_dir: str) -> list:
    """
    List all available program configurations.

    Args:
        programs_dir: Directory containing JSON program files.

    Returns:
        List of (filename, program_name) tuples.
    """
    programs = []
    if not os.path.isdir(programs_dir):
        return programs

    for filename in os.listdir(programs_dir):
        if not filename.endswith(".json") or filename == "faculty.json":
            continue
        filepath = os.path.join(programs_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Only include files that have semesters (actual program grids)
            if "semesters" not in data:
                continue
            name = data.get("program_name", filename.replace(".json", ""))
            programs.append((filepath, name))
        except (json.JSONDecodeError, IOError):
            continue

    return programs


def get_programs_dir() -> str:
    """Get the default programs directory path."""
    base = getattr(sys, '_MEIPASS', None)
    if base:
        return os.path.join(base, 'CourseTrackerApp', 'programs')
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "programs")


def load_faculty(programs_dir: str = None) -> dict:
    """
    Load faculty advisor data from faculty.json.

    Returns dict mapping department name -> list of advisor names.
    """
    if programs_dir is None:
        programs_dir = get_programs_dir()
    faculty_path = os.path.join(programs_dir, "faculty.json")
    if not os.path.isfile(faculty_path):
        return {}
    try:
        with open(faculty_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        result = {}
        for dept, info in data.get("departments", {}).items():
            result[dept] = info.get("faculty", [])
        return result
    except (json.JSONDecodeError, IOError):
        return {}


def get_faculty_for_department(department: str, programs_dir: str = None) -> list:
    """Get the list of faculty advisors for a specific department."""
    faculty = load_faculty(programs_dir)
    return faculty.get(department, [])


def save_program_grid(grid: ProgramGrid, json_path: str):
    """Save a program grid configuration to a JSON file."""
    data = {
        "program_name": grid.program_name,
        "program_code": grid.program_code,
        "school": grid.school,
        "university": grid.university,
        "total_credits": grid.total_credits,
        "elective_definitions": grid.elective_definitions,
        "ge_category_definitions": grid.ge_category_definitions,
        "semesters": [],
    }

    for sem in grid.semesters:
        sem_data = {
            "year": sem.year,
            "term": sem.term,
            "target_credits": sem.target_credits,
            "courses": [],
        }
        for c in sem.courses:
            course_data = {
                "code": c.code,
                "name": c.name,
                "credits": c.credits,
                "category": c.category,
                "match_codes": c.match_codes,
            }
            if c.is_choice:
                course_data["is_choice"] = True
            if c.is_elective_slot:
                course_data["is_elective_slot"] = True
                course_data["elective_group"] = c.elective_group
                course_data["slot_number"] = c.slot_number
            if c.is_ge_category:
                course_data["is_ge_category"] = True
                course_data["ge_category"] = c.ge_category
            if c.note:
                course_data["note"] = c.note
            if c.credits_range:
                course_data["credits_range"] = c.credits_range
            sem_data["courses"].append(course_data)
        data["semesters"].append(sem_data)

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
