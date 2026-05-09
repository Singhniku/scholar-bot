"""Indeed public-jobs scraper."""
from __future__ import annotations
import json
import logging
import re
from typing import Any
from urllib.parse import urlencode, quote_plus

from bs4 import BeautifulSoup
from ._base import BaseJobScraper

logger = logging.getLogger(__name__)


class IndeedScraper(BaseJobScraper):
    """Scrapes indeed.com /jobs?q=&l= public listing pages."""

    SOURCE   = "Indeed"
    BASE_URL = "https://www.indeed.com/jobs"
    JOB_URL  = "https://www.indeed.com/viewjob"

    def search_jobs(self, *, job_title: str, location: str = "",
                     num_jobs: int = 25, days: int = 30,
                     **kw) -> list[dict[str, Any]]:
        if not job_title:
            return []

        # Indeed `fromage` filter: 1 / 3 / 7 / 14 days; map ours
        if days <= 1:    fromage = 1
        elif days <= 3:  fromage = 3
        elif days <= 7:  fromage = 7
        else:            fromage = 14

        params = {
            "q":       job_title,
            "l":       location or "",
            "fromage": fromage,
            "sort":    "date",
        }
        url  = f"{self.BASE_URL}?{urlencode(params)}"
        logger.info(f"[Indeed] {url}")
        html = self._get(url)
        if not html:
            return []

        soup  = BeautifulSoup(html, "lxml")
        jobs  = self._parse_jobs(soup)
        return jobs[:num_jobs]

    # ── Parsing ──────────────────────────────────────────────────────────────
    def _parse_jobs(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        # Indeed embeds a JSON blob with mosaic-data on most pages
        jobs: list[dict[str, Any]] = []

        # Path 1: cards (class "job_seen_beacon" or "tapItem")
        for card in soup.select("div.job_seen_beacon, a.tapItem, div.cardOutline"):
            j = self._parse_card(card)
            if j: jobs.append(j)

        # Path 2: JSON-LD ItemList of JobPosting
        if not jobs:
            for script in soup.find_all("script", {"type": "application/ld+json"}):
                try:
                    data = json.loads(script.string or "")
                    items = data.get("itemListElement") or [data]
                    for item in items:
                        if isinstance(item, dict):
                            obj = item.get("item") or item
                            if obj.get("@type") in ("JobPosting", "jobPosting"):
                                jobs.append(self._parse_jsonld(obj))
                except Exception:
                    pass

        # Dedupe
        seen, out = set(), []
        for j in jobs:
            key = j.get("url", "") or (j.get("title", "") + j.get("company", ""))
            if key and key not in seen:
                seen.add(key); out.append(j)
        logger.info(f"[Indeed] parsed {len(out)} jobs")
        return out

    def _parse_card(self, card) -> dict[str, Any] | None:
        try:
            title_el   = card.select_one("h2.jobTitle span, h2 a span[title], h2 a")
            company_el = card.select_one("span.companyName, span[data-testid='company-name']")
            loc_el     = card.select_one("div.companyLocation, div[data-testid='text-location']")
            date_el    = card.select_one("span.date, span[data-testid='myJobsStateDate']")

            link_el = card if card.name == "a" else card.select_one("a")
            href    = link_el.get("href", "") if link_el else ""
            if href.startswith("/"):
                href = "https://www.indeed.com" + href

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
            logger.debug(f"[Indeed] card parse error: {e}")
            return None

    def _parse_jsonld(self, item: dict) -> dict[str, Any]:
        org = item.get("hiringOrganization") or {}
        loc = item.get("jobLocation") or {}
        addr = (loc.get("address") if isinstance(loc, dict) else {}) or {}
        try:
            posted = (item.get("datePosted") or "").strip()
            posted_dt = self._relative_date(posted) or None
        except Exception:
            posted_dt = None

        return {
            "title":       item.get("title", ""),
            "company":     org.get("name", "") if isinstance(org, dict) else "",
            "location":    f"{addr.get('addressLocality','')} {addr.get('addressRegion','')}".strip(),
            "url":         item.get("url", ""),
            "posted_date": posted_dt,
            "description": item.get("description", ""),
            "required_skills": [],
            "source":      self.SOURCE,
        }
