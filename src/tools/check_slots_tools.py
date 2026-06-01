"""
Tool for checking course slot availability.
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


def _contains_phrase(text: str, phrase: str) -> bool:
    """Return True when phrase appears as normalized word sequence."""
    if not phrase:
        return False
    return re.search(rf"(^|\s){re.escape(phrase)}($|\s)", text) is not None


def _find_courses(course_query: Any) -> List[Dict[str, Any]]:
    """Find courses matching the given query."""
    data = _load_data()
    queries = _split_course_query(course_query)
    matches: List[Dict[str, Any]] = []
    seen = set()

    for query in queries:
        normalized_query = _normalize(query)
        for course in data["courses"]:
            aliases = [_normalize(alias) for alias in course.get("aliases", [])]
            course_code = _normalize(course["course_code"])
            title = _normalize(course["title"])
            search_text = _course_search_text(course)
            code_match = normalized_query == course_code or _contains_phrase(normalized_query, course_code)
            alias_match = normalized_query in aliases or any(
                _contains_phrase(normalized_query, alias) for alias in aliases
            )
            title_match = normalized_query == title or _contains_phrase(normalized_query, title)
            substring_match = normalized_query and normalized_query in search_text

            if code_match or alias_match or title_match or substring_match:
                if course["course_code"] not in seen:
                    matches.append(course)
                    seen.add(course["course_code"])
                break

    return matches


def _section_summary(section: Dict[str, Any]) -> Dict[str, Any]:
    """Create a summary of section availability."""
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

    Returns:
        Dictionary with course availability information.
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


def get_check_slots_tool() -> Dict[str, Any]:
    """Get the check_slots tool definition."""
    return {
        "name": "check_slots",
        "description": (
            "Check availability for one or more VinUni courses. "
            "Input JSON: {\"course_query\": \"AI và Data Science\"} "
            "or {\"course_query\": [\"AI\", \"Data Science\"]}."
        ),
        "function": check_slots,
    }
