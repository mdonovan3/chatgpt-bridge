"""
BaseAISession — shared browser automation logic for all AI chat backends.
Subclasses override class-level constants (URL, selectors) and nothing else.
"""

import sys
import time
import random
import pathlib

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

CHROME_VERSION   = 137    # update if Chrome upgrades: google-chrome --version
RESPONSE_TIMEOUT = 180    # per-response timeout (seconds)
SESSION_TIMEOUT  = 1800   # default total session time limit (seconds)
_PROFILE_BASE    = pathlib.Path.home() / ".config"


class BaseAISession:
    """
    One browser session = one AI conversation thread.
    Override class attributes in subclasses; do not override methods.
    """

    # ── Subclass must set these ───────────────────────────────────────────────
    URL            = ""           # landing page / new-conversation URL
    PROFILE_SUBDIR = "chrome-ai"  # profile dir under ~/.config/
    SEL_TEXTAREA   = ""           # input field selector
    SEL_SEND       = ""           # send button selector
    SEL_STOP       = ""           # stop/cancel button (present while streaming)
    SEL_RESPONSE   = ""           # assistant message container(s)
    # "clipboard" (DataTransfer paste event) or "keys" (direct key injection)
    PASTE_MODE     = "clipboard"

    # ── Init ─────────────────────────────────────────────────────────────────

    def __init__(self, new_conversation=True, headless=False, verbose=True):
        self.verbose = verbose
        self._session_start = time.time()
        self._turn_count = 0
        self._log("Starting browser...")
        self.driver = self._start_browser(headless)
        self._log(f"Navigating to {self.URL} ...")
        self.driver.get(self.URL)
        time.sleep(random.uniform(2.5, 4))
        if new_conversation:
            self._ensure_new_chat()

    # ── Browser setup ─────────────────────────────────────────────────────────

    def _start_browser(self, headless):
        profile = _PROFILE_BASE / self.PROFILE_SUBDIR
        profile.mkdir(parents=True, exist_ok=True)

        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={profile}")
        options.add_argument(f"--window-size={random.randint(1280,1600)},{random.randint(900,1080)}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--remote-allow-origins=*")
        if headless:
            options.add_argument("--headless=new")

        driver = uc.Chrome(options=options, version_main=CHROME_VERSION)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins',   {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
            window.chrome = { runtime: {} };
        """})
        return driver

    def _ensure_new_chat(self):
        """Navigate to a blank conversation. Override if the AI needs a specific action."""
        try:
            btn = self.driver.find_element(By.CSS_SELECTOR, 'a[href="/"]')
            btn.click()
            time.sleep(random.uniform(1, 2))
        except Exception:
            pass

    # ── Public API ────────────────────────────────────────────────────────────

    def send(self, message, timeout=RESPONSE_TIMEOUT):
        """Send one message, wait for the full response, return response text."""
        self._paste_message(message)
        self._click_send()
        self._log(f"Turn {self._turn_count + 1} — waiting for response...")
        response = self._wait_for_response(timeout)
        self._turn_count += 1
        elapsed = time.time() - self._session_start
        self._log(f"Response received ({len(response)} chars) | turn {self._turn_count} | {elapsed:.0f}s elapsed")
        return response

    def loop(self, prompts, max_turns=None, time_limit=None, timeout=RESPONSE_TIMEOUT):
        """
        Send a sequence of prompts in the same conversation thread.
        Stops when max_turns is reached OR time_limit seconds have elapsed.

        Returns list of (prompt, response) tuples.
        """
        if time_limit is None:
            time_limit = SESSION_TIMEOUT
        results = []
        loop_start = time.time()

        for i, prompt in enumerate(prompts):
            if max_turns is not None and i >= max_turns:
                self._log(f"Reached max_turns={max_turns}, stopping.")
                break
            elapsed = time.time() - loop_start
            if elapsed >= time_limit:
                self._log(f"Reached time_limit={time_limit}s ({elapsed:.0f}s elapsed), stopping.")
                break
            remaining = time_limit - elapsed
            n = len(prompts) if hasattr(prompts, "__len__") else "?"
            self._log(f"Loop turn {i+1}/{n} | {remaining:.0f}s remaining")
            response = self.send(prompt, timeout=min(timeout, remaining))
            results.append((prompt, response))

        return results

    def session_elapsed(self):
        return time.time() - self._session_start

    # ── Internal mechanics ────────────────────────────────────────────────────

    def _paste_message(self, text):
        driver = self.driver
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, self.SEL_TEXTAREA))
        ).click()
        time.sleep(0.4)

        if self.PASTE_MODE == "clipboard":
            # DataTransfer paste event — works on React/contenteditable inputs
            driver.execute_script("""
                var el = document.querySelector(arguments[0]);
                if (el) { el.focus(); el.innerHTML = ''; }
            """, self.SEL_TEXTAREA)
            time.sleep(0.2)
            driver.execute_script("""
                var el = document.querySelector(arguments[0]);
                if (!el) return;
                el.focus();
                var dt = new DataTransfer();
                dt.setData('text/plain', arguments[1]);
                el.dispatchEvent(new ClipboardEvent('paste', {
                    clipboardData: dt, bubbles: true, cancelable: true
                }));
            """, self.SEL_TEXTAREA, text)
        else:
            # "keys" mode — direct value injection + input event, works on plain textareas
            driver.execute_script("""
                var el = document.querySelector(arguments[0]);
                if (!el) return;
                el.focus();
                var nativeInput = Object.getOwnPropertyDescriptor(
                    window.HTMLTextAreaElement.prototype, 'value') ||
                    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
                if (nativeInput) nativeInput.set.call(el, arguments[1]);
                else el.value = arguments[1];
                el.dispatchEvent(new Event('input',  {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
            """, self.SEL_TEXTAREA, text)

        time.sleep(random.uniform(0.6, 1.0))

    def _click_send(self):
        try:
            btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.SEL_SEND))
            )
            btn.click()
        except Exception:
            ta = self.driver.find_element(By.CSS_SELECTOR, self.SEL_TEXTAREA)
            ta.send_keys(Keys.RETURN)
        time.sleep(2.5)

    def _wait_for_response(self, timeout):
        driver   = self.driver
        deadline = time.time() + timeout
        for _ in range(15):
            if driver.find_elements(By.CSS_SELECTOR, self.SEL_STOP):
                break
            time.sleep(1)
        while time.time() < deadline:
            if not driver.find_elements(By.CSS_SELECTOR, self.SEL_STOP):
                break
            time.sleep(1.5)
        else:
            raise RuntimeError(f"Response did not complete within {timeout}s")
        time.sleep(2)
        msgs = driver.find_elements(By.CSS_SELECTOR, self.SEL_RESPONSE)
        return msgs[-1].text if msgs else ""

    def _log(self, msg):
        if self.verbose:
            print(f"[{self.__class__.__name__}] {msg}", flush=True)

    # ── Context manager ───────────────────────────────────────────────────────

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
