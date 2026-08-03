from pathlib import Path
from unittest.mock import patch
import pytest

from resume_trial.cli import resolve_resume_path
from resume_trial.processor import process_resume_upload
from resume_trial.llm_client import GroqClient


MOCK_LLM_RESPONSE = {
    "fields": {
        "applicant_name": "John Doe",
        "email_id": "john@example.com",
        "phone_number": "9876543210",
        "designation": "Senior Developer",
        "custom_current_role": "Senior Developer",
        "custom_qualification": "Bachelor of Technology",
        "custom_experience": "5",
        "permanent_location": "Nagpur",
        "current_location": "Nagpur",
        "lower_range": "50000",
        "upper_range": "70000",
        "custom_jp": "30 Days",
        "custom_linkedin_profile": "https://linkedin.com/in/test",
        "custom_gap": False,
        "rating": "Good Fit",
        "applicant_rating": "4.5",
    },

    "custom_skill_matrix_table": [
        {
            "skill": "Python",
            "skill_category": "Software Development",
            "experience_level": "Proficient",
            "rating": "**** - Proficient",
        },
        {
            "skill": "REST APIs",
            "skill_category": "Backend Engineering",
            "experience_level": "Expert",
            "rating": "***** - Expert",
        },
    ],
    "cover_letter": "Match Status: Match\nTarget Role: Software Engineer\nReason: Strong technical skills.",
}


@patch.object(GroqClient, "_call_groq", return_value=MOCK_LLM_RESPONSE)
def test_process_resume_upload_custom_fields_schema(mock_groq, tmp_path):
    resume_path = tmp_path / "resume.txt"
    resume_path.write_text(
        "John Doe\nSenior Python Developer\nBachelor of Technology\n5 years experience in Flask and APIs",
        encoding="utf-8",
    )

    result = process_resume_upload(
        file_path=resume_path,
        job_requirements="Need Python, Flask, and REST APIs",
        existing_fields={"custom_current_role": "Developer"},
    )

    applicant = result["applicant"]
    assert applicant["custom_current_role"] == "Developer"
    assert applicant["custom_qualification"] == "Bachelor of Technology"
    assert applicant["custom_experience"] == "5"
    assert applicant["permanent_location"] == "Nagpur"
    assert applicant["rating"] == "Good Fit"
    assert applicant["applicant_rating"] == "4.5"
    assert isinstance(applicant["custom_skill_matrix_table"], list)
    assert len(applicant["custom_skill_matrix_table"]) == 2
    assert applicant["custom_skill_matrix_table"][0]["skill"] == "Python"
    assert "cover_letter" in applicant
    assert "Match Status: Match" in applicant["cover_letter"]
    assert "skill_match" not in applicant
    assert "project_relevance" not in applicant
    assert "experience" not in applicant


def test_resolve_resume_path_rebuilds_path_from_split_shell_tokens(tmp_path):
    resume_path = tmp_path / "Resume scanner" / "siddant.pdf"
    resume_path.parent.mkdir(parents=True)
    resume_path.write_bytes(b"pdf")

    reconstructed = resolve_resume_path(str(resume_path.parent.parent), "scanner/siddant.pdf", None)

    assert reconstructed == str(resume_path)


def test_frappe_hooks_autofill_job_applicant(tmp_path):
    from types import SimpleNamespace
    from resume_trial.frappe_hooks import autofill_job_applicant

    resume_file = tmp_path / "test_resume.txt"
    resume_file.write_text("Senior Developer with 5 years experience in Python", encoding="utf-8")

    class MockChildTable(list):
        pass

    mock_doc = SimpleNamespace(
        resume_attachment=str(resume_file),
        custom_current_role="",
        custom_qualification="",
        custom_experience="",
        permanent_location="",
        current_location="",
        lower_range="",
        upper_range="",
        custom_jp="",
        custom_linkedin_profile="",
        custom_gap=False,
        rating="",
        applicant_rating="",
        cover_letter="",
        custom_skill_matrix_table=MockChildTable(),
    )
    mock_doc.set = lambda field, val: setattr(mock_doc, field, MockChildTable(val))
    mock_doc.append = lambda field, row: getattr(mock_doc, field).append(row)

    with patch.object(GroqClient, "_call_groq", return_value=MOCK_LLM_RESPONSE):
        autofill_job_applicant(mock_doc)

    assert mock_doc.custom_current_role == "Senior Developer"
    assert mock_doc.custom_qualification == "Bachelor of Technology"
    assert mock_doc.custom_experience == "5"
    assert mock_doc.rating == "Good Fit"
    assert mock_doc.applicant_rating == "4.5"
    assert len(mock_doc.custom_skill_matrix_table) == 2
    assert "Match Status: Match" in mock_doc.cover_letter




def test_groq_client_raises_when_no_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with patch("resume_trial.llm_client._load_env_file"):
        client = GroqClient(api_key="")
        with pytest.raises(RuntimeError, match="GROQ_API_KEY is not set"):
            client.extract(resume_text="sample", job_requirements="sample", existing_fields={})


def test_resume_trial_hooks_structure():
    import resume_trial.hooks as hooks
    assert hooks.app_name == "resume_trial"
    assert "Job Applicant" in hooks.doc_events
    assert "File" in hooks.doc_events


def test_download_resume_from_url_google_drive(tmp_path):
    from unittest.mock import MagicMock
    from resume_trial.frappe_hooks import download_resume_from_url

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {"Content-Type": "application/pdf"}
    mock_response.cookies = {}
    mock_response.iter_content.return_value = [b"PDF content data"]

    with patch("requests.Session.get", return_value=mock_response):
        downloaded = download_resume_from_url("https://drive.google.com/file/d/123456789/view?usp=sharing")
        assert downloaded is not None
        assert Path(downloaded).exists()


def test_rating_overwrite_and_summary_append(tmp_path):
    from types import SimpleNamespace
    from resume_trial.frappe_hooks import autofill_job_applicant

    resume_file = tmp_path / "test_resume.txt"
    resume_file.write_text("Experienced Engineer", encoding="utf-8")

    class MockChildTable(list):
        pass

    mock_doc = SimpleNamespace(
        resume_attachment=str(resume_file),
        custom_current_role="",
        custom_qualification="",
        custom_experience="",
        permanent_location="",
        current_location="",
        lower_range="",
        upper_range="",
        custom_jp="",
        custom_linkedin_profile="",
        custom_gap=False,
        rating="Not a Fit",
        applicant_rating="1.0",
        cover_letter="Existing Cover Letter text.",
        custom_skill_matrix_table=MockChildTable(),
    )
    mock_doc.set = lambda field, val: setattr(mock_doc, field, MockChildTable(val))
    mock_doc.append = lambda field, row: getattr(mock_doc, field).append(row)

    with patch.object(GroqClient, "_call_groq", return_value=MOCK_LLM_RESPONSE):
        autofill_job_applicant(mock_doc)

    assert mock_doc.rating == "Good Fit"
    assert mock_doc.applicant_rating == "4.5"
    assert "Existing Cover Letter text." in mock_doc.cover_letter
    assert "--- AI Screening Analysis (Updated) ---" in mock_doc.cover_letter
    assert "Match Status: Match" in mock_doc.cover_letter






