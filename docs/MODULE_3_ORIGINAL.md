# 🎵 Music Recommender Simulation (Module 3 / VibeFinder 1.0)

> **Preserved historical documentation.** This was my Module 3 project README. I'm keeping it here, in full, so the Module 4 final project has a clear record of the base project it extends. The top-level [`README.md`](../README.md) describes Module 4; this file describes only the original Module 3 content.
>
> Image paths have been updated to point to `module_3_screenshots/`, and the model-card link has been removed (a new Module 4 `model_card.md` lives at the repo root). Everything else is as I originally wrote it for Module 3.

---

## Project Summary

VibeFinder 1.0 is a content-based music recommender that scores each song in an 18-song catalog against a user taste profile and returns the top 5 matches with a plain-language explanation. The user profile stores four preferences: favorite genre, favorite mood, target energy level, and whether they like acoustic music. Each song is scored out of 9.0 using a two-layer formula: exact genre and mood matches earn flat bonuses (genre +3.0, mood +2.0), while energy, acousticness, and valence are scored by proximity to the user's target. Songs are then sorted from highest to lowest and the top 5 are returned.

---

## How The System Works

Real-world recommenders like Spotify actually use two big approaches: collaborative filtering, which looks at what other users with similar taste are listening to, and content-based filtering, which looks at the song itself, things like how energetic it is, what genre it belongs to, or how "happy" it sounds. Spotify actually combines both, but for this project I focused on content-based filtering because it is easier to reason about and does not require data from other users.

**What features does each Song use in the system**

My `Song` objects use five features: `genre` (e.g. pop, lofi, rock), `mood` (e.g. happy, chill, intense), `energy` (a float from 0.0 to 1.0 measuring intensity), `acousticness` (how acoustic vs. electronic the track is), and `valence` (how musically positive or happy it sounds). I left out `tempo_bpm` and `danceability` because they turned out to be redundant with energy for this small dataset.

**What information the UserProfile stores**

The `UserProfile` stores four things: `favorite_genre`, `favorite_mood`, `target_energy` (a float representing the energy level the user wants), and `likes_acoustic` (a boolean for whether they prefer acoustic music). These map directly to the song features so the scorer can compare them one-to-one.

**How the Recommender computes a score for each song**

The scorer gives each song a number out of 9.0. Genre and mood matches give flat bonuses (genre is worth more at 3.0 vs. mood at 2.0, because a wrong genre feels the most "off" no matter what). The three numeric features use a proximity formula `1 - |song value - user target|` so songs closer to the user's preference always score higher, not songs that are simply louder or faster. Energy is weighted at 2.0 since it has the widest spread in the dataset; acousticness and valence are each weighted at 1.0 as tiebreakers.

**How songs are chosen for the final list**

Once every song has a score, the ranking step sorts the full list from highest to lowest and returns the top k results. I kept scoring and ranking as two separate steps on purpose. The scorer only looks at one song at a time and produces a number, while the ranker sees the whole list and decides what to actually show the user.

See [flowchart.md](flowchart.md) for the full data flow diagram (Input → Process → Output).

---

## Finalized Algorithm Recipe

Every song gets a score out of **9.0 points**, calculated in two layers.

**Layer 1: Categorical matches (max 5.0)**

| Signal | Points | Why this weight |
|--------|--------|-----------------|
| Genre matches user's favorite genre | +3.0 | A wrong genre feels broken regardless of how well other features match, so it gets the highest weight |
| Mood matches user's favorite mood | +2.0 | Same genre can serve very different moments; mood captures context genre alone can't |

**Layer 2: Numeric proximity (max 4.0)**

Each feature uses the formula `(1 - |song value - user target|) × weight`, so songs closer to the user's preference always score higher, not songs that are simply louder or faster.

| Signal | Weight | Max pts | Why this weight |
|--------|--------|---------|-----------------|
| Energy proximity | ×2.0 | 2.0 | Widest spread in the dataset (0.22 to 0.97); most discriminating numeric feature |
| Acousticness proximity | ×1.0 | 1.0 | Maps directly to the `likes_acoustic` boolean in the user profile |
| Valence proximity | ×1.0 | 1.0 | Most emotionally independent signal; inferred from the user's favorite mood |

A song that matches both genre and mood starts with 5.0 points before any numeric scoring, meaning a wrong-genre song can never outscore a correct-genre song purely through numeric similarity (max 4.0). This was a deliberate design choice.

