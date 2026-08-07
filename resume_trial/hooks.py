from __future__ import annotations

app_name = "resume_trial"
app_title = "Resume Scanner"
app_publisher = "DeepMind Pair Team"
app_description = "AI Powered Resume Parsing and Frappe Job Applicant Autofill"
app_email = "developer@example.com"
app_license = "MIT"

# Document Events
# ------------------
# Auto-triggers disabled: AI parsing is executed exclusively via explicit "AI Parse" button click
doc_events = {}

doctype_js = {
    "Job Applicant": "public/js/job_applicant.js",
}

doctype_list_js = {
    "Job Applicant": "public/js/job_applicant_list.js",
}







