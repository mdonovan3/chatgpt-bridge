# chatgpt-bridge

Send prompts to ChatGPT via browser automation, get responses back. Uses `undetected-chromedriver` with a persistent Chrome profile so login survives across sessions.

## Install

```bash
pip install undetected-chromedriver selenium
```

Chrome must be installed (used as the browser).

## First Run — Log In

The first time you run it, Chrome opens and lands on ChatGPT. Log in manually, then close the window. Credentials are stored in the profile at `~/.config/chrome-gpt` and reused every subsequent run.

## CLI Usage

```bash
# Single prompt from file
python3 chatgpt.py prompt.txt

# Single prompt inline
python3 chatgpt.py --text "What is an eigenvector?"

# Save response to file
python3 chatgpt.py prompt.txt response.txt

# Continue last conversation instead of starting new
python3 chatgpt.py --continue-chat followup.txt

# Multi-turn: one prompt per line in a file
python3 chatgpt.py --prompts-file turns.txt

# Multi-turn with limits: max 3 turns, stop after 5 minutes
python3 chatgpt.py --prompts-file turns.txt --turns 3 --time-limit 300

# Suppress progress output
python3 chatgpt.py --quiet prompt.txt
```

### All Options

| Flag | Default | Description |
|------|---------|-------------|
| `--turns N` / `-n N` | no limit | Stop after N exchanges |
| `--time-limit S` / `-l S` | 1800 (30 min) | Stop after S seconds total |
| `--timeout S` | 180 (3 min) | Per-response timeout |
| `--continue-chat` / `-c` | false | Don't start a new conversation |
| `--prompts-file FILE` / `-p FILE` | — | Multi-turn: one prompt per line |
| `--quiet` / `-q` | false | No progress messages |

## Python Import

```python
from chatgpt import GPTSession

# Single message
with GPTSession() as gpt:
    reply = gpt.send("Explain substitution integrals")
    print(reply)

# Multi-turn with limits
with GPTSession() as gpt:
    results = gpt.loop(
        prompts=["First question", "Follow-up", "Go deeper"],
        max_turns=2,       # stop after 2 exchanges
        time_limit=120,    # or after 2 minutes — whichever comes first
    )
    for prompt, reply in results:
        print(f"Q: {prompt}\nA: {reply}\n")

# Continue across multiple sends (same conversation thread)
gpt = GPTSession()
r1 = gpt.send("Tell me about linear algebra")
r2 = gpt.send("Now focus on eigenvalues")  # same conversation
gpt.close()
```

## Multi-turn Prompts File

`--prompts-file` reads one prompt per line. Blank lines are skipped.

```text
What are the biggest risks in this business model?
What would you build first if you had 3 months and $0?
What's the most common mistake founders make in this space?
```

## Config

Edit the constants at the top of `chatgpt.py`:

```python
PROFILE_DIR     = ~/.config/chrome-gpt   # Chrome profile with saved login
CHROME_VERSION  = 137                     # match your installed Chrome version
RESPONSE_TIMEOUT = 180                    # per-response timeout (seconds)
SESSION_TIMEOUT  = 1800                   # default total session limit (seconds)
```

To check your Chrome version: `google-chrome --version`
