"""
Browser view for displaying web content.
"""

from typing import Optional, Callable
from PySide6.QtWidgets import QWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import (
    QWebEngineProfile,
    QWebEnginePage,
    QWebEngineScript,
)
from PySide6.QtCore import QUrl
from PySide6.QtGui import QContextMenuEvent, QGuiApplication
import webbrowser
from reddit_explorer.config.constants import BROWSER_DATA_DIR
from reddit_explorer.ui.browser.scripts import INITIAL_HIDE_SCRIPT, HIDE_SIDEBAR_SCRIPT

# Type alias for console message level
ConsoleLevel = QWebEnginePage.JavaScriptConsoleMessageLevel


class BrowserView(QWebEngineView):
    """Custom web view with Reddit-specific customizations."""

    def __init__(self, parent: Optional[QWidget] = None, debug: bool = False):
        """
        Initialize the browser view.

        Args:
            parent: Parent widget
            debug: Whether to enable debug logging
        """
        super().__init__(parent)
        self.debug = debug

        # Set up persistent web profile
        self.web_profile = QWebEngineProfile("reddit_explorer", self)
        self.web_profile.setPersistentStoragePath(BROWSER_DATA_DIR)
        self.web_profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
        )

        # Create and set custom page
        page = QWebEnginePage(self.web_profile, self)

        # Add script to hide content before page loads
        script = QWebEngineScript()
        script.setName("HideContent")
        script.setSourceCode(INITIAL_HIDE_SCRIPT)
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setRunsOnSubFrames(True)
        self.web_profile.scripts().insert(script)

        # Add console message handler
        if debug:
            page.javaScriptConsoleMessage = self._handle_console_message

        self.setPage(page)

    def contextMenuEvent(self, arg__1: QContextMenuEvent):
        """Handle context menu events to add custom actions."""
        # Get the context menu from the base class
        menu = self.createStandardContextMenu()

        # Add separator before our custom actions
        menu.addSeparator()

        # Add "Copy link" action that copies the current URL
        copy_link_action = menu.addAction("Copy link")
        copy_link_action.triggered.connect(self._copy_current_url)

        # Add "Open in browser" action
        open_browser_action = menu.addAction("Open in browser")
        open_browser_action.triggered.connect(self._open_in_browser)

        # Show the menu
        menu.exec_(arg__1.globalPos())
        menu.deleteLater()

    def _copy_current_url(self):
        """Copy the current URL to clipboard."""
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.url().toString())

    def _open_in_browser(self):
        """Open the current URL in the default web browser."""
        webbrowser.open(self.url().toString())

    def _handle_console_message(
        self, level: ConsoleLevel, message: str, lineNumber: int, sourceID: str
    ):
        """Handle JavaScript console messages."""
        print(f"JS {level.name}: {message} (line {lineNumber})")

    def load_url(
        self, url: str, on_load_finished: Optional[Callable[[bool], None]] = None
    ):
        """
        Load a URL and optionally run a callback when finished.

        Args:
            url: URL to load
            on_load_finished: Callback to run when page load finishes
        """
        if on_load_finished:
            self.loadFinished.connect(on_load_finished)
        self.setUrl(QUrl(url))

    def hide_sidebar(self):
        """Hide the Reddit sidebar and adjust layout."""
        self.page().runJavaScript(HIDE_SIDEBAR_SCRIPT)