---

## Potential Biases

- **Genre over-prioritization.** Because genre carries 3.0 points, a song from the right genre will almost always outrank a song from a different genre, even if the other song matches the user's mood, energy, and acousticness perfectly. A great ambient song could be invisible to a pop user even if it fits their energy target exactly.

- **Mood-valence inference is imprecise.** Valence is inferred from the user's favorite mood using a fixed lookup table rather than being set explicitly. For moods like "intense" where Storm Runner (valence 0.48) and Gym Hero (valence 0.77) are both valid but feel emotionally very different, the inferred target (0.60) splits the difference and treats both songs as roughly equal, which may not match what the user actually wants.

- **No history or feedback.** The system treats every session identically. It has no memory of what the user has already heard, skipped, or loved. A song that scored highly last time will score the same way every time, even if the user is tired of it.

- **Small catalog amplifies errors.** With only 18 songs, a single wrong weight can put the wrong song at rank 1. In a real system with thousands of songs, a slightly miscalibrated weight averages out; here it does not.

---

## Getting Started (Module 3 baseline)

### Setup

1. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Mac or Linux
   .venv\Scripts\activate         # Windows
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run the app:

   ```bash
   python -m src.main
   ```

### Running Tests

Run the starter tests with:

```bash
pytest
```

You can add more tests in `tests/test_recommender.py`.

---

## Experiments I Tried

- **Changing the weight on genre from 3.0 to 0.5.** I cut the genre bonus from 3.0 to 1.5 and doubled the energy weight from 2.0 to 4.0 to see if numeric features could beat genre dominance. The rankings barely changed. Storm Runner was still number one for the rock fan and Library Rain was still number one for the lofi listener. The problem is not the weights. The real issue is that only one rock song and one lofi song exist in the catalog, so there is nothing for the numeric features to separate inside a genre.

- **Adding tempo or valence to the score.** I added valence (weight 1.0, inferred from mood via a lookup table) and acousticness (weight 1.0) to the scoring. This changed individual scores slightly but rarely changed the rank order, because the genre and mood bonuses together are still large enough to dominate when they both match. Valence was the more interesting addition because it helped expose the sad EDM bias where the system recommended a euphoric song to a user who wanted sad music.

- **How the system behaves for different types of users.** Standard profiles worked well. The lofi listener got three lofi songs at the top and the pop dancer got the only pop plus happy song at number one. Adversarial profiles showed the limits. The sad EDM user got a euphoric song as the top result because genre matched. The country fan found no genre matches but the fallback to mood and energy still gave reasonable results. The acoustic rocker kept getting Storm Runner at number one because the genre and mood bonuses were too high for the acousticness preference to override.

### Sample Output, pop/happy profile

Running `python -m src.main` with the `pop_dancer` profile (genre=pop, mood=happy, energy=0.85, acoustic=no):

![Terminal output showing top 5 recommendations for a pop/happy user profile](module_3_screenshots/Screenshot%202026-04-12%20at%2010.26.30%E2%80%AFPM.png)

The results match expectations:
- **#1 Sunrise City**: only song with both genre (`pop`) and mood (`happy`) matching, scores 8.72 / 9.0
- **#2 Gym Hero**: genre matches (`pop`) but mood is `intense` not `happy`, drops to 6.76
- **#3 Rooftop Lights**: mood matches (`happy`) but genre is `indie pop` not `pop`, sits at 5.46, confirming genre (weight 3.0) outranks mood (weight 2.0) as designed
- **#4 and #5**: no categorical matches at all, ranked purely by energy and acousticness proximity

---

### Stress Test, All 6 Profiles

Running `python -m src.main` with `RUN_ALL = True` executes three standard and three adversarial profiles back to back.

---

#### Profile A, High-Energy Rock Fan (Standard)

`genre=rock | mood=intense | energy=0.88 | acoustic=no`

![Profile A terminal output](module_3_screenshots/Screenshot%202026-04-12%20at%2010.37.07%E2%80%AFPM.png)

