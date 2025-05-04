from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any


@dataclass
class ReaderDocument:
    """
    Document object in Reader.
    """
    # Required document identifiers
    id: str
    url: str

    # Document details
    title: str
    source_url: Optional[str] = None
    author: Optional[str] = None
    source: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    site_name: Optional[str] = None
    word_count: Optional[int] = None
    notes: Optional[str] = None
    published_date: Optional[str] = None
    summary: Optional[str] = None
    html_content: Optional[str] = None
    image_url: Optional[str] = None
    parent_id: Optional[str] = None

    # Reading state
    reading_progress: float = 0.0
    first_opened_at: Optional[datetime] = None
    last_opened_at: Optional[datetime] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    saved_at: Optional[datetime] = None
    last_moved_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, doc: Dict[str, Any]) -> "ReaderDocument":
        """Create a ReaderDocument from a dictionary representation"""
        return cls(
            id=doc.get('id', ''),
            url=doc.get('url', ''),
            title=doc.get('title', 'Untitled'),
            source_url=doc.get('source_url'),
            author=doc.get('author'),
            source=doc.get('source'),
            category=doc.get('category'),
            location=doc.get('location'),
            tags=doc.get('tags', {}),
            site_name=doc.get('site_name'),
            word_count=doc.get('word_count'),
            notes=doc.get('notes'),
            published_date=doc.get('published_date'),
            summary=doc.get('summary'),
            html_content=doc.get('html_content'),
            image_url=doc.get('image_url'),
            parent_id=doc.get('parent_id'),
            reading_progress=doc.get('reading_progress', 0.0),
            first_opened_at=doc.get('first_opened_at'),
            last_opened_at=doc.get('last_opened_at'),
            created_at=doc.get('created_at'),
            updated_at=doc.get('updated_at'),
            saved_at=doc.get('saved_at'),
            last_moved_at=doc.get('last_moved_at')
        )


@dataclass
class ListDocumentResponse:
    """Response of the document list API"""
    count: int
    results: List[ReaderDocument]
    nextPageCursor: Optional[str] = None
