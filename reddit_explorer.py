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
    QMenu,
    QSizePolicy,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineScript
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
import sqlite3
import requests
from datetime import datetime
import json
import os


class PostWidget(QFrame):
    """Widget to display a single post"""

    def __init__(self, post_data, main_window, view_type="subreddit", parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.view_type = view_type  # "subreddit" or "category"
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(1)

        # Enable mouse tracking for cursor changes
        self.setMouseTracking(True)
        # Make the widget clickable
        self.setCursor(Qt.PointingHandCursor)

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

        if view_type == "subreddit":
            checkbox_layout.addWidget(self.added_checkbox)
            self.category_checkbox.hide()
        else:  # category view
            checkbox_layout.addWidget(self.category_checkbox)
            self.added_checkbox.hide()

        self.title = QLabel(post_data["title"])
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-weight: bold;")

        header_layout.addWidget(checkbox_container)
        header_layout.addWidget(self.title, 1)
        layout.addLayout(header_layout)

        # Creation time
        created_time = datetime.fromtimestamp(post_data["created_utc"])
        time_str = created_time.strftime("%Y-%m-%d %H:%M:%S")
        self.time_label = QLabel(f"Posted: {time_str}")
        self.time_label.setStyleSheet("color: gray;")
        layout.addWidget(self.time_label)

        # Description
        if post_data.get("selftext"):
            self.description = QLabel(
                post_data["selftext"][:300] + "..."
                if len(post_data["selftext"]) > 300
                else post_data["selftext"]
            )
            self.description.setWordWrap(True)
            layout.addWidget(self.description)

        # Image (if available)
        if post_data.get("url"):
            image_path = self.main_window.cache_image(post_data)
            if image_path:
                image_label = QLabel()
                pixmap = QPixmap(image_path)
                # Scale image to fit width while maintaining aspect ratio
                scaled_pixmap = pixmap.scaledToWidth(
                    800, Qt.TransformationMode.SmoothTransformation
                )
                image_label.setPixmap(scaled_pixmap)
                layout.addWidget(image_label)

        # Footer (comments count)
        footer_layout = QHBoxLayout()
        self.comments = QLabel(f"Comments: {post_data['num_comments']}")
        footer_layout.addWidget(self.comments)
        footer_layout.addStretch()
        layout.addLayout(footer_layout)

        # Store post data
        self.post_data = post_data

        # Store initial states and set checkbox states BEFORE connecting signals
        self.is_saved = False  # Will be set by parent widget
        self.show_in_categories = True  # Will be set by parent widget
        # Connect signals AFTER setting initial states in parent widget
        # The parent widget will call setup_checkbox_connections() after setting states

    def on_added_checkbox_changed(self, state):
        """Handle added checkbox state changes"""
        if state == 2:  # Qt.Checked
            print("Saving post")
            self.main_window.save_post(self.post_data)
        else:
            print("Unsaving post")
            self.main_window.unsave_post(self.post_data)

    def on_category_checkbox_changed(self, state):
        """Handle category checkbox state changes"""
        if self.is_saved:  # Only update if post is saved
            self.main_window.update_post_category_visibility(
                self.post_data["id"], state == 2
            )

    def setup_checkbox_connections(self):
        """Connect checkbox signals after initial states are set"""
        self.added_checkbox.stateChanged.connect(self.on_added_checkbox_changed)
        self.category_checkbox.stateChanged.connect(self.on_category_checkbox_changed)

    def mouseDoubleClickEvent(self, event):
        """Handle double-click events to open post in browser"""
        # Get the post index if we're in a category
        if self.view_type == "category":
            for i, post in enumerate(self.main_window.current_category_posts):
                if post["id"] == self.post_data["id"]:
                    self.main_window.current_post_index = i
                    # Enable/disable Next button based on position
                    self.main_window.next_btn.setEnabled(
                        i < len(self.main_window.current_category_posts) - 1
                    )
                    break

        # Construct Reddit post URL
        post_url = f"https://www.reddit.com/r/{self.post_data['subreddit']}/comments/{self.post_data['id']}"

        # Update category checkbox state
        cursor = self.main_window.conn.cursor()
        cursor.execute(
            "SELECT show_in_categories FROM saved_posts WHERE reddit_id = ?",
            (self.post_data["id"],),
        )
        result = cursor.fetchone()
        if result:
            self.main_window.browser_category_checkbox.setChecked(bool(result[0]))

        # Show browser and navigation buttons
        self.main_window.browser.show()
        self.main_window.nav_buttons.show()
        self.main_window.subreddit_view.hide()
        self.main_window.browser.setUrl(post_url)
        # Run the script to hide the sidebar after page loads
        self.main_window.browser.page().loadFinished.connect(
            lambda ok: self.main_window.browser.page().runJavaScript(
                self.main_window.hide_sidebar_script
            )
        )

    def enterEvent(self, event):
        """Handle mouse enter events"""
        self.setStyleSheet("background-color: #f0f0f0;")

    def leaveEvent(self, event):
        """Handle mouse leave events"""
        self.setStyleSheet("")


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

    def add_post(
        self, post_data, is_saved=False, show_in_categories=True, view_type="subreddit"
    ):
        """Add a post widget"""
        post_widget = PostWidget(post_data, self.main_window, view_type)
        post_widget.is_saved = is_saved
        post_widget.show_in_categories = show_in_categories
        post_widget.added_checkbox.setChecked(is_saved)
        post_widget.category_checkbox.setChecked(show_in_categories)
        post_widget.category_checkbox.setEnabled(
            is_saved
        )  # Only enable if post is saved
        post_widget.setup_checkbox_connections()  # Connect signals after setting states
        self.layout.addWidget(post_widget)

        # Scroll to bottom after adding the post
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def scroll_to_bottom(self):
        """Scroll to the bottom of the view"""
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class RedditExplorer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Reddit Explorer")
        self.setMinimumSize(1200, 800)

        # Debug flag to control logging
        self.debug = False

        # Create image cache directory
        self.cache_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "image_cache"
        )
        os.makedirs(self.cache_dir, exist_ok=True)

        # Create browser data directory for persistent storage
        self.browser_data_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "browser_data"
        )
        os.makedirs(self.browser_data_dir, exist_ok=True)

        # Set up persistent web profile
        self.web_profile = QWebEngineProfile("reddit_explorer", self)
        self.web_profile.setPersistentStoragePath(self.browser_data_dir)
        self.web_profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
        )

        # Initial script to hide content
        self.initial_hide_script = """
            (function() {
                function injectStyle() {
                    try {
                        // Try to create and inject style
                        const style = document.createElement('style');
                        style.id = 'reddit-explorer-initial-hide';
                        style.textContent = `
                            /* Hide everything immediately */
                            html.reddit-explorer-loading,
                            html.reddit-explorer-loading body {
                                display: none !important;
                            }
                        `;
                        
                        const target = document.head || document.documentElement;
                        if (target) {
                            target.appendChild(style);
                            // Add class to html element to activate the style
                            document.documentElement.classList.add('reddit-explorer-loading');
                            return true;
                        }
                    } catch (e) {
                        console.log('Failed to inject style:', e);
                    }
                    return false;
                }

                // Try to inject immediately
                if (!injectStyle()) {
                    // If failed, try again when readyState changes
                    const observer = new MutationObserver((mutations, obs) => {
                        if (document.documentElement) {
                            injectStyle();
                            obs.disconnect(); // Stop observing once we succeed
                        }
                    });
                    
                    // Start observing document for when documentElement becomes available
                    observer.observe(document, {
                        childList: true,
                        subtree: true
                    });
                }
            })();
        """

        # JavaScript to hide right sidebar and show content
        self.hide_sidebar_script = """
            function adjustLayout() {
                console.log('Adjusting layout...');
                
                // Debug DOM structure
                console.log('Document body:', document.body.innerHTML.substring(0, 500));
                
                // Remove top header
                const header = document.querySelector('header');
                if (header) {
                    console.log('Found header:', header.className);
                    header.remove();
                    console.log('Header removed');
                }
                
                // Remove back button
                const backButton = document.querySelector('pdp-back-button');
                if (backButton) {
                    console.log('Found back button:', backButton.className);
                    backButton.remove();
                    console.log('Back button removed');
                }
                
                // Try to find the left nav container using both tag name and ID
                const leftNavContainer = document.querySelector('flex-left-nav-container#left-sidebar-container') || 
                                      document.getElementById('left-sidebar-container') ||
                                      document.querySelector('flex-left-nav-container');
                
                console.log('Left nav container:', leftNavContainer);
                
                if (leftNavContainer) {
                    console.log('Found left nav container with classes:', leftNavContainer.className);
                    // Try to find the parent container that might be the flex wrapper
                    const parentContainer = leftNavContainer.parentElement;
                    console.log('Parent container:', parentContainer);
                    if (parentContainer) {
                        console.log('Parent container classes:', parentContainer.className);
                        // If parent is a flex container, remove it
                        if (parentContainer.className.includes('flex')) {
                            console.log('Removing parent container');
                            parentContainer.remove();
                        } else {
                            // Otherwise just remove the nav container
                            console.log('Removing nav container');
                            leftNavContainer.remove();
                        }
                    }
                }
                
                // Find and adjust main content
                const subgridContainer = document.getElementById('subgrid-container');
                const mainContainer = document.querySelector('.main-container');
                const mainElement = document.querySelector('.main');
                
                console.log('Main elements:', {
                    subgridContainer: subgridContainer?.className,
                    mainContainer: mainContainer?.className,
                    mainElement: mainElement?.className
                });
                
                if (mainElement) {
                    console.log('Found main element, moving to top of document...');
                    
                    // Move main element to be the first child of body
                    document.body.insertBefore(mainElement, document.body.firstChild);
                    
                    // Remove the containers if they exist
                    if (mainContainer) mainContainer.remove();
                    if (subgridContainer) subgridContainer.remove();
                    
                    // Add style to ensure main takes full width and adjust for removed header
                    const style = document.createElement('style');
                    style.textContent = `
                        @media (min-width: 768px) {
                            body {
                                padding-top: 0 !important;
                                margin: 0 !important;
                                overflow-x: hidden !important;
                            }
                            .main {
                                width: 100% !important;
                                max-width: 100% !important;
                                box-sizing: border-box !important;
                                padding: 24px 24px 0 24px !important;
                                margin: 0 !important;
                                display: block !important;
                                overflow-x: hidden !important;
                            }
                        }
                    `;
                    document.head.appendChild(style);
                    console.log('Layout adjusted');

                    // Show content with a smooth transition
                    document.documentElement.classList.remove('reddit-explorer-loading');
                } else {
                    console.log('Could not find main element');
                }
            }
            
            // Run immediately and after increasing delays
            adjustLayout();
            [1000, 2000, 3000, 4000, 5000].forEach((delay) => {
                setTimeout(() => {
                    console.log(`Retrying after ${delay}ms...`);
                    adjustLayout();
                }, delay);
            });
        """

        # Main layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(8, 8, 8, 8)  # Set consistent margins
        layout.setSpacing(8)  # Set spacing between panels

        # Left panel (Explorer)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)  # Remove internal margins
        left_panel.setSizePolicy(
            QSizePolicy.Fixed, QSizePolicy.Expanding
        )  # Fixed width, expands vertically

        # Tree widget for subreddits and categories
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Explorer")
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)

        # Make tree more compact horizontally
        self.tree.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.tree.setMinimumWidth(150)  # Set minimum width
        self.tree.setMaximumWidth(
            250
        )  # Set maximum width to prevent excessive stretching

        left_layout.addWidget(self.tree)

        # Right panel (Browser)
        right_panel = QWidget()
        right_panel.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )  # Expand in both directions
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins

        # Navigation buttons
        self.nav_buttons = QWidget()
        self.nav_buttons.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )  # Make height fixed
        nav_layout = QHBoxLayout(self.nav_buttons)
        nav_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        nav_layout.setSpacing(4)  # Reduce spacing between buttons

        # Create navigation buttons and checkbox
        self.done_btn = QPushButton("Done")
        self.next_btn = QPushButton("Next")
        self.browser_category_checkbox = QCheckBox("Show in categories")
        self.browser_category_checkbox.setToolTip("Show post in categories view")

        # Set fixed height for buttons
        for btn in [self.done_btn, self.next_btn]:
            btn.setFixedHeight(24)  # Compact height
            btn.setStyleSheet(
                "padding: 0px 8px;"
            )  # Reduce vertical padding, keep horizontal

        # Add widgets to layout
        nav_layout.addWidget(self.browser_category_checkbox)
        nav_layout.addStretch()  # Add space between checkbox and buttons
        nav_layout.addWidget(self.next_btn)
        nav_layout.addWidget(self.done_btn)
        right_layout.addWidget(self.nav_buttons)
        self.nav_buttons.hide()  # Hide navigation buttons initially

        # Current category and post index for navigation
        self.current_category = None
        self.current_category_posts = []
        self.current_post_index = -1

        # Replace browser with subreddit view
        self.subreddit_view = SubredditView(self)
        self.browser = QWebEngineView()
        page = QWebEnginePage(self.web_profile, self.browser)

        # Add script to hide content before page loads
        script = QWebEngineScript()
        script.setName("HideContent")
        script.setSourceCode(self.initial_hide_script)
        script.setInjectionPoint(
            QWebEngineScript.DocumentCreation
        )  # Enum value directly from QWebEngineScript
        script.setWorldId(
            QWebEngineScript.MainWorld
        )  # Enum value directly from QWebEngineScript
        script.setRunsOnSubFrames(True)
        self.web_profile.scripts().insert(script)

        # Add console message handler
        page.javaScriptConsoleMessage = (
            (lambda level, msg, line, source: print(f"JS {level}: {msg} (line {line})"))
            if self.debug
            else lambda *args: None
        )
        self.browser.setPage(page)  # Use persistent profile
        right_layout.addWidget(self.subreddit_view)
        right_layout.addWidget(self.browser)
        self.browser.hide()  # Hide browser initially

        # Add panels to main layout with appropriate stretch factors
        layout.addWidget(left_panel, 0)  # Stretch factor 0 means no stretch
        layout.addWidget(
            right_panel, 1
        )  # Stretch factor 1 means it will take up remaining space

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
                show_in_categories BOOLEAN DEFAULT 1,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subreddit_id) REFERENCES subreddits(id)
            );
            
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE
            );
            
            CREATE TABLE IF NOT EXISTS cached_images (
                id INTEGER PRIMARY KEY,
                post_id TEXT UNIQUE,
                image_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES saved_posts(reddit_id)
            );
        """
        )

        # Ensure Uncategorized category exists
        cursor.execute(
            "INSERT OR IGNORE INTO categories (name) VALUES ('Uncategorized')"
        )
        self.conn.commit()

    def setup_connections(self):
        """Setup signal/slot connections"""
        self.next_btn.clicked.connect(self.handle_next_click)
        self.done_btn.clicked.connect(self.handle_done_click)
        self.tree.itemClicked.connect(self.handle_tree_click)
        self.browser_category_checkbox.stateChanged.connect(
            self.handle_browser_category_changed
        )
        # More connections will be added as we implement features

    def load_subreddits(self):
        """Load subreddits and categories from database into tree widget"""
        cursor = self.conn.cursor()

        # Create main categories in tree
        self.subreddits_root = QTreeWidgetItem(self.tree, ["Subreddits"])
        self.categories_root = QTreeWidgetItem(self.tree, ["Categories"])

        # Load subreddits under subreddits root
        cursor.execute("SELECT name FROM subreddits ORDER BY name")
        for row in cursor.fetchall():
            QTreeWidgetItem(self.subreddits_root, [row[0]])

        # Load categories under categories root
        cursor.execute("SELECT name FROM categories ORDER BY name")
        for row in cursor.fetchall():
            QTreeWidgetItem(self.categories_root, [row[0]])

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

    def handle_tree_click(self, item):
        """Handle single-click events on tree items"""
        parent = item.parent()
        if parent is None:
            return

        if parent.text(0) == "Subreddits":
            subreddit_name = item.text(0)
            self.load_subreddit_posts(subreddit_name)
        elif parent.text(0) == "Categories":
            category_name = item.text(0)
            self.load_category_posts(category_name)

    def load_subreddit_posts(self, subreddit_name):
        """Fetch posts from a subreddit"""
        try:
            # Clear and hide browser and navigation buttons, show subreddit view
            self.browser.hide()
            self.nav_buttons.hide()
            self.subreddit_view.show()
            self.subreddit_view.clear()

            # Reset window title
            self.setWindowTitle("Reddit Explorer")

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

            # Initialize variables for pagination
            after = None
            total_posts = 0
            found_saved = False
            MAX_POSTS = 400

            while total_posts < MAX_POSTS and not found_saved:
                # Construct URL with pagination parameters
                url = f"https://www.reddit.com/r/{subreddit_name}/new.json?limit=100"
                if after:
                    url += f"&after={after}"

                # Fetch posts
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()

                # Get posts from response
                posts = data["data"]["children"]
                if not posts:  # No more posts to load
                    break

                # Update after for next pagination
                after = data["data"].get("after")
                if not after:  # No more pages available
                    break

                # Add posts to view
                for post in posts:
                    post_data = post["data"]
                    is_saved = post_data["id"] in saved_posts
                    self.subreddit_view.add_post(
                        post_data, is_saved, view_type="subreddit"
                    )
                    total_posts += 1

                    if is_saved:  # Stop if we found a saved post
                        found_saved = True
                        break

                    if total_posts >= MAX_POSTS:  # Stop if we hit the limit
                        break

                # Update window title with post count
                self.setWindowTitle(f"Reddit Explorer ({total_posts} posts)")

        except requests.RequestException as e:
            print(f"Error fetching subreddit posts: {e}")
            # TODO: Add proper error handling/user notification

    def load_category_posts(self, category_name):
        """Load and display posts from a specific category"""
        try:
            # Clear and hide browser and navigation buttons, show subreddit view
            self.browser.hide()
            self.nav_buttons.hide()
            self.subreddit_view.show()
            self.subreddit_view.clear()

            # Reset window title
            self.setWindowTitle("Reddit Explorer")

            # Store category name for navigation
            self.current_category = category_name
            self.current_category_posts = []
            self.current_post_index = -1

            # Get posts for this category
            cursor = self.conn.cursor()
            # Enable dictionary access to rows
            cursor.row_factory = sqlite3.Row

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
                # Parse the datetime string from SQLite
                added_date = (
                    datetime.strptime(row["added_date"], "%Y-%m-%d %H:%M:%S")
                    if row["added_date"]
                    else None
                )

                # Create post_data dictionary similar to Reddit API response
                post_data = {
                    "id": row["reddit_id"],
                    "title": row["title"],
                    "url": row["url"],
                    "subreddit": row["subreddit_name"],
                    "created_utc": (added_date.timestamp() if added_date else 0),
                    "num_comments": 0,
                    "selftext": "",
                }
                # Store post data for navigation
                self.current_category_posts.append(post_data)

                # Add post to view
                self.subreddit_view.add_post(
                    post_data,
                    is_saved=True,
                    show_in_categories=True,
                    view_type="category",
                )
                total_posts += 1

            # Update window title with post count
            self.setWindowTitle(f"Reddit Explorer ({total_posts} posts)")

        except sqlite3.Error as e:
            print(f"Error loading category posts: {e}")
            # TODO: Add proper error handling/user notification

    def save_post(self, post_data):
        """Save a post to the database"""
        cursor = self.conn.cursor()

        # Get subreddit id - using case-insensitive comparison
        cursor.execute(
            "SELECT id FROM subreddits WHERE LOWER(name) = LOWER(?)",
            (post_data["subreddit"],),
        )
        result = cursor.fetchone()
        if not result:
            # Add subreddit if it doesn't exist - use the original case from our tree widget
            root = self.tree.findItems("Subreddits", Qt.MatchExactly)[0]
            existing_subreddit = None
            for i in range(root.childCount()):
                if root.child(i).text(0).lower() == post_data["subreddit"].lower():
                    existing_subreddit = root.child(i).text(0)
                    break

            # If we found a matching subreddit, use its case, otherwise use the post's case
            subreddit_name = existing_subreddit or post_data["subreddit"]
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
            cursor.execute(
                """
                INSERT INTO saved_posts (reddit_id, subreddit_id, title, url, category, show_in_categories)
                VALUES (?, ?, ?, ?, 'Uncategorized', 1)
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

    def get_cached_image(self, post_id):
        """Get the path to a cached image for a post"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT image_path FROM cached_images WHERE post_id = ?", (post_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else None

    def cache_image(self, post_data):
        """Download and cache an image from a post"""
        import hashlib

        # Skip if no image URL or already cached
        if not post_data.get("url") or not any(
            post_data["url"].lower().endswith(ext)
            for ext in [".jpg", ".jpeg", ".png", ".gif"]
        ):
            return None

        # Check if already cached
        cached_path = self.get_cached_image(post_data["id"])
        if cached_path:
            return cached_path

        try:
            # Download image
            response = requests.get(post_data["url"], headers=self.headers)
            response.raise_for_status()

            # Generate filename from URL
            ext = os.path.splitext(post_data["url"])[1]
            filename = hashlib.md5(post_data["url"].encode()).hexdigest() + ext
            filepath = os.path.join(self.cache_dir, filename)

            # Save image
            with open(filepath, "wb") as f:
                f.write(response.content)

            # Store in database
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO cached_images (post_id, image_path) VALUES (?, ?)",
                (post_data["id"], filepath),
            )
            self.conn.commit()

            return filepath

        except Exception as e:
            print(f"Error caching image: {e}")
            return None

    def show_context_menu(self, position):
        """Show context menu for tree items"""
        item = self.tree.itemAt(position)
        if not item:
            return

        # Only show menu for subreddit items
        parent = item.parent()
        if parent and parent.text(0) == "Subreddits":
            menu = QMenu()
            remove_action = menu.addAction("Remove")
            action = menu.exec_(self.tree.viewport().mapToGlobal(position))

            if action == remove_action:
                self.remove_subreddit(item.text(0))

    def remove_subreddit(self, subreddit_name):
        """Remove a subreddit from database and tree"""
        # Remove from database
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM subreddits WHERE name = ?", (subreddit_name,))
        self.conn.commit()

        # Remove from tree
        root = self.tree.findItems("Subreddits", Qt.MatchExactly)[0]
        for i in range(root.childCount()):
            if root.child(i).text(0) == subreddit_name:
                root.removeChild(root.child(i))
                break

    def handle_done_click(self):
        """Handle Done button click - return to subreddit view if in browser mode"""
        if not self.subreddit_view.isHidden():
            return

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

    def update_post_category_visibility(self, post_id, show_in_categories):
        """Update whether a post should be shown in categories view"""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE saved_posts SET show_in_categories = ? WHERE reddit_id = ?",
            (1 if show_in_categories else 0, post_id),
        )
        self.conn.commit()

    def handle_browser_category_changed(self, state):
        """Handle category checkbox changes in browser view"""
        if self.current_post_index >= 0 and self.current_post_index < len(
            self.current_category_posts
        ):
            post_data = self.current_category_posts[self.current_post_index]
            self.update_post_category_visibility(
                post_data["id"], state == 2
            )  # 2 is Qt.Checked

    def handle_next_click(self):
        """Handle Next button click - show next post in category"""
        if (
            not self.current_category_posts
            or self.current_post_index >= len(self.current_category_posts) - 1
        ):
            self.next_btn.setEnabled(False)
            return

        self.current_post_index += 1
        post_data = self.current_category_posts[self.current_post_index]

        # Update Next button state
        self.next_btn.setEnabled(
            self.current_post_index < len(self.current_category_posts) - 1
        )

        # Update checkbox state
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT show_in_categories FROM saved_posts WHERE reddit_id = ?",
            (post_data["id"],),
        )
        result = cursor.fetchone()
        if result:
            self.browser_category_checkbox.setChecked(bool(result[0]))

        # Construct and load Reddit post URL
        post_url = f"https://www.reddit.com/r/{post_data['subreddit']}/comments/{post_data['id']}"
        self.browser.setUrl(post_url)
        # Run the script to hide the sidebar after page loads
        self.browser.page().loadFinished.connect(
            lambda ok: self.browser.page().runJavaScript(self.hide_sidebar_script)
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RedditExplorer()

    # Add some test subreddits
    window.add_subreddit("LocalLLaMA")
    window.add_subreddit("Singularity")

    window.show()
    sys.exit(app.exec())
