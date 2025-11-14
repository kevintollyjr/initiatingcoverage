"""Comprehensive website crawler for business intelligence"""
from pathlib import Path
from typing import List, Optional, Set, Dict, Callable
import logging
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import re
from datetime import datetime

from ..config import TickerConfig
from ..utils import ensure_dir, save_json, save_text, slugify_filename
from ..utils.web_utils import WebCrawler, normalize_url, same_domain
from ..utils.text_extraction import extract_text_from_html, clean_text

logger = logging.getLogger(__name__)


class ComprehensiveWebCrawler:
    """
    Crawls entire company website to extract all business-relevant information

    Targets:
    - About Us / Company History
    - Products & Services
    - Technology & Innovation
    - Strategy & Vision
    - Case Studies & Success Stories
    - Press Releases & News
    - Blog Posts
    - White Papers & Research
    - Partnerships & Alliances
    - Sustainability & ESG
    - Careers & Culture
    """

    def __init__(self, ticker_config: TickerConfig, data_dir: Path):
        self.config = ticker_config
        self.data_dir = data_dir
        self.website_dir = ensure_dir(data_dir / "website")
        self.content_dir = ensure_dir(self.website_dir / "business_content")

        self.crawler = WebCrawler(
            user_agent=ticker_config.sec_user_agent,
            rate_limit=2.0,
            respect_robots=False
        )

        self.visited_urls: Set[str] = set()
        self.content_index: List[Dict] = []

    def crawl_comprehensive(
        self,
        website: str,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, any]:
        """
        Comprehensive crawl of company website

        Args:
            website: Company website URL
            progress_callback: Progress callback

        Returns:
            Dictionary with crawl results and content index
        """
        results = {
            'pages_crawled': 0,
            'content_items': 0,
            'categories': {}
        }

        if not website:
            return results

        try:
            if progress_callback:
                progress_callback("Starting comprehensive website crawl...")

            # Define target categories and URL patterns
            categories = {
                'about': ['/about', '/company', '/who-we-are', '/our-story', '/history'],
                'products': ['/product', '/solution', '/service', '/platform', '/offering'],
                'technology': ['/technology', '/innovation', '/research', '/rd', '/patents'],
                'strategy': ['/strategy', '/vision', '/mission', '/values', '/purpose'],
                'industries': ['/industry', '/industries', '/sector', '/markets', '/verticals'],
                'case_studies': ['/case-stud', '/success-stor', '/customer', '/testimonial'],
                'news': ['/news', '/press', '/media', '/newsroom', '/announcement'],
                'blog': ['/blog', '/insights', '/perspective', '/thought-leadership'],
                'resources': ['/resource', '/whitepaper', '/report', '/publication', '/research'],
                'partners': ['/partner', '/alliance', '/ecosystem', '/integration'],
                'sustainability': ['/sustainability', '/esg', '/csr', '/environment', '/social'],
                'careers': ['/career', '/jobs', '/culture', '/life-at', '/working-at']
            }

            # Start with homepage
            self._crawl_page(website, 'homepage', results)

            # Crawl each category
            for category, patterns in categories.items():
                if progress_callback:
                    progress_callback(f"Crawling {category} section...")

                category_urls = self._find_category_urls(website, patterns)

                for url in category_urls[:20]:  # Limit per category
                    if len(self.visited_urls) >= self.config.max_website_pages:
                        break

                    self._crawl_page(url, category, results)

                if category not in results['categories']:
                    results['categories'][category] = 0
                results['categories'][category] = len([
                    item for item in self.content_index
                    if item.get('category') == category
                ])

            # Save content index
            self._save_content_index()

            results['pages_crawled'] = len(self.visited_urls)
            results['content_items'] = len(self.content_index)

            if progress_callback:
                progress_callback(f"Crawled {results['pages_crawled']} pages, extracted {results['content_items']} content items")

        except Exception as e:
            logger.error(f"Error in comprehensive crawl: {e}")

        return results

    def _find_category_urls(self, website: str, patterns: List[str]) -> List[str]:
        """Find URLs matching category patterns"""
        urls = set()

        # Check homepage for links
        soup = self.crawler.fetch_html(website)
        if not soup:
            return list(urls)

        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            link_text = a_tag.get_text(strip=True)

            # Build absolute URL
            absolute_url = urljoin(website, href)

            # Only same domain
            if not same_domain(absolute_url, website):
                continue

            # Check if matches any pattern
            combined = f"{absolute_url} {link_text}".lower()
            if any(pattern in combined for pattern in patterns):
                urls.add(normalize_url(absolute_url))

        return list(urls)

    def _crawl_page(self, url: str, category: str, results: Dict):
        """Crawl a single page and extract content"""
        if url in self.visited_urls:
            return

        if len(self.visited_urls) >= self.config.max_website_pages:
            return

        self.visited_urls.add(url)

        try:
            soup = self.crawler.fetch_html(url)
            if not soup:
                return

            # Extract page title
            title = soup.find('title')
            page_title = title.get_text(strip=True) if title else "Untitled"

            # Extract main content
            content = self._extract_main_content(soup)
            if not content or len(content) < 100:
                return

            # Create filename
            slug = slugify_filename(page_title)
            filename = f"{category}_{slug}"

            # Save content
            content_path = self.content_dir / f"{filename}.txt"
            save_text(content, content_path)

            # Extract metadata
            metadata = self._extract_metadata(soup, url, category, page_title)

            # Add to index
            self.content_index.append({
                'title': page_title,
                'url': url,
                'category': category,
                'file_path': str(content_path),
                'word_count': len(content.split()),
                'metadata': metadata,
                'crawled_at': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Error crawling page {url}: {e}")

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main content from page, removing navigation/footer/etc."""
        # Remove unwanted elements
        for element in soup(['nav', 'header', 'footer', 'script', 'style', 'iframe', 'noscript']):
            element.decompose()

        # Try to find main content container
        main_content = None

        # Look for common main content tags/classes
        for selector in [
            'main',
            'article',
            '[role="main"]',
            '.main-content',
            '.content',
            '#content',
            '.article-content',
            '.post-content'
        ]:
            main_content = soup.select_one(selector)
            if main_content:
                break

        # Fallback to body
        if not main_content:
            main_content = soup.find('body')

        if not main_content:
            return ""

        # Extract and clean text
        text = extract_text_from_html(str(main_content))
        return clean_text(text)

    def _extract_metadata(self, soup: BeautifulSoup, url: str, category: str, title: str) -> Dict:
        """Extract metadata from page"""
        metadata = {
            'description': '',
            'keywords': [],
            'author': '',
            'date_published': None,
            'headings': []
        }

        # Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            metadata['description'] = meta_desc['content'][:500]

        # Meta keywords
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords and meta_keywords.get('content'):
            metadata['keywords'] = [k.strip() for k in meta_keywords['content'].split(',')]

        # Author
        meta_author = soup.find('meta', attrs={'name': 'author'})
        if meta_author and meta_author.get('content'):
            metadata['author'] = meta_author['content']

        # Published date (various formats)
        date_selectors = [
            ('meta', {'property': 'article:published_time'}),
            ('meta', {'name': 'publication_date'}),
            ('meta', {'name': 'date'}),
            ('time', {'datetime': True})
        ]

        for tag, attrs in date_selectors:
            date_elem = soup.find(tag, attrs=attrs)
            if date_elem:
                date_val = date_elem.get('content') or date_elem.get('datetime') or date_elem.get_text()
                if date_val:
                    try:
                        import dateparser
                        parsed_date = dateparser.parse(date_val)
                        if parsed_date:
                            metadata['date_published'] = parsed_date.isoformat()
                            break
                    except:
                        pass

        # Extract headings structure
        for heading in soup.find_all(['h1', 'h2', 'h3']):
            heading_text = heading.get_text(strip=True)
            if heading_text and len(heading_text) < 200:
                metadata['headings'].append({
                    'level': heading.name,
                    'text': heading_text
                })

        return metadata

    def _save_content_index(self):
        """Save content index to JSON"""
        index_path = self.website_dir / "content_index.json"
        save_json(self.content_index, index_path)
