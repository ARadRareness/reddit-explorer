"""
Module for importing Reddit links from a text file into the database.
"""

import re
import time
from typing import List, Tuple, Optional, TypedDict, Callable
from datetime import datetime
from reddit_explorer.services.reddit_service import RedditService
from reddit_explorer.data.database import Database


class PostInfo(TypedDict):
    """Type definition for post information."""

    title: str
    url: str
    created_utc: float
    num_comments: int


class LinkImporter:
    """Class for importing Reddit links into the database."""

    MAX_RETRIES = 10
    INITIAL_RETRY_DELAY = 1  # seconds
    MAX_RETRY_DELAY = 30  # seconds

    def __init__(self):
        """Initialize the link importer."""
        self.db = Database()
        self.reddit_service = RedditService()

    def retry_with_backoff(
        self, operation: Callable[[], str], error_msg: str
    ) -> Optional[str]:
        """
        Retry an operation with exponential backoff.

        Args:
            operation: Function to retry
            error_msg: Error message prefix for logging

        Returns:
            Result of the operation if successful, None if all retries failed
        """
        delay = self.INITIAL_RETRY_DELAY
        last_result = None

        for attempt in range(self.MAX_RETRIES):
            result = operation()

            # Check if the result is an error message
            if result.startswith("Error fetching post details"):
                last_result = result
                if attempt < self.MAX_RETRIES - 1:  # Don't sleep on last attempt
                    print(
                        f"{error_msg}: {result}. Retrying in {delay} seconds... "
                        f"(Attempt {attempt + 1}/{self.MAX_RETRIES})"
                    )
                    time.sleep(delay)
                    delay = min(delay * 2, self.MAX_RETRY_DELAY)  # Exponential backoff
                continue

            return result  # Return successful result

        print(f"{error_msg}: All retries failed. Last error: {last_result}")
        return None

    def parse_reddit_url(self, url: str) -> Optional[Tuple[str, str]]:
        """
        Parse a Reddit URL to extract subreddit name and post ID.

        Args:
            url: Reddit URL to parse

        Returns:
            Tuple of (subreddit_name, post_id) or None if URL is invalid
        """
        # Match Reddit URLs in format: reddit.com/r/subreddit/comments/post_id/...
        pattern = r"reddit\.com/r/([^/]+)/comments/([^/]+)"
        match = re.search(pattern, url)
        if match:
            return match.group(1), match.group(2)
        return None

    def ensure_subreddit_exists(self, subreddit_name: str) -> int:
        """
        Ensure a subreddit exists in the database.

        Args:
            subreddit_name: Name of the subreddit

        Returns:
            Subreddit ID from database
        """
        cursor = self.db.get_cursor()

        # Check if subreddit exists (case-insensitive)
        cursor.execute(
            "SELECT id FROM subreddits WHERE LOWER(name) = LOWER(?)", (subreddit_name,)
        )
        result = cursor.fetchone()

        if result:
            return result[0]

        # Add new subreddit
        cursor.execute("INSERT INTO subreddits (name) VALUES (?)", (subreddit_name,))
        self.db.commit()
        return (
            cursor.lastrowid or 0
        )  # Return 0 if lastrowid is None (should never happen)

    def extract_post_info_from_content(self, content: str) -> Optional[PostInfo]:
        """
        Extract post information from the markdown content.

        Args:
            content: Markdown formatted post content from fetch_post_details

        Returns:
            Dictionary containing post info or None if parsing fails
        """
        try:
            # Extract title from first line (# Title)
            title_match = re.match(r"# (.*?)\n", content)
            if not title_match:
                return None
            title = title_match.group(1)

            # Extract post URL if present
            url_match = re.search(r"\[Link\]\((.*?)\)", content)
            url = url_match.group(1) if url_match else ""

            # Extract timestamp from second line
            time_match = re.search(r"on (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", content)
            if not time_match:
                return None
            timestamp = datetime.strptime(time_match.group(1), "%Y-%m-%d %H:%M:%S")

            # Count comments (## Comments followed by user comments)
            comments_count = len(re.findall(r"\*\*u/.*?\*\* on \d{4}", content))

            return {
                "title": title,
                "url": url,
                "created_utc": timestamp.timestamp(),
                "num_comments": comments_count,
            }
        except Exception:
            return None

    def import_links(
        self, links_file: str, max_links: Optional[int] = None
    ) -> Tuple[int, int, List[str]]:
        """
        Import Reddit links from a text file.

        Args:
            links_file: Path to file containing Reddit links
            max_links: Maximum number of links to process (optional)

        Returns:
            Tuple of (total_processed, total_imported, errors)
        """
        total_processed = 0
        total_imported = 0
        errors = []

        try:
            with open(links_file, "r", encoding="utf-8") as f:
                links = f.readlines()

            print(f"Processing {len(links)} links...")

            # Limit number of links if specified
            if max_links:
                links = links[:max_links]

            for link in links:
                total_processed += 1
                link = link.strip()

                if not link:  # Skip empty lines
                    continue

                try:
                    # Parse URL
                    result = self.parse_reddit_url(link)
                    if not result:
                        errors.append(f"Invalid Reddit URL: {link}")
                        continue

                    subreddit_name, post_id = result

                    # Check if post already exists
                    cursor = self.db.get_cursor()
                    cursor.execute(
                        "SELECT 1 FROM saved_posts WHERE reddit_id = ?", (post_id,)
                    )
                    if cursor.fetchone():
                        continue  # Skip existing posts

                    # Ensure subreddit exists
                    subreddit_id = self.ensure_subreddit_exists(subreddit_name)

                    print(f"Processing r/{subreddit_name} post {post_id}")

                    # Fetch post details with retry
                    post_content = self.retry_with_backoff(
                        lambda: self.reddit_service.fetch_post_details(
                            subreddit_name, post_id
                        ),
                        f"Error fetching post details for {link}",
                    )

                    if not post_content:
                        errors.append(
                            f"Failed to fetch post details after retries: {link}"
                        )
                        continue

                    # Extract post info from content
                    post_info = self.extract_post_info_from_content(post_content)
                    if not post_info:
                        errors.append(f"Could not parse post content: {link}")
                        continue

                    # Format the post's creation time for SQLite
                    created_time = datetime.fromtimestamp(
                        post_info["created_utc"]
                    ).strftime("%Y-%m-%d %H:%M:%S")

                    # Save to database
                    cursor.execute(
                        """
                        INSERT INTO saved_posts (
                            reddit_id, subreddit_id, title, url, category,
                            show_in_categories, is_read, num_comments,
                            added_date, content, content_date
                        )
                        VALUES (?, ?, ?, ?, 'Uncategorized', 1, 1, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (
                            post_id,
                            subreddit_id,
                            post_info["title"],
                            post_info["url"],
                            post_info["num_comments"],
                            created_time,
                            post_content,
                        ),
                    )
                    self.db.commit()
                    total_imported += 1
                    print(f"Successfully imported post {total_imported}")

                except Exception as e:
                    errors.append(f"Error processing {link}: {str(e)}")

        except Exception as e:
            errors.append(f"Error reading links file: {str(e)}")

        return total_processed, total_imported, errors


def import_links(
    links_file: str, max_links: Optional[int] = None
) -> Tuple[int, int, List[str]]:
    """
    Convenience function to import links without creating a class instance.

    Args:
        links_file: Path to file containing Reddit links
        max_links: Maximum number of links to process (optional)

    Returns:
        Tuple of (total_processed, total_imported, errors)
    """
    importer = LinkImporter()
    return importer.import_links(links_file, max_links)


if __name__ == "__main__":
    import_links("links_to_import.txt")
