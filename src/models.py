"""
Data models for the equity research application
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import json


class FilingType(Enum):
    """SEC filing form types"""
    FORM_10K = "10-K"
    FORM_10Q = "10-Q"
    FORM_8K = "8-K"
    FORM_DEF14A = "DEF 14A"
    FORM_DEFA14A = "DEFA14A"
    OTHER = "OTHER"


@dataclass
class SECFiling:
    """SEC filing metadata"""
    form_type: str
    filing_date: datetime
    accession_number: str
    period_end: Optional[datetime] = None
    sec_url: str = ""
    local_path: Optional[str] = None
    has_text_extract: bool = False
    attachments: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        d = asdict(self)
        d['filing_date'] = self.filing_date.isoformat() if self.filing_date else None
        d['period_end'] = self.period_end.isoformat() if self.period_end else None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> 'SECFiling':
        """Create from dictionary"""
        if isinstance(data.get('filing_date'), str):
            data['filing_date'] = datetime.fromisoformat(data['filing_date'])
        if isinstance(data.get('period_end'), str) and data.get('period_end'):
            data['period_end'] = datetime.fromisoformat(data['period_end'])
        return cls(**data)


@dataclass
class IRPresentation:
    """Investor relations presentation metadata"""
    title: str
    date: Optional[datetime] = None
    url: str = ""
    local_path: Optional[str] = None
    event_type: str = "general"  # earnings, investor_day, conference, general
    file_type: str = "pdf"  # pdf, ppt, pptx
    has_text_extract: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d['date'] = self.date.isoformat() if self.date else None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> 'IRPresentation':
        if isinstance(data.get('date'), str) and data.get('date'):
            data['date'] = datetime.fromisoformat(data['date'])
        return cls(**data)


@dataclass
class Transcript:
    """Earnings call transcript metadata"""
    title: str
    date: Optional[datetime] = None
    fiscal_period: Optional[str] = None  # e.g., "2024Q2"
    source: str = "unknown"  # ir_website, sec_8k, manual_upload
    url: str = ""
    local_path: Optional[str] = None
    has_text_extract: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d['date'] = self.date.isoformat() if self.date else None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> 'Transcript':
        if isinstance(data.get('date'), str) and data.get('date'):
            data['date'] = datetime.fromisoformat(data['date'])
        return cls(**data)


@dataclass
class EarningsEstimate:
    """Earnings estimate and actuals"""
    fiscal_period: str  # e.g., "2024Q2"
    report_date: Optional[datetime] = None
    actual_eps: Optional[float] = None
    consensus_eps: Optional[float] = None
    surprise: Optional[float] = None
    surprise_percent: Optional[float] = None
    provider: str = "unknown"

    def to_dict(self) -> dict:
        d = asdict(self)
        d['report_date'] = self.report_date.isoformat() if self.report_date else None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> 'EarningsEstimate':
        if isinstance(data.get('report_date'), str) and data.get('report_date'):
            data['report_date'] = datetime.fromisoformat(data['report_date'])
        return cls(**data)


@dataclass
class PressRelease:
    """Press release metadata"""
    title: str
    date: Optional[datetime] = None
    url: str = ""
    category: str = "general"
    text: Optional[str] = None
    local_html_path: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d['date'] = self.date.isoformat() if self.date else None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> 'PressRelease':
        if isinstance(data.get('date'), str) and data.get('date'):
            data['date'] = datetime.fromisoformat(data['date'])
        return cls(**data)


@dataclass
class NewsArticle:
    """External news article metadata"""
    headline: str
    source: str
    timestamp: Optional[datetime] = None
    url: str = ""
    snippet: Optional[str] = None
    provider: str = "unknown"

    def to_dict(self) -> dict:
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat() if self.timestamp else None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> 'NewsArticle':
        if isinstance(data.get('timestamp'), str) and data.get('timestamp'):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class ManagementProfile:
    """Management/board member profile"""
    name: str
    title: str
    category: str = "executive"  # executive or board
    bio: Optional[str] = None
    profile_url: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'ManagementProfile':
        return cls(**data)


@dataclass
class BusinessSegment:
    """Business segment/product line"""
    name: str
    description: Optional[str] = None
    source_url: Optional[str] = None
    category: str = "segment"  # segment, product, solution

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'BusinessSegment':
        return cls(**data)


@dataclass
class TickerMetadata:
    """Overall metadata for a ticker's research"""
    ticker: str
    cik: Optional[str] = None
    company_name: Optional[str] = None
    website: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.now)
    layers_completed: List[str] = field(default_factory=list)

    # Counts
    filings_count: int = 0
    presentations_count: int = 0
    transcripts_count: int = 0
    press_releases_count: int = 0
    news_articles_count: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d['last_updated'] = self.last_updated.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> 'TickerMetadata':
        if isinstance(data.get('last_updated'), str):
            data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        return cls(**data)

    def save(self, path: str):
        """Save metadata to JSON file"""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> 'TickerMetadata':
        """Load metadata from JSON file"""
        with open(path, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)
