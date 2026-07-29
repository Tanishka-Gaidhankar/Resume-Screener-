from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .processor import process_resume_upload


def _get_frappe():
    """Dynamically import frappe module if available inside Frappe bench execution."""
    try:
        import frappe  # type: ignore
        return frappe
    except ImportError:
        return None


def find_resume_file_path(doc: Any) -> str | None:
    """Resolve file path for attached resume on a Frappe Job Applicant document."""
    frappe = _get_frappe()
    file_url = getattr(doc, "resume_attachment", None) or getattr(doc, "file_url", None)

    if not file_url and frappe and getattr(doc, "name", None):
        attached_files = frappe.get_all(
            "File",
            filters={
                "attached_to_doctype": "Job Applicant",
                "attached_to_name": doc.name,
            },
            fields=["file_url"],
            order_by="creation desc",
        )
        if attached_files:
            file_url = attached_files[0].get("file_url")

    if not file_url:
        return None

    if frappe:
        if file_url.startswith("/files/"):
            return frappe.get_site_path("public", file_url.lstrip("/"))
        if file_url.startswith("/private/files/"):
            return frappe.get_site_path(file_url.lstrip("/"))
        return frappe.get_site_path("public", "files", Path(file_url).name)

    if Path(file_url).exists():
        return str(Path(file_url))

    return None


def fetch_job_requirements(doc: Any) -> str:
    """Fetch description from linked Job Opening in Frappe if present."""
    frappe = _get_frappe()
    if not frappe:
        return ""

    job_opening = getattr(doc, "job_title", None) or getattr(doc, "job_opening", None)
    if job_opening:
        description = frappe.db.get_value("Job Opening", job_opening, "description")
        if description:
            return str(description)
    return ""


def autofill_job_applicant(doc: Any, method: str | None = None) -> None:
    """Frappe hook handler called when a Job Applicant document is saved/updated."""
    resume_path = find_resume_file_path(doc)
    if not resume_path or not os.path.exists(resume_path):
        return

    job_reqs = fetch_job_requirements(doc)

    existing_fields = {
        "custom_current_role": getattr(doc, "custom_current_role", ""),
        "custom_qualification": getattr(doc, "custom_qualification", ""),
        "custom_experience": getattr(doc, "custom_experience", ""),
        "permanent_location": getattr(doc, "permanent_location", ""),
        "current_location": getattr(doc, "current_location", ""),
        "lower_range": getattr(doc, "lower_range", ""),
        "upper_range": getattr(doc, "upper_range", ""),
        "custom_jp": getattr(doc, "custom_jp", ""),
        "custom_linkedin_profile": getattr(doc, "custom_linkedin_profile", ""),
        "custom_gap": getattr(doc, "custom_gap", False),
    }

    try:
        result = process_resume_upload(
            file_path=resume_path,
            job_requirements=job_reqs,
            existing_fields=existing_fields,
        )
    except Exception as exc:
        frappe = _get_frappe()
        if frappe:
            frappe.log_error(title="Resume Scanner Error", message=str(exc))
        return

    applicant_data = result.get("applicant", {})

    # Set Screening tab fields on Frappe doc
    for field in [
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
        "cover_letter",
    ]:
        if field in applicant_data and applicant_data[field] is not None:
            setattr(doc, field, applicant_data[field])

    # Set custom_skill_matrix_table child table
    matrix_items = applicant_data.get("custom_skill_matrix_table", [])
    if isinstance(matrix_items, list):
        doc.set("custom_skill_matrix_table", [])
        for item in matrix_items:
            doc.append(
                "custom_skill_matrix_table",
                {
                    "skill": item.get("skill", ""),
                    "skill_category": item.get("skill_category", ""),
                    "experience_level": item.get("experience_level", ""),
                    "rating": item.get("rating", ""),
                },
            )
