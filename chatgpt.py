#!/usr/bin/env python3
"""
chatgpt-bridge — send prompts to ChatGPT via browser automation, get responses back.

Uses undetected-chromedriver with a dedicated Chrome profile so login persists.
First run: browser opens, log in manually, then close. Subsequent runs are automatic.

Usage (CLI):
    python3 chatgpt.py <prompt_file>                         # single prompt, print response
    python3 chatgpt.py <prompt_file> <output_file>           # save response to file
    python3 chatgpt.py --text "your prompt here"             # inline text
    python3 chatgpt.py --continue-chat <prompt_file>         # continue last conversation
    python3 chatgpt.py --prompts-file turns.txt              # multi-turn: one prompt per line
    python3 chatgpt.py --prompts-file turns.txt --turns 3    # cap at 3 turns
    python3 chatgpt.py --prompts-file turns.txt --time-limit 300  # stop after 5 min

Usage (import):
    from chatgpt import GPTSession

    # Single message
    with GPTSession() as gpt:
        reply = gpt.send("Tell me about eigenvectors")
        print(reply)

    # Multi-turn loop with limits
    with GPTSession() as gpt:
        results = gpt.loop(
            prompts=["First question", "Follow-up", "Dig deeper"],
            max_turns=2,       # stop after 2 exchanges
            time_limit=120,    # or after 2 minutes, whichever comes first
        )
        for prompt, reply in results:
            print(f"Q: {prompt}\\nA: {reply}\\n")

Install:
    pip install undetected-chromedriver selenium
"""

import sys
import time
import random
import pathlib
import argparse

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ── Config ──────────────────────────────────────────────────────────────────

PROFILE_DIR     = pathlib.Path.home() / ".config" / "chrome-gpt"
CHROME_VERSION  = 137    # update if Chrome upgrades: google-chrome --version
GPT_URL         = "https://chatgpt.com/"
RESPONSE_TIMEOUT = 180   # per-response timeout (seconds); override with --timeout
SESSION_TIMEOUT  = 1800  # default total session time limit (30 min); override with --time-limit


# ── Selectors (update here if ChatGPT changes its DOM) ──────────────────────

SEL_TEXTAREA = "#prompt-textarea"
SEL_SEND     = 'button[data-testid="send-button"]'
SEL_STOP     = 'button[data-testid="stop-button"]'
SEL_RESPONSE = '[data-message-author-role="assistant"]'


# ── Core class ───────────────────────────────────────────────────────────────

