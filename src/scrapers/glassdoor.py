"""Glassdoor public-jobs scraper."""
from __future__ import annotations
import json
import logging
import re
from typing import Any
from urllib.parse import urlencode, quote_plus

from bs4 import BeautifulSoup
from ._base import BaseJobScraper

logger = logging.getLogger(__name__)


class GlassdoorScraper(BaseJobScraper):
    """Scrapes glassdoor.com /Job/jobs.htm public listing pages."""

    SOURCE   = "Glassdoor"
    BASE_URL = "https://www.glassdoor.com/Job/jobs.htm"

    def search_jobs(self, *, job_title: str, location: str = "",
                     num_jobs: int = 25, days: int = 30,
                     **kw) -> list[dict[str, Any]]:
        if not job_title:
            return []

        params = {
            "sc.keyword":       job_title,
            "locT":             "C",
            "locKeyword":       location or "United States",
            "fromAge":          min(max(days, 1), 30),
            "minSalary":        "0",
            "includeNoSalaryJobs": "true",
        }
        url = f"{self.BASE_URL}?{urlencode(params)}"
        logger.info(f"[Glassdoor] {url}")
        html = self._get(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        jobs = self._parse_jobs(soup)
        return jobs[:num_jobs]

    def _parse_jobs(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []

        # Path 1: typical job-search list items
        for li in soup.select("li.JobsList_jobListItem__wjTHv, li[data-test='jobListing']"):
            j = self._parse_card(li)
            if j: jobs.append(j)

        # Path 2: JSON-LD JobPosting
        if not jobs:
            for script in soup.find_all("script", {"type": "application/ld+json"}):
                try:
                    data = json.loads(script.string or "")
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if isinstance(item, dict) and item.get("@type") == "JobPosting":
                            jobs.append(self._parse_jsonld(item))
                except Exception:
                    pass

        # Path 3: regex extract from embedded apollo/window data
        if not jobs:
            html = str(soup)
            for m in re.finditer(
                r'"jobTitleText":"([^"]+)".*?"employerName":"([^"]+)".*?'
                r'"locationName":"([^"]*)".*?"jobViewUrl":"([^"]+)"',
                html
            )[:25]:
                jobs.append({
                    "title":       m.group(1),
                    "company":     m.group(2),
                    "location":    m.group(3),
                    "url":         f"https://www.glassdoor.com{m.group(4)}",
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
        logger.info(f"[Glassdoor] parsed {len(out)} jobs")
        return out

    def _parse_card(self, li) -> dict[str, Any] | None:
        try:
            title_el   = li.select_one("a[data-test='job-title'], a.JobCard_jobTitle")
            company_el = li.select_one("[data-test='employer-short-name'], .EmployerProfile_employerName")
            loc_el     = li.select_one("[data-test='emp-location'], .JobCard_location")
            date_el    = li.select_one("[data-test='job-age'], .JobCard_listingAge")

            href = title_el.get("href", "") if title_el else ""
            if href.startswith("/"):
                href = "https://www.glassdoor.com" + href

            title = title_el.get_text(strip=True) if title_el else ""
            if not title: return None

            return {
                "title":       title,
                "company":     company_el.get_text(strip=True) if company_el else "",
                "location":    loc_el.get_text(strip=True) if loc_el else "",
                "url":         href,
                "posted_date": self._relative_date(date_el.get_text(strip=True)) if date_el else None,
                "description": "",
                "required_skills": [],
                "source":      self.SOURCE,
            }
        except Exception as e:
            logger.debug(f"[Glassdoor] card parse error: {e}")
            return None

    def _parse_jsonld(self, item: dict) -> dict[str, Any]:
        org = item.get("hiringOrganization") or {}
        loc = item.get("jobLocation") or {}
        addr = (loc.get("address") if isinstance(loc, dict) else {}) or {}
        return {
            "title":       item.get("title", ""),
            "company":     org.get("name", "") if isinstance(org, dict) else "",
            "location":    f"{addr.get('addressLocality','')} {addr.get('addressRegion','')}".strip(),
            "url":         item.get("url", ""),
            "posted_date": self._relative_date(item.get("datePosted", "")),
            "description": item.get("description", ""),
            "required_skills": [],
            "source":      self.SOURCE,
        }
