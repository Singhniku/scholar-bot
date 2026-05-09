"""
MultiPortalScraper — fan out a job search across LinkedIn, Indeed,
Glassdoor and Instahyre in parallel, merge into one list.

Each job dict carries a `source` field so the UI can show a portal badge.
"""
from __future__ import annotations
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

from .indeed    import IndeedScraper
from .glassdoor import GlassdoorScraper
from .instahyre import InstahyreScraper

logger = logging.getLogger(__name__)

ALL_SOURCES = ("LinkedIn", "Indeed", "Glassdoor", "Instahyre")


class MultiPortalScraper:
    def __init__(self, sources: Optional[list[str]] = None,
                  delay_range: tuple[float, float] = (0.5, 1.2)):
        self.sources = [s for s in (sources or list(ALL_SOURCES))]
        self.delay_range = delay_range

    def search_jobs(self, *, job_title: str, location: str = "",
                     num_jobs_per_source: int = 15, days: int = 30,
                     **kw) -> list[dict[str, Any]]:
        if not job_title:
            return []

        # Build callable scrapers for each requested source
        from ..linkedin_scraper import LinkedInScraper

        def _linkedin():
            scraper = LinkedInScraper(delay_range=self.delay_range)
            return scraper.search_jobs(
                keywords=[job_title],
                location=location or "United States",
                num_jobs=num_jobs_per_source,
                days=days,
                job_title=job_title,
            )

        def _indeed():
            return IndeedScraper(delay_range=self.delay_range).search_jobs(
                job_title=job_title, location=location,
                num_jobs=num_jobs_per_source, days=days)

        def _glassdoor():
            return GlassdoorScraper(delay_range=self.delay_range).search_jobs(
                job_title=job_title, location=location,
                num_jobs=num_jobs_per_source, days=days)

        def _instahyre():
            return InstahyreScraper(delay_range=self.delay_range).search_jobs(
                job_title=job_title, location=location,
                num_jobs=num_jobs_per_source, days=days)

        runners = {
            "LinkedIn":  _linkedin,
            "Indeed":    _indeed,
            "Glassdoor": _glassdoor,
            "Instahyre": _instahyre,
        }

        all_jobs: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(runners[src]): src
                for src in self.sources if src in runners
            }
            for fut in as_completed(futures):
                src = futures[fut]
                try:
                    jobs = fut.result(timeout=45)
                    # LinkedIn doesn't tag source — add it
                    for j in jobs or []:
                        j.setdefault("source", src)
                    all_jobs.extend(jobs or [])
                    logger.info(f"[multi] {src}: {len(jobs or [])} jobs")
                except Exception as e:
                    logger.warning(f"[multi] {src} failed: {e}")

        return _dedupe(all_jobs)


def _dedupe(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop duplicates that occur across portals (same title @ same company)."""
    seen, out = set(), []
    for j in jobs:
        title = (j.get("title", "") or "").strip().lower()
        comp  = (j.get("company", "") or "").strip().lower()
        key   = (title, comp) if (title and comp) else j.get("url", "")
        if key and key not in seen:
            seen.add(key); out.append(j)
    return out


def scrape_all(*, job_title: str, location: str = "",
                num_jobs_per_source: int = 15, days: int = 30,
                sources: Optional[list[str]] = None,
                ) -> list[dict[str, Any]]:
    """One-call helper used by the pipeline."""
    return MultiPortalScraper(sources=sources).search_jobs(
        job_title=job_title, location=location,
        num_jobs_per_source=num_jobs_per_source, days=days,
    )
