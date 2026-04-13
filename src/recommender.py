import csv
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

# Valence targets inferred from mood labels, grounded in actual song values in the dataset.
# Used by score_song to compute valence proximity when the user has no explicit valence target.
MOOD_VALENCE: Dict[str, float] = {
    "happy":       0.80,
    "chill":       0.60,
    "focused":     0.55,
    "relaxed":     0.65,
    "intense":     0.60,
    "moody":       0.45,
    "energetic":   0.72,
    "melancholic": 0.35,
    "romantic":    0.74,
    "angry":       0.22,
    "nostalgic":   0.58,
    "euphoric":    0.82,
    "sad":         0.28,
    "uplifting":   0.88,
}

@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float

@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool

class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """
    def __init__(self, songs: List[Song]):
        self.songs = songs

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        """Return the top-k songs for this user, sorted by score descending."""
        # TODO: Implement recommendation logic
        return self.songs[:k]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        """Return a plain-language string explaining why this song was recommended."""
        # TODO: Implement explanation logic
        return "Explanation placeholder"

def score_song(user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
    """Score one song against user preferences and return (score, reasons) out of 9.0."""
    score = 0.0
    reasons = []

    # --- Layer 1: Categorical matches ---

    if song["genre"] == user_prefs.get("favorite_genre", ""):
        pts = 3.0
        score += pts
        reasons.append(f"genre match: {song['genre']} (+{pts})")

    if song["mood"] == user_prefs.get("favorite_mood", ""):
        pts = 2.0
        score += pts
        reasons.append(f"mood match: {song['mood']} (+{pts})")

    # --- Layer 2: Numeric proximity ---

    # Energy — weight 2.0 (widest spread in dataset, most discriminating)
    target_energy = user_prefs.get("target_energy", 0.5)
    energy_pts = round((1 - abs(song["energy"] - target_energy)) * 2.0, 2)
    score += energy_pts
    reasons.append(
        f"energy: {song['energy']} vs target {target_energy} (+{energy_pts})"
    )

    # Acousticness — weight 1.0 (maps to likes_acoustic boolean)
    acoustic_target = 1.0 if user_prefs.get("likes_acoustic", False) else 0.0
    acoustic_pts = round((1 - abs(song["acousticness"] - acoustic_target)) * 1.0, 2)
    score += acoustic_pts
    reasons.append(
        f"acousticness: {song['acousticness']} vs target {acoustic_target} (+{acoustic_pts})"
    )

    # Valence — weight 1.0 (inferred from favorite_mood)
    target_valence = MOOD_VALENCE.get(user_prefs.get("favorite_mood", ""), 0.6)
    valence_pts = round((1 - abs(song["valence"] - target_valence)) * 1.0, 2)
    score += valence_pts
    reasons.append(
        f"valence: {song['valence']} vs mood target {target_valence} (+{valence_pts})"
    )

    return round(score, 3), reasons


def load_songs(csv_path: str) -> List[Dict]:
    """Read songs.csv and return a list of dicts with correctly typed numeric fields."""
    songs = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            songs.append({
                "id":           int(row["id"]),
                "title":        row["title"],
                "artist":       row["artist"],
                "genre":        row["genre"],
                "mood":         row["mood"],
                "energy":       float(row["energy"]),
                "tempo_bpm":    float(row["tempo_bpm"]),
                "valence":      float(row["valence"]),
                "danceability": float(row["danceability"]),
                "acousticness": float(row["acousticness"]),
            })
    return songs

def score_song(user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
    """
    Scores a single song against user preferences.
    Required by recommend_songs() and src/main.py
    """
    # TODO: Implement scoring logic using your Algorithm Recipe from Phase 2.
    # Expected return format: (score, reasons)
    return []

def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5) -> List[Tuple[Dict, float, str]]:
    """Score all songs, rank them highest to lowest, and return the top k as (song, score, explanation) tuples."""
    # Step 1: judge every song
    scored = []
    for song in songs:
        score, reasons = score_song(user_prefs, song)
        explanation = " | ".join(reasons)
        scored.append((song, score, explanation))

    # Step 2: rank — sorted() returns a new list, leaving the original unchanged
    ranked = sorted(scored, key=lambda item: item[1], reverse=True)

    # Step 3: slice to top k
    return ranked[:k]
