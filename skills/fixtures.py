"""
Reusable test fixtures for Scholar-Bot.

Import in any test file:
    from skills.fixtures import RESUME_POSITIVE, JOB_POSITIVE, MOCK_AI_CLIENT

The MOCK_AI_CLIENT is a drop-in AIClient replacement that returns
deterministic JSON without hitting any real API — safe for CI/CD.
"""
from __future__ import annotations
import json
from typing import Any


# ─── Positive resume fixture ──────────────────────────────────────────────────
# A well-structured, realistic resume that should score high against most jobs.
RESUME_POSITIVE = {
    "name": "Alex Johnson",
    "email": "alex.johnson@email.com",
    "phone": "+1-555-0199",
    "location": "San Francisco, CA",
    "summary": (
        "Senior Software Engineer with 7 years of experience building scalable "
        "distributed systems in Python and Go. Expert in cloud-native architectures "
        "on AWS and GCP. Passionate about developer experience and CI/CD automation."
    ),
    "experience_years": 7,
    "current_title": "Senior Software Engineer",
    "technical_skills": ["Python", "Go", "SQL", "NoSQL", "REST APIs", "GraphQL"],
    "soft_skills": ["Leadership", "Communication", "Problem Solving", "Mentoring"],
    "tools": ["Docker", "Kubernetes", "Terraform", "Git", "Jenkins", "GitHub Actions"],
    "languages": ["Python", "Go", "JavaScript", "Bash"],
    "frameworks": ["Django", "FastAPI", "React", "gRPC"],
    "certifications": ["AWS Certified Solutions Architect", "CKA (Kubernetes)"],
    "education": [
        {"degree": "B.S. Computer Science", "institution": "UC Berkeley", "year": 2017}
    ],
    "experience": [
        {
            "title": "Senior Software Engineer",
            "company": "TechCorp Inc.",
            "duration": "Jan 2021 – Present",
            "achievements": [
                "Led migration of monolith to microservices, reducing deployment time by 60%",
                "Designed and built a real-time data pipeline processing 5M events/day",
                "Mentored 4 junior engineers; 2 promoted to mid-level within 18 months",
            ],
        },
        {
            "title": "Software Engineer",
            "company": "StartupXYZ",
            "duration": "Jun 2017 – Dec 2020",
            "achievements": [
                "Built REST API serving 1M+ daily active users with 99.95% uptime",
                "Reduced AWS costs by 35% through spot instance optimization",
            ],
        },
    ],
    "projects": [
        {
            "name": "OpenCache",
            "description": "Distributed caching library for Python with Redis/Memcached backends",
            "technologies": ["Python", "Redis", "Docker"],
        }
    ],
    "all_keywords": [
        "Python", "Go", "AWS", "GCP", "Kubernetes", "Docker", "Terraform",
        "microservices", "REST API", "GraphQL", "CI/CD", "distributed systems",
        "Django", "FastAPI", "React", "SQL", "NoSQL", "gRPC",
    ],
}

# ─── Negative resume fixture ──────────────────────────────────────────────────
# Sparse resume — missing key fields, short experience, vague language.
# Should score low against technical job postings.
RESUME_NEGATIVE = {
    "name": "Sam Smith",
    "email": "",
    "phone": "",
    "location": "",
    "summary": "Looking for a job in tech.",
    "experience_years": 0,
    "current_title": "",
    "technical_skills": [],
    "soft_skills": [],
    "tools": [],
    "languages": [],
    "frameworks": [],
    "certifications": [],
    "education": [],
    "experience": [],
    "projects": [],
    "all_keywords": [],
}

# ─── Positive job fixture ─────────────────────────────────────────────────────
# A detailed job posting that closely matches RESUME_POSITIVE.
JOB_POSITIVE = {
    "title": "Senior Software Engineer — Platform",
    "company": "Acme Cloud",
    "location": "San Francisco, CA (Hybrid)",
    "url": "https://linkedin.com/jobs/view/12345",
    "job_id": "12345",
    "posted_date": None,
    "description": """
We are looking for a Senior Software Engineer to join our Platform team.

Requirements:
- 5+ years of professional software development experience
- Strong Python and/or Go expertise
- Experience with microservices and distributed systems
- Hands-on with AWS, GCP, or Azure
- Proficiency in Docker and Kubernetes
- CI/CD experience (GitHub Actions, Jenkins)
- Excellent communication and leadership skills

Nice to have:
- Terraform or infrastructure-as-code experience
- GraphQL or gRPC knowledge
- Experience mentoring junior engineers

Responsibilities:
- Design and build scalable backend services
- Lead technical design reviews
- Improve developer platform tooling
""",
    "required_skills": ["Python", "Go", "AWS", "Docker", "Kubernetes", "CI/CD"],
    "preferred_skills": ["Terraform", "GraphQL", "gRPC"],
}

