"""
Data models for Reddit Explorer.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class RedditPost:
    """Represents a Reddit post."""

    id: str
    title: str
    url: Optional[str]
    subreddit: str
    created_utc: float
    num_comments: int
    selftext: str = ""

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "RedditPost":
        """Create a RedditPost instance from Reddit API data."""
        return cls(
            id=data["id"],
            title=data["title"],
            url=data.get("url"),
            subreddit=data["subreddit"],
            created_utc=data["created_utc"],
            num_comments=data["num_comments"],
            selftext=data.get("selftext", ""),
        )

    @property
    def created_time(self) -> datetime:
        """Get the post creation time as a datetime object."""
        return datetime.fromtimestamp(self.created_utc)


@dataclass
class SavedPost:
    """Represents a saved Reddit post."""

    id: int
    reddit_id: str
    subreddit_id: int
    title: str
    url: Optional[str]
    category: str
    is_read: bool
    show_in_categories: bool
    added_date: datetime

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "SavedPost":
        """Create a SavedPost instance from a database row."""
        return cls(
            id=row["id"],
            reddit_id=row["reddit_id"],
            subreddit_id=row["subreddit_id"],
            title=row["title"],
            url=row["url"],
            category=row["category"],
            is_read=bool(row["is_read"]),
            show_in_categories=bool(row["show_in_categories"]),
            added_date=datetime.strptime(row["added_date"], "%Y-%m-%d %H:%M:%S"),
        )


@dataclass
class Subreddit:
    """Represents a subreddit."""

    id: int
    name: str


@dataclass
class Category:
    """Represents a category for organizing saved posts."""

    id: int
    name: str
