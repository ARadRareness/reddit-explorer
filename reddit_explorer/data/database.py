"""
Database connection and schema management for Reddit Explorer.
"""

import sqlite3
from typing import Optional
from reddit_explorer.config.constants import DATABASE_PATH, DEFAULT_CATEGORY


class Database:
    _instance: Optional["Database"] = None

    def __new__(cls) -> "Database":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize database connection and create tables if they don't exist."""
        self.conn = sqlite3.connect(DATABASE_PATH)
        self._create_schema()

    def _create_schema(self) -> None:
        """Create database schema if it doesn't exist."""
        cursor = self.conn.cursor()

        # First check if we need to add the analysis columns
        cursor.execute("PRAGMA table_info(saved_posts)")
        columns = {row[1] for row in cursor.fetchall()}

        # Create base schema
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
                num_comments INTEGER DEFAULT 0,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                content TEXT,
                content_date TIMESTAMP,
                summary TEXT,
                FOREIGN KEY (subreddit_id) REFERENCES subreddits(id)
            );
            
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE,
                description TEXT
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

        # Ensure default category exists
        cursor.execute(
            "INSERT OR IGNORE INTO categories (name) VALUES (?)", (DEFAULT_CATEGORY,)
        )
        self.conn.commit()

    def get_cursor(self) -> sqlite3.Cursor:
        """Get a database cursor."""
        return self.conn.cursor()

    def commit(self) -> None:
        """Commit current transaction."""
        self.conn.commit()

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()
        Database._instance = None  # Reset singleton instance
