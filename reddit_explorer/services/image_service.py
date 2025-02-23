"""
Service for handling image downloads and caching.
"""

import os
import hashlib
import requests
from typing import Optional
from reddit_explorer.config.constants import (
    CACHE_DIR,
    REDDIT_HEADERS,
    VALID_IMAGE_EXTENSIONS,
)
from reddit_explorer.data.database import Database


class ImageService:
    """Service for managing images."""

    def __init__(self):
        """Initialize the image service."""
        os.makedirs(CACHE_DIR, exist_ok=True)
        self.db = Database()

    def get_cached_image(self, post_id: str) -> Optional[str]:
        """
        Get the path to a cached image for a post.

        Args:
            post_id: Reddit post ID

        Returns:
            Path to cached image or None if not cached
        """
        cursor = self.db.get_cursor()
        cursor.execute(
            "SELECT image_path FROM cached_images WHERE post_id = ?", (post_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else None

    def cache_image(self, post_id: str, image_url: str) -> Optional[str]:
        """
        Download and cache an image.

        Args:
            post_id: Reddit post ID
            image_url: URL of the image to cache

        Returns:
            Path to cached image or None if failed
        """
        # Skip if no image URL or invalid extension
        if not image_url or not any(
            image_url.lower().endswith(ext) for ext in VALID_IMAGE_EXTENSIONS
        ):
            return None

        # Check if already cached
        cached_path = self.get_cached_image(post_id)
        if cached_path:
            return cached_path

        try:
            # Download image
            response = requests.get(image_url, headers=REDDIT_HEADERS)
            response.raise_for_status()

            # Generate filename from URL
            ext = os.path.splitext(image_url)[1]
            filename = hashlib.md5(image_url.encode()).hexdigest() + ext
            filepath = os.path.join(CACHE_DIR, filename)

            # Save image
            with open(filepath, "wb") as f:
                f.write(response.content)

            # Store in database
            cursor = self.db.get_cursor()
            cursor.execute(
                "INSERT INTO cached_images (post_id, image_path) VALUES (?, ?)",
                (post_id, filepath),
            )
            self.db.commit()

            return filepath

        except Exception as e:
            print(f"Error caching image: {e}")
            return None
