import time
import random
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import urlencode, quote_plus

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

logger = logging.getLogger(__name__)

_TIME_FILTER = {
    1: "r86400",
    7: "r604800",
    30: "r2592000",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


class LinkedInScraper:
    """
    Scrapes LinkedIn public job listings without authentication.

    LinkedIn's public /jobs/search endpoint returns HTML pages with embedded
    JSON-LD and data attributes that we parse here. No login is required for
    the basic listing data; full JD text is fetched per-job.
    """

    BASE_URL = "https://www.linkedin.com/jobs/search/"
    JOB_URL = "https://www.linkedin.com/jobs/view/{job_id}/"

    def __init__(self, delay_range: tuple[float, float] = (2.0, 5.0)):
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)
        self.delay_range = delay_range
        self._init_session()

    def _init_session(self):
        """Warm up the session so LinkedIn sets cookies."""
        try:
            self.session.get("https://www.linkedin.com", timeout=10)
            self._sleep()
        except Exception as e:
            logger.warning(f"Could not warm up LinkedIn session: {e}")

    def _sleep(self):
        time.sleep(random.uniform(*self.delay_range))

    def search_jobs(
        self,
        keywords: list[str],
        location: str = "United States",
        num_jobs: int = 50,
        days: int = 30,
        job_title: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Search LinkedIn for jobs matching the given keywords.

        When job_title is provided it becomes the first (most-weighted) term so
        LinkedIn returns title-matched results rather than generic skill matches.
        Returns a list of job dicts sorted by posting date descending.
        """
        if job_title:
            skill_terms = [k for k in keywords if k.lower() != job_title.lower()]
            query = " ".join([job_title] + skill_terms[:5])
        else:
            query = " ".join(keywords[:8])

        # Compute seconds for any number of days (LinkedIn accepts r{seconds})
        time_filter = _TIME_FILTER.get(days) or f"r{days * 86400}"
        jobs: list[dict[str, Any]] = []
        start = 0
        page_size = 25

        while len(jobs) < num_jobs:
            params = {
                "keywords": query,
                "location": location,
                "f_TPR": time_filter,
                "start": start,
                "count": page_size,
                "sortBy": "DD",  # date descending
            }
            url = f"{self.BASE_URL}?{urlencode(params)}"
            logger.info(f"Fetching jobs: start={start} — {url}")

            page_jobs = self._fetch_job_listing_page(url)
            if not page_jobs:
                break

            jobs.extend(page_jobs)
            if len(page_jobs) < page_size:
                break

            start += page_size
            self._sleep()

        # Fetch full JD for top matches (limit to save time)
        unique = {j["job_id"]: j for j in jobs if j.get("job_id")}.values()
        result = list(unique)[:num_jobs]

        logger.info(f"Fetching full descriptions for {min(len(result), 20)} jobs...")
        for job in result[:20]:
            if not job.get("description"):
                self._enrich_job(job)
                self._sleep()

        result.sort(key=lambda j: j.get("posted_date") or datetime.min, reverse=True)
        return result

    def _fetch_job_listing_page(self, url: str) -> list[dict[str, Any]]:
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        jobs = []

        # LinkedIn job cards — data is in <li> elements with class "job-search-card"
        cards = soup.select("li.job-search-card, div.base-card")
        for card in cards:
            job = self._parse_card(card)
            if job:
                jobs.append(job)

        if not jobs:
            # Fallback: parse JSON-LD structured data
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    import json
                    data = json.loads(script.string or "")
                    if isinstance(data, list):
                        for item in data:
                            job = self._parse_jsonld(item)
                            if job:
                                jobs.append(job)
                    elif isinstance(data, dict):
                        job = self._parse_jsonld(data)
                        if job:
                            jobs.append(job)
                except Exception:
                    pass

        logger.info(f"Parsed {len(jobs)} job cards from page")
        return jobs

    def _parse_card(self, card) -> Optional[dict[str, Any]]:
        try:
            # Job ID
            job_id = (
                card.get("data-job-id")
                or card.get("data-entity-urn", "").split(":")[-1]
            )

            title_el = card.select_one(
                "h3.base-search-card__title, h3.job-search-card__title, "
                "a.base-card__full-link span"
            )
            company_el = card.select_one(
                "h4.base-search-card__subtitle, "
                "a.job-search-card__company-name, "
                "h4.job-search-card__company"
            )
            location_el = card.select_one(
                "span.job-search-card__location, span.base-search-card__metadata"
            )
            date_el = card.select_one("time")
            link_el = card.select_one("a.base-card__full-link, a[href*='/jobs/view/']")

            if not title_el:
                return None

            title = title_el.get_text(strip=True)
            company = company_el.get_text(strip=True) if company_el else "Unknown"
            location = location_el.get_text(strip=True) if location_el else ""
            url = link_el["href"] if link_el else ""

            # Extract job id from URL if not found
            if not job_id and url:
                match = re.search(r"/jobs/view/(\d+)", url)
                if match:
                    job_id = match.group(1)

            posted_date = None
            if date_el:
                dt_attr = date_el.get("datetime", "")
                if dt_attr:
                    try:
                        posted_date = datetime.fromisoformat(dt_attr.replace("Z", "+00:00"))
                    except ValueError:
                        pass
                if not posted_date:
                    posted_date = self._parse_relative_date(date_el.get_text(strip=True))

            return {
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "url": url,
                "posted_date": posted_date,
                "description": "",
                "required_skills": [],
            }
        except Exception as e:
            logger.debug(f"Card parse error: {e}")
            return None

    def _parse_jsonld(self, data: dict) -> Optional[dict[str, Any]]:
        if data.get("@type") not in ("JobPosting", "jobPosting"):
            return None
        try:
            url = data.get("url", "")
            job_id = ""
            if url:
                match = re.search(r"/jobs/view/(\d+)", url)
                if match:
                    job_id = match.group(1)

            posted_str = data.get("datePosted", "")
            posted_date = None
            if posted_str:
                try:
                    posted_date = dateparser.parse(posted_str)
                except Exception:
                    pass

            org = data.get("hiringOrganization", {})
            company = org.get("name", "") if isinstance(org, dict) else str(org)

            loc = data.get("jobLocation", {})
            if isinstance(loc, dict):
                addr = loc.get("address", {})
                location = (
                    f"{addr.get('addressLocality', '')}, {addr.get('addressRegion', '')}"
                    if isinstance(addr, dict)
                    else str(addr)
                )
            else:
                location = ""

            return {
                "job_id": job_id,
                "title": data.get("title", ""),
                "company": company,
                "location": location,
                "url": url,
                "posted_date": posted_date,
                "description": data.get("description", ""),
                "required_skills": [],
            }
        except Exception as e:
            logger.debug(f"JSON-LD parse error: {e}")
            return None

    def _enrich_job(self, job: dict[str, Any]):
        """Fetch the full job description from the individual job page."""
        url = job.get("url") or (
            self.JOB_URL.format(job_id=job["job_id"]) if job.get("job_id") else None
        )
        if not url:
            return

        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            desc_el = soup.select_one(
                "div.show-more-less-html__markup, "
                "div.description__text, "
                "section.description"
            )
            if desc_el:
                job["description"] = desc_el.get_text(separator="\n", strip=True)

            # Skills listed on the page
            skill_els = soup.select(
                "li.job-criteria__item span, "
                "span.skill-pill, "
                "li.description__job-criteria-item"
            )
            if skill_els:
                job["required_skills"] = [el.get_text(strip=True) for el in skill_els]

        except Exception as e:
            logger.debug(f"Failed to enrich job {job.get('job_id')}: {e}")

    @staticmethod
    def _parse_relative_date(text: str) -> Optional[datetime]:
        text = text.lower().strip()
        now = datetime.now()
        patterns = [
            (r"(\d+)\s*minute", lambda m: now - timedelta(minutes=int(m.group(1)))),
            (r"(\d+)\s*hour", lambda m: now - timedelta(hours=int(m.group(1)))),
            (r"(\d+)\s*day", lambda m: now - timedelta(days=int(m.group(1)))),
            (r"(\d+)\s*week", lambda m: now - timedelta(weeks=int(m.group(1)))),
            (r"(\d+)\s*month", lambda m: now - timedelta(days=int(m.group(1)) * 30)),
            (r"just now|moments ago", lambda m: now),
            (r"yesterday", lambda m: now - timedelta(days=1)),
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
