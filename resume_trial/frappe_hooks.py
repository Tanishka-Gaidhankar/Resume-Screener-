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

    if frappe and getattr(doc, "name", None):
        file_records = []
        if file_url:
            file_records = frappe.get_all("File", filters={"file_url": file_url}, fields=["name", "file_url"])
        if not file_records:
            file_records = frappe.get_all(
                "File",
                filters={
                    "attached_to_doctype": "Job Applicant",
                    "attached_to_name": doc.name,
                },
                fields=["name", "file_url"],
                order_by="creation desc",
            )
        if file_records:
            try:
                file_doc = frappe.get_doc("File", file_records[0].name)
                full_path = file_doc.get_full_path()
                if full_path and os.path.exists(full_path):
                    return full_path
            except Exception:
                pass
            if not file_url:
                file_url = file_records[0].get("file_url")

    if not file_url:
        return None

    if frappe:
        clean_url = file_url.lstrip("/")
        site_path = frappe.get_site_path(clean_url)
        if os.path.exists(site_path):
            return site_path

        filename = Path(clean_url).name
        if "private/files/" in clean_url or clean_url.startswith("private/"):
            priv_path = frappe.get_site_path("private", "files", filename)
            if os.path.exists(priv_path):
                return priv_path

        pub_path = frappe.get_site_path("public", "files", filename)
        if os.path.exists(pub_path):
            return pub_path

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
    frappe = _get_frappe()
    resume_path = find_resume_file_path(doc)
    if not resume_path or not os.path.exists(resume_path):
        if frappe and getattr(doc, "resume_attachment", None):
            frappe.msgprint(f"Resume Scanner: Resume file path could not be located on server for '{doc.resume_attachment}'.")
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
        "rating": getattr(doc, "rating", ""),
        "applicant_rating": getattr(doc, "applicant_rating", ""),
    }

    try:
        result = process_resume_upload(
            file_path=resume_path,
            job_requirements=job_reqs,
            existing_fields=existing_fields,
        )
    except Exception as exc:
        if frappe:
            frappe.log_error(title="Resume Scanner Error", message=str(exc))
            frappe.msgprint(f"Resume Scanner AI Error: {exc}")
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
        "rating",
        "applicant_rating",
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


def on_file_attached(doc: Any, method: str | None = None) -> None:
    """Trigger auto-fill when a File is attached directly to a Job Applicant."""
    if getattr(doc, "attached_to_doctype", None) == "Job Applicant" and getattr(doc, "attached_to_name", None):
        frappe = _get_frappe()
        if frappe:
            try:
                applicant = frappe.get_doc("Job Applicant", doc.attached_to_name)
                autofill_job_applicant(applicant)
                applicant.save(ignore_permissions=True)
            except Exception as exc:
                frappe.log_error(title="Resume Scanner File Attachment Error", message=str(exc))






