"""File handling utilities"""
from pathlib import Path
from slugify import slugify
import json
from typing import Any, Dict, List


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def slugify_filename(text: str, max_length: int = 100) -> str:
    """Convert text to safe filename"""
    slug = slugify(text, max_length=max_length)
    return slug if slug else "unnamed"


def save_text(content: str, filepath: Path):
    """Save text content to file"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def load_json(filepath: Path) -> Dict[str, Any]:
    """Load JSON from file"""
    if not filepath.exists():
        return {}
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data: Any, filepath: Path, indent: int = 2):
    """Save data as JSON"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, default=str)


def load_json_list(filepath: Path) -> List[Dict[str, Any]]:
    """Load JSON array from file"""
    if not filepath.exists():
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data if isinstance(data, list) else []
