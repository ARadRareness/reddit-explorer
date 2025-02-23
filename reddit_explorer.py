import sys
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QPushButton,
    QFrame,
    QTreeWidgetItem,
    QScrollArea,
    QCheckBox,
    QLabel,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt
import sqlite3
import requests
from datetime import datetime
import json


class PostWidget(QFrame):
    """Widget to display a single post"""

    def __init__(self, post_data, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(1)

        layout = QVBoxLayout(self)

        # Header layout (checkbox and title)
        header_layout = QHBoxLayout()
        self.checkbox = QCheckBox()
        self.title = QLabel(post_data["title"])
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-weight: bold;")

        header_layout.addWidget(self.checkbox)
        header_layout.addWidget(self.title, 1)
        layout.addLayout(header_layout)

        # Description
        if post_data.get("selftext"):
            self.description = QLabel(
                post_data["selftext"][:300] + "..."
                if len(post_data["selftext"]) > 300
                else post_data["selftext"]
            )
            self.description.setWordWrap(True)
            layout.addWidget(self.description)

        # Footer (comments count)
        footer_layout = QHBoxLayout()
        self.comments = QLabel(f"Comments: {post_data['num_comments']}")
        footer_layout.addWidget(self.comments)
        footer_layout.addStretch()
        layout.addLayout(footer_layout)

        # Store post data
        self.post_data = post_data

        # Store initial saved state and set checkbox state BEFORE connecting signal
        self.is_saved = False  # Will be set by parent widget
        # Connect signal AFTER setting initial state in parent widget
        # The parent widget will call setup_checkbox_connection() after setting states

    def on_checkbox_changed(self, state):
        """Handle checkbox state changes"""
        if state == 2:  # Qt.Checked
            print("Saving post")
            self.main_window.save_post(self.post_data)
        else:
            print("Unsaving post")
            self.main_window.unsave_post(self.post_data)

    def setup_checkbox_connection(self):
        """Connect checkbox signal after initial state is set"""
        self.checkbox.stateChanged.connect(self.on_checkbox_changed)


class SubredditView(QScrollArea):
    """Widget to display subreddit posts"""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window  # Store reference to main window
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.setWidget(self.container)
        self.setWidgetResizable(True)
        self.container.setLayout(self.layout)

    def clear(self):
        """Clear all posts"""
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def add_post(self, post_data, is_saved=False):
        """Add a post widget"""
        post_widget = PostWidget(post_data, self.main_window)
        post_widget.is_saved = is_saved
        post_widget.checkbox.setChecked(is_saved)
        post_widget.setup_checkbox_connection()  # Connect signal after setting states
        self.layout.addWidget(post_widget)


class RedditExplorer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Reddit Explorer")
        self.setMinimumSize(1200, 800)

        # Main layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # Left panel (Explorer)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Tree widget for subreddits and categories
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Explorer")
        left_layout.addWidget(self.tree)

        # Right panel (Browser)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Navigation buttons
        nav_buttons = QWidget()
        nav_layout = QHBoxLayout(nav_buttons)
        self.back_btn = QPushButton("Back")
        self.forward_btn = QPushButton("Forward")
        self.done_btn = QPushButton("Done")
        nav_layout.addWidget(self.back_btn)
        nav_layout.addWidget(self.forward_btn)
        nav_layout.addWidget(self.done_btn)
        right_layout.addWidget(nav_buttons)

        # Replace browser with subreddit view
        self.subreddit_view = SubredditView(self)
        self.browser = QWebEngineView()
        right_layout.addWidget(self.subreddit_view)
        right_layout.addWidget(self.browser)
        self.browser.hide()  # Hide browser initially

        # Add panels to main layout
        layout.addWidget(left_panel, 1)  # 1 is the stretch factor
        layout.addWidget(right_panel, 2)  # 2 is the stretch factor

        self.init_database()
        self.setup_connections()
        self.load_subreddits()

        # Add Reddit API headers
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"  # Replace with your username
        }

    def init_database(self):
        """Initialize SQLite database and create tables if they don't exist"""
        self.conn = sqlite3.connect("reddit_explorer.db")
        cursor = self.conn.cursor()

        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS subreddits (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE
            );
            
            CREATE TABLE IF NOT EXISTS saved_posts (
                id INTEGER PRIMARY KEY,
                reddit_id TEXT UNIQUE,
                subreddit_id INTEGER,
                title TEXT,
                url TEXT,
                category TEXT,
                is_read BOOLEAN DEFAULT 0,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subreddit_id) REFERENCES subreddits(id)
            );
            
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE
            );
        """
        )
        self.conn.commit()

    def setup_connections(self):
        """Setup signal/slot connections"""
        self.back_btn.clicked.connect(self.browser.back)
        self.forward_btn.clicked.connect(self.browser.forward)
        self.tree.itemDoubleClicked.connect(self.handle_tree_click)
        # More connections will be added as we implement features

    def load_subreddits(self):
        """Load subreddits from database into tree widget"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM subreddits ORDER BY name")

        # Create main categories in tree
        self.subreddits_root = QTreeWidgetItem(self.tree, ["Subreddits"])
        self.categories_root = QTreeWidgetItem(self.tree, ["Categories"])

        # Load subreddits under subreddits root
        for row in cursor.fetchall():
            QTreeWidgetItem(self.subreddits_root, [row[0]])

        self.tree.expandAll()

    def add_subreddit(self, subreddit_name):
        """Add a new subreddit to database and tree"""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO subreddits (name) VALUES (?)", (subreddit_name,)
            )
            self.conn.commit()
            QTreeWidgetItem(self.subreddits_root, [subreddit_name])
        except sqlite3.IntegrityError:
            # Subreddit already exists
            pass

    def handle_tree_click(self, item, column):
        """Handle double-click events on tree items"""
        parent = item.parent()
        if parent is None:
            return

        if parent.text(0) == "Subreddits":
            subreddit_name = item.text(0)
            self.load_subreddit_posts(subreddit_name)
        elif parent.text(0) == "Categories":
            # TODO: Load category posts
            pass

    def load_subreddit_posts(self, subreddit_name):
        """Fetch posts from a subreddit"""
        try:
            url = f"https://www.reddit.com/r/{subreddit_name}/new.json"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()

            data = response.json()
            posts = data["data"]["children"]

            # Clear and hide browser, show subreddit view
            self.browser.hide()
            self.subreddit_view.show()
            self.subreddit_view.clear()

            # Get list of saved post IDs for this subreddit
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT reddit_id FROM saved_posts sp
                JOIN subreddits s ON sp.subreddit_id = s.id
                WHERE s.name = ?
            """,
                (subreddit_name,),
            )
            saved_posts = {row[0] for row in cursor.fetchall()}

            # Add posts to subreddit view
            for post in posts:
                post_data = post["data"]
                is_saved = post_data["id"] in saved_posts
                self.subreddit_view.add_post(post_data, is_saved)

        except requests.RequestException as e:
            print(f"Error fetching subreddit posts: {e}")
            # TODO: Add proper error handling/user notification

    def save_post(self, post_data):
        """Save a post to the database"""
        cursor = self.conn.cursor()

        # Get subreddit id
        cursor.execute(
            "SELECT id FROM subreddits WHERE name = ?", (post_data["subreddit"],)
        )
        result = cursor.fetchone()
        if not result:
            # Add subreddit if it doesn't exist
            cursor.execute(
                "INSERT INTO subreddits (name) VALUES (?)", (post_data["subreddit"],)
            )
            subreddit_id = cursor.lastrowid
        else:
            subreddit_id = result[0]

        try:
            cursor.execute(
                """
                INSERT INTO saved_posts (reddit_id, subreddit_id, title, url)
                VALUES (?, ?, ?, ?)
            """,
                (post_data["id"], subreddit_id, post_data["title"], post_data["url"]),
            )
            self.conn.commit()

        except sqlite3.IntegrityError:
            # Post already saved
            pass

    def unsave_post(self, post_data):
        """Remove a post from saved posts"""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM saved_posts WHERE reddit_id = ?", (post_data["id"],)
        )
        self.conn.commit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RedditExplorer()

    # Add some test subreddits
    window.add_subreddit("LocalLLaMA")
    window.add_subreddit("Singularity")

    window.show()
    sys.exit(app.exec())
