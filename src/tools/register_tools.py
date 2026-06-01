"""
Tool for simulating course registration.
"""
import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "course_registration_mock.json"


@lru_cache(maxsize=1)
def _load_data() -> Dict[str, Any]:
    """Load course registration mock data."""
    with DATA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def _find_student(student_id: str) -> Optional[Dict[str, Any]]:
    """Find student by ID."""
    data = _load_data()
    return next((student for student in data["students"] if student["student_id"] == student_id), None)


def _find_section(section_id: str) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """Find section and its parent course."""
    data = _load_data()
    for course in data["courses"]:
        for section in course["sections"]:
            if section["section_id"] == section_id:
                return course, section
    return None


def _time_to_minutes(value: str) -> int:
    parsed = datetime.strptime(value, "%H:%M")
    return parsed.hour * 60 + parsed.minute


def _sections_overlap(first: Dict[str, Any], second: Dict[str, Any]) -> bool:
    """Check whether two sections overlap by day and time."""
    for first_meeting in first["schedule"]:
        for second_meeting in second["schedule"]:
            if first_meeting["day"] != second_meeting["day"]:
                continue
            first_start = _time_to_minutes(first_meeting["start"])
            first_end = _time_to_minutes(first_meeting["end"])
            second_start = _time_to_minutes(second_meeting["start"])
            second_end = _time_to_minutes(second_meeting["end"])
            if first_start < second_end and second_start < first_end:
                return True
    return False


def _missing_prerequisites(student: Dict[str, Any], course: Dict[str, Any]) -> List[str]:
    completed_courses = set(student.get("completed_courses", []))
    return [
        prerequisite
        for prerequisite in course.get("prerequisites", [])
        if prerequisite not in completed_courses
    ]


def _section_availability(section: Dict[str, Any]) -> Dict[str, Any]:
    available_seats = max(section["capacity"] - section["enrolled"], 0)
    waitlist_available_seats = max(section["waitlist_capacity"] - section["waitlisted"], 0)

    if section["status"] == "open" and available_seats > 0:
        availability_status = "available"
    elif section["status"] in {"open", "waitlist_only"} and waitlist_available_seats > 0:
        availability_status = "waitlist_available"
    else:
        availability_status = section["status"]

    return {
        "available_seats": available_seats,
        "waitlist_available_seats": waitlist_available_seats,
        "availability_status": availability_status,
    }


def register(student_id: str, section_ids: List[str], confirm_payment: bool = False) -> Dict[str, Any]:
    """
    Simulate final course registration for selected sections.

    This tool validates against the mock dataset and returns the outcome without
    mutating the JSON file.
    """
    data = _load_data()
    student = _find_student(student_id)
    errors: List[str] = []
    warnings: List[str] = []
    registered_sections: List[Dict[str, Any]] = []
    waitlisted_sections: List[Dict[str, Any]] = []

    if not student:
        return {
            "ok": False,
            "registration_status": "failed",
            "student_id": student_id,
            "registered_sections": [],
            "waitlisted_sections": [],
            "warnings": [],
            "errors": ["Student not found."],
        }

    if student["account_status"] in data["registration_rules"]["block_registration_when_account_status"]:
        errors.append(f"Student account status is {student['account_status']}.")

    blocking_holds = [
        hold["hold_code"]
        for hold in student.get("holds", [])
        if hold["hold_code"] in data["registration_rules"]["block_registration_when_holds"]
    ]
    if blocking_holds:
        errors.append(f"Registration blocked by holds: {', '.join(blocking_holds)}.")

    if data["registration_rules"]["payment_required_for_final_registration"] and not confirm_payment:
        errors.append("Payment confirmation is required before final registration.")

    if not section_ids:
        errors.append("At least one section_id is required.")

    selected: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for section_id in section_ids:
        found = _find_section(section_id)
        if not found:
            errors.append(f"Section {section_id} not found.")
            continue
        selected.append(found)

    existing_section_ids = set(student.get("current_registrations", []))
    selected_section_ids = [section["section_id"] for _, section in selected]
    duplicate_sections = sorted(existing_section_ids.intersection(selected_section_ids))
    if duplicate_sections:
        errors.append(f"Student is already registered for: {', '.join(duplicate_sections)}.")

    if data["registration_rules"]["require_prerequisites"]:
        for course, _section in selected:
            missing = _missing_prerequisites(student, course)
            if missing:
                errors.append(f"{course['course_code']} prerequisites not met: {', '.join(missing)}.")

    if data["registration_rules"]["prevent_time_conflicts"]:
        for index, (_first_course, first_section) in enumerate(selected):
            for _second_course, second_section in selected[index + 1:]:
                if _sections_overlap(first_section, second_section):
                    errors.append(
                        f"Time conflict between {first_section['section_id']} and {second_section['section_id']}."
                    )

    if errors:
        return {
            "ok": False,
            "registration_status": "failed",
            "student_id": student_id,
            "student_name": student["full_name"],
            "registered_sections": [],
            "waitlisted_sections": [],
            "warnings": warnings,
            "errors": errors,
        }

    for course, section in selected:
        availability = _section_availability(section)
        record = {
            "registration_id": f"REG-MOCK-{student_id}-{section['section_id']}",
            "course_code": course["course_code"],
            "title": course["title"],
            "section_id": section["section_id"],
            "status": availability["availability_status"],
        }

        if availability["availability_status"] == "available":
            registered_sections.append({**record, "status": "registered"})
        elif availability["availability_status"] == "waitlist_available" and data["registration_rules"]["allow_waitlist"]:
            waitlisted_sections.append({**record, "status": "waitlisted"})
            warnings.append(f"{section['section_id']} has no open seat; student was added to waitlist.")
        else:
            errors.append(f"{section['section_id']} is not available for registration.")

    if errors and not registered_sections and not waitlisted_sections:
        registration_status = "failed"
    elif errors:
        registration_status = "partial"
    elif waitlisted_sections and not registered_sections:
        registration_status = "waitlisted"
    elif waitlisted_sections:
        registration_status = "registered_with_waitlist"
    else:
        registration_status = "registered"

    return {
        "ok": not errors,
        "registration_status": registration_status,
        "student_id": student_id,
        "student_name": student["full_name"],
        "registered_sections": registered_sections,
        "waitlisted_sections": waitlisted_sections,
        "warnings": warnings,
        "errors": errors,
    }


def get_register_tool() -> Dict[str, Any]:
    """Get the register tool definition."""
    return {
        "name": "register",
        "description": (
            "Attempt final registration or waitlisting for selected section_ids. "
            "Input JSON: {\"student_id\": \"2A202600713\", "
            "\"section_ids\": [\"AI3010-01\", \"DATA3020-02\"], \"confirm_payment\": true}."
        ),
        "function": register,
    }
