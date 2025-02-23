"""
Service for interacting with the Reddit API.
"""

import requests
from typing import List, Optional, Dict, Any
from datetime import datetime
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

    @staticmethod
    def fetch_post_details(subreddit: str, post_id: str) -> str:
        """
        Fetch a post's details and comments.

        Args:
            subreddit: Name of the subreddit
            post_id: ID of the post

        Returns:
            Markdown formatted string containing post details and comments
        """
        url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}/.json?limit=100"

        try:
            response = requests.get(url, headers=REDDIT_HEADERS)
            response.raise_for_status()
            data = response.json()

            # Extract post data
            post_data = data[0]["data"]["children"][0]["data"]
            comments_data = data[1]["data"]["children"]

            # Format post details
            created_time = datetime.fromtimestamp(post_data["created_utc"])
            time_str = created_time.strftime("%Y-%m-%d %H:%M:%S")
            author = post_data.get("author", "[deleted]")

            markdown = f"# {post_data['title']}\n\n"
            markdown += f"**Posted by u/{author} on {time_str}**\n\n"

            if post_data.get("selftext"):
                markdown += f"{post_data['selftext']}\n\n"

            if (
                post_data.get("url")
                and post_data["url"]
                != f"https://www.reddit.com{post_data['permalink']}"
            ):
                markdown += f"[Link]({post_data['url']})\n\n"

            markdown += "---\n\n"
            markdown += "## Comments\n\n"

            def format_comment(comment: Dict[str, Any], depth: int = 0) -> str:
                if comment.get("kind") != "t1":  # Skip non-comment entries
                    return ""

                data = comment["data"]
                if data.get("body") is None:  # Skip deleted/removed comments
                    return ""

                author = data.get("author", "[deleted]")
                created = datetime.fromtimestamp(data["created_utc"])
                time_str = created.strftime("%Y-%m-%d %H:%M:%S")
                indent = "  " * depth

                text = f"{indent}**u/{author}** on {time_str}\n\n"
                text += f"{indent}{data['body']}\n\n"

                # Process replies recursively
                if data.get("replies") and isinstance(data["replies"], dict):
                    replies = data["replies"]["data"]["children"]
                    for reply in replies:
                        text += format_comment(reply, depth + 1)

                return text

            # Format all comments
            for comment in comments_data:
                markdown += format_comment(comment)

            return markdown

        except requests.RequestException as e:
            print(f"Error fetching post details: {e}")
            return f"Error fetching post details: {str(e)}"