Storm Runner scores 8.72, the only song with both genre and mood matching. Gym Hero (#2, 5.68) gains the mood bonus only; no other song comes close to the top.

---

#### Profile B, Chill Lofi Listener (Standard)

`genre=lofi | mood=chill | energy=0.38 | acoustic=yes`

![Profile B terminal output](module_3_screenshots/Screenshot%202026-04-12%20at%2010.37.16%E2%80%AFPM.png)

Three lofi songs fill the top 3 (Library Rain 8.80, Midnight Coding 8.59, Focus Flow 6.73). Spacewalk Thoughts (#4) earns a spot via mood match despite being ambient, showing mood can partially compensate for a genre miss.

---

#### Profile C, Upbeat Pop Dancer (Standard)

`genre=pop | mood=happy | energy=0.85 | acoustic=no`

![Profile C terminal output](module_3_screenshots/Screenshot%202026-04-12%20at%2010.37.26%E2%80%AFPM.png)

Sunrise City wins with 8.72. Gym Hero (#2, 6.76) beats Rooftop Lights (#3, 5.46) because genre match (+3.0) outweighs mood match (+2.0), confirming the weight ratio is working as designed.

---

#### Profile D, Sad but Energetic (Adversarial)

`genre=edm | mood=sad | energy=0.90 | acoustic=no`

![Profile D terminal output](module_3_screenshots/Screenshot%202026-04-12%20at%2010.37.36%E2%80%AFPM.png)

**Bias exposed.** Drop Zone (euphoric EDM, valence 0.82) ranks #1 at 6.31 despite the user wanting `mood=sad`. The genre bonus (+3.0) overwhelms the valence mismatch. The genuinely sad song Empty Chairs only reaches #2 at 4.05, so a sad user gets a euphoric recommendation.

---

#### Profile E, Genre Ghost / Country (Adversarial)

`genre=country | mood=relaxed | energy=0.38 | acoustic=yes`

![Profile E terminal output](module_3_screenshots/Screenshot%202026-04-12%20at%2010.37.45%E2%80%AFPM.png)

No country songs exist in the catalog, so the genre bonus never fires. The system falls back to mood + numeric proximity and surfaces Coffee Shop Stories (jazz, relaxed, 5.81). The fallback behavior is stable even when genre is useless.

---

#### Profile F, Acoustic Rocker (Adversarial)

`genre=rock | mood=intense | energy=0.90 | acoustic=yes`

![Profile F terminal output](module_3_screenshots/Screenshot%202026-04-12%20at%2010.37.52%E2%80%AFPM.png)

**Bias exposed.** Storm Runner still wins at 7.96 despite scoring only 0.10 on acousticness. The genre + mood categorical ceiling (5.0 pts) is too high to be overridden by a contradictory numeric preference; the `likes_acoustic` flag is effectively ignored when both categorical signals match.

---

## Limitations and Risks

- **It only works on a tiny catalog.** The catalog has 18 songs and 13 of the 15 genres have only one song each. This means the genre bonus almost always just picks the one available song in that genre with no variety at all.

- **It does not understand lyrics or language.** The system only looks at numeric attributes like energy and acousticness and categorical labels like genre and mood. It has no idea what a song actually sounds like, what the lyrics say, or what language it is in. Two songs can have the same genre and energy but feel completely different, and the system cannot tell them apart.

- **It might over-favor one genre or mood.** Because genre is worth 3.0 points out of 9.0, a song from the right genre will almost always appear at the top no matter what. In the adversarial testing, a euphoric EDM song ranked number one for a user who wanted sad music purely because the genre matched. The genre bonus is strong enough to override the emotional fit.

---

## Reflection (Module 3)

The most surprising thing I learned is how much a recommender can feel accurate without actually understanding anything. When the lofi listener profile returned three lofi songs in exactly the right order, it genuinely felt like the system knew what that user wanted. But the code is just doing subtraction and comparing numbers. There is no taste, no judgment, and no awareness of what music actually sounds like to a human. That gap between what the output feels like and what is happening inside the code made me realize why it is so easy to over-trust AI systems. They can produce results that seem thoughtful even when the logic underneath is extremely simple.

The biggest lesson about bias came from the adversarial profiles. When a user said their mood was "sad" but their favorite genre was EDM, the system recommended a euphoric dance track because the genre bonus was worth more points than the mood mismatch penalty. The system was not being unfair on purpose; it just could not weigh emotional fit against genre identity the way a human would. That taught me that bias in a recommender does not always come from bad intentions or bad data. Sometimes it comes from a weight being slightly too high, or from a catalog that does not have enough variety to let the right signals win. Small design choices that seem neutral can end up systematically failing certain types of users, and you usually do not notice until you test the edge cases on purpose.
