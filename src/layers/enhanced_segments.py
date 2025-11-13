"""Enhanced business segments extraction from multiple sources"""
from pathlib import Path
from typing import List, Optional, Set, Dict
import logging
from bs4 import BeautifulSoup
import re

from ..models import BusinessSegment
from ..config import TickerConfig
from ..utils import ensure_dir, save_json
from ..utils.web_utils import WebCrawler, find_links, normalize_url, same_domain
from ..utils.text_extraction import extract_text_from_html, clean_text, extract_text_from_file
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class EnhancedSegmentsExtractor:
    """Extract business segments from website and 10-K filings"""

    def __init__(self, ticker_config: TickerConfig, data_dir: Path):
        self.config = ticker_config
        self.data_dir = data_dir
        self.website_dir = ensure_dir(data_dir / "website")
        self.sec_dir = data_dir / "sec_filings"

        self.crawler = WebCrawler(
            user_agent=ticker_config.sec_user_agent,
            rate_limit=2.0,
            respect_robots=False
        )

        # Collected segments with deduplication
        self.segments: Dict[str, BusinessSegment] = {}

    def extract_all(
        self,
        company_website: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> List[BusinessSegment]:
        """
        Extract segments from all available sources

        Args:
            company_website: Company website URL
            progress_callback: Progress callback

        Returns:
            List of BusinessSegment objects
        """
        # 1. Extract from 10-K filings
        if progress_callback:
            progress_callback("Extracting segments from 10-K filings...")
        self._extract_from_10k()

        # 2. Extract from website
        if company_website:
            if progress_callback:
                progress_callback("Extracting segments from company website...")
            self._extract_from_website(company_website)

        # Save results
        segments_list = list(self.segments.values())
        self._save_segments(segments_list)

        if progress_callback:
            progress_callback(f"Extracted {len(segments_list)} business segments")

        return segments_list

    def _extract_from_10k(self):
        """Extract segments from 10-K filings"""
        try:
            k10_dir = self.sec_dir / "10-K"
            if not k10_dir.exists():
                return

            # Get most recent 10-K
            txt_files = sorted(k10_dir.glob("*.txt"), reverse=True)
            if not txt_files:
                return

            # Parse the most recent one
            text = extract_text_from_file(txt_files[0])
            if not text:
                return

            # Look for business segments section
            self._parse_10k_segments(text)

        except Exception as e:
            logger.error(f"Error extracting from 10-K: {e}")

    def _parse_10k_segments(self, text: str):
        """Parse business segments from 10-K text"""
        # Common section headers for segments
        segment_patterns = [
            r'BUSINESS SEGMENTS?',
            r'OPERATING SEGMENTS?',
            r'REPORTABLE SEGMENTS?',
            r'SEGMENT INFORMATION',
            r'Item 1\..*Business',
            r'DESCRIPTION OF BUSINESS'
        ]

        for pattern in segment_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Extract the section (next ~10000 chars)
                section_start = match.end()
                section_text = text[section_start:section_start + 10000]

                # Look for segment names - often in headings or bolded
                # Pattern 1: Look for capitalized headings that might be segments
                lines = section_text.split('\n')

                current_segment = None
                current_description = []

                for line in lines:
                    line = line.strip()

                    # Check if line looks like a segment heading
                    # Usually short, may be all caps or title case
                    if len(line) > 5 and len(line) < 100:
                        # If it's mostly uppercase or looks like a title
                        if line.isupper() or (line[0].isupper() and sum(c.isupper() for c in line) > len(line) * 0.3):
                            # Save previous segment if exists
                            if current_segment and current_description:
                                desc = ' '.join(current_description)[:500]
                                if current_segment not in self.segments:
                                    self.segments[current_segment] = BusinessSegment(
                                        name=current_segment,
                                        description=desc,
                                        source_url=None,
                                        category='segment'
                                    )

                            # Start new segment
                            current_segment = line
                            current_description = []

                        elif current_segment and line:
                            # Add to description
                            current_description.append(line)

                # Save last segment
                if current_segment and current_description:
                    desc = ' '.join(current_description)[:500]
                    if current_segment not in self.segments:
                        self.segments[current_segment] = BusinessSegment(
                            name=current_segment,
                            description=desc,
                            source_url=None,
                            category='segment'
                        )

                break  # Found the section

    def _extract_from_website(self, website: str):
        """Extract segments from company website"""
        try:
            # Find product/solution/segment pages
            soup = self.crawler.fetch_html(website)
            if not soup:
                return

            # Target URL patterns for segments/products
            target_patterns = [
                '/product', '/solution', '/service', '/platform',
                '/industry', '/segment', '/business', '/offering',
                'what-we-do', 'our-business', 'markets'
            ]

            # Collect relevant links
            segment_links = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                link_text = a_tag.get_text(strip=True)

                # Build absolute URL
                absolute_url = urljoin(website, href)

                # Only same domain
                if not same_domain(absolute_url, website):
                    continue

                # Check if URL or link text matches patterns
                combined = f"{absolute_url} {link_text}".lower()
                if any(pattern in combined for pattern in target_patterns):
                    segment_links.append((absolute_url, link_text))

            # Deduplicate
            segment_links = list(set([normalize_url(url) for url, _ in segment_links]))

            # Visit each link
            for url in segment_links[:self.config.max_website_pages]:
                self._parse_segment_page(url)

            # Also check main pages
            self._parse_main_pages(website)

        except Exception as e:
            logger.error(f"Error extracting segments from website: {e}")

    def _parse_segment_page(self, url: str):
        """Parse a page for segment information"""
        try:
            soup = self.crawler.fetch_html(url)
            if not soup:
                return

            # Method 1: Look for structured segments
            segment_containers = soup.find_all(
                ['div', 'section', 'article'],
                class_=re.compile(r'(product|solution|service|segment|offering)', re.I)
            )

            for container in segment_containers:
                # Try to extract name and description
                name_tag = container.find(['h1', 'h2', 'h3', 'h4'])
                if name_tag:
                    name = name_tag.get_text(strip=True)
                    if len(name) > 5 and len(name) < 100:
                        # Get description
                        desc_tag = container.find('p')
                        description = desc_tag.get_text(strip=True)[:500] if desc_tag else ""

                        if name not in self.segments:
                            self.segments[name] = BusinessSegment(
                                name=name,
                                description=description,
                                source_url=url,
                                category='product'
                            )

            # Method 2: Look for lists of products/segments
            for list_tag in soup.find_all(['ul', 'ol']):
                # Check if list seems to be about products/segments
                list_text = list_tag.get_text()[:200].lower()
                if any(keyword in list_text for keyword in ['product', 'solution', 'service', 'segment']):
                    for li in list_tag.find_all('li', limit=20):
                        item_text = li.get_text(strip=True)
                        if len(item_text) > 5 and len(item_text) < 200:
                            # Split into name and description if possible
                            parts = item_text.split('-', 1)
                            name = parts[0].strip()
                            desc = parts[1].strip() if len(parts) > 1 else ""

                            if name and len(name) < 100 and name not in self.segments:
                                self.segments[name] = BusinessSegment(
                                    name=name,
                                    description=desc[:500],
                                    source_url=url,
                                    category='product'
                                )

            # Method 3: Look for feature sections with headings
            for heading in soup.find_all(['h2', 'h3', 'h4']):
                heading_text = heading.get_text(strip=True)
                if len(heading_text) > 5 and len(heading_text) < 100:
                    # Get following paragraph as description
                    next_p = heading.find_next('p')
                    if next_p:
                        description = next_p.get_text(strip=True)[:500]
                        if heading_text not in self.segments and description:
                            self.segments[heading_text] = BusinessSegment(
                                name=heading_text,
                                description=description,
                                source_url=url,
                                category='product'
                            )

        except Exception as e:
            logger.error(f"Error parsing segment page {url}: {e}")

    def _parse_main_pages(self, website: str):
        """Parse main pages (homepage, about) for segment mentions"""
        try:
            main_urls = [
                website,
                urljoin(website, '/about'),
                urljoin(website, '/about-us'),
                urljoin(website, '/company')
            ]

            for url in main_urls:
                soup = self.crawler.fetch_html(url)
                if not soup:
                    continue

                # Look for overview sections that mention segments
                for section in soup.find_all(['section', 'div'], class_=re.compile(r'(overview|about|business)', re.I)):
                    text = section.get_text()

                    # Look for phrases like "our products include" or "we offer"
                    patterns = [
                        r'(?:products?|solutions?|services?|offerings?|segments?)(?:\s+include|\s+are|\s+:)(.+?)(?:\.|;)',
                        r'we (?:provide|offer|deliver)(.+?)(?:\.|;)',
                    ]

                    for pattern in patterns:
                        matches = re.finditer(pattern, text, re.IGNORECASE)
                        for match in matches:
                            items_text = match.group(1)
                            # Split by commas/and
                            items = re.split(r',|\s+and\s+', items_text)
                            for item in items:
                                item = item.strip()
                                if len(item) > 5 and len(item) < 100 and item not in self.segments:
                                    self.segments[item] = BusinessSegment(
                                        name=item,
                                        description="",
                                        source_url=url,
                                        category='product'
                                    )

        except Exception as e:
            logger.error(f"Error parsing main pages: {e}")

    def _save_segments(self, segments: List[BusinessSegment]):
        """Save segments to JSON"""
        index_path = self.website_dir / "segments.json"
        # Clean up segments - remove obvious garbage
        clean_segments = []
        for seg in segments:
            # Skip segments that are too generic or look like menu items
            skip_words = ['home', 'about', 'contact', 'news', 'careers', 'privacy', 'terms', 'copyright']
            if seg.name.lower() in skip_words:
                continue
            if len(seg.name) < 3:
                continue
            clean_segments.append(seg)

        index_data = [s.to_dict() for s in clean_segments]
        save_json(index_data, index_path)
