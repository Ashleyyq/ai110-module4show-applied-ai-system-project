# 🎵 Music Recommender Simulation

## Project Summary

In this project you will build and explain a small music recommender system.

Your goal is to:

- Represent songs and a user "taste profile" as data
- Design a scoring rule that turns that data into recommendations
- Evaluate what your system gets right and wrong
- Reflect on how this mirrors real world AI recommenders

Replace this paragraph with your own summary of what your version does.

---

## How The System Works

Real-world recommenders like Spotify actually use two big approaches: collaborative filtering, which looks at what other users with similar taste are listening to, and content-based filtering, which looks at the song itself, things like how energetic it is, what genre it belongs to, or how "happy" it sounds. Spotify actually combines both, but for this project I focused on content-based filtering because it is easier to reason about and does not require data from other users.

Explain your design in plain language.

Some prompts to answer:

- What features does each `Song` use in your system
  - For example: genre, mood, energy, tempo
  - My `Song` objects use five features: `genre` (e.g. pop, lofi, rock), `mood` (e.g. happy, chill, intense), `energy` (a float from 0.0 to 1.0 measuring intensity), `acousticness` (how acoustic vs. electronic the track is), and `valence` (how musically positive or happy it sounds). I left out `tempo_bpm` and `danceability` because they turned out to be redundant with energy for this small dataset.

- What information does your `UserProfile` store
  - The `UserProfile` stores four things: `favorite_genre`, `favorite_mood`, `target_energy` (a float representing the energy level the user wants), and `likes_acoustic` (a boolean for whether they prefer acoustic music). These map directly to the song features so the scorer can compare them one-to-one.

- How does your `Recommender` compute a score for each song
  - The scorer gives each song a number out of 9.0. Genre and mood matches give flat bonuses (genre is worth more at 3.0 vs. mood at 2.0, because a wrong genre feels the most "off" no matter what). The three numeric features use a proximity formula `1 - |song value - user target|` so songs closer to the user's preference always score higher, not songs that are simply louder or faster. Energy is weighted at 2.0 since it has the widest spread in the dataset; acousticness and valence are each weighted at 1.0 as tiebreakers.

- How do you choose which songs to recommend
  - Once every song has a score, the ranking step sorts the full list from highest to lowest and returns the top k results. I kept scoring and ranking as two separate steps on purpose, the scorer only looks at one song at a time and produces a number, while the ranker sees the whole list and decides what to actually show the user.

You can include a simple diagram or bullet list if helpful.

See [flowchart.md](flowchart.md) for the full data flow diagram (Input → Process → Output).

---

### Finalized Algorithm Recipe

Every song gets a score out of **9.0 points**, calculated in two layers:

**Layer 1 — Categorical matches (max 5.0)**

| Signal | Points | Why this weight |
|--------|--------|----------------|
| Genre matches user's favorite genre | +3.0 | A wrong genre feels broken regardless of how well other features match, it gets the highest weight |
| Mood matches user's favorite mood | +2.0 | Same genre can serve very different moments; mood captures context genre alone can't |

**Layer 2 — Numeric proximity (max 4.0)**

Each feature uses the formula `(1 - |song value - user target|) × weight`, so songs closer to the user's preference always score higher, not songs that are simply louder or faster.

| Signal | Weight | Max pts | Why this weight |
|--------|--------|---------|----------------|
| Energy proximity | ×2.0 | 2.0 | Widest spread in the dataset (0.22–0.97); most discriminating numeric feature |
| Acousticness proximity | ×1.0 | 1.0 | Maps directly to the `likes_acoustic` boolean in the user profile |
| Valence proximity | ×1.0 | 1.0 | Most emotionally independent signal; inferred from the user's favorite mood |

A song that matches both genre and mood starts with 5.0 points before any numeric scoring, meaning a wrong-genre song can never outscore a correct-genre song purely through numeric similarity (max 4.0). This was a deliberate design choice.

---

### Potential Biases

- **Genre over-prioritization:** Because genre carries 3.0 points, a song from the right genre will almost always outrank a song from a different genre, even if the other song matches the user's mood, energy, and acousticness perfectly. A great ambient song could be invisible to a pop user even if it fits their energy target exactly.

