"""
Widget for displaying a single post.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QCheckBox,
    QLabel,
    QMenu,
)
from PySide6.QtCore import Qt, QEvent, QPoint
from PySide6.QtGui import QPixmap, QCursor
from reddit_explorer.data.models import RedditPost
from reddit_explorer.config.constants import IMAGE_MAX_WIDTH
from reddit_explorer.ui.main_window_interface import MainWindowInterface


class PostWidget(QFrame):
    """Widget to display a single post."""

    def __init__(
        self,
        post: RedditPost,
        main_window: MainWindowInterface,
        view_type: str = "subreddit",
        parent: Optional[QWidget] = None,
    ):
        """
        Initialize the post widget.

        Args:
            post: RedditPost object containing post data
            main_window: Main window instance
            view_type: Type of view ("subreddit" or "category")
            parent: Parent widget
        """
        super().__init__(parent)
        self.main_window = main_window
        self.view_type = view_type
        self.post_data = post

        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(1)

        # Enable mouse tracking for cursor changes
        self.setMouseTracking(True)
        # Make the widget clickable
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Set context menu policy
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._init_ui()

    def _init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)

        # Header layout (checkbox and title)
        header_layout = QHBoxLayout()

        # Checkbox container for better alignment
        checkbox_container = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_container)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox_layout.setSpacing(4)

        # Create both checkboxes but only show the relevant one
        self.added_checkbox = QCheckBox()
        self.added_checkbox.setToolTip("Add post")
        self.category_checkbox = QCheckBox()
        self.category_checkbox.setToolTip("Show in categories")

        if self.view_type == "subreddit":
            checkbox_layout.addWidget(self.added_checkbox)
            self.category_checkbox.hide()
        else:  # category view
            checkbox_layout.addWidget(self.category_checkbox)
            self.added_checkbox.hide()

        self.title = QLabel(self.post_data.title)
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-weight: bold;")

        header_layout.addWidget(checkbox_container)
        header_layout.addWidget(self.title, 1)
        layout.addLayout(header_layout)

        # Creation time
        time_str = self.post_data.created_time.strftime("%Y-%m-%d %H:%M:%S")
        self.time_label = QLabel(f"Posted: {time_str}")
        self.time_label.setStyleSheet("color: gray;")
        layout.addWidget(self.time_label)

        # Description
        if self.post_data.selftext:
            text = (
                f"{self.post_data.selftext[:300]}..."
                if len(self.post_data.selftext) > 300
                else self.post_data.selftext
            )
            self.description = QLabel(text)
            self.description.setWordWrap(True)
            layout.addWidget(self.description)

        # Image (if available)
        if self.post_data.url:
            image_path = self.main_window.image_service.cache_image(
                self.post_data.id, self.post_data.url
            )
            if image_path:
                image_label = QLabel()
                pixmap = QPixmap(image_path)
                # Scale image to fit width while maintaining aspect ratio
                scaled_pixmap = pixmap.scaledToWidth(
                    IMAGE_MAX_WIDTH, Qt.TransformationMode.SmoothTransformation
                )
                image_label.setPixmap(scaled_pixmap)
                layout.addWidget(image_label)

        # Footer (comments count)
        footer_layout = QHBoxLayout()
        self.comments = QLabel(f"Comments: {self.post_data.num_comments}")
        footer_layout.addWidget(self.comments)
        footer_layout.addStretch()
        layout.addLayout(footer_layout)

        # Store initial states
        self.is_saved = False  # Will be set by parent widget
        self.show_in_categories = True  # Will be set by parent widget

    def setup_checkbox_connections(self):
        """Connect checkbox signals after initial states are set."""
        self.added_checkbox.stateChanged.connect(self.on_added_checkbox_changed)
        self.category_checkbox.stateChanged.connect(self.on_category_checkbox_changed)

    def on_added_checkbox_changed(self, state: int):
        """Handle added checkbox state changes."""
        if state == 2:
            print("Saving post")
            self.main_window.save_post(self.post_data)
        else:
            print("Unsaving post")
            self.main_window.unsave_post(self.post_data)

    def on_category_checkbox_changed(self, state: int):
        """Handle category checkbox state changes."""
        if self.is_saved:  # Only update if post is saved
            self.main_window.update_post_category_visibility(
                self.post_data.id, state == 2
            )

    def mouseDoubleClickEvent(self, event: QEvent):
        """Handle double-click events to open post in browser."""
        # Get the post index if we're in a category
        if self.view_type == "category":
            for i, post in enumerate(self.main_window.current_category_posts):
                if post.id == self.post_data.id:
                    self.main_window.current_post_index = i
                    # Enable/disable Next button based on position
                    self.main_window.next_btn.setEnabled(
                        i < len(self.main_window.current_category_posts) - 1
                    )
                    break

        # Construct Reddit post URL
        post_url = f"https://www.reddit.com/r/{self.post_data.subreddit}/comments/{self.post_data.id}"

        # Update category checkbox state
        self.main_window.browser_category_checkbox.setChecked(True)

        # Show browser and navigation buttons
        self.main_window.browser.show()
        self.main_window.nav_buttons.show()
        self.main_window.subreddit_view.hide()
        self.main_window.browser.load_url(
            post_url, lambda ok: self.main_window.browser.hide_sidebar()
        )

    def enterEvent(self, event: QEvent):
        """Handle mouse enter events."""
        self.setStyleSheet("background-color: #f0f0f0;")

    def leaveEvent(self, event: QEvent):
        """Handle mouse leave events."""
        self.setStyleSheet("")

    def _show_context_menu(self, position: QPoint):
        """Show context menu for post widget."""
        if self.view_type != "category":
            return

        menu = QMenu()
        set_category_action = menu.addAction("Set category")
        action = menu.exec_(self.mapToGlobal(position))

        if action == set_category_action:
            self._show_category_menu()

    def _show_category_menu(self):
        """Show submenu to select category."""
        # Get list of categories from database
        cursor = self.main_window.db.get_cursor()
        cursor.execute("SELECT name FROM categories ORDER BY name")
        categories = [row[0] for row in cursor.fetchall()]

        # Create menu
        menu = QMenu()
        for category in categories:
            action = menu.addAction(category)
            action.setData(category)

        # Show menu at cursor position
        action = menu.exec_(self.cursor().pos())
        if action:
            new_category = action.data()
            cursor.execute(
                "UPDATE saved_posts SET category = ? WHERE reddit_id = ?",
                (new_category, self.post_data.id),
            )
            self.main_window.db.commit()

            # Refresh the view - using public methods
            self.main_window.refresh_category_counts()
            if (
                hasattr(self.main_window, "current_category")
                and self.main_window.current_category
            ):
                self.main_window.load_category_posts(self.main_window.current_category)
