"""
evaluate.py — Module 4 Test Harness

One script, three rubric items simultaneously:

  1. Required "Reliability / Evaluation Component" (3 pts) — end-to-end
     behavioral assertions against 8 predefined inputs. Confirms the agent
     produces expected behavior: guardrail rejection, critic triggering on
     the right failure modes, retry firing only when retryable, warnings
     surfaced without suppression.

  2. Stretch — Test Harness (+2 pts) — pass/fail summary table, exits with
     non-zero status if any test fails (so this could drop straight into CI).

  3. Stretch — RAG Enhancement measurable improvement (+2 pts) — runs each
     profile twice (use_rag=True and use_rag=False) and prints a comparison
     table with per-profile and aggregate deltas across four metrics:
     explanation length, vocabulary diversity, song_notes reference rate,
     and mood_guide reference rate.

Usage:
    python evaluate.py                # full report (default)
    python evaluate.py --verbose      # also prints the agent's internal logs
"""
import argparse
import logging
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Union

from src.agent import run_agent, AgentResult
from src.recommender import load_songs
from src.explainer import load_mood_guides


# ═══════════════════════════════════════════════════════════════════════════
#   Profile fixtures — same 6 as agent_runner, kept here so evaluate.py is
#   self-contained and the test specs live next to the test data.
# ═══════════════════════════════════════════════════════════════════════════

PROFILES: Dict[str, Dict] = {
    "A": {"favorite_genre": "rock",    "favorite_mood": "intense",
          "target_energy": 0.88, "likes_acoustic": False},
    "B": {"favorite_genre": "lofi",    "favorite_mood": "chill",
          "target_energy": 0.38, "likes_acoustic": True},
    "C": {"favorite_genre": "pop",     "favorite_mood": "happy",
          "target_energy": 0.85, "likes_acoustic": False},
    "D": {"favorite_genre": "edm",     "favorite_mood": "sad",
          "target_energy": 0.90, "likes_acoustic": False},
    "E": {"favorite_genre": "country", "favorite_mood": "relaxed",
          "target_energy": 0.38, "likes_acoustic": True},
    "F": {"favorite_genre": "rock",    "favorite_mood": "intense",
          "target_energy": 0.90, "likes_acoustic": True},
}


# ═══════════════════════════════════════════════════════════════════════════
#   Test case specifications
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TestCase:
    id: str
    label: str
    input: Union[str, Dict]
    expect_success: bool = True
    expect_retried: bool = False
    # Codes (any severity) that MUST appear in first_critique.issues.
    # If empty, no fail-severity issues are allowed (warnings OK).
    expect_issues: List[str] = field(default_factory=list)


TESTS: List[TestCase] = [
    TestCase("A", "rock/intense standard",         PROFILES["A"]),
    TestCase("B", "lofi/chill standard",           PROFILES["B"]),
    TestCase("C", "pop/happy standard",            PROFILES["C"]),
    TestCase("D", "sad/EDM adversarial",           PROFILES["D"],
             expect_retried=True,
             expect_issues=["mood_valence_conflict"]),
    TestCase("E", "missing genre (country)",       PROFILES["E"],
             expect_issues=["missing_genre"]),   # warn, no retry
    TestCase("F", "acoustic rocker adversarial",   PROFILES["F"],
             expect_retried=True,
             expect_issues=["acoustic_violation"]),
    TestCase("G", "NL: high-energy rock for gym",  "high-energy rock for the gym"),
    TestCase("H", "gibberish input (guardrail)",   "xxxxxxxxx yyyyyyyyy",
             expect_success=False),
]


# ═══════════════════════════════════════════════════════════════════════════
#   Behavioral test runner
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TestOutcome:
    case: TestCase
    result: AgentResult
    passed: bool
    reasons: List[str] = field(default_factory=list)


