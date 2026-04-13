"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

from src.recommender import load_songs, recommend_songs


def main() -> None:
    songs = load_songs("data/songs.csv")
    print(f"Loaded songs: {len(songs)}")

    # --- User profiles ---
    # Switch between these to test how the recommender responds to very different users.

    # Profile A: high-energy rock fan — should surface Storm Runner, Iron Collapse
    rock_fan = {
        "favorite_genre":  "rock",
        "favorite_mood":   "intense",
        "target_energy":   0.88,
        "likes_acoustic":  False,
    }

    # Profile B: study-mode lofi listener — should surface Focus Flow, Library Rain, Midnight Coding
    lofi_listener = {
        "favorite_genre":  "lofi",
        "favorite_mood":   "chill",
        "target_energy":   0.38,
        "likes_acoustic":  True,
    }

    # Profile C: upbeat pop dancer — should surface Gym Hero, Sunrise City, Drop Zone
    pop_dancer = {
        "favorite_genre":  "pop",
        "favorite_mood":   "happy",
        "target_energy":   0.85,
        "likes_acoustic":  False,
    }

    # Active profile — change this line to switch users
    user_prefs = pop_dancer

    recommendations = recommend_songs(user_prefs, songs, k=5)

    # --- Output ---
    print(f"\nUser profile: genre={user_prefs['favorite_genre']} | "
          f"mood={user_prefs['favorite_mood']} | "
          f"energy={user_prefs['target_energy']} | "
          f"acoustic={'yes' if user_prefs['likes_acoustic'] else 'no'}")
    print("=" * 60)
    print(f"Top {len(recommendations)} Recommendations")
    print("=" * 60)

    for rank, (song, score, explanation) in enumerate(recommendations, start=1):
        print(f"\n#{rank}  {song['title']}  —  {song['artist']}")
        print(f"    Genre: {song['genre']}  |  Mood: {song['mood']}  |  Score: {score:.2f} / 9.0")
        print(f"    Why:")
        for reason in explanation.split(" | "):
            print(f"      • {reason}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
