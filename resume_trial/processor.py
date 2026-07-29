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


def build_applicant_payload(existing_fields: dict[str, Any], llm_response: dict[str, Any]) -> dict[str, Any]:
    applicant = copy.deepcopy(existing_fields)
    fields = llm_response.get("fields", {})

    for field in FIELDS_TO_EXTRACT:
        if not applicant.get(field):
            applicant[field] = fields.get(field, "" if field != "custom_gap" else False)

    applicant["custom_skill_matrix_table"] = llm_response.get("custom_skill_matrix_table", [])
    applicant["cover_letter"] = llm_response.get("cover_letter", "")

    return applicant