def check(tc: TestCase, result: AgentResult) -> TestOutcome:
    """Compare one agent result to its expected behavior."""
    reasons: List[str] = []

    if result.success != tc.expect_success:
        reasons.append(f"success={result.success} (expected {tc.expect_success})")

    if result.success:
        if result.retried != tc.expect_retried:
            reasons.append(f"retried={result.retried} (expected {tc.expect_retried})")

        got_codes = {i.code for i in (result.first_critique.issues
                                      if result.first_critique else [])}
        got_fail_codes = {i.code for i in (result.first_critique.issues
                                           if result.first_critique else [])
                          if i.severity == "fail"}

        missing = set(tc.expect_issues) - got_codes
        if missing:
            reasons.append(f"expected issues not found: {sorted(missing)}")

        # For tests that don't expect any issues, no fail-severity issue may appear
        if not tc.expect_issues and got_fail_codes:
            reasons.append(f"unexpected failures: {sorted(got_fail_codes)}")

    return TestOutcome(case=tc, result=result, passed=not reasons, reasons=reasons)


def run_behavioral_tests(songs, guides) -> List[TestOutcome]:
    outcomes: List[TestOutcome] = []
    for tc in TESTS:
        result = run_agent(tc.input, songs, guides, use_rag=True)
        outcomes.append(check(tc, result))
    return outcomes


def print_behavioral_summary(outcomes: List[TestOutcome]) -> int:
    """Print pass/fail table, return exit code."""
    print("\n" + "═" * 76)
    print(f"  BEHAVIORAL TESTS ({len(outcomes)})")
    print("═" * 76 + "\n")

    for o in outcomes:
        tag = "[ PASS ]" if o.passed else "[ FAIL ]"
        # Describe observed behavior so the reader understands what the agent did
        if o.result.success:
            issues = (o.result.first_critique.issues
                      if o.result.first_critique else [])
            fails = sorted(i.code for i in issues if i.severity == "fail")
            warns = sorted(i.code for i in issues if i.severity == "warn")
            if o.result.retried:
                desc = f"retry fired (caught {fails})"
            elif fails:
                desc = f"fail without retry: {fails}"   # shouldn't normally happen
            elif warns:
                desc = f"clean pass with warnings: {warns}"
            else:
                desc = "clean pass"
        else:
            desc = "guardrail rejected"

        print(f"  {tag}  {o.case.id}  {o.case.label:<36s}  — {desc}")
        for r in o.reasons:
            print(f"              ↳ {r}")

    passed = sum(1 for o in outcomes if o.passed)
    print(f"\n  Total: {passed} / {len(outcomes)} passed\n")
    return 0 if passed == len(outcomes) else 1


# ═══════════════════════════════════════════════════════════════════════════
#   RAG vs baseline comparison
# ═══════════════════════════════════════════════════════════════════════════

def _text_stats(explanations: List[str]):
    """Return (avg_word_count, total_unique_tokens) across a list of strings."""
    total_words = 0
    all_tokens = set()
    for e in explanations:
        words = e.split()
        total_words += len(words)
        all_tokens.update(w.lower().strip(".,!?'\";:()") for w in words)
    avg = total_words / max(1, len(explanations))
    return avg, len(all_tokens)


def _ref_rates(result: AgentResult, mood_guides: Dict[str, str]):
    """
    Returns (% of recs whose prose contains the song's own song_notes,
             % of recs whose prose contains the user's mood guide text).

    Works for both RAG and baseline modes — in baseline mode, neither
    fragment is in the prose, so rates are 0%.
    """
    if not result.recommendations:
        return (0.0, 0.0)

    user_mood = (result.parser_result.prefs.get("favorite_mood", "")
                 if result.parser_result else "")
    guide_text = mood_guides.get(user_mood, "")

    n = len(result.recommendations)
    n_note = 0
    n_guide = 0
    for song, _, _, prose in result.recommendations:
        notes = (song.get("song_notes") or "").strip()
        if notes and notes in prose:
            n_note += 1
        if guide_text and guide_text in prose:
            n_guide += 1

    return (100 * n_note / n, 100 * n_guide / n)


