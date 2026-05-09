"""Shared HTTP session and helpers for all job-board scrapers."""
from __future__ import annotations
import logging
import random
import re
import time
from datetime import datetime, timedelta
from typing import Any, Optional

import requests
from dateutil import parser as dateparser

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
              "image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Ch-Ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


class BaseJobScraper:
    """Common HTTP session + sleep + relative-date helpers."""

    SOURCE = "unknown"

    def __init__(self, delay_range: tuple[float, float] = (0.6, 1.4)):
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)
        self.delay_range = delay_range

    def _sleep(self):
        time.sleep(random.uniform(*self.delay_range))

    def _get(self, url: str, timeout: int = 12) -> Optional[str]:
        try:
            r = self.session.get(url, timeout=timeout)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            logger.warning(f"[{self.SOURCE}] GET failed {url[:80]}: {e}")
            return None

    @staticmethod
    def _relative_date(text: str) -> Optional[datetime]:
        text = (text or "").lower().strip()
        now = datetime.now()
        patterns = [
            (r"(\d+)\s*minute",      lambda m: now - timedelta(minutes=int(m.group(1)))),
            (r"(\d+)\s*hour",        lambda m: now - timedelta(hours=int(m.group(1)))),
            (r"(\d+)\s*day",         lambda m: now - timedelta(days=int(m.group(1)))),
            (r"(\d+)\s*week",        lambda m: now - timedelta(weeks=int(m.group(1)))),
            (r"(\d+)\+?\s*month",    lambda m: now - timedelta(days=int(m.group(1)) * 30)),
            (r"just now|moments ago|today|posted today", lambda m: now),
            (r"yesterday",           lambda m: now - timedelta(days=1)),
        ]
        for pattern, calc in patterns:
            m = re.search(pattern, text)
            if m:
                try:
                    return calc(m)
                except Exception:
                    pass
        try:
            return dateparser.parse(text, dayfirst=False)
        except Exception:
            return None

    def search_jobs(self, *, job_title: str, location: str = "",
                     num_jobs: int = 25, days: int = 30,
                     **kw) -> list[dict[str, Any]]:
        """Override in subclasses. Must return list[dict] with the standard
        shape: title, company, location, url, posted_date, description,
        source."""
        raise NotImplementedError
