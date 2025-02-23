"""
Service for interacting with OpenAI's API.
"""

import os
from typing import Optional, Dict, Any
from pathlib import Path
import openai
from openai import OpenAI
from dotenv import load_dotenv
from reddit_explorer.config.constants import (
    BASE_DIR,
    DEFAULT_OPENAI_MODEL,
)

# Load environment variables from .env file if it exists
env_path = Path(BASE_DIR).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


class OpenAIService:
    """Service for making OpenAI API calls."""

    _instance: Optional["OpenAIService"] = None

    def __new__(cls) -> "OpenAIService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize OpenAI client with API key."""
        # Try to get API key from environment first, then constants
        api_key = os.getenv("OPENAI_API_KEY", None)
        if not api_key:
            raise ValueError(
                "OpenAI API key not found. Please set OPENAI_API_KEY in environment or constants."
            )

        # Get optional base URL from environment
        base_url = os.getenv("OPENAI_BASE_URL")

        # Initialize client with appropriate configuration
        client_config = {"api_key": api_key}
        if base_url:
            client_config["base_url"] = base_url

        self.client = OpenAI(**client_config)

    def get_completion(
        self,
        system_message: str,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """
        Get a completion from OpenAI.

        Args:
            system_message: System message to set context
            prompt: User prompt/question
            model: OpenAI model to use (defaults to OPENAI_MODEL from env or DEFAULT_OPENAI_MODEL)
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens in response (None for model default)

        Returns:
            Model's response as a string

        Raises:
            openai.OpenAIError: If API call fails
            ValueError: If parameters are invalid
        """
        try:
            # Validate parameters
            if not system_message or not prompt:
                raise ValueError("System message and prompt are required")
            if not 0.0 <= temperature <= 2.0:
                raise ValueError("Temperature must be between 0.0 and 2.0")

            # Get model from environment or use default
            model = model or os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)

            # Prepare messages
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ]

            # Prepare API parameters
            params: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens:
                params["max_tokens"] = max_tokens

            # Make API call
            response = self.client.chat.completions.create(**params)

            # Extract and return response text
            return response.choices[0].message.content or ""

        except openai.OpenAIError as e:
            print(f"OpenAI API error: {str(e)}")
            raise


# test main

if __name__ == "__main__":
    openai_service = OpenAIService()
    print(
        openai_service.get_completion(
            "You are a helpful assistant.", "What is the capital of France?"
        )
    )
