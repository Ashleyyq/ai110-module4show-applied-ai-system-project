"""
agent_runner.py — Module 4 Extension

CLI entry point for the agentic pipeline. Handles three responsibilities that
agent.py deliberately does not:

  1. Logging config: routes all [PARSER] [SCORER] [CRITIC] [AGENT] log lines
     to stdout (same stream as print()) with line buffering, so interleaved
     output preserves order. Fixes the stdout/stderr ordering problem visible
     in the individual module smoke tests.
  2. Argument parsing: pick a profile, pass a free-form query, toggle RAG,
     or silence internal logs.
  3. Human-readable rendering of AgentResult for demos.

Usage:
  python -m src.agent_runner                       # all 6 profiles
  python -m src.agent_runner --profile D           # one profile
  python -m src.agent_runner --query "chill lofi for studying"
  python -m src.agent_runner --no-rag              # baseline Explainer
  python -m src.agent_runner --quiet               # hide internal reasoning
"""
import argparse
import logging
import sys

from src.agent import run_agent, AgentResult
from src.recommender import load_songs
from src.explainer import load_mood_guides


# The same 6 profiles as src/main.py, kept here so the agentic runner and
# the baseline runner can be compared one-for-one.
PROFILES = {
    "A": ("High-Energy Rock Fan (standard)",
          {"favorite_genre": "rock", "favorite_mood": "intense",
           "target_energy": 0.88, "likes_acoustic": False}),
    "B": ("Chill Lofi Listener (standard)",
          {"favorite_genre": "lofi", "favorite_mood": "chill",
           "target_energy": 0.38, "likes_acoustic": True}),
    "C": ("Upbeat Pop Dancer (standard)",
          {"favorite_genre": "pop", "favorite_mood": "happy",
           "target_energy": 0.85, "likes_acoustic": False}),
    "D": ("Sad but Energetic (adversarial)",
          {"favorite_genre": "edm", "favorite_mood": "sad",
           "target_energy": 0.90, "likes_acoustic": False}),
    "E": ("Genre Ghost / Country (adversarial)",
          {"favorite_genre": "country", "favorite_mood": "relaxed",
           "target_energy": 0.38, "likes_acoustic": True}),
    "F": ("Acoustic Rocker (adversarial)",
          {"favorite_genre": "rock", "favorite_mood": "intense",
           "target_energy": 0.90, "likes_acoustic": True}),
}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _print_banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


def render_result(label: str, user_input, result: AgentResult) -> None:
    _print_banner(label)

    # Echo the input for demo clarity
    if isinstance(user_input, dict):
        pretty = " | ".join(f"{k}={v}" for k, v in user_input.items())
        print(f"  Input : {pretty}")
    else:
        print(f"  Input : {user_input!r}")
    mode = "RAG-enhanced" if result.used_rag else "baseline (no RAG)"
    print(f"  Mode  : {mode}")
    print("-" * 72)

    # Guardrail reject
    if not result.success:
        print(f"\n  ❌  Guardrail rejected input:  {result.error}")
        return

    # Agent decisions (summary for the reader — detailed logs are above this,
    # in --verbose mode)
    if result.retried:
        print(f"\n  🔁  Critic triggered retry with hints: "
              f"{result.first_critique.retry_hints}")

    warn_issues = [
        i for i in (result.first_critique.issues if result.first_critique else [])
        if i.severity == "warn"
    ]
    if warn_issues:
        print("\n  ℹ️   Critic warnings:")
        for i in warn_issues:
            print(f"        · {i.message}")

    if (result.retried and result.second_critique
            and not result.second_critique.passed):
        residual = [i for i in result.second_critique.issues if i.severity == "fail"]
        if residual:
            print("\n  ⚠️   Residual issues after retry (1-retry cap — surfaced):")
            for i in residual:
                print(f"        · {i.message}")

    # The recommendations themselves
    print("\n  Recommendations:")
    for rank, (song, score, _, prose) in enumerate(result.recommendations, 1):
        print(f"\n    #{rank}  {song['title']}  —  {song['artist']}  "
              f"(score {score:.2f})")
        # Indent the prose nicely so it stays readable in a terminal
        for line in _wrap(prose, width=66, indent=" " * 8):
            print(line)


def _wrap(text: str, width: int, indent: str) -> list:
    """Simple word-wrap for prose explanations in terminal output."""
    words = text.split()
    lines, cur = [], indent
    for w in words:
        if len(cur) + len(w) + 1 > width + len(indent) and cur.strip():
            lines.append(cur.rstrip())
            cur = indent + w
        else:
            cur += (" " if cur != indent else "") + w
    if cur.strip():
        lines.append(cur.rstrip())
    return lines


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Music Recommender — agentic pipeline (Module 4)"
    )
    ap.add_argument("--profile", choices=sorted(PROFILES.keys()),
                    help="Run a single profile (A-F) instead of all six")
    ap.add_argument("--query",
                    help="Run a free-form natural-language query")
    ap.add_argument("--no-rag", action="store_true",
                    help="Use the baseline Explainer (no song_notes, no mood_guides)")
    ap.add_argument("--quiet", action="store_true",
                    help="Hide internal [PARSER][SCORER][CRITIC][AGENT] logs")
    args = ap.parse_args()

    # ─── Logging config: stdout + line buffering so log lines and print()
    #     calls interleave in true chronological order ─────────────────
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass  # older Python; best-effort fallback
    level = logging.WARNING if args.quiet else logging.INFO
    # force=True reinitializes the root logger if another import set it up
    logging.basicConfig(level=level, format="%(message)s",
                        stream=sys.stdout, force=True)

    # ─── Load data once, reuse across runs ────────────────────────────
    songs = load_songs("data/songs.csv")
    guides = load_mood_guides("data/mood_guides.csv")
    use_rag = not args.no_rag

    # ─── Dispatch ─────────────────────────────────────────────────────
    if args.query:
        result = run_agent(args.query, songs, guides, use_rag=use_rag)
        render_result("Free-form NL query", args.query, result)
    elif args.profile:
        label, prefs = PROFILES[args.profile]
        result = run_agent(prefs, songs, guides, use_rag=use_rag)
        render_result(f"Profile {args.profile} — {label}", prefs, result)
    else:
        for key in ["A", "B", "C", "D", "E", "F"]:
            label, prefs = PROFILES[key]
            result = run_agent(prefs, songs, guides, use_rag=use_rag)
            render_result(f"Profile {key} — {label}", prefs, result)


if __name__ == "__main__":
    main()