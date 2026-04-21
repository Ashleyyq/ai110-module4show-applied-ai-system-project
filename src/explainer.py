"""
explainer.py — Module 4 Extension

Stage 3 of the agentic chain. Converts a ranked list of recommendations into
prose explanations.

Two modes, deliberately both present:
  - use_rag=True  : pulls song_notes (from songs.csv) and mood guide
                    (from mood_guides.csv) to enrich the explanation with
                    human-authored context.
  - use_rag=False : uses only the structured columns (genre, mood, energy),
                    producing a template-only "baseline" explanation.

Keeping both modes is a design choice driven by the RAG Enhancement stretch's
"measurable improvement" criterion. `evaluate.py` runs both and compares
explanation length, vocabulary diversity, and specific-reference rate to
demonstrate that the custom RAG documents materially change output quality.
"""
import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RAG data loader
# ---------------------------------------------------------------------------

def load_mood_guides(csv_path: str) -> Dict[str, str]:
    """
    Load mood_guides.csv into a {mood: guide_text} dict.

    This is our second RAG source (the first being the song_notes column
    already in songs.csv). Two independent sources = multi-source retrieval.
    """
    guides: Dict[str, str] = {}
    path = Path(csv_path)
    if not path.exists():
        logger.warning(f"[EXPLAINER] mood guide file not found: {csv_path}")
        return guides

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            guides[row["mood"]] = row["guide"]
    logger.info(f"[EXPLAINER] loaded {len(guides)} mood guides from {csv_path}")
    return guides


# ---------------------------------------------------------------------------
# Core explanation builder
# ---------------------------------------------------------------------------

def explain(song: Dict,
            score: float,
            user_prefs: Dict,
            mood_guides: Optional[Dict[str, str]] = None,
            use_rag: bool = True) -> str:
    """
    Build a prose explanation for a single recommendation.

    Both modes share the same structural template (opening + match summary
    + energy comment) so the measurable delta between them is cleanly
    attributable to the two RAG injections.
    """
    title = song["title"]
    artist = song["artist"]
    genre = song["genre"]
    mood = song["mood"]
    energy = song["energy"]

    user_genre = user_prefs.get("favorite_genre", "?")
    user_mood = user_prefs.get("favorite_mood", "?")
    target_energy = user_prefs.get("target_energy", 0.5)

    genre_match = (genre == user_genre)
    mood_match = (mood == user_mood)

    parts: List[str] = []

    # 1. Opening — always present
    parts.append(f"'{title}' by {artist} (score {score:.2f}/9.0).")

    # 2. RAG injection — song_notes
    if use_rag:
        notes = (song.get("song_notes") or "").strip()
        if notes:
            parts.append(notes)
        else:
            logger.debug(f"[EXPLAINER] song {title!r} has no song_notes; RAG injection skipped for this field")

    # 3. RAG injection — mood guide
    if use_rag and mood_guides and user_mood in mood_guides:
        parts.append(f"The '{user_mood}' mood family: {mood_guides[user_mood]}")

    # 4. Categorical match summary — always present, phrased by case
    if genre_match and mood_match:
        parts.append(f"Both genre ({genre}) and mood ({mood}) align with your preferences.")
    elif genre_match:
        parts.append(f"Genre matches ({genre}); the mood is {mood} rather than your preferred {user_mood}.")
    elif mood_match:
        parts.append(f"Mood matches ({mood}); the genre is {genre} rather than your preferred {user_genre}.")
    else:
        parts.append(
            f"Neither genre ({genre}) nor mood ({mood}) is an exact match with your preferences "
            f"({user_genre} / {user_mood}); this song was ranked via numeric proximity only."
        )

    # 5. Energy proximity comment — always present
    energy_diff = abs(energy - target_energy)
    if energy_diff < 0.1:
        parts.append(f"Energy ({energy}) is very close to your target ({target_energy}).")
    elif energy_diff < 0.3:
        parts.append(f"Energy ({energy}) is within range of your target ({target_energy}).")
    else:
        parts.append(f"Energy ({energy}) is notably different from your target ({target_energy}).")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Batch API
# ---------------------------------------------------------------------------

def explain_all(ranked: List[Tuple[Dict, float, str]],
                user_prefs: Dict,
                mood_guides: Optional[Dict[str, str]] = None,
                use_rag: bool = True
                ) -> List[Tuple[Dict, float, str, str]]:
    """
    Generate explanations for a whole ranked list.

    Input: the output of recommender.recommend_songs(), which is a list of
    (song, score, raw_reasons_string) tuples.

    Output: (song, score, raw_reasons, prose_explanation) tuples. The raw
    Module 3 reason string is preserved unchanged for transparency — the
    prose explanation is additive, not a replacement.
    """
    logger.info(
        f"[EXPLAINER] generating {len(ranked)} explanations "
        f"(mode={'rag' if use_rag else 'baseline'})"
    )
    out: List[Tuple[Dict, float, str, str]] = []
    for song, score, raw_reasons in ranked:
        prose = explain(song, score, user_prefs, mood_guides, use_rag=use_rag)
        out.append((song, score, raw_reasons, prose))
    return out


# ---------------------------------------------------------------------------
# Smoke test — compares baseline vs RAG side by side
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import os
    # allow running this file directly from project root
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from src.recommender import load_songs, recommend_songs

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    songs = load_songs("data/songs.csv")
    guides = load_mood_guides("data/mood_guides.csv")

    # Use Profile B (chill lofi) — it's the cleanest case where we'd expect
    # the RAG version to read much richer than the baseline.
    user_prefs = {
        "favorite_genre": "lofi",
        "favorite_mood": "chill",
        "target_energy": 0.38,
        "likes_acoustic": True,
    }

    ranked = recommend_songs(user_prefs, songs, k=3)

    print("\n" + "=" * 70)
    print("  BASELINE EXPLANATIONS (use_rag=False)")
    print("=" * 70)
    baseline = explain_all(ranked, user_prefs, mood_guides=guides, use_rag=False)
    for i, (song, score, _, prose) in enumerate(baseline, 1):
        words = len(prose.split())
        unique = len(set(prose.lower().split()))
        print(f"\n  #{i} — {words} words, {unique} unique tokens")
        print(f"  {prose}")

    print("\n" + "=" * 70)
    print("  RAG-ENHANCED EXPLANATIONS (use_rag=True)")
    print("=" * 70)
    rag = explain_all(ranked, user_prefs, mood_guides=guides, use_rag=True)
    for i, (song, score, _, prose) in enumerate(rag, 1):
        words = len(prose.split())
        unique = len(set(prose.lower().split()))
        print(f"\n  #{i} — {words} words, {unique} unique tokens")
        print(f"  {prose}")

    # Quick aggregate comparison — the basis for evaluate.py's RAG metric
    print("\n" + "=" * 70)
    print("  AGGREGATE COMPARISON")
    print("=" * 70)
    b_words = sum(len(p.split()) for _, _, _, p in baseline)
    r_words = sum(len(p.split()) for _, _, _, p in rag)
    b_unique = len(set(w.lower() for _, _, _, p in baseline for w in p.split()))
    r_unique = len(set(w.lower() for _, _, _, p in rag for w in p.split()))
    print(f"  Avg explanation length : baseline={b_words/len(baseline):.1f} words  "
          f"→  rag={r_words/len(rag):.1f} words  "
          f"(+{(r_words - b_words)/b_words*100:.0f}%)")
    print(f"  Total unique vocabulary: baseline={b_unique}  "
          f"→  rag={r_unique}  "
          f"(+{(r_unique - b_unique)/b_unique*100:.0f}%)")