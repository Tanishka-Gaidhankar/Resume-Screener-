from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .processor import process_resume_upload


def resolve_resume_path(base_path: str | None, candidate: str | None, fallback: str | None = None) -> str | None:
    candidates = []
    if candidate:
        candidates.append(candidate)
    if fallback:
        candidates.append(fallback)

    for item in candidates:
        if not item:
            continue

        candidate_path = Path(item)
        if candidate_path.exists():
            return str(candidate_path)

        if base_path:
            combined = Path(base_path) / candidate_path
            if combined.exists():
                return str(combined)

            if candidate_path.parts:
                basename = candidate_path.name
                if basename:
                    for root, _, files in os.walk(base_path):
                        if basename in files:
                            return str(Path(root) / basename)

                for index in range(1, len(candidate_path.parts)):
                    partial = Path(*candidate_path.parts[-index:])
                    combined_partial = Path(base_path) / partial
                    if combined_partial.exists():
                        return str(combined_partial)

    return None


def _load_job_descriptions(path: str | None) -> str | list[dict[str, str]]:
    if not path:
        return []

    file_path = Path(path)
    if not file_path.exists():
        return []

    with file_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the resume scanner trial")
    parser.add_argument("file_path", nargs="?", help="Path to the resume file")
    parser.add_argument("--file-path", dest="file_path_flag", help="Path to the resume file")
    parser.add_argument("job_requirements", nargs="?", help="Text describing the job requirements")
    parser.add_argument("--existing-json", default="{}", help="Optional JSON object of existing applicant fields")
    parser.add_argument("--job-descriptions-file", default="job_descriptions.json", help="Path to a JSON file containing job descriptions")
    parser.add_argument("--output-file", help="Optional text file path to save the CLI output")
    args = parser.parse_args()

    resume_path = resolve_resume_path(
        base_path=str(Path.cwd()),
        candidate=args.file_path_flag or args.file_path,
        fallback=args.file_path_flag or args.file_path,
    )
    if not resume_path:
        parser.error("Please provide a resume file path. Use --file-path '/path/to/resume.pdf' if the path contains spaces.")

    existing = json.loads(args.existing_json)
    job_requirements = args.job_requirements if args.job_requirements is not None else _load_job_descriptions(args.job_descriptions_file)
    result = process_resume_upload(
        file_path=Path(resume_path),
        job_requirements=job_requirements,
        existing_fields=existing,
    )
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    print(rendered)

    if args.output_file:
        output_path = Path(args.output_file)
        output_path.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
