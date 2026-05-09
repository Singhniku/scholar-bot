"""Instahyre public-jobs scraper (India-focused tech jobs)."""
from __future__ import annotations
import json
import logging
import re
from typing import Any
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from ._base import BaseJobScraper

logger = logging.getLogger(__name__)


class InstahyreScraper(BaseJobScraper):
    """Scrapes instahyre.com public job listings."""

    SOURCE   = "Instahyre"
    SEARCH_URL = "https://www.instahyre.com/search-jobs/"
    API_URL    = "https://www.instahyre.com/api/v1/job_search"

    def search_jobs(self, *, job_title: str, location: str = "",
                     num_jobs: int = 25, days: int = 30,
                     **kw) -> list[dict[str, Any]]:
        if not job_title:
            return []

        # Try the public API first (returns clean JSON)
        params = {
            "search_keyword": job_title,
            "search_location": location or "",
            "limit":           min(num_jobs, 50),
        }
        api_url = f"{self.API_URL}?{urlencode(params)}"
        logger.info(f"[Instahyre] {api_url}")
        try:
            r = self.session.get(api_url, timeout=12, headers={"Accept": "application/json"})
            r.raise_for_status()
            data = r.json()
            jobs = self._parse_api(data)
            if jobs:
                logger.info(f"[Instahyre] parsed {len(jobs)} via API")
                return jobs[:num_jobs]
        except Exception as e:
            logger.warning(f"[Instahyre] API fetch failed: {e}")

        # Fallback: HTML search page
        params2 = {"keyword": job_title}
        url2 = f"{self.SEARCH_URL}?{urlencode(params2)}"
        logger.info(f"[Instahyre] HTML fallback {url2}")
        html = self._get(url2)
        if not html:
            return []
        soup = BeautifulSoup(html, "lxml")
        return self._parse_html(soup)[:num_jobs]

    # ── API JSON ─────────────────────────────────────────────────────────────
    def _parse_api(self, data: Any) -> list[dict[str, Any]]:
        objects = data.get("objects") if isinstance(data, dict) else None
        if not isinstance(objects, list):
            return []

        jobs: list[dict[str, Any]] = []
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            employer = obj.get("employer") or {}
            jobs.append({
                "title":       obj.get("title", "") or obj.get("designation", ""),
                "company":     employer.get("company_name", "")
                               if isinstance(employer, dict) else str(employer),
                "location":    ", ".join(obj.get("locations", []) or []) if isinstance(obj.get("locations"), list)
                               else obj.get("city", "") or obj.get("location", ""),
                "url":         "https://www.instahyre.com" + (obj.get("public_url", "") or
                                                               obj.get("absolute_url", "")),
                "posted_date": self._relative_date(str(obj.get("created_on", "")
                                                       or obj.get("posted_at", ""))),
                "description": obj.get("description", "") or obj.get("job_description", ""),
                "required_skills": obj.get("skills", []) or [],
                "source":      self.SOURCE,
            })
        return jobs

    # ── HTML fallback ────────────────────────────────────────────────────────
    def _parse_html(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        for card in soup.select("div.job-listing, div.job-card, article"):
            title_el = card.select_one("h2, h3, a.job-title")
            comp_el  = card.select_one(".company-name, .employer")
            loc_el   = card.select_one(".job-location, .location")
            link_el  = card.select_one("a[href*='/jobs/']")
            if not title_el: continue

            href = link_el.get("href", "") if link_el else ""
            if href.startswith("/"):
                href = "https://www.instahyre.com" + href

            jobs.append({
                "title":       title_el.get_text(strip=True),
                "company":     comp_el.get_text(strip=True) if comp_el else "",
                "location":    loc_el.get_text(strip=True) if loc_el else "",
                "url":         href,
                "posted_date": None,
                "description": "",
                "required_skills": [],
                "source":      self.SOURCE,
            })

        # Dedupe
        seen, out = set(), []
        for j in jobs:
            key = j.get("url", "") or (j.get("title", "") + j.get("company", ""))
            if key and key not in seen:
                seen.add(key); out.append(j)
        return out
