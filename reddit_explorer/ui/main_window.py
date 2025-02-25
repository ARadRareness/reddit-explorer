"""
Main window for the Reddit Explorer application.
"""

from typing import List, Optional, Dict, Any, cast, Callable
from datetime import datetime
import sqlite3
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFrame,
    QTreeWidget,
    QTreeWidgetItem,
    QCheckBox,
    QMenu,
    QSizePolicy,
    QInputDialog,
    QMessageBox,
    QProgressDialog,
)
from PySide6.QtCore import Qt, QPoint
from reddit_explorer.data.models import RedditPost
from reddit_explorer.data.database import Database
from reddit_explorer.services.reddit_service import RedditService
from reddit_explorer.services.image_service import ImageService
from reddit_explorer.services.ai_service import AIService
from reddit_explorer.ui.browser.browser_view import BrowserView
from reddit_explorer.ui.widgets.subreddit_view import SubredditView
from reddit_explorer.ui.main_window_interface import MainWindowInterface

# Type alias for row factory function
RowFactory = Callable[[sqlite3.Cursor, tuple[Any, ...]], Dict[str, Any]]


class RedditExplorer(QMainWindow):
    """Main window for the Reddit Explorer application."""

    def __init__(self):
        """Initialize the main window."""
        super().__init__()
        self.setWindowTitle("Reddit Explorer")
        self.setMinimumSize(1200, 800)

        # Initialize services
        self.db = Database()
        self.reddit_service = RedditService()
        self.image_service = ImageService()
        self.ai_service = AIService()

        # Initialize UI
        self._init_ui()

        # Initialize state
        self.current_category: Optional[str] = None
        self.current_category_posts: List[RedditPost] = []
        self.current_post_index: int = -1

    def _init_ui(self):
        """Initialize the UI components."""
        # Main layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Left panel (Explorer)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        # Tree widget for subreddits and categories
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Explorer")
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)

        # Make tree more compact horizontally
        self.tree.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        self.tree.setMinimumWidth(150)
        self.tree.setMaximumWidth(250)

        left_layout.addWidget(self.tree)

        # Right panel (Browser)
        right_panel = QWidget()
        right_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Navigation buttons
        self.nav_buttons = QWidget()
        self.nav_buttons.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        nav_layout = QHBoxLayout(self.nav_buttons)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(4)

        # Create navigation buttons and checkbox
        self.done_btn = QPushButton("Done")
        self.next_btn = QPushButton("Next")
        self.browser_category_checkbox = QCheckBox("Show in categories")
        self.browser_category_checkbox.setToolTip("Show post in categories view")

        # Set fixed height for buttons
        for btn in [self.done_btn, self.next_btn]:
            btn.setFixedHeight(24)
            btn.setStyleSheet("padding: 0px 8px;")

        # Add widgets to layout
        nav_layout.addWidget(self.browser_category_checkbox)
        nav_layout.addStretch()
        nav_layout.addWidget(self.next_btn)
        nav_layout.addWidget(self.done_btn)
        right_layout.addWidget(self.nav_buttons)
        self.nav_buttons.hide()

        # Create browser and subreddit view
        self.subreddit_view = SubredditView(self)
        self.browser = BrowserView(debug=False)
        right_layout.addWidget(self.subreddit_view)
        right_layout.addWidget(self.browser)
        self.browser.hide()

        # Add panels to main layout
        layout.addWidget(left_panel, 0)
        layout.addWidget(right_panel, 1)

        # Load initial data
        self._load_subreddits()
        self._setup_connections()

    def _load_subreddits(self):
        """Load subreddits and categories from database into tree widget."""
        cursor = self.db.get_cursor()

        # Create main categories in tree
        self.subreddits_root = QTreeWidgetItem(self.tree, ["Subreddits"])
        self.categories_root = QTreeWidgetItem(self.tree, ["Categories"])

        # Load subreddits under subreddits root
        cursor.execute("SELECT name FROM subreddits ORDER BY name")
        for row in cursor.fetchall():
            QTreeWidgetItem(self.subreddits_root, [row[0]])

        # Load categories and their post counts under categories root
        cursor.execute(
            """
            SELECT c.name, COUNT(sp.id) as post_count 
            FROM categories c 
            LEFT JOIN saved_posts sp ON sp.category = c.name AND sp.show_in_categories = 1
            GROUP BY c.name 
            ORDER BY c.name
        """
        )
        for row in cursor.fetchall():
            category_name = row[0]
            post_count = row[1]
            display_text = f"{category_name} ({post_count})"
            QTreeWidgetItem(self.categories_root, [display_text])

        self.tree.expandAll()

    def _setup_connections(self):
        """Setup signal/slot connections."""
        self.next_btn.clicked.connect(self._handle_next_click)
        self.done_btn.clicked.connect(self._handle_done_click)
        self.tree.itemClicked.connect(self._handle_tree_click)
        self.browser_category_checkbox.stateChanged.connect(
            self._handle_browser_category_changed
        )

    def _show_context_menu(self, position: QPoint):
        """Show context menu for tree items."""
        item = cast(Optional[QTreeWidgetItem], self.tree.itemAt(position))
        if item is None:
            return

        menu = QMenu()

        # Handle right-click on root items
        if item.text(0) == "Categories":
            add_action = menu.addAction("Add Category")
            action = menu.exec_(self.tree.viewport().mapToGlobal(position))

            if action == add_action:
                self._add_category()
            return
        elif item.text(0) == "Subreddits":
            add_action = menu.addAction("Add Subreddit")
            action = menu.exec_(self.tree.viewport().mapToGlobal(position))

            if action == add_action:
                self._add_subreddit_with_dialog()
            return

        # Handle right-click on category items
        parent = item.parent()
        if parent and parent.text(0) == "Categories":
            category_name = item.text(0).split(" (")[0]

            # Initialize menu actions
            rename_action = None
            remove_action = None
            uncategorize_action = None
            auto_categorize_action = menu.addAction("Analyze categories")
            analyze_action = menu.addAction("Download posts")
            set_desc_action = menu.addSeparator()
            set_desc_action = menu.addAction("Set description")

            # Don't allow renaming or removing Uncategorized
            if category_name != "Uncategorized":
                rename_action = menu.addAction("Rename")
                remove_action = menu.addAction("Remove")
                uncategorize_action = menu.addAction("Uncategorize posts")

            action = menu.exec_(self.tree.viewport().mapToGlobal(position))

            if action == set_desc_action:
                self._set_category_description(category_name)
            elif action == analyze_action:
                self._analyze_category_posts(category_name)
            elif action == auto_categorize_action:
                self._auto_categorize_posts(category_name)
            elif category_name != "Uncategorized":
                if action == rename_action:
                    self._rename_category(item, category_name)
                elif action == remove_action:
                    self._remove_category(item, category_name)
                elif action == uncategorize_action:
                    self._uncategorize_posts(item, category_name)
            return

        # Handle right-click on subreddit items
        if parent and parent.text(0) == "Subreddits":
            subreddit_name = item.text(0)
            show_200_action = menu.addAction("Show 200")
            menu.addSeparator()
            rename_action = menu.addAction("Rename")
            remove_action = menu.addAction("Remove")

            action = menu.exec_(self.tree.viewport().mapToGlobal(position))

            if action == remove_action:
                self._remove_subreddit(subreddit_name)
            elif action == rename_action:
                self._rename_subreddit(item, subreddit_name)
            elif action == show_200_action:
                self._load_subreddit_posts_fixed(subreddit_name, 200)

    def _add_category(self):
        """Show dialog to add a new category."""
        name, ok = QInputDialog.getText(self, "Add Category", "Enter category name:")

        if ok and name:
            # Clean the input - remove leading/trailing whitespace
            name = name.strip()

            if not name:  # Check if name is empty after stripping
                return

            cursor = self.db.get_cursor()
            try:
                # Add to database
                cursor.execute("INSERT INTO categories (name) VALUES (?)", (name,))
                self.db.commit()

                # Add to tree with initial count of 0
                display_text = f"{name} (0)"

                # Find the correct position to insert alphabetically
                insert_pos = 0
                for i in range(self.categories_root.childCount()):
                    item = self.categories_root.child(i)
                    current_name = item.text(0).split(" (")[0]
                    if name.lower() < current_name.lower():
                        break
                    insert_pos = i + 1

                # Insert at the correct position
                QTreeWidgetItem(self.categories_root)  # Create empty item
                self.categories_root.insertChild(
                    insert_pos, QTreeWidgetItem([display_text])
                )
                self.categories_root.takeChild(
                    self.categories_root.childCount() - 1
                )  # Remove empty item

            except sqlite3.IntegrityError:
                # Category already exists
                pass

    def _set_category_description(self, category_name: str):
        """Show dialog to set category description."""
        cursor = self.db.get_cursor()

        # Get current description
        cursor.execute(
            "SELECT description FROM categories WHERE name = ?", (category_name,)
        )
        result = cursor.fetchone()
        current_desc = result[0] if result and result[0] else ""

        # Show dialog with current description
        desc, ok = QInputDialog.getMultiLineText(
            self,
            "Set Category Description",
            "Enter description for category:",
            current_desc,
        )

        if ok:
            # Update description in database
            cursor.execute(
                "UPDATE categories SET description = ? WHERE name = ?",
                (desc.strip() if desc else None, category_name),
            )
            self.db.commit()

    def _remove_subreddit(self, subreddit_name: str):
        """Remove a subreddit from database and tree."""
        # Remove from database
        cursor = self.db.get_cursor()
        cursor.execute("DELETE FROM subreddits WHERE name = ?", (subreddit_name,))
        self.db.commit()

        # Remove from tree
        root = self.tree.findItems("Subreddits", Qt.MatchFlag.MatchExactly)[0]
        for i in range(root.childCount()):
            if root.child(i).text(0) == subreddit_name:
                root.removeChild(root.child(i))
                break

    def _handle_tree_click(self, item: QTreeWidgetItem):
        """Handle single-click events on tree items."""
        parent = cast(Optional[QTreeWidgetItem], item.parent())
        if parent is None:
            return

        if parent.text(0) == "Subreddits":
            subreddit_name = item.text(0)
            self._load_subreddit_posts(subreddit_name)
        elif parent.text(0) == "Categories":
            # Extract category name without post count
            category_name = item.text(0).split(" (")[0]
            self.load_category_posts(category_name)

    def _load_subreddit_posts(self, subreddit_name: str):
        """Load and display posts from a subreddit."""
        # Clear and hide browser and navigation buttons, show subreddit view
        self.browser.hide()
        self.nav_buttons.hide()
        self.subreddit_view.show()
        self.subreddit_view.clear()

        # Reset window title
        self.setWindowTitle("Reddit Explorer")

        # Get list of saved post IDs for this subreddit
        cursor = self.db.get_cursor()
        cursor.execute(
            """
            SELECT reddit_id FROM saved_posts sp
            JOIN subreddits s ON sp.subreddit_id = s.id
            WHERE s.name = ?
            """,
            (subreddit_name,),
        )
        saved_posts = {row[0] for row in cursor.fetchall()}

        # Fetch posts from Reddit
        posts = self.reddit_service.fetch_all_subreddit_posts(subreddit_name)

        # First find the most recent saved post
        posts_to_show = []
        found_saved = False
        for post in posts:
            is_saved = post.id in saved_posts
            posts_to_show.append(post)

            if is_saved:  # Stop if we found a saved post
                found_saved = True
                break

            if len(posts_to_show) >= 200:  # Also stop if we hit the limit
                break

        # Now reverse the posts we want to show
        posts_to_show.reverse()

        # Add posts to view
        total_posts = 0
        for post in posts_to_show:
            is_saved = post.id in saved_posts
            self.subreddit_view.add_post(post, is_saved, view_type="subreddit")
            total_posts += 1

        # Update window title with post count
        self.setWindowTitle(f"Reddit Explorer ({total_posts} posts)")

        # Scroll to top
        self.subreddit_view.verticalScrollBar().setValue(0)

    def load_category_posts(self, category_name: str):
        """Load and display posts from a specific category."""
        # Clear and hide browser and navigation buttons, show subreddit view
        self.browser.hide()
        self.nav_buttons.hide()
        self.subreddit_view.show()
        self.subreddit_view.clear()

        # Store category name for navigation
        self.current_category = category_name
        self.current_category_posts = []
        self.current_post_index = -1

        # Get posts for this category
        cursor = self.db.get_cursor()

        # Enable dictionary access to rows
        def dict_factory(
            cursor: sqlite3.Cursor, row: tuple[Any, ...]
        ) -> Dict[str, Any]:
            d = {}
            for idx, col in enumerate(cursor.description):
                d[col[0]] = row[idx]
            return d

        # Cast to avoid type error
        cursor.row_factory = cast(sqlite3.Row, dict_factory)

        cursor.execute(
            """
            SELECT sp.*, s.name as subreddit_name
            FROM saved_posts sp
            JOIN subreddits s ON sp.subreddit_id = s.id
            WHERE sp.category = ? AND sp.show_in_categories = 1
            ORDER BY sp.added_date DESC
            """,
            (category_name,),
        )

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
                selftext="",
            )

            # Add to navigation list since we're already filtering in SQL
            self.current_category_posts.append(post)

            # Add post to view
            self.subreddit_view.add_post(
                post,
                is_saved=True,
                show_in_categories=True,
                view_type="category",
            )
            total_posts += 1

        # Update window title with post count only
        self.setWindowTitle(f"Reddit Explorer ({total_posts} posts)")

    def _handle_next_click(self):
        """Handle Next button click - show next post in category."""
        if (
            not self.current_category_posts
            or self.current_post_index >= len(self.current_category_posts) - 1
        ):
            self.next_btn.setEnabled(False)
            return

        self.current_post_index += 1
        post = self.current_category_posts[self.current_post_index]

        # Update Next button state
        self.next_btn.setEnabled(
            self.current_post_index < len(self.current_category_posts) - 1
        )

        # Update checkbox state
        cursor = self.db.get_cursor()
        cursor.execute(
            "SELECT show_in_categories FROM saved_posts WHERE reddit_id = ?", (post.id,)
        )
        result = cursor.fetchone()
        if result:
            self.browser_category_checkbox.setChecked(bool(result[0]))

        # Construct and load Reddit post URL
        post_url = f"https://www.reddit.com/r/{post.subreddit}/comments/{post.id}"
        self.browser.load_url(post_url, lambda ok: self.browser.hide_sidebar())

    def _handle_done_click(self):
        """Handle Done button click - return to subreddit view."""
        if not self.subreddit_view.isHidden():
            return

        # Get current checkbox state before switching views
        show_in_categories = None
        if self.current_post_index >= 0 and self.current_post_index < len(
            self.current_category_posts
        ):
            post = self.current_category_posts[self.current_post_index]
            cursor = self.db.get_cursor()
            cursor.execute(
                "SELECT show_in_categories FROM saved_posts WHERE reddit_id = ?",
                (post.id,),
            )
            result = cursor.fetchone()
            if result:
                show_in_categories = bool(result[0])

        # Switch back to subreddit view
        self.browser.hide()
        self.nav_buttons.hide()
        self.subreddit_view.show()

        # Reset window title
        self.setWindowTitle("Reddit Explorer")

        # Clear browser URL to prevent memory usage
        self.browser.setUrl("")

        # If we were viewing a category, reload it to reflect any checkbox changes
        if self.current_category:
            self.load_category_posts(self.current_category)

            # Restore checkbox state if we have it
            if show_in_categories is not None:
                self.browser_category_checkbox.setChecked(show_in_categories)

    def _handle_browser_category_changed(self, state: int):
        """Handle category checkbox changes in browser view."""
        # Always update the database regardless of whether the post is in current_category_posts
        post = (
            self.current_category_posts[self.current_post_index]
            if self.current_category_posts
            else None
        )
        if post is None:
            return

        show_in_categories = state == 2
        self.update_post_category_visibility(post.id, show_in_categories)

        # Refresh category counts after visibility change
        self.refresh_category_counts()

    def save_post(self, post: RedditPost) -> None:
        """Save a post to the database."""
        cursor = self.db.get_cursor()

        # Get subreddit id - using case-insensitive comparison
        cursor.execute(
            "SELECT id FROM subreddits WHERE LOWER(name) = LOWER(?)", (post.subreddit,)
        )
        result = cursor.fetchone()
        if not result:
            # Add subreddit if it doesn't exist - use the original case from our tree widget
            root = self.tree.findItems("Subreddits", Qt.MatchFlag.MatchExactly)[0]
            existing_subreddit = None
            for i in range(root.childCount()):
                if root.child(i).text(0).lower() == post.subreddit.lower():
                    existing_subreddit = root.child(i).text(0)
                    break

            # If we found a matching subreddit, use its case, otherwise use the post's case
            subreddit_name = existing_subreddit or post.subreddit
            cursor.execute(
                "INSERT INTO subreddits (name) VALUES (?)", (subreddit_name,)
            )
            subreddit_id = cursor.lastrowid

            # Add to tree if it's a new subreddit
            if not existing_subreddit:
                QTreeWidgetItem(self.subreddits_root, [subreddit_name])
        else:
            subreddit_id = result[0]

        try:
            # Format the post's creation time for SQLite
            created_time = datetime.fromtimestamp(post.created_utc).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            cursor.execute(
                """
                INSERT INTO saved_posts (reddit_id, subreddit_id, title, url, category, show_in_categories, is_read, num_comments, added_date)
                VALUES (?, ?, ?, ?, 'Uncategorized', 1, 1, ?, ?)
                """,
                (
                    post.id,
                    subreddit_id,
                    post.title,
                    post.url,
                    post.num_comments,
                    created_time,
                ),
            )
            self.db.commit()

            # Refresh category counts after saving new post
            self.refresh_category_counts()

        except sqlite3.IntegrityError:
            # Post already saved
            pass

    def unsave_post(self, post: RedditPost) -> None:
        """Remove a post from saved posts."""
        cursor = self.db.get_cursor()
        cursor.execute("DELETE FROM saved_posts WHERE reddit_id = ?", (post.id,))
        self.db.commit()

        # Refresh category counts after deleting the post
        self.refresh_category_counts()

    def update_post_category_visibility(
        self, post_id: str, show_in_categories: bool
    ) -> None:
        """Update whether a post should be shown in categories view."""
        cursor = self.db.get_cursor()
        cursor.execute(
            "UPDATE saved_posts SET show_in_categories = ? WHERE reddit_id = ?",
            (1 if show_in_categories else 0, post_id),
        )
        self.db.commit()

        # Refresh category counts after visibility change
        self.refresh_category_counts()

    def add_subreddit(self, subreddit_name: str) -> None:
        """Add a new subreddit to database and tree."""
        cursor = self.db.get_cursor()
        try:
            cursor.execute(
                "INSERT INTO subreddits (name) VALUES (?)", (subreddit_name,)
            )
            self.db.commit()
            QTreeWidgetItem(self.subreddits_root, [subreddit_name])
        except sqlite3.IntegrityError:
            # Subreddit already exists
            pass

    def _add_subreddit_with_dialog(self):
        """Show dialog to add a new subreddit."""
        name, ok = QInputDialog.getText(self, "Add Subreddit", "Enter subreddit name:")

        if ok and name:
            # Clean the input - remove leading/trailing whitespace and r/ prefix if present
            name = name.strip()
            if name.lower().startswith("r/"):
                name = name[2:]

            if not name:  # Check if name is empty after cleaning
                return

            # Find the correct position to insert alphabetically
            insert_pos = 0
            for i in range(self.subreddits_root.childCount()):
                item = self.subreddits_root.child(i)
                if name.lower() < item.text(0).lower():
                    break
                insert_pos = i + 1

            try:
                # Add to database
                cursor = self.db.get_cursor()
                cursor.execute("INSERT INTO subreddits (name) VALUES (?)", (name,))
                self.db.commit()

                # Insert at the correct position
                QTreeWidgetItem(self.subreddits_root)  # Create empty item
                self.subreddits_root.insertChild(insert_pos, QTreeWidgetItem([name]))
                self.subreddits_root.takeChild(
                    self.subreddits_root.childCount() - 1
                )  # Remove empty item

            except sqlite3.IntegrityError:
                # Subreddit already exists
                pass

    def _rename_category(self, item: QTreeWidgetItem, old_name: str):
        """Show dialog to rename a category."""
        new_name, ok = QInputDialog.getText(
            self, "Rename Category", "Enter new category name:", text=old_name
        )

        if ok and new_name:
            # Clean the input
            new_name = new_name.strip()
            if not new_name or new_name == old_name:
                return

            cursor = self.db.get_cursor()
            try:
                # Update in database
                cursor.execute(
                    "UPDATE categories SET name = ? WHERE name = ?",
                    (new_name, old_name),
                )
                cursor.execute(
                    "UPDATE saved_posts SET category = ? WHERE category = ?",
                    (new_name, old_name),
                )
                self.db.commit()

                # Update tree item
                post_count = (
                    item.text(0).split(" (")[1].rstrip(")")
                )  # Get count from display text
                item.setText(0, f"{new_name} ({post_count})")

                # Move item to maintain alphabetical order
                parent = item.parent()
                current_index = parent.indexOfChild(item)
                parent.takeChild(current_index)

                # Find new position
                insert_pos = 0
                for i in range(parent.childCount()):
                    current_name = parent.child(i).text(0).split(" (")[0]
                    if new_name.lower() < current_name.lower():
                        break
                    insert_pos = i + 1

                parent.insertChild(insert_pos, item)

            except sqlite3.IntegrityError:
                # Category name already exists
                pass

    def _rename_subreddit(self, item: QTreeWidgetItem, old_name: str):
        """Show dialog to rename a subreddit."""
        new_name, ok = QInputDialog.getText(
            self, "Rename Subreddit", "Enter new subreddit name:", text=old_name
        )

        if ok and new_name:
            # Clean the input - remove leading/trailing whitespace and r/ prefix if present
            new_name = new_name.strip()
            if new_name.lower().startswith("r/"):
                new_name = new_name[2:]

            if not new_name or new_name == old_name:
                return

            cursor = self.db.get_cursor()
            try:
                # Update in database
                cursor.execute(
                    "UPDATE subreddits SET name = ? WHERE name = ?",
                    (new_name, old_name),
                )
                self.db.commit()

                # Update tree item
                item.setText(0, new_name)

                # Move item to maintain alphabetical order
                parent = item.parent()
                current_index = parent.indexOfChild(item)
                parent.takeChild(current_index)

                # Find new position
                insert_pos = 0
                for i in range(parent.childCount()):
                    if new_name.lower() < parent.child(i).text(0).lower():
                        break
                    insert_pos = i + 1

                parent.insertChild(insert_pos, item)

            except sqlite3.IntegrityError:
                # Subreddit name already exists
                pass

    def _remove_category(self, item: QTreeWidgetItem, category_name: str):
        """Remove a category after confirmation."""
        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            "Remove Category",
            f"Are you sure you want to remove the category '{category_name}'?\n\nAll posts in this category will be moved to 'Uncategorized'.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            cursor = self.db.get_cursor()
            try:
                # Move posts to Uncategorized
                cursor.execute(
                    "UPDATE saved_posts SET category = 'Uncategorized' WHERE category = ?",
                    (category_name,),
                )
                # Remove the category
                cursor.execute(
                    "DELETE FROM categories WHERE name = ?", (category_name,)
                )
                self.db.commit()

                # Remove from tree
                parent = item.parent()
                parent.takeChild(parent.indexOfChild(item))

                # Refresh category counts to update Uncategorized
                self.refresh_category_counts()

            except sqlite3.Error:
                # Handle database error
                pass

    def _uncategorize_posts(self, item: QTreeWidgetItem, category_name: str):
        """Move all posts from a category to Uncategorized after confirmation."""
        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            "Uncategorize Posts",
            f"Are you sure you want to move all posts from '{category_name}' to 'Uncategorized'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            cursor = self.db.get_cursor()
            try:
                # Move posts to Uncategorized
                cursor.execute(
                    "UPDATE saved_posts SET category = 'Uncategorized' WHERE category = ?",
                    (category_name,),
                )
                self.db.commit()

                # Refresh category counts to update both categories
                self.refresh_category_counts()

                # If we're currently viewing this category, switch to Uncategorized
                if self.current_category == category_name:
                    self.load_category_posts("Uncategorized")

            except sqlite3.Error:
                # Handle database error
                pass

    def refresh_category_counts(self):
        """Refresh the category counts in the tree widget."""
        cursor = self.db.get_cursor()

        # Get current category counts
        cursor.execute(
            """
            SELECT c.name, COUNT(sp.id) as post_count 
            FROM categories c 
            LEFT JOIN saved_posts sp ON sp.category = c.name AND sp.show_in_categories = 1
            GROUP BY c.name 
            ORDER BY c.name
            """
        )
        category_counts = {row[0]: row[1] for row in cursor.fetchall()}

        # Update tree items
        for i in range(self.categories_root.childCount()):
            item = self.categories_root.child(i)
            category_name = item.text(0).split(" (")[0]  # Get name without count
            count = category_counts.get(category_name, 0)
            item.setText(0, f"{category_name} ({count})")

    def _analyze_category_posts(self, category_name: str):
        """Analyze all unanalyzed posts in a category."""
        cursor = self.db.get_cursor()

        # Get all unanalyzed posts in the category
        cursor.execute(
            """
            SELECT sp.reddit_id, s.name as subreddit_name
            FROM saved_posts sp
            JOIN subreddits s ON sp.subreddit_id = s.id
            WHERE sp.category = ? AND sp.content IS NULL
            """,
            (category_name,),
        )
        posts = cursor.fetchall()

        if not posts:
            QMessageBox.information(
                self,
                "Download Complete",
                "All posts in this category have already been downloaded.",
            )
            return

        # Create progress dialog
        progress = QProgressDialog(
            "Downloading posts...", "Cancel", 0, len(posts), self
        )
        progress.setWindowTitle("Downloading Posts")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)  # Show immediately

        try:
            # Analyze each post
            for i, post in enumerate(posts):
                if progress.wasCanceled():
                    break

                reddit_id = post[0]
                subreddit_name = post[1]

                # Update progress
                progress.setValue(i)
                progress.setLabelText(f"Downloading post {i + 1} of {len(posts)}...")

                # Fetch and store analysis
                analysis = self.reddit_service.fetch_post_details(
                    subreddit_name, reddit_id
                )
                cursor.execute(
                    """
                    UPDATE saved_posts 
                    SET content = ?, content_date = CURRENT_TIMESTAMP
                    WHERE reddit_id = ?
                    """,
                    (analysis, reddit_id),
                )
                self.db.commit()

            # Ensure progress dialog is closed
            progress.setValue(len(posts))

            if not progress.wasCanceled():
                QMessageBox.information(
                    self,
                    "Download Complete",
                    f"Successfully downloaded {len(posts)} posts in {category_name}.",
                )

        except Exception as e:
            progress.cancel()  # Ensure progress dialog is closed on error
            QMessageBox.warning(
                self,
                "Download Error",
                f"An error occurred while downloading posts: {str(e)}",
            )

    def _auto_categorize_posts(self, category_name: str):
        """Auto-categorize all analyzed posts in a category using AI."""
        cursor = self.db.get_cursor()

        # First check for any undownloaded posts
        cursor.execute(
            """
            SELECT sp.reddit_id, s.name as subreddit_name
            FROM saved_posts sp
            JOIN subreddits s ON sp.subreddit_id = s.id
            WHERE sp.category = ? AND sp.content IS NULL
            """,
            (category_name,),
        )
        undownloaded_posts = cursor.fetchall()

        # If there are undownloaded posts, download them first
        if undownloaded_posts:
            # Create progress dialog for downloading
            download_progress = QProgressDialog(
                "Downloading posts...", "Cancel", 0, len(undownloaded_posts), self
            )
            download_progress.setWindowTitle("Downloading Posts")
            download_progress.setWindowModality(Qt.WindowModality.WindowModal)
            download_progress.setMinimumDuration(0)

            try:
                # Download each post
                for i, post in enumerate(undownloaded_posts):
                    if download_progress.wasCanceled():
                        return

                    reddit_id = post[0]
                    subreddit_name = post[1]

                    # Update progress
                    download_progress.setValue(i)
                    download_progress.setLabelText(
                        f"Downloading post {i + 1} of {len(undownloaded_posts)}..."
                    )

                    # Fetch and store content
                    content = self.reddit_service.fetch_post_details(
                        subreddit_name, reddit_id
                    )
                    cursor.execute(
                        """
                        UPDATE saved_posts 
                        SET content = ?, content_date = CURRENT_TIMESTAMP
                        WHERE reddit_id = ?
                        """,
                        (content, reddit_id),
                    )
                    self.db.commit()

                download_progress.setValue(len(undownloaded_posts))

            except Exception as e:
                download_progress.cancel()
                QMessageBox.warning(
                    self,
                    "Download Error",
                    f"An error occurred while downloading posts: {str(e)}",
                )
                return

        # Now get all posts with content for categorization
        cursor.execute(
            """
            SELECT sp.reddit_id, sp.title, sp.content, s.name as subreddit_name, sp.summary
            FROM saved_posts sp
            JOIN subreddits s ON sp.subreddit_id = s.id
            WHERE sp.category = ? AND sp.content IS NOT NULL
            """,
            (category_name,),
        )
        posts = cursor.fetchall()

        if not posts:
            QMessageBox.information(
                self,
                "Auto-categorize",
                "No posts found to categorize in this category.",
            )
            return

        # Get all categories and their descriptions
        cursor.execute("SELECT name, description FROM categories")
        categories = {row[0]: row[1] for row in cursor.fetchall()}

        # Create progress dialog for categorization
        progress = QProgressDialog(
            "Auto-categorizing posts...", "Cancel", 0, len(posts), self
        )
        progress.setWindowTitle("Auto-categorizing Posts")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        try:
            # Process each post
            for i, post_data in enumerate(posts):
                if progress.wasCanceled():
                    break

                # Update progress
                progress.setValue(i)
                progress.setLabelText(f"Categorizing post {i + 1} of {len(posts)}...")

                # Create RedditPost object
                post = RedditPost(
                    id=post_data[0],
                    title=post_data[1],
                    content=post_data[2] or "",  # Use content for categorization
                    subreddit=post_data[3],
                    created_utc=datetime.now().timestamp(),  # Not important for categorization
                    num_comments=0,  # Not important for categorization
                    url="",  # Not important for categorization
                )

                # Get AI suggestion, using existing summary if available
                suggested_category, summary = self.ai_service.categorize_post(
                    post, categories, post_data[4]
                )

                # Update category and summary if different
                if suggested_category != category_name or not post_data[4]:
                    cursor.execute(
                        "UPDATE saved_posts SET category = ?, summary = ? WHERE reddit_id = ?",
                        (suggested_category, summary, post.id),
                    )
                    self.db.commit()

            # Ensure progress dialog is closed
            progress.setValue(len(posts))

            if not progress.wasCanceled():
                # Refresh category counts
                self.refresh_category_counts()

                # If we're currently viewing this category, reload it
                if self.current_category == category_name:
                    self.load_category_posts(category_name)

                QMessageBox.information(
                    self,
                    "Auto-categorize Complete",
                    f"Successfully processed {len(posts)} posts.",
                )

        except Exception as e:
            progress.cancel()  # Ensure progress dialog is closed on error
            QMessageBox.warning(
                self,
                "Auto-categorize Error",
                f"An error occurred while categorizing posts: {str(e)}",
            )

    @property
    def current_category(self) -> Optional[str]:
        """Get the current category name."""
        return self._current_category

    @current_category.setter
    def current_category(self, value: Optional[str]):
        """Set the current category name."""
        self._current_category = value

    def _load_subreddit_posts_fixed(self, subreddit_name: str, post_count: int):
        """
        Load and display a fixed number of posts from a subreddit.

        Args:
            subreddit_name: Name of the subreddit
            post_count: Number of posts to display
        """
        # Clear and hide browser and navigation buttons, show subreddit view
        self.browser.hide()
        self.nav_buttons.hide()
        self.subreddit_view.show()
        self.subreddit_view.clear()

        # Reset window title
        self.setWindowTitle("Reddit Explorer")

        # Get list of saved post IDs for this subreddit
        cursor = self.db.get_cursor()
        cursor.execute(
            """
            SELECT reddit_id FROM saved_posts sp
            JOIN subreddits s ON sp.subreddit_id = s.id
            WHERE s.name = ?
            """,
            (subreddit_name,),
        )
        saved_posts = {row[0] for row in cursor.fetchall()}

        # Fetch posts from Reddit
        posts = self.reddit_service.fetch_all_subreddit_posts(
            subreddit_name, post_count
        )

        # Reverse posts to show oldest first
        posts.reverse()

        # Add posts to view
        total_posts = 0
        for post in posts:
            is_saved = post.id in saved_posts
            self.subreddit_view.add_post(post, is_saved, view_type="subreddit")
            total_posts += 1

            if total_posts >= post_count:  # Stop when we hit the requested count
                break

        # Update window title with post count
        self.setWindowTitle(f"Reddit Explorer ({total_posts} posts)")

        # Scroll to top
        self.subreddit_view.verticalScrollBar().setValue(0)
