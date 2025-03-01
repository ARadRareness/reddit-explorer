"""
Service for AI-powered post categorization.
"""

from typing import Dict, Optional, Tuple, List, Set
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

    def summarize_post(self, post: RedditPost) -> Optional[str]:
        """
        Create a concise summary of a post's content.

        Args:
            post: The post to summarize

        Returns:
            A concise summary of the post's content
        """

        if post.content is None:
            return None

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

        print(prompt)

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

            if summary is None:
                return "Uncategorized", None

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

    def generate_bullet_points(
        self, summaries: List[Tuple[str, str]]
    ) -> List[Tuple[str, str]]:
        """
        Generate bullet points from multiple post summaries, focusing on posts with meaningful learnable information.
        Processes summaries in batches of 30 to avoid overwhelming the AI model.

        Args:
            summaries: List of tuples containing (summary, post_id)

        Returns:
            List of tuples containing (bullet_point, post_id), where each bullet point represents
            a meaningful insight or learnable information from the selected posts.
        """
        # Process in batches of 30
        BATCH_SIZE = 30
        all_bullet_points: List[Tuple[str, str]] = []

        # Process each batch
        for batch_start in range(0, len(summaries), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(summaries))
            batch = summaries[batch_start:batch_end]

            # Adjust indices to be relative to the current batch
            batch_points = self._process_bullet_point_batch(batch, batch_start)
            all_bullet_points.extend(batch_points)

        # Select the most valuable points if we have more than needed
        if all_bullet_points and len(all_bullet_points) > 15:
            all_bullet_points = self._select_most_valuable_points(all_bullet_points)

        # If no valid bullet points were found, return a message indicating no learnable content
        if not all_bullet_points:
            return [
                ("No significant technical insights found in the recent posts.", "")
            ]

        return all_bullet_points

    def _process_bullet_point_batch(
        self, summaries_batch: List[Tuple[str, str]], batch_start_index: int = 0
    ) -> List[Tuple[str, str]]:
        """
        Process a batch of summaries to generate bullet points.

        Args:
            summaries_batch: A batch of summaries to process
            batch_start_index: The starting index of this batch in the original list

        Returns:
            List of bullet points with their corresponding post_ids
        """
        system_message = """You are an expert technical content curator. Your task is to analyze Reddit post summaries and extract ONLY the most technically valuable and actionable insights.

REQUIRED OUTPUT FORMAT:
You MUST format each insight using XML tags exactly like this:
<point>The actual insight text goes here</point><id>N</id>

Where N is the index number (0-based) of the post that contains this insight.

Example outputs:
<point>...</point><id>9</id>
<point>...</point><id>0</id>

Content Selection Rules:
1. ONLY select posts containing:
   - Concrete technical innovations or tools
   - Specific performance metrics or benchmarks
   - Novel technical approaches or methodologies
   - Actionable technical findings
2. STRICTLY AVOID:
   - General discussions or opinions
   - Vague or non-technical content
   - Redundant information
   - Personal experiences without technical merit
   - Basic announcements

Output Rules:
1. Each point MUST use the exact <point>...</point><id>N</id> format
2. NO other formatting (no bullets, numbers, or other markers)
3. Include specific technical details, metrics, or comparisons
4. Keep each point focused and concise (1-2 sentences)
5. The id number MUST match the source post's index (0-based)
6. Extract only the most significant technical insights (quality over quantity)

DO NOT summarize or group points together. Each point should be a distinct, specific technical insight from a single post."""

        # Build the prompt with all summaries in the batch
        prompt = """Extract ONLY the most technically significant and actionable insights from these summaries. Focus on concrete technical details, metrics, and innovations.

REQUIRED FORMAT FOR EACH INSIGHT:
<point>Technical insight here</point><id>N</id>

Where N is the index (0-based) of the source post.

Summaries to analyze:

"""
        for i, (summary, _) in enumerate(summaries_batch):
            prompt += f"[{i}] {summary}\n"

        prompt += "\nRemember: Only extract specific technical insights, using the exact <point>...</point><id>N</id> format for each one."

        # Get bullet points
        response = self.openai.get_completion(
            system_message=system_message,
            prompt=prompt,
            temperature=0.1,  # Lower temperature for more focused results
        )

        print("SYSTEM MESSAGE: ", system_message)
        print("PROMPT: ", prompt)
        print("RESPONSE: ", response)

        # Extract bullet points and their corresponding post indices
        bullet_points = []
        import re

        # Find all bullet points with their post IDs using a more flexible regex pattern
        matches = re.finditer(
            r"<point>\s*(.*?)\s*</point>\s*<id>\s*(\d+)\s*</id>",
            response,
            re.DOTALL,  # Allow matching across newlines
        )

        for match in matches:
            # Clean up the point text
            point_text = match.group(1).strip()
            point_text = re.sub(r"\s+", " ", point_text)  # Normalize whitespace
            point_text = point_text.strip("\"'")  # Remove quotes if present

            # Get the batch-relative index
            batch_relative_index = int(match.group(2))

            # Only add if the index is valid
            if 0 <= batch_relative_index < len(summaries_batch):
                # Get the original post_id for this summary
                _, post_id = summaries_batch[batch_relative_index]
                bullet_points.append((point_text, post_id))

        return bullet_points

    def _select_most_valuable_points(
        self, bullet_points: List[Tuple[str, str]], max_points: int = 15
    ) -> List[Tuple[str, str]]:
        """
        Use AI to select the most valuable points from the collected bullet points.

        Args:
            bullet_points: List of tuples containing (bullet_point, post_id)
            max_points: Maximum number of points to select (default: 15)

        Returns:
            List of the most valuable bullet points
        """
        if len(bullet_points) <= max_points:
            return bullet_points

        system_message = """You are an expert at evaluating and ranking technical content.
Your task is to analyze a list of technical bullet points and select the most valuable ones based on their technical merit.

REQUIRED OUTPUT FORMAT:
For each selected point, output its index (0-based) between <selected></selected> tags.
Example: <selected>2</selected> means you've selected the point at index 2.

Rules for selecting the most valuable points:
1. Prioritize points containing:
   - Concrete technical innovations or breakthroughs
   - Specific performance metrics or benchmarks
   - Novel technical approaches or methodologies
   - Actionable technical findings with practical applications
   - Emerging technologies or tools with significant potential impact

2. Consider these factors when ranking:
   - Technical depth and specificity
   - Novelty and innovation
   - Practical applicability
   - Clarity and information density
   - Topic diversity (when choosing between points of similar quality, prefer those that cover different domains)

3. Aim for a balanced selection:
   - When multiple high-quality points cover similar topics, select the best one and use remaining slots for different topics
   - Try to include insights from different domains
   - All else being equal, a diverse set of topics is more valuable than redundant coverage

4. Select EXACTLY {max_points} points (no more, no less)
5. Do not explain your reasoning, just output the tags"""

        # Build the prompt with all bullet points
        prompt = f"""Select the {max_points} most valuable technical insights from this list, favoring diversity when points are of similar quality:

"""
        for i, (point, _) in enumerate(bullet_points):
            prompt += f"[{i}] {point}\n"

        prompt += f"\nOutput the indices of the {max_points} most valuable points using <selected>INDEX</selected> tags."

        # Get selection analysis
        response = self.openai.get_completion(
            system_message=system_message,
            prompt=prompt,
            temperature=0.1,
        )

        # Extract selected indices
        import re

        selected_indices: Set[int] = set()
        matches = re.finditer(r"<selected>\s*(\d+)\s*</selected>", response)

        for match in matches:
            index = int(match.group(1))
            if 0 <= index < len(bullet_points):
                selected_indices.add(index)

        # If we didn't get enough selections, take the first max_points
        if len(selected_indices) < max_points:
            selected_indices = set(range(min(max_points, len(bullet_points))))

        # If we got too many selections, take only the first max_points
        if len(selected_indices) > max_points:
            selected_indices = set(sorted(list(selected_indices))[:max_points])

        # Create a new list with only the selected points
        selected_points = [
            point for i, point in enumerate(bullet_points) if i in selected_indices
        ]

        return selected_points


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