def compare_rag_vs_baseline(songs, guides) -> Dict:
    """Run each profile twice and collect metrics."""
    per_profile: Dict[str, Dict] = {}
    for pid, prefs in PROFILES.items():
        rag = run_agent(prefs, songs, guides, use_rag=True)
        base = run_agent(prefs, songs, guides, use_rag=False)

        rag_prose = [p for _, _, _, p in rag.recommendations]
        base_prose = [p for _, _, _, p in base.recommendations]

        rag_avg, rag_vocab = _text_stats(rag_prose)
        base_avg, base_vocab = _text_stats(base_prose)
        rag_note_pct, rag_guide_pct = _ref_rates(rag, guides)
        base_note_pct, base_guide_pct = _ref_rates(base, guides)

        per_profile[pid] = {
            "base_avg": base_avg, "rag_avg": rag_avg,
            "base_vocab": base_vocab, "rag_vocab": rag_vocab,
            "base_note_pct": base_note_pct, "rag_note_pct": rag_note_pct,
            "base_guide_pct": base_guide_pct, "rag_guide_pct": rag_guide_pct,
        }

    return per_profile


def _pct_delta(base: float, rag: float) -> str:
    if base <= 0:
        return "  n/a"
    return f"{(rag - base) / base * 100:+.0f}%"


def print_rag_comparison(per_profile: Dict) -> None:
    print("═" * 76)
    print("  RAG vs BASELINE COMPARISON (6 profiles, use_rag=True vs False)")
    print("═" * 76 + "\n")

    # Aggregate across 6 profiles
    def mean(key):
        return sum(p[key] for p in per_profile.values()) / len(per_profile)

    avg_base_len  = mean("base_avg")
    avg_rag_len   = mean("rag_avg")
    avg_base_vo   = mean("base_vocab")
    avg_rag_vo    = mean("rag_vocab")
    avg_base_note = mean("base_note_pct")
    avg_rag_note  = mean("rag_note_pct")
    avg_base_gd   = mean("base_guide_pct")
    avg_rag_gd    = mean("rag_guide_pct")

    print(f"  Aggregate (mean across {len(per_profile)} profiles):\n")
    print(f"    {'Metric':<38s} {'Baseline':>11s}   {'RAG':>11s}   {'Δ':>6s}")
    print(f"    {'-'*38} {'-'*11}   {'-'*11}   {'-'*6}")
    print(f"    {'Avg explanation length (words)':<38s} "
          f"{avg_base_len:>11.1f}   {avg_rag_len:>11.1f}   {_pct_delta(avg_base_len, avg_rag_len):>6s}")
    print(f"    {'Unique vocab tokens (per profile)':<38s} "
          f"{avg_base_vo:>11.1f}   {avg_rag_vo:>11.1f}   {_pct_delta(avg_base_vo, avg_rag_vo):>6s}")
    print(f"    {'Recs referencing song_notes':<38s} "
          f"{avg_base_note:>10.0f}%   {avg_rag_note:>10.0f}%")
    print(f"    {'Recs referencing mood_guides':<38s} "
          f"{avg_base_gd:>10.0f}%   {avg_rag_gd:>10.0f}%")

    print(f"\n  Per-profile explanation length (words):\n")
    print(f"    {'Profile':<10s} {'Baseline':>10s}   {'RAG':>10s}   {'Δ':>6s}")
    print(f"    {'-'*10} {'-'*10}   {'-'*10}   {'-'*6}")
    for pid, m in per_profile.items():
        d = _pct_delta(m["base_avg"], m["rag_avg"])
        print(f"    {pid:<10s} {m['base_avg']:>10.1f}   {m['rag_avg']:>10.1f}   {d:>6s}")
    print()


# ═══════════════════════════════════════════════════════════════════════════
#   Entry point
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Module 4 test harness — behavioral tests + RAG comparison"
    )
    ap.add_argument("--verbose", action="store_true",
                    help="Show the agent's internal [PARSER][SCORER][CRITIC] logs")
    args = ap.parse_args()

    # The harness calls run_agent ~20 times. Default is quiet so the final
    # report isn't buried under per-run logs. --verbose for debugging.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass
    level = logging.INFO if args.verbose else logging.ERROR
    logging.basicConfig(level=level, format="%(message)s",
                        stream=sys.stdout, force=True)

    songs = load_songs("data/songs.csv")
    guides = load_mood_guides("data/mood_guides.csv")

    outcomes = run_behavioral_tests(songs, guides)
    rc = print_behavioral_summary(outcomes)

    metrics = compare_rag_vs_baseline(songs, guides)
    print_rag_comparison(metrics)

    sys.exit(rc)


if __name__ == "__main__":
    main()