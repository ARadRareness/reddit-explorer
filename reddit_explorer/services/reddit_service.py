"""
Service for interacting with the Reddit API.
"""

import requests
from typing import List, Optional, Dict, Any
from reddit_explorer.config.constants import REDDIT_HEADERS, MAX_POSTS
from reddit_explorer.data.models import RedditPost


class RedditService:
    """Service for fetching data from Reddit."""

    @staticmethod
    def fetch_subreddit_posts(
        subreddit_name: str, after: Optional[str] = None
    ) -> List[RedditPost]:
        """
        Fetch posts from a subreddit.

        Args:
            subreddit_name: Name of the subreddit
            after: Reddit fullname of the last post for pagination

        Returns:
            List of RedditPost objects and the next pagination token
        """
        url = f"https://www.reddit.com/r/{subreddit_name}/new.json?limit=100"
        if after:
            url += f"&after={after}"

        try:
            response = requests.get(url, headers=REDDIT_HEADERS)
            response.raise_for_status()
            data = response.json()

            posts = []
            for post in data["data"]["children"]:
                posts.append(RedditPost.from_api(post["data"]))

            return posts

        except requests.RequestException as e:
            print(f"Error fetching subreddit posts: {e}")
            return []

    @staticmethod
    def fetch_all_subreddit_posts(
        subreddit_name: str, max_posts: int = MAX_POSTS
    ) -> List[RedditPost]:
        """
        Fetch all posts from a subreddit up to max_posts.

        Args:
            subreddit_name: Name of the subreddit
            max_posts: Maximum number of posts to fetch

        Returns:
            List of RedditPost objects
        """
        all_posts = []
        after = None

        while len(all_posts) < max_posts:
            posts = RedditService.fetch_subreddit_posts(subreddit_name, after)
            if not posts:
                break

            all_posts.extend(posts)

            # Get the last post's fullname for pagination
            after = f"t3_{posts[-1].id}" if posts else None
            if not after:
                break

        return all_posts[:max_posts]
