"""ChatGPT backend for chatgpt-bridge."""

from base import BaseAISession


class ChatGPTSession(BaseAISession):
    URL            = "https://chatgpt.com/"
    PROFILE_SUBDIR = "chrome-gpt"
    SEL_TEXTAREA   = "#prompt-textarea"
    SEL_SEND       = 'button[data-testid="send-button"]'
    SEL_STOP       = 'button[data-testid="stop-button"]'
    SEL_RESPONSE   = '[data-message-author-role="assistant"]'
    PASTE_MODE     = "clipboard"


# Backwards-compatibility alias — existing `from chatgpt import GPTSession` still works
GPTSession = ChatGPTSession
