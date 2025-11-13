"""Web scraping utilities with robots.txt compliance"""
from urllib.parse import urlparse, urljoin, urlunparse
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup
from typing import Optional, List, Set, Dict
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class RobotsChecker:
    """Check robots.txt compliance for a domain"""

    def __init__(self, user_agent: str = "ResearchBot"):
        self.user_agent = user_agent
        self.parsers: Dict[str, RobotFileParser] = {}

    def can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt"""
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"

        if domain not in self.parsers:
            robots_url = urljoin(domain, "/robots.txt")
            parser = RobotFileParser()
            parser.set_url(robots_url)
            try:
                parser.read()
                self.parsers[domain] = parser
            except Exception as e:
                logger.warning(f"Could not read robots.txt from {robots_url}: {e}")
                # If we can't read robots.txt, allow by default
                return True

        return self.parsers[domain].can_fetch(self.user_agent, url)


class WebCrawler:
    """Simple web crawler with rate limiting and robots.txt compliance"""

    def __init__(
        self,
        user_agent: str = "ResearchBot/1.0",
        rate_limit: float = 1.0,  # seconds between requests
        respect_robots: bool = True
    ):
        self.user_agent = user_agent
        self.rate_limit = rate_limit
        self.last_request_time = 0.0
        self.respect_robots = respect_robots
        self.robots_checker = RobotsChecker(user_agent) if respect_robots else None
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': user_agent})

    def _wait_for_rate_limit(self):
        """Wait if necessary to respect rate limit"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()

    def fetch(self, url: str, timeout: int = 30) -> Optional[requests.Response]:
        """
        Fetch URL with rate limiting and robots.txt check

        Args:
            url: URL to fetch
            timeout: Request timeout in seconds

        Returns:
            Response object or None if fetch failed
        """
        # Check robots.txt
        if self.respect_robots and not self.robots_checker.can_fetch(url):
            logger.info(f"Blocked by robots.txt: {url}")
            return None

        # Rate limit
        self._wait_for_rate_limit()

        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def fetch_html(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse HTML"""
        response = self.fetch(url)
        if response:
            try:
                return BeautifulSoup(response.content, 'lxml')
            except Exception as e:
                logger.error(f"Error parsing HTML from {url}: {e}")
        return None

    def download_file(self, url: str, save_path: Path) -> bool:
        """
        Download file to disk

        Args:
            url: URL to download
            save_path: Local path to save file

        Returns:
            True if successful
        """
        response = self.fetch(url)
        if response:
            try:
                save_path.parent.mkdir(parents=True, exist_ok=True)
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"Downloaded {url} to {save_path}")
                return True
            except Exception as e:
                logger.error(f"Error saving {url} to {save_path}: {e}")
        return False


def find_links(soup: BeautifulSoup, base_url: str, patterns: Optional[List[str]] = None) -> List[str]:
    """
    Find links in HTML matching optional patterns

    Args:
        soup: BeautifulSoup object
        base_url: Base URL for resolving relative links
        patterns: List of substrings to match in URLs/link text (case-insensitive)

    Returns:
        List of absolute URLs
    """
    links = []
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        link_text = a_tag.get_text(strip=True)

        # Skip anchors and javascript
        if href.startswith('#') or href.startswith('javascript:'):
            continue

        # Match patterns if provided
        if patterns:
            combined = f"{href} {link_text}".lower()
            if not any(pattern.lower() in combined for pattern in patterns):
                continue

        # Resolve to absolute URL
        absolute_url = urljoin(base_url, href)
        links.append(absolute_url)

    return list(set(links))  # Remove duplicates


def same_domain(url1: str, url2: str) -> bool:
    """Check if two URLs are from the same domain"""
    return urlparse(url1).netloc == urlparse(url2).netloc


def normalize_url(url: str) -> str:
    """Normalize URL by removing fragments and standardizing"""
    parsed = urlparse(url)
    # Remove fragment
    normalized = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        ''  # no fragment
    ))
    # Remove trailing slash for consistency
    if normalized.endswith('/') and parsed.path != '/':
        normalized = normalized[:-1]
    return normalized
