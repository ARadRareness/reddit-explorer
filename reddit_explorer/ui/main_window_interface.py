"""
Interface for the main window to avoid circular dependencies.
"""

from typing import List, Protocol, TYPE_CHECKING, Optional
from PySide6.QtWidgets import QWidget, QPushButton, QCheckBox
from reddit_explorer.data.models import RedditPost
from reddit_explorer.data.database import Database
from reddit_explorer.services.image_service import ImageService
from reddit_explorer.services.ai_service import AIService
from reddit_explorer.ui.browser.browser_view import BrowserView

if TYPE_CHECKING:
    from reddit_explorer.ui.widgets.subreddit_view import SubredditView
    from reddit_explorer.ui.widgets.summarize_view import SummarizeView
    from reddit_explorer.ui.widgets.search_view import SearchView


class MainWindowInterface(Protocol):
    """Protocol defining the interface for the main window."""

    # Properties that must be defined by implementing classes
    db: Database
    image_service: ImageService
    ai_service: AIService
    browser: BrowserView
    subreddit_view: "SubredditView"
    summarize_view: "SummarizeView"
    search_view: "SearchView"
    nav_buttons: QWidget
    next_btn: QPushButton
    browser_category_checkbox: QCheckBox
    current_category: Optional[str]
    current_category_posts: List[RedditPost]
    current_post_index: int

    def save_post(self, post: RedditPost) -> None:
        """Save a post to the database."""
        ...

    def unsave_post(self, post: RedditPost) -> None:
        """Remove a post from saved posts."""
        ...

    def update_post_category_visibility(
        self, post_id: str, show_in_categories: bool
    ) -> None:
        """Update whether a post should be shown in categories view."""
        ...

    def refresh_category_counts(self) -> None:
        """Refresh the category counts in the tree widget."""
        ...

    def load_category_posts(self, category_name: str) -> None:
        """Load and display posts from a specific category."""
        ...

    def generate_summaries(self, time_period: str = "Last 24 hours") -> None:
        """Generate summaries for posts in a time period."""
        ...

    def open_post(self, post_id: str) -> None:
        """Open a post in the browser view."""
        ...
