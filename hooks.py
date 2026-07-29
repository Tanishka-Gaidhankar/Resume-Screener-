from __future__ import annotations

app_name = "resume_trial"
app_title = "Resume Scanner"
app_publisher = "DeepMind Pair Team"
app_description = "AI Powered Resume Parsing and Frappe Job Applicant Autofill"
app_email = "developer@example.com"
app_license = "MIT"

# Document Events
# ------------------
# Hook on Job Applicant document validation/save in Frappe

doc_events = {
    "Job Applicant": {
        "validate": "resume_trial.frappe_hooks.autofill_job_applicant",
        "on_update": "resume_trial.frappe_hooks.autofill_job_applicant",
    }
}
