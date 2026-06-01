"""
Tool for calculating course tuition fees.
"""
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional


DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "course_registration_mock.json"


@lru_cache(maxsize=1)
def _load_data() -> Dict[str, Any]:
    """Load course registration mock data."""
    with DATA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def _normalize(value: str) -> str:
    """Normalize string for search matching."""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _split_course_query(course_query: Any) -> List[str]:
    """Split course query into individual course identifiers."""
    if isinstance(course_query, list):
        return [str(item).strip() for item in course_query if str(item).strip()]

    text = str(course_query).strip()
    if not text:
        return []

    parts = re.split(r"\s*(?:,|;|\band\b|\bva\b|\bvà\b|\+|&)\s*", text, flags=re.IGNORECASE)
    return [part.strip() for part in parts if part.strip()]


def _course_search_text(course: Dict[str, Any]) -> str:
    """Generate searchable text from course data."""
    values = [course["course_code"], course["title"], *course.get("aliases", [])]
    return " | ".join(_normalize(value) for value in values)


def _find_courses(course_query: Any) -> List[Dict[str, Any]]:
    """Find courses matching the given query."""
    data = _load_data()
    queries = _split_course_query(course_query)
    matches: List[Dict[str, Any]] = []
    seen = set()

    for query in queries:
        normalized_query = _normalize(query)
        for course in data["courses"]:
            search_text = _course_search_text(course)
            code_match = normalized_query == _normalize(course["course_code"])
            alias_match = normalized_query in [_normalize(alias) for alias in course.get("aliases", [])]
            title_match = normalized_query == _normalize(course["title"])
            substring_match = normalized_query and normalized_query in search_text

            if code_match or alias_match or title_match or substring_match:
                if course["course_code"] not in seen:
                    matches.append(course)
                    seen.add(course["course_code"])
                break

    return matches


def _find_student(student_id: str) -> Optional[Dict[str, Any]]:
    """Find student by ID."""
    data = _load_data()
    return next((student for student in data["students"] if student["student_id"] == student_id), None)


def get_tuition(course_code: Any, student_id: str) -> Dict[str, Any]:
    """
    Calculate estimated tuition for one or more courses for a student.

    Args:
        course_code: Course code/title/alias, or a list such as ["AI3010", "DATA3020"].
        student_id: Student ID used to determine domestic/international tuition.

    Returns:
        Dictionary with tuition calculation details.
    """
    data = _load_data()
    student = _find_student(student_id)
    courses = _find_courses(course_code)

    if not student:
        return {
            "ok": False,
            "student_id": student_id,
            "courses": [],
            "currency": data["metadata"]["currency"],
            "estimated_total": 0,
            "errors": ["Student not found."],
        }

    if not courses:
        return {
            "ok": False,
            "student_id": student_id,
            "student_name": student["full_name"],
            "courses": [],
            "currency": data["metadata"]["currency"],
            "estimated_total": 0,
            "errors": ["No matching course found."],
        }

    tuition_key = f"{student['tuition_category']}_per_credit"
    course_totals = []
    estimated_total = 0

    for course in courses:
        tuition = course["tuition"]
        per_credit = tuition[tuition_key]
        base_tuition = per_credit * course["credits"]
        fees = {
            "lab_fee": tuition["lab_fee"],
            "material_fee": tuition["material_fee"],
        }
        course_total = base_tuition + sum(fees.values())
        estimated_total += course_total

        course_totals.append(
            {
                "course_code": course["course_code"],
                "title": course["title"],
                "credits": course["credits"],
                "tuition_category": student["tuition_category"],
                "per_credit": per_credit,
                "base_tuition": base_tuition,
                "fees": fees,
                "estimated_total": course_total,
            }
        )

    return {
        "ok": True,
        "student_id": student_id,
        "student_name": student["full_name"],
        "tuition_category": student["tuition_category"],
        "currency": data["metadata"]["currency"],
        "courses": course_totals,
        "estimated_total": estimated_total,
        "errors": [],
    }


def get_get_tuition_tool() -> Dict[str, Any]:
    """Get the get_tuition tool definition."""
    return {
        "name": "get_tuition",
        "description": (
            "Calculate estimated tuition and fees for one or more courses "
            "for a given student_id. Input JSON: "
            "{\"course_code\": [\"AI3010\", \"DATA3020\"], \"student_id\": \"2A202600713\"}."
        ),
        "function": get_tuition,
    }
