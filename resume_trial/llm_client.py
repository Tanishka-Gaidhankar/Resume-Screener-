from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests


def _load_env_file() -> None:
    """Load variables from .env file into os.environ if not already set."""
    search_paths = [
        Path(".env"),
        Path.cwd() / ".env",
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent / ".env",
    ]
    try:
        import frappe  # type: ignore
        if hasattr(frappe, "get_site_path"):
            search_paths.insert(0, Path(frappe.get_site_path(".env")))
        if hasattr(frappe, "get_app_path"):
            search_paths.insert(0, Path(frappe.get_app_path("resume_trial", "..", ".env")))
    except Exception:
        pass

    for env_path in search_paths:
        if env_path.exists():
            try:
                content = env_path.read_text(encoding="utf-8")
                for line in content.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
                    elif ":" in line:
                        k, v = line.split(":", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            except Exception:
                pass


def normalize_job_requirements(job_requirements: str | list[dict[str, Any]] | None) -> str:
    if job_requirements is None:
        return ""
    if isinstance(job_requirements, str):
        return job_requirements
    if isinstance(job_requirements, list):
        return "\n".join(
            f"Role: {item.get('role', 'Unknown')}\nDescription: {item.get('description', '')}"
            for item in job_requirements
            if isinstance(item, dict)
        )
    return str(job_requirements)


def _get_frappe_api_key() -> str | None:
    try:
        import frappe  # type: ignore
        key = frappe.conf.get("groq_api_key") or frappe.conf.get("GROQ_API_KEY")
        if key:
            return str(key).strip()
    except Exception:
        pass
    return None



class GroqClient:
    """Groq API client for Frappe resume screening autofill."""

    def __init__(self, api_key: str | None = None):
        _load_env_file()
        self.api_key = api_key or os.getenv("GROQ_API_KEY") or _get_frappe_api_key()


    def extract(
        self,
        *,
        resume_text: str,
        job_requirements: str | list[dict[str, Any]] | None,
        existing_fields: dict[str, Any],
    ) -> dict[str, Any]:
        normalized_requirements = normalize_job_requirements(job_requirements)
        if not self.api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Please provide an API key in the environment or .env file."
            )

        return self._call_groq(
            resume_text=resume_text,
            job_requirements=normalized_requirements,
            existing_fields=existing_fields,
        )

    def _call_groq(
        self,
        *,
        resume_text: str,
        job_requirements: str,
        existing_fields: dict[str, Any],
    ) -> dict[str, Any]:
        user_prompt = (
            "You are an expert AI resume parser. Extract screening information and evaluate candidate job matching from the provided resume and target job requirements.\n\n"
            f"RESUME CONTENT:\n---\n{resume_text}\n---\n\n"
            f"JOB REQUIREMENTS:\n---\n{job_requirements}\n---\n\n"
            f"EXISTING APPLICANT FIELDS:\n{json.dumps(existing_fields)}\n\n"
            "INSTRUCTIONS:\n"
            "1. Extract Screening tab custom fields in an object named 'fields':\n"
            "   - 'custom_current_role': Candidate's current or recent role title (e.g. 'R.C.C. Draughtsman', 'MBA Candidate', or '' if none).\n"
            "   - 'custom_qualification': Highest academic qualification (e.g. 'Diploma in Civil Engineering', 'MBA in Finance', etc.).\n"
            "   - 'custom_experience': Total professional experience in years as string number (e.g. '8', '5', '0.5', or '' if fresher).\n"
            "   - 'permanent_location': Permanent location city/state (e.g. 'Pune', 'Nagpur').\n"
            "   - 'current_location': Current location city/state (e.g. 'Pune', 'Nagpur').\n"
            "   - 'lower_range': Current salary if mentioned in resume, otherwise ''.\n"
            "   - 'upper_range': Expected salary if mentioned in resume, otherwise ''.\n"
            "   - 'custom_jp': Joining period or notice period if mentioned, otherwise ''.\n"
            "   - 'custom_linkedin_profile': LinkedIn URL if present, otherwise ''.\n"
            "   - 'custom_gap': Boolean (true if employment/academic gap is detected, false otherwise).\n"
            "   - 'rating': Primary candidate match rating. MUST BE EXACTLY ONE OF: 'Good Fit', 'May be', or 'Not a Fit'.\n"
            "   - 'applicant_rating': Primary candidate scoring rating (e.g. '4.5', '5.0', '3.5', or '2.0' based on overall fit).\n\n"

            "2. Populate 'custom_skill_matrix_table' as a list of objects based on candidate's skills and usage in resume/projects:\n"
            "   Each object in 'custom_skill_matrix_table' MUST have:\n"
            "   - 'skill': Skill name (e.g. 'Auto-cad 2D&3D', 'Revit', 'Microsoft Excel', 'Financial Management')\n"
            "   - 'skill_category': Category (e.g. 'Drafting / Software', 'Civil Engineering', 'Finance', 'Management')\n"
            "   - 'experience_level': Proficiency description ('Expert', 'Proficient', 'Working Knowledge', 'Basic Knowledge', or 'No Knowledge')\n"
            "   - 'rating': Rating string matching legend:\n"
            "     * '* - No Knowledge'\n"
            "     * '** - Basic Knowledge'\n"
            "     * '*** - Working Knowledge'\n"
            "     * '**** - Proficient'\n"
            "     * '***** - Expert'\n\n"
            "3. Generate 'cover_letter':\n"
            "   - A professional, detailed candidate screening and job matching analysis.\n"
            "   - Include Match Status (e.g. Match / No Match), Matched Role (if any), and a clear explanation of how the candidate's background, qualifications, and skills align or do not align with the job description.\n\n"
            "4. Exclude extra sections:\n"
            "   - Do NOT include keys like 'skill_match', 'project_relevance', 'experience', 'about_profile', 'date_quality_flags', or basic details (full_name, email, etc.).\n\n"
            "Return ONLY a single valid JSON object containing keys: 'fields', 'custom_skill_matrix_table', and 'cover_letter'."
        )

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert resume parser. Respond ONLY with valid JSON.",
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "temperature": 0.1,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        return json.loads(content)
