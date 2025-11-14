"""
Base Layer: SEC filings, IR presentations, and earnings transcripts
"""
from pathlib import Path
from typing import List, Optional, Callable
import logging
from datetime import datetime, timedelta
from sec_edgar_downloader import Downloader
import time
import re

from ..models import SECFiling, IRPresentation, Transcript, TickerMetadata
from ..config import TickerConfig, APP_CONFIG
from ..utils import (
    ensure_dir, slugify_filename, save_text, save_json, load_json,
    extract_text_from_file, extract_text_from_html
)
from ..utils.web_utils import WebCrawler, find_links, same_domain
from ..utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# PDF conversion support
try:
    from weasyprint import HTML as WeasyHTML
    from weasyprint.text.fonts import FontConfiguration
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    logger.warning("weasyprint not available - PDF conversion will be skipped")


class SECFilingsCollector:
    """Collect SEC filings using sec-edgar-downloader"""

    def __init__(self, ticker_config: TickerConfig, data_dir: Path):
        self.config = ticker_config
        self.data_dir = data_dir
        self.filings_dir = ensure_dir(data_dir / "sec_filings")

        # Initialize SEC downloader
        self.downloader = Downloader(
            company_name="Research",
            email_address=ticker_config.sec_user_agent.split()[-1] if '@' in ticker_config.sec_user_agent else "research@example.com"
        )

        # Rate limiter for SEC (10 requests per second max)
        self.rate_limiter = RateLimiter(calls_per_second=10)

    def collect(
        self,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[SECFiling]:
        """
        Collect SEC filings for the ticker

        Args:
            progress_callback: Optional callback for progress updates

        Returns:
            List of SECFiling objects
        """
        filings = []
        ticker = self.config.ticker

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365 * self.config.lookback_years)

        # Form types to download based on config
        form_types = []
        if self.config.collect_10k:
            form_types.append('10-K')
        if self.config.collect_10q:
            form_types.append('10-Q')
        if self.config.collect_def14a:
            form_types.extend(['DEF 14A', 'DEFA14A'])
        if self.config.collect_8k:
            form_types.append('8-K')

        if not form_types:
            if progress_callback:
                progress_callback("No SEC filing types selected")
            return []

        for form_type in form_types:
            if progress_callback:
                progress_callback(f"Downloading {form_type} filings...")

            try:
                # Create form type directory
                form_dir = ensure_dir(self.filings_dir / form_type.replace(' ', '_'))

                # Download filings
                self.rate_limiter.wait()
                num_downloaded = self.downloader.get(
                    form_type,
                    ticker,
                    after=start_date.strftime('%Y-%m-%d'),
                    before=end_date.strftime('%Y-%m-%d'),
                    download_details=True
                )

                logger.info(f"Downloaded {num_downloaded} {form_type} filings for {ticker}")

                # Process downloaded filings
                filing_objects = self._process_downloaded_filings(form_type, form_dir)
                filings.extend(filing_objects)

            except Exception as e:
                logger.error(f"Error downloading {form_type} for {ticker}: {e}")
                if progress_callback:
                    progress_callback(f"Error downloading {form_type}: {str(e)}")

        # Save filings index
        self._save_filings_index(filings)

        if progress_callback:
            progress_callback(f"Collected {len(filings)} total filings")

        return filings

    def _process_downloaded_filings(self, form_type: str, form_dir: Path) -> List[SECFiling]:
        """Process downloaded filings and extract text"""
        filings = []

        # sec-edgar-downloader saves to: sec-edgar-filings/{ticker}/{form_type}/
        default_download_dir = Path("sec-edgar-filings") / self.config.ticker / form_type.replace(' ', '_')

        if not default_download_dir.exists():
            return filings

        # Iterate through downloaded filings
        for filing_dir in default_download_dir.iterdir():
            if not filing_dir.is_dir():
                continue

            try:
                # Parse accession number from directory name
                accession = filing_dir.name

                # Find the primary document (usually full-submission.txt or filing-details.html)
                primary_doc = None
                for doc_file in filing_dir.glob("*.txt"):
                    if "full-submission" in doc_file.name:
                        primary_doc = doc_file
                        break

                if not primary_doc:
                    # Try HTML
                    for doc_file in filing_dir.glob("*.html"):
                        primary_doc = doc_file
                        break

                if not primary_doc:
                    logger.warning(f"No primary document found in {filing_dir}")
                    continue

                # Extract filing date from filename or metadata
                filing_date = self._extract_filing_date(filing_dir, primary_doc)

                # Create SECFiling object
                filing = SECFiling(
                    form_type=form_type,
                    filing_date=filing_date,
                    accession_number=accession,
                    sec_url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={self.config.ticker}&type={form_type}&dateb=&owner=exclude&count=100",
                    local_path=str(primary_doc),
                    has_text_extract=False
                )

                # Extract text
                text_path = form_dir / f"{filing_date.strftime('%Y-%m-%d')}_{accession}_{form_type.replace(' ', '_')}.txt"
                if not text_path.exists():
                    text_content = extract_text_from_file(primary_doc)
                    if text_content:
                        save_text(text_content, text_path)
                        filing.has_text_extract = True

                # Handle file format based on user preference
                format_pref = self.config.sec_filing_format
                final_paths = []

                # Copy/convert based on format preference
                if format_pref in ["html", "both"]:
                    # Keep original HTML/TXT
                    organized_path = form_dir / f"{filing_date.strftime('%Y-%m-%d')}_{accession}_{form_type.replace(' ', '_')}{primary_doc.suffix}"
                    if not organized_path.exists():
                        import shutil
                        shutil.copy2(primary_doc, organized_path)
                    final_paths.append(organized_path)

                if format_pref in ["pdf", "both"]:
                    # Convert to PDF
                    pdf_path = form_dir / f"{filing_date.strftime('%Y-%m-%d')}_{accession}_{form_type.replace(' ', '_')}.pdf"
                    if not pdf_path.exists():
                        if self._convert_to_pdf(primary_doc, pdf_path):
                            final_paths.append(pdf_path)
                        else:
                            # Fallback to original if PDF conversion fails
                            logger.warning(f"PDF conversion failed for {primary_doc}, keeping original")
                            organized_path = form_dir / f"{filing_date.strftime('%Y-%m-%d')}_{accession}_{form_type.replace(' ', '_')}{primary_doc.suffix}"
                            if not organized_path.exists():
                                import shutil
                                shutil.copy2(primary_doc, organized_path)
                            final_paths.append(organized_path)
                    else:
                        final_paths.append(pdf_path)

                # Use the primary path (PDF if available, otherwise original)
                filing.local_path = str(final_paths[0]) if final_paths else str(primary_doc)

                filings.append(filing)

            except Exception as e:
                logger.error(f"Error processing filing {filing_dir}: {e}")

        return filings

    def _extract_filing_date(self, filing_dir: Path, primary_doc: Path) -> datetime:
        """Extract filing date from directory or document"""
        # Try to extract from directory name or document
        # Directory name format is usually the accession number
        # Look for metadata file
        for meta_file in filing_dir.glob("*.xml"):
            # Could parse XBRL metadata here
            pass

        # Fallback: use file modification time
        return datetime.fromtimestamp(primary_doc.stat().st_mtime)

    def _convert_to_pdf(self, source_file: Path, output_pdf: Path) -> bool:
        """
        Convert HTML or TXT file to PDF

        Args:
            source_file: Path to HTML or TXT file
            output_pdf: Path where PDF should be saved

        Returns:
            True if conversion succeeded, False otherwise
        """
        if not WEASYPRINT_AVAILABLE:
            logger.warning("weasyprint not installed - cannot convert to PDF")
            return False

        try:
            # Read source content
            with open(source_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Determine if HTML or plain text
            is_html = source_file.suffix.lower() in ['.html', '.htm']

            if not is_html:
                # Wrap plain text in basic HTML for better PDF rendering
                content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <style>
                        body {{
                            font-family: 'Courier New', monospace;
                            font-size: 10pt;
                            margin: 1in;
                            line-height: 1.4;
                            white-space: pre-wrap;
                            word-wrap: break-word;
                        }}
                    </style>
                </head>
                <body>
                {content}
                </body>
                </html>
                """

            # Convert to PDF
            font_config = FontConfiguration()
            html = WeasyHTML(string=content, base_url=str(source_file.parent))
            html.write_pdf(output_pdf, font_config=font_config)

            logger.info(f"Successfully converted {source_file.name} to PDF")
            return True

        except Exception as e:
            logger.error(f"Error converting {source_file} to PDF: {e}")
            return False

    def _save_filings_index(self, filings: List[SECFiling]):
        """Save filings index to JSON"""
        index_path = self.filings_dir / "filings_index.json"
        index_data = [f.to_dict() for f in filings]
        save_json(index_data, index_path)


class IRPresentationsCollector:
    """Collect investor relations presentations from company website"""

    def __init__(self, ticker_config: TickerConfig, data_dir: Path):
        self.config = ticker_config
        self.data_dir = data_dir
        self.ir_dir = ensure_dir(data_dir / "ir")
        self.presentations_dir = ensure_dir(self.ir_dir / "presentations")

        # Web crawler with rate limiting
        self.crawler = WebCrawler(
            user_agent=ticker_config.sec_user_agent,
            rate_limit=2.0,  # 2 seconds between requests
            respect_robots=False
        )

    def collect(
        self,
        company_website: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[IRPresentation]:
        """
        Collect IR presentations from company website

        Args:
            company_website: Company website URL (if known)
            progress_callback: Optional callback for progress updates

        Returns:
            List of IRPresentation objects
        """
        if not company_website:
            if progress_callback:
                progress_callback("No company website provided, skipping IR presentations")
            return []

        presentations = []

        try:
            if progress_callback:
                progress_callback(f"Finding IR page on {company_website}...")

            # Find IR page
            ir_url = self._find_ir_page(company_website)
            if not ir_url:
                if progress_callback:
                    progress_callback("Could not find IR page")
                return []

            if progress_callback:
                progress_callback(f"Found IR page: {ir_url}")

            # Find presentations
            presentation_links = self._find_presentation_links(ir_url)

            if progress_callback:
                progress_callback(f"Found {len(presentation_links)} potential presentations")

            # Download presentations
            cutoff_date = datetime.now() - timedelta(days=365 * self.config.lookback_years)

            for i, (url, title, date_str) in enumerate(presentation_links):
                # Parse date and check if within timeframe
                parsed_date = None
                if date_str:
                    try:
                        import dateparser
                        parsed_date = dateparser.parse(date_str)
                    except:
                        pass

                # Skip if date is outside our timeframe
                if parsed_date and parsed_date < cutoff_date:
                    if progress_callback:
                        progress_callback(f"Skipping old presentation: {title} ({date_str})")
                    continue

                if progress_callback:
                    progress_callback(f"Downloading presentation {i+1}/{len(presentation_links)}: {title}")

                presentation = self._download_presentation(url, title, date_str)
                if presentation:
                    presentations.append(presentation)

        except Exception as e:
            logger.error(f"Error collecting IR presentations: {e}")
            if progress_callback:
                progress_callback(f"Error: {str(e)}")

        # Save presentations index
        self._save_presentations_index(presentations)

        return presentations

    def _find_ir_page(self, website: str) -> Optional[str]:
        """Find the investor relations page"""
        soup = self.crawler.fetch_html(website)
        if not soup:
            return None

        # Look for IR links
        ir_patterns = [
            'investor', 'investors', 'investor relations',
            'ir', 'shareholder', 'financial'
        ]

        links = find_links(soup, website, ir_patterns)

        # Return the first match that looks like a main IR page
        for link in links:
            if any(pattern in link.lower() for pattern in ['investor', '/ir']):
                return link

        return links[0] if links else None

    def _find_presentation_links(self, ir_url: str) -> List[tuple]:
        """
        Find presentation file links from IR page

        Returns:
            List of (url, title, date_str) tuples
        """
        soup = self.crawler.fetch_html(ir_url)
        if not soup:
            return []

        presentations = []

        # Find links to PDFs, PPTs
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']

            # Check if it's a presentation file
            if not any(ext in href.lower() for ext in ['.pdf', '.ppt', '.pptx']):
                continue

            # Get title and try to extract date
            title = a_tag.get_text(strip=True) or "Untitled Presentation"

            # Look for date in surrounding context
            date_str = self._extract_date_from_context(a_tag)

            # Build absolute URL
            from urllib.parse import urljoin
            absolute_url = urljoin(ir_url, href)

            presentations.append((absolute_url, title, date_str))

        return presentations

    def _extract_date_from_context(self, tag) -> str:
        """Try to extract date from surrounding HTML context"""
        # Look in parent elements for dates
        parent = tag.parent
        for _ in range(3):  # Check up to 3 levels up
            if not parent:
                break
            text = parent.get_text()
            # Simple date pattern matching
            date_match = re.search(r'\d{4}[-/]\d{2}[-/]\d{2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}', text)
            if date_match:
                return date_match.group()
            parent = parent.parent

        return ""

    def _download_presentation(self, url: str, title: str, date_str: str) -> Optional[IRPresentation]:
        """Download a presentation file"""
        try:
            # Determine file type
            file_type = 'pdf'
            if '.ppt' in url.lower():
                file_type = 'pptx' if '.pptx' in url.lower() else 'ppt'

            # Create filename
            slug = slugify_filename(title)
            date_prefix = date_str.replace('/', '-').replace(' ', '_') if date_str else 'undated'
            filename = f"{date_prefix}_{slug}.{file_type}"
            save_path = self.presentations_dir / filename

            # Download
            if self.crawler.download_file(url, save_path):
                # Try to extract text if PDF
                has_text = False
                if file_type == 'pdf':
                    text_path = save_path.with_suffix('.txt')
                    if not text_path.exists():
                        text = extract_text_from_file(save_path)
                        if text:
                            save_text(text, text_path)
                            has_text = True

                # Parse date
                parsed_date = None
                if date_str:
                    try:
                        import dateparser
                        parsed_date = dateparser.parse(date_str)
                    except:
                        pass

                return IRPresentation(
                    title=title,
                    date=parsed_date,
                    url=url,
                    local_path=str(save_path),
                    event_type="general",
                    file_type=file_type,
                    has_text_extract=has_text
                )

        except Exception as e:
            logger.error(f"Error downloading presentation {url}: {e}")

        return None

    def _save_presentations_index(self, presentations: List[IRPresentation]):
        """Save presentations index to JSON"""
        index_path = self.ir_dir / "presentations_index.json"
        index_data = [p.to_dict() for p in presentations]
        save_json(index_data, index_path)


class TranscriptsCollector:
    """Collect earnings call transcripts"""

    def __init__(self, ticker_config: TickerConfig, data_dir: Path):
        self.config = ticker_config
        self.data_dir = data_dir
        self.transcripts_dir = ensure_dir(data_dir / "transcripts")
        self.ir_transcripts_dir = ensure_dir(data_dir / "ir" / "transcripts")

    def collect(
        self,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[Transcript]:
        """
        Collect transcripts from available sources

        Args:
            progress_callback: Optional callback for progress updates

        Returns:
            List of Transcript objects
        """
        transcripts = []

        # Note: Most transcripts are either:
        # 1. Available through IR website (handled by IR crawler)
        # 2. In SEC 8-K filings as exhibits (we'd need to parse exhibits)
        # 3. Behind paywalls (which we should not scrape)

        # For now, provide a placeholder for manual uploads
        # In a real implementation, you would:
        # - Check SEC 8-K exhibits for "Transcript" or "Prepared Remarks"
        # - Parse IR pages for transcript links
        # - Allow manual upload via Streamlit

        if progress_callback:
            progress_callback("Transcript collection requires manual upload or IR website parsing")

        # Save transcripts index
        self._save_transcripts_index(transcripts)

        return transcripts

    def save_uploaded_transcript(
        self,
        file_content: bytes,
        filename: str,
        fiscal_period: Optional[str] = None
    ) -> Transcript:
        """
        Save a manually uploaded transcript

        Args:
            file_content: File content bytes
            filename: Original filename
            fiscal_period: Optional fiscal period (e.g., "2024Q2")

        Returns:
            Transcript object
        """
        save_path = self.transcripts_dir / filename

        with open(save_path, 'wb') as f:
            f.write(file_content)

        # Extract text if possible
        has_text = False
        text_path = save_path.with_suffix('.txt')
        if not text_path.exists():
            try:
                text = extract_text_from_file(save_path)
                if text:
                    save_text(text, text_path)
                    has_text = True
            except:
                pass

        return Transcript(
            title=filename,
            fiscal_period=fiscal_period,
            source="manual_upload",
            local_path=str(save_path),
            has_text_extract=has_text
        )

    def _save_transcripts_index(self, transcripts: List[Transcript]):
        """Save transcripts index to JSON"""
        index_path = self.data_dir / "transcripts_index.json"
        index_data = [t.to_dict() for t in transcripts]
        save_json(index_data, index_path)


class BaseLayer:
    """Orchestrates Base Layer data collection"""

    def __init__(self, ticker_config: TickerConfig, data_dir: Path):
        self.config = ticker_config
        self.data_dir = data_dir

        # Initialize collectors
        self.sec_collector = SECFilingsCollector(ticker_config, data_dir)
        self.ir_collector = IRPresentationsCollector(ticker_config, data_dir)
        self.transcripts_collector = TranscriptsCollector(ticker_config, data_dir)

    def collect(
        self,
        company_website: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> dict:
        """
        Run full Base Layer collection

        Args:
            company_website: Company website URL
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with collection results
        """
        results = {
            'filings': [],
            'presentations': [],
            'transcripts': []
        }

        # Collect SEC filings (if any filing types are selected)
        if any([self.config.collect_10k, self.config.collect_10q,
                self.config.collect_def14a, self.config.collect_8k]):
            if progress_callback:
                progress_callback("Starting SEC filings collection...")
            results['filings'] = self.sec_collector.collect(progress_callback)
        else:
            if progress_callback:
                progress_callback("SEC filings collection skipped (no filing types selected)")

        # Collect IR presentations
        if self.config.collect_ir_presentations and company_website:
            if progress_callback:
                progress_callback("Starting IR presentations collection...")
            results['presentations'] = self.ir_collector.collect(company_website, progress_callback)
        else:
            if progress_callback:
                reason = "no website provided" if not company_website else "disabled in settings"
                progress_callback(f"IR presentations collection skipped ({reason})")

        # Collect transcripts
        if self.config.collect_transcripts:
            if progress_callback:
                progress_callback("Starting transcripts collection...")
            results['transcripts'] = self.transcripts_collector.collect(progress_callback)
        else:
            if progress_callback:
                progress_callback("Transcripts collection skipped (disabled in settings)")

        return results
