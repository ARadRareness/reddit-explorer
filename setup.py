from setuptools import setup, find_packages

setup(
    name="reddit_explorer",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "PySide6",
        "requests",
    ],
    entry_points={
        "console_scripts": [
            "reddit_explorer=reddit_explorer.main:main",
        ],
    },
)
