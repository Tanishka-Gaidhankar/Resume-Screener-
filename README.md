# Resume Scanner Trial Project

This workspace contains a standalone prototype of a resume scanner pipeline that:

- extracts resume text from plain text, PDF, or DOCX files
- sends the resume text, job requirements, and existing applicant fields to a Groq-style extraction client
- validates the response against a strict schema
- stores scored sections and job_matching payload (description vs resume alignment & match decision)

## Run locally

```bash
cd '/home/kbp/Downloads/Resume scanner'
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m resume_trial.cli sample-resume.txt "Need Python, Flask, and REST APIs"
```
