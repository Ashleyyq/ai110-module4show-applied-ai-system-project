"""
parser.py — Module 4 Extension

Stage 1 of the agentic chain. Converts user input (structured dict OR free-form
English string) into a validated preference dict that the Module 3 baseline
scorer can consume.

Implements input guardrails (required Reliability component):
  - energy ∈ [0,1]
  - mood in known vocabulary
  - genre in catalog (soft warning — scorer can still run in fallback mode)
  - required fields present for structured input

Emits [PARSER] log lines so the agent's reasoning is observable in output
(Agentic Workflow Enhancement stretch criterion 2).
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

logger = logging.getLogger(__name__)


# Known moods — kept in sync with recommender.MOOD_VALENCE
KNOWN_MOODS = {
    "happy", "chill", "focused", "relaxed", "intense", "moody",
    "energetic", "melancholic", "romantic", "angry", "nostalgic",
    "euphoric", "sad", "uplifting",
}

# ---------------------------------------------------------------------------
# Natural-language keyword maps (rule-based NLU)
# ---------------------------------------------------------------------------

NL_MOOD_KEYWORDS: Dict[str, str] = {
    "chill": "chill", "calm": "chill",
    "relax": "relaxed", "relaxed": "relaxed",
    "study": "focused", "focus": "focused", "focused": "focused", "working": "focused",
    "sad": "sad", "down": "sad", "heartbroken": "sad",
    "happy": "happy", "upbeat": "happy", "joyful": "happy", "cheerful": "happy",
    "intense": "intense",
    "energetic": "energetic", "workout": "energetic", "gym": "energetic",
    "party": "euphoric", "euphoric": "euphoric",
    "angry": "angry", "mad": "angry",
    "moody": "moody",
    "nostalgic": "nostalgic",
    "romantic": "romantic",
    "melancholic": "melancholic", "melancholy": "melancholic",
    "uplifting": "uplifting",
}

NL_ENERGY_KEYWORDS: Dict[str, float] = {
    "low": 0.25, "quiet": 0.25, "slow": 0.30,
    "mellow": 0.35, "chill": 0.35, "calm": 0.30,
    "medium": 0.55,
    "upbeat": 0.75,
    "energetic": 0.85, "intense": 0.90, "pumped": 0.92,
    "workout": 0.88, "gym": 0.88, "high": 0.88,
}

NL_GENRE_KEYWORDS: Dict[str, str] = {
    "pop": "pop",
    "rock": "rock",
    "lofi": "lofi", "lo-fi": "lofi",
    "ambient": "ambient",
    "jazz": "jazz",
    "synthwave": "synthwave",
    "hip-hop": "hip-hop", "hiphop": "hip-hop", "rap": "hip-hop",
    "classical": "classical",
    "r&b": "r&b", "rnb": "r&b",
    "metal": "metal",
    "folk": "folk",
    "edm": "edm", "electronic": "edm", "dance": "edm",
    "soul": "soul",
    "reggae": "reggae",
    "indie": "indie pop",
    "country": "country",  # not in catalog — intentional, triggers warning
}

# Multi-word genre phrases checked before single-token loop
NL_GENRE_PHRASES: List[tuple] = [
    ("indie pop", "indie pop"),
    ("hip hop", "hip-hop"),
    ("hip-hop", "hip-hop"),
]

NL_ACOUSTIC_YES = {"acoustic", "unplugged", "organic"}
NL_ACOUSTIC_NO = {"electronic", "electric", "synth", "digital"}


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
    """Structured output of parsing, including validation metadata."""
    prefs: Dict
    is_valid: bool
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    raw_input: Union[Dict, str, None] = None
    source: str = "structured"   # "structured" or "nl"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse(user_input: Union[Dict, str],
          catalog_genres: Optional[set] = None) -> ParseResult:
    """
    Parse user input into a validated ParseResult.

    Args:
        user_input: either a prefs dict (same shape as Module 3's UserProfile)
                    or a free-form English string query.
        catalog_genres: set of genres present in songs.csv, used for
                        genre-in-catalog warnings. If None, that check is
                        skipped.
    """
    if catalog_genres is None:
        catalog_genres = set()

    if isinstance(user_input, dict):
        return _parse_structured(user_input, catalog_genres)
    if isinstance(user_input, str):
        return _parse_natural_language(user_input, catalog_genres)

    return ParseResult(
        prefs={},
        is_valid=False,
        errors=[f"Unsupported input type: {type(user_input).__name__}"],
        raw_input=user_input,
    )


def build_catalog_genres(songs: List[Dict]) -> set:
    """Extract the set of unique genres actually present in the catalog."""
    return {s["genre"] for s in songs}


# ---------------------------------------------------------------------------
# Internal — structured input
# ---------------------------------------------------------------------------

def _parse_structured(prefs_dict: Dict, catalog_genres: set) -> ParseResult:
    result = ParseResult(prefs={}, is_valid=True,
                         raw_input=prefs_dict, source="structured")

    # Required fields
    required = {"favorite_genre", "favorite_mood", "target_energy", "likes_acoustic"}
    missing = required - set(prefs_dict.keys())
    if missing:
        result.errors.append(f"Missing required fields: {sorted(missing)}")
        result.is_valid = False
        logger.warning(f"[PARSER] rejected structured input: {result.errors[-1]}")
        return result

    # Hard guardrail: energy in [0,1]
    energy = prefs_dict["target_energy"]
    if not isinstance(energy, (int, float)) or not (0.0 <= energy <= 1.0):
        result.errors.append(
            f"target_energy must be a number in [0,1], got {energy!r}"
        )
        result.is_valid = False

    # Hard guardrail: likes_acoustic is bool
    if not isinstance(prefs_dict["likes_acoustic"], bool):
        result.errors.append(
            f"likes_acoustic must be bool, got "
            f"{type(prefs_dict['likes_acoustic']).__name__}"
        )
        result.is_valid = False

    # Soft: unknown mood → scorer will fall back to default valence 0.6
    mood = prefs_dict["favorite_mood"]
    if mood not in KNOWN_MOODS:
        result.warnings.append(
            f"Mood '{mood}' not in known vocabulary; valence target will default to 0.6."
        )

    # Soft: genre not in catalog → scorer runs but genre bonus never fires
    genre = prefs_dict["favorite_genre"]
    if catalog_genres and genre not in catalog_genres:
        result.warnings.append(
            f"Genre '{genre}' not in catalog; genre bonus will not apply. "
            f"Recommendations will fall back to mood + numeric proximity."
        )

    if result.is_valid:
        result.prefs = dict(prefs_dict)

    logger.info(
        f"[PARSER] structured → genre={genre!r} mood={mood!r} "
        f"energy={energy} acoustic={prefs_dict['likes_acoustic']} "
        f"| valid={result.is_valid} warnings={len(result.warnings)} errors={len(result.errors)}"
    )
    return result


# ---------------------------------------------------------------------------
# Internal — natural-language input
# ---------------------------------------------------------------------------

def _parse_natural_language(query: str, catalog_genres: set) -> ParseResult:
    query_lower = query.lower().strip()
    tokens = re.findall(r"[\w&-]+", query_lower)

    prefs = {
        "favorite_genre": None,
        "favorite_mood": None,
        "target_energy": 0.5,
        "likes_acoustic": False,
    }
    warnings: List[str] = []
    errors: List[str] = []

    # Genre — check multi-word phrases before single tokens
    detected_genre = None
    for phrase, canonical in NL_GENRE_PHRASES:
        if phrase in query_lower:
            detected_genre = canonical
            break
    if detected_genre is None:
        for tok in tokens:
            if tok in NL_GENRE_KEYWORDS:
                detected_genre = NL_GENRE_KEYWORDS[tok]
                break
    prefs["favorite_genre"] = detected_genre

    # Mood — first match wins
    for tok in tokens:
        if tok in NL_MOOD_KEYWORDS:
            prefs["favorite_mood"] = NL_MOOD_KEYWORDS[tok]
            break

    # Energy — take the most extreme explicit hint, or infer from mood
    energy_hints = [NL_ENERGY_KEYWORDS[tok]
                    for tok in tokens if tok in NL_ENERGY_KEYWORDS]
    if energy_hints:
        prefs["target_energy"] = max(energy_hints, key=lambda e: abs(e - 0.5))
    elif prefs["favorite_mood"]:
        MOOD_ENERGY_DEFAULT = {
            "chill": 0.35, "relaxed": 0.35, "melancholic": 0.30, "sad": 0.35,
            "focused": 0.40, "nostalgic": 0.35, "moody": 0.60, "romantic": 0.55,
            "happy": 0.75, "uplifting": 0.70, "intense": 0.85, "angry": 0.88,
            "energetic": 0.85, "euphoric": 0.90,
        }
        prefs["target_energy"] = MOOD_ENERGY_DEFAULT.get(prefs["favorite_mood"], 0.5)

    # Acoustic
    if any(tok in NL_ACOUSTIC_YES for tok in tokens):
        prefs["likes_acoustic"] = True
    elif any(tok in NL_ACOUSTIC_NO for tok in tokens):
        prefs["likes_acoustic"] = False

    # Hard error: need at least a genre or a mood to give the scorer something
    # categorical to work with
    if prefs["favorite_genre"] is None and prefs["favorite_mood"] is None:
        errors.append(
            f"Could not extract a recognizable genre or mood from: {query!r}. "
            f"Try phrasing like 'chill lofi for studying' or 'high-energy rock'."
        )

    # Soft: genre not in catalog
    if (prefs["favorite_genre"]
            and catalog_genres
            and prefs["favorite_genre"] not in catalog_genres):
        warnings.append(
            f"Detected genre '{prefs['favorite_genre']}' not in catalog; "
            f"scoring will fall back to mood + numeric proximity."
        )

    # Fill safe sentinels so downstream scorer doesn't crash on None
    if not errors:
        prefs["favorite_genre"] = prefs["favorite_genre"] or "unknown"
        prefs["favorite_mood"] = prefs["favorite_mood"] or "chill"

    result = ParseResult(
        prefs=prefs,
        is_valid=not errors,
        warnings=warnings,
        errors=errors,
        raw_input=query,
        source="nl",
    )

    logger.info(
        f"[PARSER] nl {query!r} → genre={prefs['favorite_genre']!r} "
        f"mood={prefs['favorite_mood']!r} energy={prefs['target_energy']} "
        f"acoustic={prefs['likes_acoustic']} "
        f"| valid={result.is_valid} warnings={len(warnings)} errors={len(errors)}"
    )
    return result


# ---------------------------------------------------------------------------
# Smoke test — lets you sanity-check the parser in isolation
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    catalog = {"pop", "lofi", "rock", "ambient", "jazz", "synthwave",
               "hip-hop", "classical", "r&b", "metal", "folk", "edm",
               "soul", "reggae", "indie pop"}

    test_cases = [
        # Structured inputs
        {"favorite_genre": "lofi", "favorite_mood": "chill",
         "target_energy": 0.38, "likes_acoustic": True},
        {"favorite_genre": "country", "favorite_mood": "relaxed",
         "target_energy": 0.38, "likes_acoustic": True},          # warning
        {"favorite_genre": "pop", "favorite_mood": "happy",
         "target_energy": 1.5, "likes_acoustic": False},           # hard error
        # Natural language
        "chill lofi for studying",
        "high-energy rock for the gym",
        "acoustic folk that sounds nostalgic",
        "gibberish with no musical words",                          # hard error
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n--- test {i}: {case!r}")
        r = parse(case, catalog_genres=catalog)
        print(f"    is_valid={r.is_valid}")
        print(f"    prefs   ={r.prefs}")
        if r.warnings: print(f"    warnings={r.warnings}")
        if r.errors:   print(f"    errors  ={r.errors}")