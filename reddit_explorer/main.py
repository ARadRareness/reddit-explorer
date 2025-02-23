"""
Main entry point for the Reddit Explorer application.
"""

import sys
from PySide6.QtWidgets import QApplication
from reddit_explorer.ui.main_window import RedditExplorer


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    window = RedditExplorer()

    # Add some test subreddits
    window.add_subreddit("LocalLLaMA")
    window.add_subreddit("Singularity")

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
