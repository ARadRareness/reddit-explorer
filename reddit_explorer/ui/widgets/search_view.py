"""
Widget for displaying search results.
"""

from typing import Optional, Callable, Any, Dict, cast
from PySide6.QtWidgets import (
    QScrollArea,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QCheckBox,
)
from PySide6.QtCore import Qt
from reddit_explorer.data.models import RedditPost
from reddit_explorer.ui.main_window_interface import MainWindowInterface
from reddit_explorer.ui.widgets.post_widget import PostWidget
import sqlite3
from datetime import datetime


class SearchView(QScrollArea):
    """Widget to display search results."""

    def __init__(
        self, main_window: MainWindowInterface, parent: Optional[QWidget] = None
    ):
        """
        Initialize the search view.

        Args:
            main_window: Main window instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.main_window = main_window
        self.update_title_callback: Optional[Callable[[str], None]] = None

        # Create container widget
        self.container = QWidget()
        self._layout = QVBoxLayout(self.container)
        self.setWidget(self.container)
        self.setWidgetResizable(True)

        # Create search controls
        self._init_search_controls()

        # Create results container
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self._layout.addWidget(self.results_container)

    def set_title_callback(self, callback: Callable[[str], None]):
        """Set the callback for updating the window title."""
        self.update_title_callback = callback

    def _init_search_controls(self):
        """Initialize search input and button."""
        # Create search controls container
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 8)

        # Create search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search terms...")
        self.search_input.returnPressed.connect(self._handle_search)

        # Create search button
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self._handle_search)
        self.search_button.setFixedWidth(100)

        # Create saved posts checkbox
        self.saved_only_checkbox = QCheckBox("Show only saved posts")
        self.saved_only_checkbox.setChecked(True)

        # Add widgets to layout
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)
        search_layout.addWidget(self.saved_only_checkbox)

        # Add search controls to main layout
        self._layout.addWidget(search_container)

    def _handle_search(self):
        """Handle search button click or enter key press."""
        search_term = self.search_input.text().strip()
        if not search_term:
            return

        # Clear previous results
        self.clear_results()

        # Get database cursor
        cursor = self.main_window.db.get_cursor()

        # Enable dictionary access to rows
        def dict_factory(
            cursor: sqlite3.Cursor, row: tuple[Any, ...]
        ) -> Dict[str, Any]:
            d = {}
            for idx, col in enumerate(cursor.description):
                d[col[0]] = row[idx]
            return d

        # Cast to avoid type error
        cursor.row_factory = cast(
            Callable[[sqlite3.Cursor, sqlite3.Row], Any], dict_factory
        )

        # Search in title, content, and summary with LIMIT
        base_query = """
            SELECT sp.*, s.name as subreddit_name
            FROM saved_posts sp
            JOIN subreddits s ON sp.subreddit_id = s.id
            WHERE (sp.title LIKE ? 
               OR sp.content LIKE ?
               OR sp.summary LIKE ?)
        """

        if self.saved_only_checkbox.isChecked():
            base_query += " AND sp.show_in_categories = 1"

        base_query += """
            ORDER BY sp.added_date DESC
            LIMIT 400
        """

        cursor.execute(
            base_query,
            (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"),
        )

        # Process results
        total_posts = 0
        for row in cursor.fetchall():
            # Create post data from database row
            post = RedditPost(
                id=row["reddit_id"],
                title=row["title"],
                url=row["url"],
                subreddit=row["subreddit_name"],
                created_utc=datetime.strptime(
                    row["added_date"], "%Y-%m-%d %H:%M:%S"
                ).timestamp(),
                num_comments=row["num_comments"],
                selftext=row["content"] or "",
            )

            # Add post to view
            self.add_post(
                post, is_saved=True, show_in_categories=row["show_in_categories"]
            )
            total_posts += 1

        # Update results count
        if total_posts == 0:
            self.show_no_results()
        else:
            if self.update_title_callback:
                self.update_title_callback(
                    f"Reddit Explorer - Search Results ({total_posts} posts)"
                )

    def clear_results(self):
        """Clear all search results."""
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def show_no_results(self):
        """Show no results message."""
        no_results = QLabel("No results found.")
        no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_results.setStyleSheet("color: gray; padding: 20px;")
        self.results_layout.addWidget(no_results)
        if self.update_title_callback:
            self.update_title_callback("Reddit Explorer - No Search Results")

    def add_post(
        self,
        post: RedditPost,
        is_saved: bool = False,
        show_in_categories: bool = True,
    ):
        """
        Add a post widget to the results.

        Args:
            post: RedditPost object containing post data
            is_saved: Whether the post is saved
            show_in_categories: Whether to show in categories view
        """
        post_widget = PostWidget(post, self.main_window, "search")
        post_widget.is_saved = is_saved
        post_widget.show_in_categories = show_in_categories
        post_widget.added_checkbox.setChecked(is_saved)
        post_widget.category_checkbox.setEnabled(is_saved)
        post_widget.category_checkbox.setChecked(show_in_categories)
        post_widget.setup_checkbox_connections()
        self.results_layout.addWidget(post_widget)
