"""
Extra Layer: Website crawl, business segments, management team
"""
from pathlib import Path
from typing import List, Optional, Callable, Set, Dict
import logging
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import re

from ..models import BusinessSegment, ManagementProfile
from ..config import TickerConfig
from ..utils import ensure_dir, save_json, save_text, slugify_filename
from ..utils.web_utils import WebCrawler, find_links, same_domain, normalize_url
from ..utils.text_extraction import extract_text_from_html, clean_text

logger = logging.getLogger(__name__)


class WebsiteCrawler:
    """Crawl company website for segments, products, and other content"""

    def __init__(self, ticker_config: TickerConfig, data_dir: Path):
        self.config = ticker_config
        self.data_dir = data_dir
        self.website_dir = ensure_dir(data_dir / "website")
        self.raw_html_dir = ensure_dir(self.website_dir / "raw_html")
        self.cleaned_text_dir = ensure_dir(self.website_dir / "cleaned_text")

        self.crawler = WebCrawler(
            user_agent=ticker_config.sec_user_agent,
            rate_limit=2.0,
            respect_robots=True
        )

        self.visited_urls: Set[str] = set()
        self.max_pages = ticker_config.max_website_pages
        self.max_depth = ticker_config.website_crawl_depth

    def crawl(
        self,
        website: str,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, List]:
        """
        Crawl website focusing on products, segments, solutions

        Args:
            website: Company website URL
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with crawl results
        """
        results = {
            'pages_crawled': [],
            'segments': [],
            'products': []
        }

        if not website:
            if progress_callback:
                progress_callback("No website URL provided")
            return results

        try:
            if progress_callback:
                progress_callback(f"Starting website crawl of {website}...")

            # Define target URL patterns
            target_patterns = [
                '/product', '/solution', '/service', '/platform',
                '/industry', '/segment', '/business', '/offering'
            ]

            # Find initial links
            soup = self.crawler.fetch_html(website)
            if not soup:
                return results

            # Collect links matching patterns
            to_visit = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                absolute_url = urljoin(website, href)

                # Only same domain
                if not same_domain(absolute_url, website):
                    continue

                # Check if matches target patterns
                if any(pattern in absolute_url.lower() for pattern in target_patterns):
                    to_visit.append(absolute_url)

            # Remove duplicates
            to_visit = list(set([normalize_url(url) for url in to_visit]))

            if progress_callback:
                progress_callback(f"Found {len(to_visit)} relevant pages to crawl")

            # Crawl pages
            for i, url in enumerate(to_visit[:self.max_pages]):
                if progress_callback:
                    progress_callback(f"Crawling page {i+1}/{min(len(to_visit), self.max_pages)}: {url}")

                page_data = self._crawl_page(url)
                if page_data:
                    results['pages_crawled'].append(page_data)

                # Extract segments/products from page
                segments = self._extract_segments(page_data)
                results['segments'].extend(segments)

            if progress_callback:
                progress_callback(f"Crawled {len(results['pages_crawled'])} pages")

        except Exception as e:
            logger.error(f"Error crawling website: {e}")
            if progress_callback:
                progress_callback(f"Error: {str(e)}")

        # Save results
        self._save_segments_index(results['segments'])

        return results

    def _crawl_page(self, url: str) -> Optional[dict]:
        """Crawl a single page and save HTML + text"""
        if url in self.visited_urls:
            return None

        self.visited_urls.add(url)

        try:
            soup = self.crawler.fetch_html(url)
            if not soup:
                return None

            # Create filename from URL
            parsed = urlparse(url)
            slug = slugify_filename(parsed.path.replace('/', '_'))
            if not slug:
                slug = 'index'

            # Save raw HTML
            html_path = self.raw_html_dir / f"{slug}.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(str(soup))

            # Extract and save cleaned text
            text = extract_text_from_html(str(soup), method='html2text')
            cleaned = clean_text(text)
            text_path = self.cleaned_text_dir / f"{slug}.txt"
            save_text(cleaned, text_path)

            return {
                'url': url,
                'title': soup.find('title').get_text(strip=True) if soup.find('title') else '',
                'html_path': str(html_path),
                'text_path': str(text_path),
                'text_preview': cleaned[:500]
            }

        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            return None

    def _extract_segments(self, page_data: dict) -> List[BusinessSegment]:
        """Extract business segment information from a page"""
        segments = []

        if not page_data or 'text_path' not in page_data:
            return segments

        try:
            # Read the cleaned text
            with open(page_data['text_path'], 'r', encoding='utf-8') as f:
                text = f.read()

            # Look for segment-like headings
            # This is a simple heuristic - could be improved with NLP
            lines = text.split('\n')

            for i, line in enumerate(lines):
                line = line.strip()

                # Check if line looks like a heading (short, maybe has special chars)
                if len(line) > 5 and len(line) < 100:
                    # Check if followed by description
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if len(next_line) > 20:  # Has description
                            # Looks like a segment!
                            segment = BusinessSegment(
                                name=line,
                                description=next_line[:500],  # First 500 chars
                                source_url=page_data['url'],
                                category='segment'
                            )
                            segments.append(segment)

        except Exception as e:
            logger.error(f"Error extracting segments from {page_data.get('url')}: {e}")

        return segments

    def _save_segments_index(self, segments: List[BusinessSegment]):
        """Save segments to JSON"""
        index_path = self.website_dir / "segments.json"
        # Deduplicate by name
        seen = set()
        unique_segments = []
        for seg in segments:
            if seg.name not in seen:
                seen.add(seg.name)
                unique_segments.append(seg)

        index_data = [s.to_dict() for s in unique_segments]
        save_json(index_data, index_path)