class GPTSession:
    """
    One browser session = one ChatGPT conversation thread.
    Create a new GPTSession() for a fresh conversation.
    Call .send() multiple times to continue the thread.
    Call .loop() to run multiple prompts with turn/time limits.
    Call .close() or use as a context manager.
    """

    def __init__(self, new_conversation=True, headless=False, verbose=True):
        self.verbose = verbose
        self._session_start = time.time()
        self._turn_count = 0
        self._log("Starting browser...")
        self.driver = self._start_browser(headless)
        self._log("Navigating to ChatGPT...")
        self.driver.get(GPT_URL)
        time.sleep(random.uniform(2.5, 4))
        if new_conversation:
            self._ensure_new_chat()

    # ── Setup ────────────────────────────────────────────────────────────────

    def _start_browser(self, headless):
        options = uc.ChromeOptions()
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={PROFILE_DIR}")
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
        try:
            btn = self.driver.find_element(By.CSS_SELECTOR, 'a[href="/"]')
            btn.click()
            time.sleep(random.uniform(1, 2))
        except Exception:
            pass

    # ── Send / receive ────────────────────────────────────────────────────────

    def send(self, message, timeout=RESPONSE_TIMEOUT):
        """
        Send one message, wait for the full response, return response text.
        Raises RuntimeError if the response does not complete within timeout.
        """
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
        Send a sequence of prompts in order, continuing the same conversation thread.
        Stops early when max_turns is reached OR time_limit seconds have elapsed.

        Args:
            prompts:    iterable of strings to send in order
            max_turns:  stop after this many turns (None = no limit)
            time_limit: stop after this many seconds total (None = SESSION_TIMEOUT)
            timeout:    per-response timeout in seconds

        Returns:
            list of (prompt, response) tuples for each completed turn
        """
        if time_limit is None:
            time_limit = SESSION_TIMEOUT
        results = []
        loop_start = time.time()

        for i, prompt in enumerate(prompts):
            if max_turns is not None and i >= max_turns:
                self._log(f"Reached max_turns={max_turns}, stopping loop.")
                break
            elapsed = time.time() - loop_start
            if elapsed >= time_limit:
                self._log(f"Reached time_limit={time_limit}s ({elapsed:.0f}s elapsed), stopping loop.")
                break
            remaining = time_limit - elapsed
            self._log(f"Loop turn {i+1}/{len(prompts) if hasattr(prompts,'__len__') else '?'} | {remaining:.0f}s remaining in session")
            response = self.send(prompt, timeout=min(timeout, remaining))
            results.append((prompt, response))

        return results

    def session_elapsed(self):
        """Seconds since this session started."""
        return time.time() - self._session_start

    # ── Internals ─────────────────────────────────────────────────────────────

    def _paste_message(self, text):
        """Set message text using a simulated paste event — works for any length."""
        driver = self.driver
        textarea = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SEL_TEXTAREA))
        )
        textarea.click()
        time.sleep(0.4)
        driver.execute_script("""
            var el = document.querySelector(arguments[0]);
            if (el) { el.focus(); el.innerHTML = ''; }
        """, SEL_TEXTAREA)
        time.sleep(0.2)
        driver.execute_script("""
            var el = document.querySelector(arguments[0]);
            if (!el) return;
            el.focus();
            var dt = new DataTransfer();
            dt.setData('text/plain', arguments[1]);
            el.dispatchEvent(new ClipboardEvent('paste', {
                clipboardData: dt,
                bubbles: true,
                cancelable: true
            }));
        """, SEL_TEXTAREA, text)
        time.sleep(random.uniform(0.6, 1.0))

    def _click_send(self):
        try:
            btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, SEL_SEND))
            )
            btn.click()
        except Exception:
            ta = self.driver.find_element(By.CSS_SELECTOR, SEL_TEXTAREA)
            ta.send_keys(Keys.RETURN)
        time.sleep(2.5)

    def _wait_for_response(self, timeout):
        driver   = self.driver
        deadline = time.time() + timeout
        for _ in range(15):
            if driver.find_elements(By.CSS_SELECTOR, SEL_STOP):
                break
            time.sleep(1)
        while time.time() < deadline:
            if not driver.find_elements(By.CSS_SELECTOR, SEL_STOP):
                break
            time.sleep(1.5)
        else:
            raise RuntimeError(f"Response did not complete within {timeout}s")
        time.sleep(2)
        msgs = driver.find_elements(By.CSS_SELECTOR, SEL_RESPONSE)
        return msgs[-1].text if msgs else ""

    def _log(self, msg):
        if self.verbose:
            print(f"[chatgpt] {msg}", flush=True)

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Send prompts to ChatGPT, get responses back.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 chatgpt.py prompt.txt                         single prompt
  python3 chatgpt.py --text "What is calculus?"         inline prompt
  python3 chatgpt.py prompt.txt response.txt            save response
  python3 chatgpt.py --prompts-file turns.txt           run all turns in file
  python3 chatgpt.py --prompts-file turns.txt \\
      --turns 3 --time-limit 300                        cap at 3 turns or 5 min
        """,
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("prompt_file",    nargs="?", help="File containing single prompt")
    source.add_argument("--text",  "-t",             help="Inline prompt text")
    source.add_argument("--prompts-file", "-p",      help="Multi-turn: one prompt per line (blank lines skipped)")

    parser.add_argument("output_file",   nargs="?",  help="Save last response to this file")
    parser.add_argument("--continue-chat", "-c", action="store_true",
                        help="Continue the last conversation instead of starting a new one")
    parser.add_argument("--turns", "-n", type=int, default=None,
                        help="Max number of turns (exchanges) to run (default: all in file)")
    parser.add_argument("--time-limit", "-l", type=int, default=SESSION_TIMEOUT,
                        help=f"Max total session time in seconds (default: {SESSION_TIMEOUT})")
    parser.add_argument("--timeout", type=int, default=RESPONSE_TIMEOUT,
                        help=f"Per-response timeout in seconds (default: {RESPONSE_TIMEOUT})")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress progress messages")
    args = parser.parse_args()

    with GPTSession(new_conversation=not args.continue_chat,
                    verbose=not args.quiet) as gpt:

        if args.prompts_file:
            lines = pathlib.Path(args.prompts_file).read_text().splitlines()
            prompts = [l.strip() for l in lines if l.strip()]
            results = gpt.loop(
                prompts,
                max_turns=args.turns,
                time_limit=args.time_limit,
                timeout=args.timeout,
            )
            last_response = ""
            for i, (prompt, response) in enumerate(results, 1):
                print(f"\n{'='*60}\n[Turn {i}] Prompt: {prompt[:80]}{'...' if len(prompt)>80 else ''}\n{'='*60}")
                print(response)
                last_response = response
            if args.output_file and last_response:
                pathlib.Path(args.output_file).write_text(last_response)
                print(f"\n[chatgpt] Last response saved to: {args.output_file}", file=sys.stderr)

        else:
            if args.text:
                prompt = args.text
            else:
                p = pathlib.Path(args.prompt_file)
                if not p.exists():
                    print(f"Error: file not found: {p}", file=sys.stderr)
                    sys.exit(1)
                prompt = p.read_text()

            response = gpt.send(prompt, timeout=args.timeout)
            print(response)
            if args.output_file:
                pathlib.Path(args.output_file).write_text(response)
                print(f"\n[chatgpt] Saved to: {args.output_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
