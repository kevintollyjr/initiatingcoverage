"""Text extraction from various file formats"""
from pathlib import Path
from typing import Optional
import logging
from bs4 import BeautifulSoup
import html2text

logger = logging.getLogger(__name__)


def extract_text_from_html(html_content: str, method: str = "html2text") -> str:
    """
    Extract readable text from HTML

    Args:
        html_content: Raw HTML string
        method: 'html2text' or 'beautifulsoup'

    Returns:
        Extracted plain text
    """
    try:
        if method == "html2text":
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = True
            h.ignore_emphasis = False
            return h.handle(html_content)
        else:
            soup = BeautifulSoup(html_content, 'lxml')
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            return soup.get_text(separator='\n', strip=True)
    except Exception as e:
        logger.error(f"Error extracting text from HTML: {e}")
        return ""


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract text from PDF file

    Args:
        pdf_path: Path to PDF file

    Returns:
        Extracted text
    """
    text = ""

    # Try pdfplumber first
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
        if text.strip():
            return text
    except Exception as e:
        logger.warning(f"pdfplumber failed for {pdf_path}: {e}")

    # Fallback to PyMuPDF
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text() + "\n\n"
        doc.close()
        return text
    except Exception as e:
        logger.error(f"PyMuPDF also failed for {pdf_path}: {e}")
        return ""


def extract_text_from_file(file_path: Path) -> str:
    """
    Extract text from file based on extension

    Args:
        file_path: Path to file

    Returns:
        Extracted text
    """
    suffix = file_path.suffix.lower()

    if suffix == '.pdf':
        return extract_text_from_pdf(file_path)
    elif suffix in ['.html', '.htm']:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return extract_text_from_html(f.read())
    elif suffix == '.txt':
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    else:
        logger.warning(f"Unsupported file type: {suffix}")
        return ""


def clean_text(text: str) -> str:
    """Clean and normalize extracted text"""
    # Remove excessive whitespace
    lines = [line.strip() for line in text.split('\n')]
    lines = [line for line in lines if line]
    return '\n'.join(lines)
