"""
Service for AI-powered post categorization.
"""

from typing import Dict, Optional, Tuple
from reddit_explorer.services.openai_service import OpenAIService
from reddit_explorer.data.models import RedditPost


class AIService:
    """Service for AI-powered features."""

    _instance: Optional["AIService"] = None
    suggest_mode = False

    def __new__(cls) -> "AIService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize the AI service."""
        self.openai = OpenAIService()

    def summarize_post(self, post: RedditPost) -> str:
        """
        Create a concise summary of a post's content.

        Args:
            post: The post to summarize

        Returns:
            A concise summary of the post's content
        """
        system_message = """You are an expert content summarizer. Your task is to create a concise but informative summary of Reddit posts.
The summary should capture the key points and context while being brief.

Rules:
1. Keep summaries between 2-4 sentences
2. Focus on the main topic and key details
3. Include relevant context from the subreddit if applicable
4. Be objective and factual
5. Preserve any important technical details or specifications
6. Output just the summary text with no additional formatting"""

        # Build the prompt
        prompt = (
            f"Please create a concise summary of this Reddit post:\n\n{post.content}"
        )

        # Get summary
        return self.openai.get_completion(
            system_message=system_message,
            prompt=prompt,
            temperature=0.2,  # Lower temperature for more consistent results
        )

    def categorize_post(
        self,
        post: RedditPost,
        categories: Dict[str, Optional[str]],
        summary: Optional[str] = None,
    ) -> Tuple[str, Optional[str]]:
        """
        Categorize a post using AI.

        Args:
            post: The post to categorize
            categories: Dictionary of category names and their descriptions
            summary: Optional pre-generated summary of the post

        Returns:
            A tuple of (category_name, summary)
        """
        # Generate summary if not provided
        if summary is None:
            summary = self.summarize_post(post)

        if self.suggest_mode:
            extra_instructions = """
            8. If you would have preferred to choose a non-existing category, output the category name you would have chosen between <suggested_category></suggested_category> tags as well.
            """
        else:
            extra_instructions = ""

        # Build the system message
        system_message = f"""You are an expert content categorizer for Reddit posts. Your task is to analyze posts and assign them to the most appropriate category based on their content, title, and source subreddit.

Rules:
1. You must choose from the provided categories only
2. Use 'Uncategorized' if no category is a good fit or if you're uncertain
3. Consider the category descriptions when provided
4. Output your choice between XML-like tags, e.g. <category>Technology</category>
5. Choose only ONE category
6. Be consistent with category names - use exact matches only
7. Go step by step through your reasoning and then output your choice between <category></category> tags, always give your reasoning before outputting the category.
{extra_instructions}
Example output: <category>Gaming</category>"""

        # Build the category information
        category_info = "Available categories:\n"
        for name, desc in categories.items():
            if desc:
                category_info += f"- {name}: {desc}\n"
            else:
                category_info += f"- {name}\n"

        # Build the post information using summary instead of full content
        post_info = f"""
Post to categorize:
Title: {post.title}
Subreddit: r/{post.subreddit}
Summary: {summary}
"""

        # Build the prompt
        prompt = f"{category_info}\n{post_info}\n\nBased on the above information, which category best fits this post? Remember to output your choice between <category></category> tags."

        # Get AI suggestion
        response = self.openai.get_completion(
            system_message=system_message,
            prompt=prompt,
            temperature=0.2,  # Lower temperature for more consistent results
        )

        print("SYSTEM MESSAGE: ", system_message)
        print("PROMPT: ", prompt)
        print("RESPONSE: ", response)

        # Extract category from response
        import re

        suggested_match = re.search(
            r"<suggested_category>(.*?)</suggested_category>", response
        )
        if suggested_match:
            suggested_category = suggested_match.group(1).strip()
            # Only add suggestion if it's not an existing category
            if suggested_category not in categories:
                add_suggestion(suggested_category)

        match = re.search(r"<category>(.*?)</category>", response)
        category = "Uncategorized"
        if match:
            suggested_category = match.group(1).strip()
            # Verify the category exists
            if suggested_category in categories:
                category = suggested_category

        return category, summary


def add_suggestion(category: str):
    """Add a suggestion to the suggested_categories.txt file."""
    try:
        # First check if the category already exists in the file
        try:
            with open("suggested_categories.txt", "r") as f:
                if category in f.read():
                    return
        except FileNotFoundError:
            pass  # File doesn't exist yet, will be created

        # If it doesn't exist, add it
        with open("suggested_categories.txt", "a") as f:
            f.write(category + "\n")
    except Exception as e:
        print(f"Error saving category suggestion: {str(e)}")
