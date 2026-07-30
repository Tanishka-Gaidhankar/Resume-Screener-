from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from .file_reader import extract_text
from .llm_client import GroqClient


FIELDS_TO_EXTRACT = [
    "custom_current_role",
    "custom_qualification",
    "custom_experience",
    "permanent_location",
    "current_location",
    "lower_range",
    "upper_range",
    "custom_jp",
    "custom_linkedin_profile",
    "custom_gap",
    "rating",
    "applicant_rating",
]



def process_resume_upload(*, file_path: str | Path, job_requirements: str | list[dict[str, Any]] | None, existing_fields: dict[str, Any]) -> dict[str, Any]:
    """Run trial resume processing pipeline and return the applicant payload for Frappe autofill."""
    resume_text = extract_text(file_path)
    client = GroqClient()
    response = client.extract(resume_text=resume_text, job_requirements=job_requirements, existing_fields=existing_fields)

    validated = validate_schema(response)
    applicant = build_applicant_payload(existing_fields, validated)
    return {"applicant": applicant}


def validate_schema(response: dict[str, Any]) -> dict[str, Any]:
    """Validate the LLM payload against the Frappe custom field schema."""
    if not isinstance(response, dict):
        raise ValueError("LLM response must be an object")

    fields = response.get("fields")
    if not isinstance(fields, dict):
        raise ValueError("Missing fields object")

    for field in FIELDS_TO_EXTRACT:
        if field not in fields:
            raise ValueError(f"Missing field: {field}")

    skill_matrix = response.get("custom_skill_matrix_table")
    if not isinstance(skill_matrix, list):
        raise ValueError("Missing or invalid custom_skill_matrix_table")

    for item in skill_matrix:
        if not isinstance(item, dict):
            raise ValueError("Items in custom_skill_matrix_table must be objects")
        for key in ["skill", "skill_category", "experience_level", "rating"]:
            if key not in item:
                raise ValueError(f"Missing key '{key}' in custom_skill_matrix_table item")

    cover_letter = response.get("cover_letter")
    if not isinstance(cover_letter, str):
        raise ValueError("Missing or invalid cover_letter string")

    return response


ALLOWED_SKILL_CATEGORIES = [
    "Personal",
    "Technical",
    "Professional",
    "Planning",
    "Leadership",
    "Legal",
    "Digital / IT",
    "Commercial",
]


def sanitize_skill_category(raw_category: str | None) -> str:
    """Sanitize skill category to strictly match Frappe select options."""
    if not raw_category or not isinstance(raw_category, str):
        return "Technical"

    cat = raw_category.strip()
    if cat in ALLOWED_SKILL_CATEGORIES:
        return cat

    cat_lower = cat.lower()
    if any(k in cat_lower for k in ["digital", "it", "software", "drafting", "cad", "programming", "tool", "excel", "code", "dev"]):
        return "Digital / IT"
    if any(k in cat_lower for k in ["tech", "engineering", "civil", "rcc", "structure"]):
        return "Technical"
    if any(k in cat_lower for k in ["plan", "project", "schedule", "mgmt", "management"]):
        return "Planning"
    if any(k in cat_lower for k in ["lead", "team", "manager"]):
        return "Leadership"
    if any(k in cat_lower for k in ["legal", "law", "contract"]):
        return "Legal"
    if any(k in cat_lower for k in ["commercial", "finance", "billing", "cost", "account"]):
        return "Commercial"
    if any(k in cat_lower for k in ["personal", "soft", "communication"]):
        return "Personal"
    if any(k in cat_lower for k in ["professional"]):
        return "Professional"

    return "Technical"


def build_applicant_payload(existing_fields: dict[str, Any], llm_response: dict[str, Any]) -> dict[str, Any]:
    applicant = copy.deepcopy(existing_fields)
    fields = llm_response.get("fields", {})

    for field in FIELDS_TO_EXTRACT:
        if not applicant.get(field):
            applicant[field] = fields.get(field, "" if field != "custom_gap" else False)

    raw_matrix = llm_response.get("custom_skill_matrix_table", [])
    sanitized_matrix = []
    if isinstance(raw_matrix, list):
        for item in raw_matrix:
            if isinstance(item, dict):
                sanitized_item = copy.deepcopy(item)
                sanitized_item["skill_category"] = sanitize_skill_category(item.get("skill_category"))
                sanitized_matrix.append(sanitized_item)

    applicant["custom_skill_matrix_table"] = sanitized_matrix
    applicant["cover_letter"] = llm_response.get("cover_letter", "")

    return applicant

