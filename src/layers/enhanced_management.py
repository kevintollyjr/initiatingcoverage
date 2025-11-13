"""Enhanced management team extraction from multiple sources"""
from pathlib import Path
from typing import List, Optional, Set, Dict
import logging
from bs4 import BeautifulSoup
import re
import json

from ..models import ManagementProfile
from ..config import TickerConfig
from ..utils import ensure_dir, save_json
from ..utils.web_utils import WebCrawler, find_links
from ..utils.text_extraction import extract_text_from_file

logger = logging.getLogger(__name__)


class EnhancedManagementExtractor:
    """Extract management team from website, proxy statements, and Google"""

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

        # Collected profiles with deduplication
        self.profiles: Dict[str, ManagementProfile] = {}

    def extract_all(
        self,
        company_website: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> List[ManagementProfile]:
        """
        Extract management from all available sources

        Args:
            company_website: Company website URL
            progress_callback: Progress callback

        Returns:
            List of ManagementProfile objects
        """
        # 1. Extract from website
        if company_website:
            if progress_callback:
                progress_callback("Extracting management from company website...")
            self._extract_from_website(company_website)

        # 2. Extract from proxy statements (DEF 14A)
        if progress_callback:
            progress_callback("Extracting management from proxy statements...")
        self._extract_from_proxies()

        # 3. Enrich with Google searches
        if progress_callback:
            progress_callback(f"Enriching {len(self.profiles)} profiles with Google searches...")
        self._enrich_with_google()

        # Save results
        profiles_list = list(self.profiles.values())
        self._save_profiles(profiles_list)

        if progress_callback:
            progress_callback(f"Extracted {len(profiles_list)} total management profiles")

        return profiles_list

    def _extract_from_website(self, website: str):
        """Extract management from company website"""
        try:
            # Find leadership pages
            soup = self.crawler.fetch_html(website)
            if not soup:
                return

            # Look for leadership/management links
            leadership_patterns = [
                'leadership', 'management', 'executive', 'team',
                'board', 'directors', 'governance', 'about/team',
                'about-us/leadership', 'company/leadership'
            ]

            leadership_links = find_links(soup, website, leadership_patterns)

            for link in leadership_links[:10]:  # Check up to 10 pages
                self._parse_leadership_page(link, "website")

        except Exception as e:
            logger.error(f"Error extracting from website: {e}")

    def _parse_leadership_page(self, url: str, source: str):
        """Parse a leadership page for profiles"""
        try:
            soup = self.crawler.fetch_html(url)
            if not soup:
                return

            # Determine category from URL/title
            page_text = soup.get_text().lower()
            is_board = 'board' in url.lower() or 'board of directors' in page_text

            category = 'board' if is_board else 'executive'

            # Method 1: Look for structured profiles
            profile_containers = soup.find_all(
                ['div', 'section', 'article'],
                class_=re.compile(r'(team|profile|bio|executive|director|leadership|officer)', re.I)
            )

            for container in profile_containers:
                profile = self._extract_profile_from_container(container, category, source)
                if profile:
                    # Use name as key for deduplication
                    self.profiles[profile.name] = profile

            # Method 2: Look for simple heading + paragraph patterns
            for heading in soup.find_all(['h2', 'h3', 'h4', 'h5']):
                name = heading.get_text(strip=True)
                if len(name) < 3 or len(name) > 100:
                    continue

                # Skip common non-name headings
                skip_words = ['our', 'meet', 'leadership', 'team', 'board', 'executive', 'management']
                if any(word in name.lower() for word in skip_words):
                    continue

                next_elem = heading.find_next(['p', 'span', 'div'])
                if next_elem:
                    text = next_elem.get_text(strip=True)
                    # Check if it looks like a title (short) or bio
                    if text and len(text) < 500:
                        if name not in self.profiles:
                            # Try to separate title from bio
                            lines = text.split('\n')
                            title = lines[0] if lines else text[:200]
                            bio = '\n'.join(lines[1:]) if len(lines) > 1 else ""

                            profile = ManagementProfile(
                                name=name,
                                title=title,
                                category=category,
                                bio=bio[:1000] if bio else None,
                                profile_url=url
                            )
                            self.profiles[name] = profile

        except Exception as e:
            logger.error(f"Error parsing leadership page {url}: {e}")

    def _extract_profile_from_container(self, container, category: str, source: str) -> Optional[ManagementProfile]:
        """Extract a profile from a container element"""
        try:
            # Extract name
            name_tag = container.find(['h2', 'h3', 'h4', 'h5', 'strong', 'b'])
            if not name_tag:
                return None

            name = name_tag.get_text(strip=True)
            if len(name) < 3 or len(name) > 100:
                return None

            # Extract title
            title = ""
            title_tag = container.find(['span', 'p', 'div'], class_=re.compile(r'title|position|role', re.I))
            if title_tag:
                title = title_tag.get_text(strip=True)
            else:
                # Look for text after name
                next_p = name_tag.find_next('p')
                if next_p:
                    text = next_p.get_text(strip=True)
                    if len(text) < 200:
                        title = text

            # Extract bio
            bio = ""
            bio_tag = container.find('p')
            if bio_tag:
                bio = bio_tag.get_text(strip=True)[:1000]

            if name and (title or bio):
                return ManagementProfile(
                    name=name,
                    title=title or "Unknown",
                    category=category,
                    bio=bio if bio else None,
                    profile_url=container.get('href', '')
                )

        except Exception as e:
            logger.error(f"Error extracting profile from container: {e}")

        return None

    def _extract_from_proxies(self):
        """Extract management from DEF 14A proxy statements"""
        try:
            proxy_dir = self.sec_dir / "DEF_14A"
            if not proxy_dir.exists():
                return

            # Get all proxy text files
            for proxy_file in sorted(proxy_dir.glob("*.txt"), reverse=True)[:3]:  # Last 3 years
                try:
                    text = extract_text_from_file(proxy_file)
                    if not text:
                        continue

                    # Look for executive officers section
                    self._parse_proxy_executives(text)

                    # Look for board members section
                    self._parse_proxy_board(text)

                except Exception as e:
                    logger.error(f"Error parsing proxy {proxy_file}: {e}")

        except Exception as e:
            logger.error(f"Error extracting from proxies: {e}")

    def _parse_proxy_executives(self, text: str):
        """Parse executive officers from proxy text"""
        # Look for executive officers section
        exec_patterns = [
            r'EXECUTIVE OFFICERS',
            r'Executive Officers of',
            r'Our Executive Officers',
            r'INFORMATION ABOUT.*EXECUTIVE OFFICERS'
        ]

        for pattern in exec_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Extract the section (next ~5000 chars)
                section_start = match.end()
                section_text = text[section_start:section_start + 5000]

                # Look for name, age, title patterns
                # Common format: "John Doe, 55, Chief Executive Officer"
                name_patterns = [
                    r'([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),?\s*(?:age\s+)?(\d{2}),?\s+(.+?)(?:\n|\.)',
                    r'([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:serves as|is)\s+(?:our\s+)?(.+?)(?:\.|,)',
                ]

                for name_pattern in name_patterns:
                    matches = re.finditer(name_pattern, section_text)
                    for match in matches:
                        name = match.group(1).strip()
                        if len(name) > 100:
                            continue

                        # Get title (last group)
                        title = match.groups()[-1].strip()[:200]

                        if name and title and name not in self.profiles:
                            self.profiles[name] = ManagementProfile(
                                name=name,
                                title=title,
                                category='executive',
                                bio=None,
                                profile_url=None
                            )

                break  # Found the section

    def _parse_proxy_board(self, text: str):
        """Parse board members from proxy text"""
        # Look for board/director section
        board_patterns = [
            r'BOARD OF DIRECTORS',
            r'Our Board of Directors',
            r'Director Nominees',
            r'PROPOSAL.*ELECTION OF DIRECTORS'
        ]

        for pattern in board_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                section_start = match.end()
                section_text = text[section_start:section_start + 10000]

                # Look for director names and titles
                name_patterns = [
                    r'([A-Z][a-z]+ [A-Z]\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),?\s*(?:age\s+)?(\d{2})',
                    r'([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+has served',
                ]

                for name_pattern in name_patterns:
                    matches = re.finditer(name_pattern, section_text)
                    for match in matches:
                        name = match.group(1).strip()
                        if len(name) < 3 or len(name) > 100:
                            continue

                        # If not already in profiles, add as board member
                        if name not in self.profiles:
                            self.profiles[name] = ManagementProfile(
                                name=name,
                                title="Director",
                                category='board',
                                bio=None,
                                profile_url=None
                            )
                        else:
                            # Update category if it was executive
                            if self.profiles[name].category == 'executive':
                                self.profiles[name].category = 'board'  # They're on both

                break

    def _enrich_with_google(self):
        """Enrich profiles with Google search results"""
        try:
            import requests

            for name, profile in list(self.profiles.items()):
                try:
                    # Build search query
                    query = f"{name} {self.config.ticker} {profile.title}"

                    # Simple Google search (using basic search, not API)
                    search_url = f"https://www.google.com/search?q={requests.utils.quote(query)}"

                    response = self.crawler.fetch(search_url)
                    if response:
                        soup = BeautifulSoup(response.content, 'lxml')

                        # Try to extract snippets from search results
                        snippets = []
                        for result_div in soup.find_all('div', class_=re.compile(r'g'), limit=3):
                            snippet_div = result_div.find('div', class_=re.compile(r'VwiC3b'))
                            if snippet_div:
                                snippet = snippet_div.get_text(strip=True)
                                if snippet and len(snippet) > 20:
                                    snippets.append(snippet)

                        # Add snippets to bio if we don't have one
                        if snippets and not profile.bio:
                            profile.bio = ' '.join(snippets)[:1000]

                except Exception as e:
                    logger.warning(f"Could not enrich {name} with Google: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in Google enrichment: {e}")

    def _save_profiles(self, profiles: List[ManagementProfile]):
        """Save profiles to JSON"""
        index_path = self.website_dir / "management_team.json"
        index_data = [p.to_dict() for p in profiles]
        save_json(index_data, index_path)
