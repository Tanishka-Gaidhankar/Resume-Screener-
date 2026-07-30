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


import re
import tempfile
import requests


def download_resume_from_url(url: str) -> str | None:
    """Download a file from an HTTP/HTTPS URL or Google Drive link to a local temp file."""
    frappe = _get_frappe()
    download_url = url.strip()

    # Convert Google Drive file view links to direct download link
    if "drive.google.com" in download_url or "docs.google.com" in download_url:
        match = re.search(r"/d/([a-zA-Z0-9_-]+)", download_url) or re.search(r"id=([a-zA-Z0-9_-]+)", download_url)
        if match:
            file_id = match.group(1)
            download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

    try:
        session = requests.Session()
        res = session.get(download_url, stream=True, timeout=30, headers={"User-Agent": "Mozilla/5.0"})

        # Handle Google Drive virus scan warning redirect cookie if needed
        for key, value in res.cookies.items():
            if key.startswith("download_warning"):
                confirm_url = f"{download_url}&confirm={value}"
                res = session.get(confirm_url, stream=True, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
                break

        res.raise_for_status()

        ext = ".pdf"
        content_type = res.headers.get("Content-Type", "").lower()
        if "word" in content_type or "docx" in content_type or url.endswith(".docx"):
            ext = ".docx"
        elif "plain" in content_type or "text" in content_type or url.endswith(".txt"):
            ext = ".txt"

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        for chunk in res.iter_content(chunk_size=8192):
            if chunk:
                temp_file.write(chunk)
        temp_file.close()
        return temp_file.name
    except Exception as exc:
        if frappe:
            frappe.log_error(title="Resume Scanner URL Download Error", message=f"Failed to download from '{url}': {exc}")
        return None


def find_resume_file_path(doc: Any) -> str | None:
    """Resolve file path or download remote URL for attached resume on a Frappe Job Applicant document."""
    frappe = _get_frappe()

    # Collect candidate file paths or URLs from all potential resume fields
    possible_values = []
    for fieldname in [
        "resume_attachment",
        "resume_link",
        "file_url",
        "resume",
        "custom_resume_link",
        "attachment",
        "link",
    ]:
        val = getattr(doc, fieldname, None)
        if val and isinstance(val, str) and val.strip():
            possible_values.append(val.strip())

    # 1. Check if any value is an HTTP/HTTPS URL or Google Drive link
    for val in possible_values:
        if val.startswith("http://") or val.startswith("https://") or "drive.google.com" in val or "docs.google.com" in val:
            temp_path = download_resume_from_url(val)
            if temp_path and os.path.exists(temp_path):
                return temp_path

    # 2. Check File doctype attached records in Frappe DB
    if frappe and getattr(doc, "name", None):
        file_records = []
        for val in possible_values:
            if not val.startswith("http://") and not val.startswith("https://"):
                file_records = frappe.get_all("File", filters={"file_url": val}, fields=["name", "file_url"])
                if file_records:
                    break

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

            file_url_val = file_records[0].get("file_url")
            if file_url_val:
                possible_values.insert(0, file_url_val)

    # 3. Check local file paths on Frappe site
    for val in possible_values:
        if val.startswith("http://") or val.startswith("https://"):
            continue

        if Path(val).exists():
            return str(Path(val))

        if frappe:
            clean_url = val.lstrip("/")
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