- **Mood-valence inference is imprecise:** Valence is inferred from the user's favorite mood using a fixed lookup table rather than being set explicitly. For moods like "intense" where Storm Runner (valence 0.48) and Gym Hero (valence 0.77) are both valid but feel emotionally very different, the inferred target (0.60) splits the difference and treats both songs as roughly equal, which may not match what the user actually wants.

- **No history or feedback:** The system treats every session identically. It has no memory of what the user has already heard, skipped, or loved. A song that scored highly last time will score the same way every time, even if the user is tired of it.

- **Small catalog amplifies errors:** With only 18 songs, a single wrong weight can put the wrong song at rank 1. In a real system with thousands of songs, a slightly miscalibrated weight averages out, here it does not.

---

## Getting Started

### Setup

1. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Mac or Linux
   .venv\Scripts\activate         # Windows

2. Install dependencies

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

## Experiments You Tried

Use this section to document the experiments you ran. For example:

- What happened when you changed the weight on genre from 2.0 to 0.5
- What happened when you added tempo or valence to the score
- How did your system behave for different types of users

### Sample Output — pop/happy profile

Running `python -m src.main` with the `pop_dancer` profile (genre=pop, mood=happy, energy=0.85, acoustic=no):

![Terminal output showing top 5 recommendations for a pop/happy user profile](Screenshot%202026-04-12%20at%2010.26.30%20PM.png)

The results match expectations:
- **#1 Sunrise City** — only song with both genre (`pop`) and mood (`happy`) matching, scores 8.72 / 9.0
- **#2 Gym Hero** — genre matches (`pop`) but mood is `intense` not `happy`, drops to 6.76
- **#3 Rooftop Lights** — mood matches (`happy`) but genre is `indie pop` not `pop`, sits at 5.46 — confirming genre (weight 3.0) outranks mood (weight 2.0) as designed
- **#4 and #5** — no categorical matches at all, ranked purely by energy and acousticness proximity

---

## Limitations and Risks

Summarize some limitations of your recommender.

Examples:

- It only works on a tiny catalog
- It does not understand lyrics or language
- It might over favor one genre or mood

You will go deeper on this in your model card.

---

## Reflection

Read and complete `model_card.md`:

[**Model Card**](model_card.md)

Write 1 to 2 paragraphs here about what you learned:

- about how recommenders turn data into predictions
- about where bias or unfairness could show up in systems like this


---

## 7. `model_card_template.md`

Combines reflection and model card framing from the Module 3 guidance. :contentReference[oaicite:2]{index=2}  

```markdown
# 🎧 Model Card - Music Recommender Simulation

## 1. Model Name

Give your recommender a name, for example:

> VibeFinder 1.0

---

## 2. Intended Use

- What is this system trying to do
- Who is it for

Example:

> This model suggests 3 to 5 songs from a small catalog based on a user's preferred genre, mood, and energy level. It is for classroom exploration only, not for real users.

---

## 3. How It Works (Short Explanation)

Describe your scoring logic in plain language.

- What features of each song does it consider
- What information about the user does it use
- How does it turn those into a number

Try to avoid code in this section, treat it like an explanation to a non programmer.

---

## 4. Data

Describe your dataset.

- How many songs are in `data/songs.csv`
- Did you add or remove any songs
- What kinds of genres or moods are represented
- Whose taste does this data mostly reflect

---

## 5. Strengths

Where does your recommender work well

You can think about:
- Situations where the top results "felt right"
- Particular user profiles it served well
- Simplicity or transparency benefits

---

## 6. Limitations and Bias

Where does your recommender struggle

Some prompts:
- Does it ignore some genres or moods
- Does it treat all users as if they have the same taste shape
- Is it biased toward high energy or one genre by default
- How could this be unfair if used in a real product

---

## 7. Evaluation

How did you check your system

Examples:
- You tried multiple user profiles and wrote down whether the results matched your expectations
- You compared your simulation to what a real app like Spotify or YouTube tends to recommend
- You wrote tests for your scoring logic

You do not need a numeric metric, but if you used one, explain what it measures.

---

## 8. Future Work

If you had more time, how would you improve this recommender

Examples:

- Add support for multiple users and "group vibe" recommendations
- Balance diversity of songs instead of always picking the closest match
- Use more features, like tempo ranges or lyric themes

---

## 9. Personal Reflection

A few sentences about what you learned:

- What surprised you about how your system behaved
- How did building this change how you think about real music recommenders
- Where do you think human judgment still matters, even if the model seems "smart"

