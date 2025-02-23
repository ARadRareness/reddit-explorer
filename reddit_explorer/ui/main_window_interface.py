"""
Interface for the main window to avoid circular dependencies.
"""

from typing import List, Protocol, TYPE_CHECKING
from PySide6.QtWidgets import QWidget, QPushButton, QCheckBox
from reddit_explorer.data.models import RedditPost
from reddit_explorer.data.database import Database
from reddit_explorer.services.image_service import ImageService
from reddit_explorer.ui.browser.browser_view import BrowserView

if TYPE_CHECKING:
    from reddit_explorer.ui.widgets.subreddit_view import SubredditView


class MainWindowInterface(Protocol):
    """Protocol defining the interface for the main window."""

    # Properties that must be defined by implementing classes
    db: Database
    image_service: ImageService
    browser: BrowserView
    subreddit_view: "SubredditView"
    nav_buttons: QWidget
    next_btn: QPushButton
    browser_category_checkbox: QCheckBox
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
