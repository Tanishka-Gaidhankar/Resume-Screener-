from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="resume_trial",
    version="0.1.0",
    description="AI Powered Resume Parsing and Frappe Job Applicant Autofill",
    author="DeepMind Pair Team",
    author_email="developer@example.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
