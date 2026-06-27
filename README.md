# chatgpt-bridge

Send prompts to AI chat interfaces via browser automation, get responses back.
Supports ChatGPT and Gemini today; adding a new backend is ~10 lines.

Uses `undetected-chromedriver` with a persistent Chrome profile per AI so login survives across sessions.

## Install

```bash
pip install undetected-chromedriver selenium
```

Chrome must be installed.

## First Run — Log In

Each AI uses its own Chrome profile (`~/.config/chrome-gpt`, `~/.config/chrome-gemini`).
On first run the browser opens and waits. Log in manually, then close — credentials are saved and reused automatically from then on.

## CLI — `bridge.py` (multi-AI entry point)

```bash
# Single prompt
python3 bridge.py --ai chatgpt prompt.txt
python3 bridge.py --ai gemini  prompt.txt

# Inline text
python3 bridge.py --ai chatgpt --text "What is an eigenvector?"

# Save response to file
python3 bridge.py --ai gemini prompt.txt response.txt

# Continue last conversation
python3 bridge.py --ai chatgpt --continue-chat followup.txt

# Multi-turn: one prompt per line
python3 bridge.py --ai chatgpt --prompts-file turns.txt

# Multi-turn with limits: max 3 turns, stop after 5 minutes
python3 bridge.py --ai chatgpt --prompts-file turns.txt --turns 3 --time-limit 300
```

### All options

| Flag | Default | Description |
|------|---------|-------------|
| `--ai` | `chatgpt` | Which AI: `chatgpt` or `gemini` |
| `--turns N` / `-n N` | no limit | Stop after N exchanges |
| `--time-limit S` / `-l S` | 1800 (30 min) | Stop after S seconds total |
| `--timeout S` | 180 (3 min) | Per-response timeout |
| `--continue-chat` / `-c` | false | Don't start a new conversation |
| `--prompts-file FILE` / `-p FILE` | — | Multi-turn mode: one prompt per line |
| `--quiet` / `-q` | false | No progress messages |

## Python Import

```python
from chatgpt import ChatGPTSession
from gemini  import GeminiSession

# Single message
with ChatGPTSession() as gpt:
    reply = gpt.send("Explain substitution integrals")

# Gemini
with GeminiSession() as g:
    reply = g.send("Same question, different model")

# Multi-turn with limits (works identically on any backend)
with ChatGPTSession() as gpt:
    results = gpt.loop(
        prompts=["First question", "Follow-up", "Go deeper"],
        max_turns=2,       # stop after 2 exchanges
        time_limit=120,    # or after 2 minutes — whichever comes first
    )
    for prompt, reply in results:
        print(f"Q: {prompt}\nA: {reply}\n")

# Backwards-compatible alias
from chatgpt import GPTSession   # same as ChatGPTSession
```

## Multi-turn Prompts File

`--prompts-file` reads one prompt per line; blank lines are skipped.

```text
What are the biggest risks in this business model?
What would you build first with 3 months and $0?
What's the most common mistake founders make in this space?
```

## Adding a New AI Backend

Create a new file (e.g. `perplexity.py`) with a subclass that sets the selectors:

```python
from base import BaseAISession

class PerplexitySession(BaseAISession):
    URL            = "https://www.perplexity.ai/"
    PROFILE_SUBDIR = "chrome-perplexity"
    SEL_TEXTAREA   = "textarea[placeholder]"
    SEL_SEND       = 'button[aria-label="Submit"]'
    SEL_STOP       = 'button[aria-label="Stop generating"]'
    SEL_RESPONSE   = ".prose"
    PASTE_MODE     = "keys"   # plain textarea — use value injection
```

Then register it in `bridge.py`:

```python
from perplexity import PerplexitySession
AI_CLASSES = {
    "chatgpt":    ChatGPTSession,
    "gemini":     GeminiSession,
    "perplexity": PerplexitySession,
}
```

## File Structure

```
bridge.py      — unified CLI entry point (--ai flag)
base.py        — BaseAISession: all browser automation logic
chatgpt.py     — ChatGPTSession: selectors only (~10 lines)
gemini.py      — GeminiSession: selectors + new-chat override (~15 lines)
```

## Config

Edit constants at the top of `base.py`:

```python
CHROME_VERSION   = 137   # match your installed Chrome: google-chrome --version
RESPONSE_TIMEOUT = 180   # per-response timeout (seconds)
SESSION_TIMEOUT  = 1800  # default total session limit (seconds)
```