# ─── Negative job fixture ─────────────────────────────────────────────────────
# A job requiring skills completely absent from RESUME_POSITIVE.
JOB_NEGATIVE = {
    "title": "Embedded Systems Engineer",
    "company": "HardwareCo",
    "location": "Austin, TX",
    "url": "https://linkedin.com/jobs/view/99999",
    "job_id": "99999",
    "posted_date": None,
    "description": """
Required:
- 5+ years C/C++ firmware development
- RTOS experience (FreeRTOS, Zephyr)
- ARM Cortex-M microcontroller expertise
- Experience with JTAG/SWD debugging
- PCB bring-up and hardware/software integration
- CAN bus, SPI, I2C, UART protocols
""",
    "required_skills": ["C", "C++", "RTOS", "ARM Cortex-M", "JTAG", "CAN bus"],
    "preferred_skills": ["FreeRTOS", "Zephyr", "PCB design"],
}

# ─── Mock AI client ───────────────────────────────────────────────────────────
# Drop-in replacement for AIClient that returns pre-baked responses.
# Never hits the network — deterministic, fast, CI-safe.

_RESUME_EXTRACT_RESPONSE = json.dumps(RESUME_POSITIVE)

_JOB_EXTRACT_RESPONSE = json.dumps({
    "title": "Senior Software Engineer",
    "required_skills": ["Python", "Go", "AWS", "Docker", "Kubernetes"],
    "preferred_skills": ["Terraform", "GraphQL"],
    "required_experience_years": 5,
    "education_required": "Bachelor's degree",
    "key_responsibilities": ["Build backend services", "Lead design reviews"],
    "ats_keywords": ["Python", "microservices", "Kubernetes", "CI/CD", "distributed systems"],
    "seniority_level": "Senior",
    "job_type": "Full-time",
})

_OPTIMISED_RESUME_RESPONSE = json.dumps({
    **RESUME_POSITIVE,
    "summary": (
        "Senior Software Engineer with 7 years building distributed systems using Python "
        "and Go. Architected microservices on AWS/GCP with Kubernetes and Terraform. "
        "Led CI/CD automation with GitHub Actions, improving deployment frequency by 60%."
    ),
    "optimization_notes": [
        "Added 'microservices' and 'CI/CD' to summary for ATS keyword match",
        "Rewrote TechCorp bullet to quantify deployment improvement",
    ],
    "added_keywords": ["microservices", "CI/CD"],
})


class MockAIClient:
    """
    Deterministic mock of AIClient.
    Routes prompts to pre-baked JSON responses based on keyword detection.
    Safe to use in unit tests — no API key required.
    """
    provider = "mock"
    model    = "mock-v1"
    provider_label = "Mock AI (no API calls)"

    def generate(self, system: str, user: str, max_tokens: int = 4096, retries: int = 3) -> str:
        user_lower = user.lower()
        # Order matters: check optimise FIRST (its prompt also contains "job posting")
        if "optimis" in user_lower or "optimiz" in user_lower:
            return _OPTIMISED_RESUME_RESPONSE
        if "extract" in user_lower and "resume" in user_lower:
            return _RESUME_EXTRACT_RESPONSE
        if "job description" in user_lower or "job posting" in user_lower:
            return _JOB_EXTRACT_RESPONSE
        return json.dumps({"result": "mock_response", "input_preview": user[:80]})

    @classmethod
    def from_keys(cls, **_) -> "MockAIClient":
        return cls()

    @classmethod
    def from_env(cls) -> "MockAIClient":
        return cls()


# Export the singleton
MOCK_AI_CLIENT = MockAIClient()