class ManagementParser:
    """Parse management team and board information from website"""

    def __init__(self, ticker_config: TickerConfig, data_dir: Path):
        self.config = ticker_config
        self.data_dir = data_dir
        self.website_dir = ensure_dir(data_dir / "website")

        self.crawler = WebCrawler(
            user_agent=ticker_config.sec_user_agent,
            rate_limit=2.0,
            respect_robots=True
        )

    def parse(
        self,
        website: str,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[ManagementProfile]:
        """
        Parse management team information

        Args:
            website: Company website URL
            progress_callback: Optional callback for progress updates

        Returns:
            List of ManagementProfile objects
        """
        profiles = []

        if not website:
            return profiles

        try:
            if progress_callback:
                progress_callback("Looking for management/leadership pages...")

            # Find leadership pages
            soup = self.crawler.fetch_html(website)
            if not soup:
                return profiles

            # Look for leadership/management links
            leadership_patterns = [
                'leadership', 'management', 'executive', 'team',
                'board', 'directors', 'governance', 'about/team'
            ]

            leadership_links = find_links(soup, website, leadership_patterns)

            if progress_callback:
                progress_callback(f"Found {len(leadership_links)} potential leadership pages")

            # Visit leadership pages
            for link in leadership_links[:5]:  # Limit to first 5
                if progress_callback:
                    progress_callback(f"Parsing {link}...")

                page_profiles = self._parse_leadership_page(link)
                profiles.extend(page_profiles)

                if len(profiles) >= 50:  # Reasonable limit
                    break

        except Exception as e:
            logger.error(f"Error parsing management: {e}")
            if progress_callback:
                progress_callback(f"Error: {str(e)}")

        # Save management index
        self._save_management_index(profiles)

        return profiles

    def _parse_leadership_page(self, url: str) -> List[ManagementProfile]:
        """Parse a leadership/management page"""
        profiles = []

        try:
            soup = self.crawler.fetch_html(url)
            if not soup:
                return profiles

            # Determine if this is executives or board based on URL/title
            page_text = soup.get_text().lower()
            is_board = 'board' in url.lower() or 'board of directors' in page_text

            category = 'board' if is_board else 'executive'

            # Look for common patterns:
            # 1. Divs/sections with class containing "team", "profile", "bio", "executive"
            # 2. Heading (h2, h3, h4) with name + paragraph with title/bio

            # Method 1: Look for profile-like divs
            profile_containers = soup.find_all(['div', 'section', 'article'], class_=re.compile(r'(team|profile|bio|executive|director|leadership)', re.I))

            for container in profile_containers:
                # Try to extract name (usually in h2, h3, h4, or strong)
                name_tag = container.find(['h2', 'h3', 'h4', 'h5', 'strong'])
                if not name_tag:
                    continue

                name = name_tag.get_text(strip=True)
                if len(name) < 3 or len(name) > 100:  # Sanity check
                    continue

                # Try to extract title (often in a span, p, or div following the name)
                title = ""
                title_tag = container.find(['span', 'p', 'div'], class_=re.compile(r'title|position|role', re.I))
                if title_tag:
                    title = title_tag.get_text(strip=True)
                else:
                    # Look for text immediately after name
                    next_p = name_tag.find_next('p')
                    if next_p:
                        text = next_p.get_text(strip=True)
                        # If it's short, might be the title
                        if len(text) < 200:
                            title = text

                # Try to extract bio
                bio = ""
                bio_tag = container.find('p')
                if bio_tag:
                    bio = bio_tag.get_text(strip=True)[:1000]  # Limit length

                # Create profile
                if name and (title or bio):
                    profile = ManagementProfile(
                        name=name,
                        title=title or "Unknown",
                        category=category,
                        bio=bio if bio else None,
                        profile_url=url
                    )
                    profiles.append(profile)

            # Method 2: Simple heading + paragraph pattern
            if len(profiles) < 5:  # If we didn't find many, try simpler method
                for heading in soup.find_all(['h2', 'h3', 'h4']):
                    name = heading.get_text(strip=True)
                    if len(name) < 3 or len(name) > 100:
                        continue

                    # Look for following paragraph
                    next_p = heading.find_next('p')
                    if next_p:
                        text = next_p.get_text(strip=True)
                        # Try to split into title and bio
                        lines = text.split('\n')
                        title = lines[0] if lines else text[:200]
                        bio = '\n'.join(lines[1:]) if len(lines) > 1 else text

                        profile = ManagementProfile(
                            name=name,
                            title=title,
                            category=category,
                            bio=bio[:1000] if bio else None,
                            profile_url=url
                        )
                        profiles.append(profile)

        except Exception as e:
            logger.error(f"Error parsing leadership page {url}: {e}")

        return profiles

    def _save_management_index(self, profiles: List[ManagementProfile]):
        """Save management profiles to JSON"""
        index_path = self.website_dir / "management_team.json"
        # Deduplicate by name
        seen = set()
        unique_profiles = []
        for profile in profiles:
            if profile.name not in seen:
                seen.add(profile.name)
                unique_profiles.append(profile)

        index_data = [p.to_dict() for p in unique_profiles]
        save_json(index_data, index_path)


class ExtraLayer:
    """Orchestrates Extra Layer data collection"""

    def __init__(self, ticker_config: TickerConfig, data_dir: Path):
        self.config = ticker_config
        self.data_dir = data_dir

        # Initialize collectors
        self.website_crawler = WebsiteCrawler(ticker_config, data_dir)
        self.management_parser = ManagementParser(ticker_config, data_dir)

    def collect(
        self,
        company_website: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> dict:
        """
        Run full Extra Layer collection

        Args:
            company_website: Company website URL
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with collection results
        """
        results = {
            'website_crawl': {},
            'management': []
        }

        if not company_website:
            if progress_callback:
                progress_callback("No company website provided, skipping extra layer")
            return results

        # Crawl website for segments
        if self.config.collect_website_segments:
            if progress_callback:
                progress_callback(f"Starting website crawl (max {self.config.max_website_pages} pages, depth {self.config.website_crawl_depth})...")
            results['website_crawl'] = self.website_crawler.crawl(company_website, progress_callback)
        else:
            if progress_callback:
                progress_callback("Website crawl skipped (disabled in settings)")

        # Parse management
        if self.config.collect_management_profiles:
            if progress_callback:
                progress_callback("Parsing management team...")
            results['management'] = self.management_parser.parse(company_website, progress_callback)
        else:
            if progress_callback:
                progress_callback("Management parsing skipped (disabled in settings)")

        return results
