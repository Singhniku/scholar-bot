"""Multi-portal job scrapers — LinkedIn, Indeed, Glassdoor, Instahyre."""
from .multi   import MultiPortalScraper, scrape_all
from .indeed  import IndeedScraper
from .glassdoor import GlassdoorScraper
from .instahyre import InstahyreScraper

__all__ = [
    "MultiPortalScraper", "scrape_all",
    "IndeedScraper", "GlassdoorScraper", "InstahyreScraper",
]
