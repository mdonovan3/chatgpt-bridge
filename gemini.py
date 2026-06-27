"""Gemini backend for chatgpt-bridge."""

import time
from selenium.webdriver.common.by import By
from base import BaseAISession


class GeminiSession(BaseAISession):
    URL            = "https://gemini.google.com/"
    PROFILE_SUBDIR = "chrome-gemini"
    # Gemini uses a Quill-based rich-textarea; verify selectors on first run
    SEL_TEXTAREA   = ".ql-editor"
    SEL_SEND       = 'button[aria-label="Send message"]'
    SEL_STOP       = 'button[aria-label="Stop response"]'
    SEL_RESPONSE   = "model-response"          # custom element wrapping each reply
    PASTE_MODE     = "clipboard"

    def _ensure_new_chat(self):
        """Gemini: click 'New chat' button in the sidebar."""
        try:
            btn = self.driver.find_element(
                By.CSS_SELECTOR, 'a[href="/app"], button[aria-label="New chat"]'
            )
            btn.click()
            time.sleep(1.5)
        except Exception:
            pass
