#!/usr/bin/env python3
"""
bridge.py — unified entry point for chatgpt-bridge.

Selects the AI backend with --ai; all other flags are identical to chatgpt.py.

Usage:
    python3 bridge.py --ai chatgpt prompt.txt
    python3 bridge.py --ai gemini  prompt.txt response.txt
    python3 bridge.py --ai chatgpt --prompts-file turns.txt --turns 3 --time-limit 300
    python3 bridge.py --ai gemini  --text "What is calculus?"
"""

import sys
import pathlib
import argparse

from chatgpt import ChatGPTSession
from gemini  import GeminiSession
from base    import RESPONSE_TIMEOUT, SESSION_TIMEOUT

AI_CLASSES = {
    "chatgpt": ChatGPTSession,
    "gemini":  GeminiSession,
}


def main():
    parser = argparse.ArgumentParser(
        description="Send prompts to an AI chat interface, get responses back.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 bridge.py --ai chatgpt prompt.txt
  python3 bridge.py --ai gemini  --text "Explain eigenvectors"
  python3 bridge.py --ai chatgpt --prompts-file turns.txt --turns 3 --time-limit 300
  python3 bridge.py --ai gemini  prompt.txt response.txt --continue-chat
        """,
    )
    parser.add_argument("--ai", choices=list(AI_CLASSES), default="chatgpt",
                        help="Which AI to use (default: chatgpt)")

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("prompt_file",    nargs="?", help="File containing single prompt")
    source.add_argument("--text",  "-t",             help="Inline prompt text")
    source.add_argument("--prompts-file", "-p",      help="Multi-turn: one prompt per line")

    parser.add_argument("output_file",   nargs="?",  help="Save last response to this file")
    parser.add_argument("--continue-chat", "-c", action="store_true",
                        help="Continue the last conversation instead of starting a new one")
    parser.add_argument("--turns", "-n", type=int, default=None,
                        help="Max number of turns to run (default: all prompts)")
    parser.add_argument("--time-limit", "-l", type=int, default=SESSION_TIMEOUT,
                        help=f"Max total session time in seconds (default: {SESSION_TIMEOUT})")
    parser.add_argument("--timeout", type=int, default=RESPONSE_TIMEOUT,
                        help=f"Per-response timeout in seconds (default: {RESPONSE_TIMEOUT})")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress progress messages")
    args = parser.parse_args()

    SessionClass = AI_CLASSES[args.ai]

    with SessionClass(new_conversation=not args.continue_chat,
                      verbose=not args.quiet) as session:

        if args.prompts_file:
            lines   = pathlib.Path(args.prompts_file).read_text().splitlines()
            prompts = [l.strip() for l in lines if l.strip()]
            results = session.loop(
                prompts,
                max_turns=args.turns,
                time_limit=args.time_limit,
                timeout=args.timeout,
            )
            last_response = ""
            for i, (prompt, response) in enumerate(results, 1):
                print(f"\n{'='*60}\n[Turn {i}] {prompt[:80]}{'...' if len(prompt)>80 else ''}\n{'='*60}")
                print(response)
                last_response = response
            if args.output_file and last_response:
                pathlib.Path(args.output_file).write_text(last_response)

        else:
            prompt = args.text if args.text else pathlib.Path(args.prompt_file).read_text()
            response = session.send(prompt, timeout=args.timeout)
            print(response)
            if args.output_file:
                pathlib.Path(args.output_file).write_text(response)


if __name__ == "__main__":
    main()
