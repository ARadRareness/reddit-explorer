"""
Widget for displaying subreddit posts.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QScrollArea,
    QWidget,
    QVBoxLayout,
    QLabel,
)
from reddit_explorer.data.models import RedditPost
from reddit_explorer.ui.main_window_interface import MainWindowInterface
from reddit_explorer.ui.widgets.post_widget import PostWidget


class SubredditView(QScrollArea):
    """Widget to display subreddit posts."""

    def __init__(
        self, main_window: MainWindowInterface, parent: Optional[QWidget] = None
    ):
        """
        Initialize the subreddit view.

        Args:
            main_window: Main window instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.main_window = main_window

        # Create container widget
        self.container = QWidget()
        self._layout = QVBoxLayout(self.container)
        self.setWidget(self.container)
        self.setWidgetResizable(True)

    def clear(self):
        """Clear all posts."""
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def add_description(self, description: str):
        """
        Add a category description to the view.

        Args:
            description: The category description text
        """
        # Create description label with some styling
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(
            """
            QLabel {
                background-color: #f0f0f0;
                padding: 10px;
                border-radius: 5px;
                margin: 5px;
                font-style: italic;
            }
        """
        )
        self._layout.addWidget(desc_label)

    def add_post(
        self,
        post: RedditPost,
        is_saved: bool = False,
        show_in_categories: bool = True,
        view_type: str = "subreddit",
    ):
        """
        Add a post widget.

        Args:
            post: RedditPost object containing post data
            is_saved: Whether the post is saved
            show_in_categories: Whether to show in categories view
            view_type: Type of view ("subreddit" or "category")
        """
        post_widget = PostWidget(post, self.main_window, view_type)
        post_widget.is_saved = is_saved
        post_widget.show_in_categories = show_in_categories
        post_widget.added_checkbox.setChecked(is_saved)
        post_widget.category_checkbox.setEnabled(
            is_saved
        )  # Only enable if post is saved
        post_widget.category_checkbox.setChecked(show_in_categories)
        post_widget.setup_checkbox_connections()  # Connect signals after setting states
        self._layout.addWidget(post_widget)

        # Scroll to bottom after adding the post
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def scroll_to_bottom(self):
        """Scroll to the bottom of the view."""
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def remove_post_widget(self, post_id: str):
        """
        Remove a post widget by its ID.

        Args:
            post_id: ID of the post to remove
        """
        for i in range(self._layout.count()):
            widget = self._layout.itemAt(i).widget()
            if isinstance(widget, PostWidget) and widget.post_data.id == post_id:
                widget.deleteLater()
                self._layout.removeWidget(widget)
                break
