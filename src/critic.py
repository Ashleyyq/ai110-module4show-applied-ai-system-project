"""
critic.py — Module 4 Extension

Stage 4 of the agentic chain. Inspects a ranked list of recommendations
against four rule-based checks and decides whether the result set should
be accepted, surfaced with a warning, or retried with adjusted scoring.

Checks (severity in parens):
  1. mood_valence_conflict (fail)    — top-1 valence clashes with the user's
                                       mood-inferred target. Retries with a
                                       valence penalty applied to every song.
  2. missing_genre         (warn)    — user's favorite_genre is not in catalog.
                                       Does not retry: no amount of reweighting
                                       can conjure a missing genre. Critic just
                                       surfaces the fallback.
  3. acoustic_violation    (fail)    — likes_acoustic=True but top-1 acousticness
                                       < 0.3, or vice versa. Retries with a
                                       HARD FILTER on the candidate pool, not
                                       a soft penalty — acoustic preference is
                                       strong enough to override the genre+mood
                                       ceiling otherwise.
  4. low_diversity         (fail)    — top-5 dominated by a single genre
                                       (>=4/5). Retries with a diversity
                                       penalty that compounds per repeat.

A deliberate design choice: not every fail triggers retry. Some issues
(missing_genre) are irreducible and the agent's correct response is to
tell the user honestly, not to pretend otherwise. This is tracked via
the per-issue `retryable` flag.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.recommender import MOOD_VALENCE

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class CriticIssue:
    """One finding from the Critic."""
    code: str
    severity: str             # "fail" or "warn"
    message: str
    retryable: bool = False   # if True, hints below feed into rerank_with_hints
    hints: Dict = field(default_factory=dict)


@dataclass
class CritiqueResult:
    """Aggregate outcome of all critic checks on a single recommendation set."""
    issues: List[CriticIssue]
    passed: bool              # no "fail"-severity issues
    should_retry: bool        # at least one retryable fail
    retry_hints: Dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Thresholds — tuned against the adversarial profiles D/E/F
# ---------------------------------------------------------------------------

VALENCE_CONFLICT_GAP = 0.4       # |valence - target| > this = conflict
VALENCE_PENALTY_WEIGHT = 5.0     # aggressive on retry: must overcome +5 categorical ceiling
ACOUSTIC_VIOLATION_GAP = 0.5     # diff between acousticness and target
ACOUSTIC_FILTER_THRESHOLD = 0.5  # on retry: keep only songs on user's side of 0.5
DIVERSITY_DOMINANT_COUNT = 4     # >=N of 5 = dominated
DIVERSITY_PENALTY_WEIGHT = 1.5   # subtracted per repeat


# ---------------------------------------------------------------------------
# Public API: critique
# ---------------------------------------------------------------------------

def critique(ranked: List[Tuple[Dict, float, str]],
             user_prefs: Dict,
             catalog_genres: Optional[set] = None) -> CritiqueResult:
    """
    Run all four checks against the current top-5 slice of `ranked`.

    Args:
        ranked: full ranked list from recommend_songs (longer than 5 is fine;
                only the top 5 are judged, but rerank will see the full list)
        user_prefs: validated prefs from parser
        catalog_genres: set of genres actually in the catalog (for missing_genre check)

    Returns a CritiqueResult.
    """
    top_n = ranked[:5]
    if not top_n:
        return CritiqueResult(
            issues=[CriticIssue(
                code="empty_result",
                severity="fail",
                message="No recommendations produced. Upstream pipeline failure.",
                retryable=False,
            )],
            passed=False,
            should_retry=False,
        )

    issues: List[CriticIssue] = []

    issues.extend(_check_mood_valence(top_n, user_prefs))
    issues.extend(_check_missing_genre(user_prefs, catalog_genres or set()))
    issues.extend(_check_acoustic(top_n, user_prefs))
    issues.extend(_check_diversity(top_n))

    failed = [i for i in issues if i.severity == "fail"]
    retryable_hints: Dict = {}
    for i in failed:
        if i.retryable:
            retryable_hints.update(i.hints)

    passed = len(failed) == 0
    should_retry = bool(retryable_hints)

    # Log a human-readable verdict line — this is what makes the agent's
    # decision-making observable in demo output.
    if passed and not issues:
        logger.info("[CRITIC] ✅ pass (all checks clean)")
    elif passed:
        warn_codes = [i.code for i in issues if i.severity == "warn"]
        logger.info(f"[CRITIC] ✅ pass with warnings: {warn_codes}")
    else:
        fail_codes = [i.code for i in failed]
        retry_str = f" → retry with {retryable_hints}" if should_retry else " → no retry available"
        logger.info(f"[CRITIC] ⚠️  fail: {fail_codes}{retry_str}")

    return CritiqueResult(
        issues=issues,
        passed=passed,
        should_retry=should_retry,
        retry_hints=retryable_hints,
    )


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_mood_valence(top_n: List[Tuple[Dict, float, str]],
                        user_prefs: Dict) -> List[CriticIssue]:
    user_mood = user_prefs.get("favorite_mood", "")
    target_valence = MOOD_VALENCE.get(user_mood, 0.6)
    top1_song = top_n[0][0]
    top1_valence = top1_song["valence"]

    gap = abs(top1_valence - target_valence)
    if gap <= VALENCE_CONFLICT_GAP:
        return []

    return [CriticIssue(
        code="mood_valence_conflict",
        severity="fail",
        message=(
            f"Top result '{top1_song['title']}' has valence={top1_valence:.2f}, "
            f"but mood '{user_mood}' implies target {target_valence:.2f} "
            f"(gap {gap:.2f} exceeds threshold {VALENCE_CONFLICT_GAP})."
        ),
        retryable=True,
        hints={"valence_penalty_weight": VALENCE_PENALTY_WEIGHT},
    )]


def _check_missing_genre(user_prefs: Dict, catalog_genres: set) -> List[CriticIssue]:
    user_genre = user_prefs.get("favorite_genre", "")
    if not catalog_genres:
        return []
    if user_genre in catalog_genres:
        return []

    return [CriticIssue(
        code="missing_genre",
        severity="warn",    # warn, not fail — this isn't the ranker's fault
        message=(
            f"Genre '{user_genre}' is not present in the catalog. "
            f"Recommendations fell back to mood + numeric proximity; "
            f"genre bonus could not fire for any song."
        ),
        retryable=False,
    )]


def _check_acoustic(top_n: List[Tuple[Dict, float, str]],
                    user_prefs: Dict) -> List[CriticIssue]:
    likes_acoustic = user_prefs.get("likes_acoustic", False)
    target = 1.0 if likes_acoustic else 0.0
    top1_acoustic = top_n[0][0]["acousticness"]
    gap = abs(top1_acoustic - target)

    if gap <= ACOUSTIC_VIOLATION_GAP:
        return []

    return [CriticIssue(
        code="acoustic_violation",
        severity="fail",
        message=(
            f"User likes_acoustic={likes_acoustic} but top result "
            f"'{top_n[0][0]['title']}' has acousticness={top1_acoustic:.2f} "
            f"(gap {gap:.2f} from target {target})."
        ),
        retryable=True,
        hints={"acoustic_filter": ACOUSTIC_FILTER_THRESHOLD,
               "acoustic_filter_side": "high" if likes_acoustic else "low"},
    )]


def _check_diversity(top_n: List[Tuple[Dict, float, str]]) -> List[CriticIssue]:
    genres = [item[0]["genre"] for item in top_n]
    if not genres:
        return []
    dominant = max(set(genres), key=genres.count)
    count = genres.count(dominant)

    if count < DIVERSITY_DOMINANT_COUNT:
        return []

    return [CriticIssue(
        code="low_diversity",
        severity="fail",
        message=(
            f"Top 5 dominated by genre '{dominant}' ({count}/5). "
            f"User may want more variety."
        ),
        retryable=True,
        hints={"diversity_penalty_weight": DIVERSITY_PENALTY_WEIGHT},
    )]


# ---------------------------------------------------------------------------
# Public API: rerank_with_hints
# ---------------------------------------------------------------------------

def rerank_with_hints(ranked: List[Tuple[Dict, float, str]],
                      user_prefs: Dict,
                      hints: Dict,
                      k: int = 5) -> List[Tuple[Dict, float, str]]:
    """
    Apply the Critic's retry hints to rerank the full ranked list.

    Args:
        ranked: full ranked list (longer than k so we have candidates to promote)
        hints: the `retry_hints` dict from CritiqueResult
        k: number to return

    Returns a new top-k ranking.
    """
    logger.info(f"[CRITIC] reranking {len(ranked)} candidates with hints={hints}")

    # 1. Optional hard filter (acoustic)
    candidates = list(ranked)
    if "acoustic_filter" in hints:
        threshold = hints["acoustic_filter"]
        side = hints["acoustic_filter_side"]
        before = len(candidates)
        if side == "high":
            candidates = [c for c in candidates if c[0]["acousticness"] >= threshold]
        else:
            candidates = [c for c in candidates if c[0]["acousticness"] <= threshold]
        logger.info(
            f"[CRITIC] acoustic filter ({side}>={threshold}): "
            f"{before} → {len(candidates)} candidates"
        )
        if not candidates:
            # Filter eliminated everyone; fall back to original ranking
            logger.warning("[CRITIC] filter would eliminate all candidates; keeping original")
            candidates = list(ranked)

    # 2. Apply per-song penalties (valence, then diversity greedy)
    penalty_weight_v = hints.get("valence_penalty_weight", 0.0)
    target_valence = MOOD_VALENCE.get(user_prefs.get("favorite_mood", ""), 0.6)

    rescored: List[Tuple[Dict, float, str]] = []
    for song, base_score, reasons in candidates:
        new_score = base_score
        if penalty_weight_v:
            diff = abs(song["valence"] - target_valence)
            new_score -= diff * penalty_weight_v
        rescored.append((song, new_score, reasons))

    # First-pass sort by the penalty-adjusted score
    rescored.sort(key=lambda x: x[1], reverse=True)

    # 3. Diversity penalty — applied greedily in final selection pass
    penalty_weight_d = hints.get("diversity_penalty_weight", 0.0)
    if penalty_weight_d:
        picked: List[Tuple[Dict, float, str]] = []
        genre_counts: Dict[str, int] = {}

        remaining = list(rescored)
        while remaining and len(picked) < k:
            # Recompute "effective score" for each remaining candidate given what's already picked
            best_idx = 0
            best_eff = remaining[0][1] - penalty_weight_d * genre_counts.get(remaining[0][0]["genre"], 0)
            for i in range(1, len(remaining)):
                eff = remaining[i][1] - penalty_weight_d * genre_counts.get(remaining[i][0]["genre"], 0)
                if eff > best_eff:
                    best_eff = eff
                    best_idx = i
            chosen = remaining.pop(best_idx)
            picked.append(chosen)
            genre_counts[chosen[0]["genre"]] = genre_counts.get(chosen[0]["genre"], 0) + 1
        return picked

    return rescored[:k]


# ---------------------------------------------------------------------------
# Smoke test — reproduces adversarial profiles D/E/F and shows critic in action
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from src.recommender import load_songs, recommend_songs

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    songs = load_songs("data/songs.csv")
    catalog_genres = {s["genre"] for s in songs}

    PROFILES = [
        ("D — sad but energetic (mood-valence conflict)", {
            "favorite_genre": "edm", "favorite_mood": "sad",
            "target_energy": 0.9, "likes_acoustic": False,
        }),
        ("E — country (missing genre)", {
            "favorite_genre": "country", "favorite_mood": "relaxed",
            "target_energy": 0.38, "likes_acoustic": True,
        }),
        ("F — acoustic rocker (acoustic violation)", {
            "favorite_genre": "rock", "favorite_mood": "intense",
            "target_energy": 0.9, "likes_acoustic": True,
        }),
    ]

    for label, prefs in PROFILES:
        print("\n" + "=" * 72)
        print(f"  Profile {label}")
        print("=" * 72)

        # Request more candidates than we display, so rerank has room to work
        candidates = recommend_songs(prefs, songs, k=len(songs))
        top5 = candidates[:5]

        print("\n  BEFORE critic — baseline top 5:")
        for i, (s, sc, _) in enumerate(top5, 1):
            print(f"    {i}. {s['title']:<24s} ({s['genre']:<10s} / {s['mood']:<12s}) "
                  f"score={sc:.2f} valence={s['valence']:.2f} acoustic={s['acousticness']:.2f}")

        verdict = critique(top5, prefs, catalog_genres)
        print(f"\n  CRITIC:")
        for issue in verdict.issues:
            icon = "⚠️ " if issue.severity == "fail" else "ℹ️ "
            print(f"    {icon}[{issue.severity}] {issue.code}: {issue.message}")

        if verdict.should_retry:
            reranked = rerank_with_hints(candidates, prefs, verdict.retry_hints, k=5)
            print("\n  AFTER retry — reranked top 5:")
            for i, (s, sc, _) in enumerate(reranked, 1):
                print(f"    {i}. {s['title']:<24s} ({s['genre']:<10s} / {s['mood']:<12s}) "
                      f"score={sc:.2f} valence={s['valence']:.2f} acoustic={s['acousticness']:.2f}")

            # Re-critique the reranked result as a sanity check
            second_verdict = critique(reranked, prefs, catalog_genres)
            print(f"\n  SECOND CRITIC PASS: passed={second_verdict.passed} "
                  f"(issues: {[i.code for i in second_verdict.issues] or 'none'})")
        elif not verdict.passed:
            print("\n  (no retry — issue is not retryable; would surface warning to user)")