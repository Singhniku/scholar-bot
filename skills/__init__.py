# Skills — reusable test fixtures and scenario helpers for Scholar-Bot modules.
# Import directly: from skills.fixtures import RESUME_POSITIVE, JOB_POSITIVE
from .fixtures import (
    RESUME_POSITIVE,
    RESUME_NEGATIVE,
    JOB_POSITIVE,
    JOB_NEGATIVE,
    MOCK_AI_CLIENT,
)

__all__ = [
    "RESUME_POSITIVE",
    "RESUME_NEGATIVE",
    "JOB_POSITIVE",
    "JOB_NEGATIVE",
    "MOCK_AI_CLIENT",
]
