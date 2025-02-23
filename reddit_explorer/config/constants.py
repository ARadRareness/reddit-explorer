"""
Constants and configuration values for the Reddit Explorer application.
"""

import os

# File paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "image_cache")
BROWSER_DATA_DIR = os.path.join(BASE_DIR, "browser_data")
DATABASE_PATH = os.path.join(BASE_DIR, "reddit_explorer.db")

# Reddit API
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
REDDIT_HEADERS = {"User-Agent": USER_AGENT}

# UI Constants
MAX_POSTS = 400
TREE_MIN_WIDTH = 150
TREE_MAX_WIDTH = 250
NAV_BUTTON_HEIGHT = 24
IMAGE_MAX_WIDTH = 800

# Database
DEFAULT_CATEGORY = "Uncategorized"

# Image Extensions
VALID_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif"]

# OpenAI
DEFAULT_OPENAI_MODEL = "gpt-4o"  # Default model if not specified in environment
