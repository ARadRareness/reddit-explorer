"""
Widget for displaying summarized content.
"""

from typing import Optional, List, Dict, Tuple
from PySide6.QtWidgets import (
    QScrollArea,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
)
from PySide6.QtCore import Qt
from reddit_explorer.ui.main_window_interface import MainWindowInterface


class SummarizeView(QScrollArea):
    """Widget to display summarized content with bullet points."""

    def __init__(
        self, main_window: MainWindowInterface, parent: Optional[QWidget] = None
    ):
        """
        Initialize the summarize view.

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

        # Create Generate button
        self.generate_btn = QPushButton("Generate")
        self.generate_btn.setFixedHeight(32)
        self.generate_btn.clicked.connect(self.main_window.generate_summaries)
        self._layout.addWidget(self.generate_btn)

        # Create content area
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self._layout.addWidget(self.content_widget)

        # Initialize empty cache for summaries
        self.summary_cache: Dict[str, List[Tuple[str, str]]] = {}

    def clear(self):
        """Clear all content."""
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def display_summaries(self, time_period: str, summaries: List[Tuple[str, str]]):
        """
        Display summarized bullet points.

        Args:
            time_period: The time period being summarized (e.g. "Last 24 hours")
            summaries: List of tuples containing (bullet_point, post_id)
        """
        # Cache the summaries
        self.summary_cache[time_period] = summaries

        # Clear existing content
        self.clear()

        # Add title
        title = QLabel(f"Summary for {time_period}")
        title.setStyleSheet(
            """
            QLabel {
                font-size: 16px;
                font-weight: bold;
                margin: 10px 0;
            }
        """
        )
        self.content_layout.addWidget(title)

        # Add each bullet point
        for bullet_point, post_id in summaries:
            bullet_widget = QLabel(f"• {bullet_point}")
            bullet_widget.setWordWrap(True)
            bullet_widget.setTextFormat(Qt.TextFormat.RichText)
            bullet_widget.setOpenExternalLinks(True)

            # Make the bullet point clickable if it has a post_id
            if post_id:
                bullet_widget.setCursor(Qt.CursorShape.PointingHandCursor)
                bullet_widget.mousePressEvent = (
                    lambda _, pid=post_id: self.main_window.open_post(pid)
                )

            self.content_layout.addWidget(bullet_widget)

        # Add stretch at the end
        self.content_layout.addStretch()

    def get_cached_summaries(self, time_period: str) -> Optional[List[Tuple[str, str]]]:
        """
        Get cached summaries for a time period.

        Args:
            time_period: The time period to get summaries for

        Returns:
            List of tuples containing (bullet_point, post_id) or None if not cached
        """
        return self.summary_cache.get(time_period)
