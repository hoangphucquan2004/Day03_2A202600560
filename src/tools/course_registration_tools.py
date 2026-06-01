import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional


DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "course_registration_mock.json"


@lru_cache(maxsize=1)
def _load_data() -> Dict[str, Any]:
    with DATA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _split_course_query(course_query: Any) -> List[str]:
    if isinstance(course_query, list):
        return [str(item).strip() for item in course_query if str(item).strip()]

    text = str(course_query).strip()
    if not text:
        return []

    parts = re.split(r"\s*(?:,|;|\band\b|\bva\b|\bvà\b|\+|&)\s*", text, flags=re.IGNORECASE)
    return [part.strip() for part in parts if part.strip()]


def _course_search_text(course: Dict[str, Any]) -> str:
    values = [course["course_code"], course["title"], *course.get("aliases", [])]
    return " | ".join(_normalize(value) for value in values)


def _find_courses(course_query: Any) -> List[Dict[str, Any]]:
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
    data = _load_data()
    return next((student for student in data["students"] if student["student_id"] == student_id), None)


def _section_summary(section: Dict[str, Any]) -> Dict[str, Any]:
    available_seats = max(section["capacity"] - section["enrolled"], 0)
    waitlist_seats = max(section["waitlist_capacity"] - section["waitlisted"], 0)

    if section["status"] == "open" and available_seats > 0:
        availability_status = "available"
    elif section["status"] in {"open", "waitlist_only"} and waitlist_seats > 0:
        availability_status = "waitlist_available"
    else:
        availability_status = section["status"]

    return {
        "section_id": section["section_id"],
        "instructor": section["instructor"],
        "schedule": section["schedule"],
        "capacity": section["capacity"],
        "enrolled": section["enrolled"],
        "available_seats": available_seats,
        "waitlist_capacity": section["waitlist_capacity"],
        "waitlisted": section["waitlisted"],
        "waitlist_available_seats": waitlist_seats,
        "status": section["status"],
        "availability_status": availability_status,
    }


def check_slots(course_query: Any, term: Optional[str] = None) -> Dict[str, Any]:
    """
    Check seat availability for one or more courses.

    Args:
        course_query: Course code/title/alias, or a list such as ["AI", "Data Science"].
        term: Optional term label. The mock dataset currently contains one term.
    """
    data = _load_data()
    courses = _find_courses(course_query)
    warnings = []

    if term and term != data["metadata"]["term"]:
        warnings.append(f"Dataset only contains term {data['metadata']['term']}; requested {term}.")

    if not courses:
        return {
            "ok": False,
            "query": course_query,
            "term": term or data["metadata"]["term"],
            "courses": [],
            "warnings": warnings,
            "errors": ["No matching course found."],
        }

    results = []
    for course in courses:
        sections = [_section_summary(section) for section in course["sections"]]
        has_available_section = any(section["availability_status"] == "available" for section in sections)
        has_waitlist = any(section["availability_status"] == "waitlist_available" for section in sections)

        if has_available_section:
            availability_status = "available"
        elif has_waitlist:
            availability_status = "waitlist_available"
        else:
            availability_status = "unavailable"

        results.append(
            {
                "course_code": course["course_code"],
                "title": course["title"],
                "credits": course["credits"],
                "department": course["department"],
                "prerequisites": course["prerequisites"],
                "sections": sections,
                "availability_status": availability_status,
            }
        )

    return {
        "ok": True,
        "query": course_query,
        "term": term or data["metadata"]["term"],
        "courses": results,
        "warnings": warnings,
        "errors": [],
    }


def get_tuition(course_code: Any, student_id: str) -> Dict[str, Any]:
    """
    Calculate estimated tuition for one or more courses for a student.

    Args:
        course_code: Course code/title/alias, or a list such as ["AI3010", "DATA3020"].
        student_id: Student id used to determine domestic/international tuition.
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


def get_course_registration_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": "check_slots",
            "description": (
                "Check availability for one or more VinUni courses. "
                "Input JSON: {\"course_query\": \"AI và Data Science\"} "
                "or {\"course_query\": [\"AI\", \"Data Science\"]}."
            ),
            "function": check_slots,
        },
        {
            "name": "get_tuition",
            "description": (
                "Calculate estimated tuition and fees for one or more courses "
                "for a given student_id. Input JSON: "
                "{\"course_code\": [\"AI3010\", \"DATA3020\"], \"student_id\": \"2A202600713\"}."
            ),
            "function": get_tuition,
        },
    ]
