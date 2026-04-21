# Model Card: VibeFinder 2.0

**Module 4 Final Project, CodePath AI 110**  
Author: Ashley Qu

---

## 1. Model Name

**VibeFinder 2.0**: a rule-based music recommender packaged as a multi-stage agent. It is an extension of VibeFinder 1.0 (my Module 3 project), which was a content-based scorer without any agentic layer.

## 2. Intended Use

This system is a classroom / portfolio demonstration of applied AI concepts, not a consumer product. The target use case is showing how four building blocks (input parsing, retrieval-scored recommendations, RAG-enhanced explanations, and rule-based self-critique with retry) can be composed into an agentic pipeline that is observable, testable, and honest about its limitations.

It is not intended for:

- Real listener-facing music discovery. The catalog has only 18 songs.
- Any setting where music recommendation might meaningfully influence emotional state (see Misuse Potential).
- Production deployment, because the "agent" is deterministic rule-based logic hand-tuned against a small dataset.

## 3. How It Works (Short)

A user request flows through five stages:

1. **Parser** accepts either a structured dict (`favorite_genre`, `favorite_mood`, `target_energy`, `likes_acoustic`) or a free-form English query like `"chill lofi for studying"`. Input guardrails reject malformed input (energy outside [0, 1], unknown moods, missing required fields).

2. **Retriever** (the Module 3 baseline scorer, retained as-is) computes a 0 to 9 score for each of the 18 songs. Genre match contributes +3.0, mood match contributes +2.0, plus weighted numeric proximity on energy (×2.0), acousticness (×1.0), and valence (×1.0).

3. **Explainer** generates a prose explanation for each top-5 recommendation. In RAG mode, it injects hand-written `song_notes` from `data/songs.csv` and `mood_guide` content from `data/mood_guides.csv` into the output.

4. **Self-Critic** runs four rule-based checks on the top-5 (`mood_valence_conflict`, `missing_genre`, `acoustic_violation`, `low_diversity`). Retryable failures trigger a rerank pass.

5. **Rerank** applies the Critic's hints (soft valence / diversity penalties; hard acoustic filter) to the full candidate pool and returns a new top-5. Maximum 1 retry. Residual issues are surfaced to the user, not suppressed.

No LLM is involved. The entire chain is deterministic.

## 4. Data

### Song catalog (18 songs)
`data/songs.csv`. Each row has 11 columns: `id`, `title`, `artist`, `genre`, `mood`, `energy`, `tempo_bpm`, `valence`, `danceability`, `acousticness`, and (new in Module 4) `song_notes`. The first 10 columns are inherited from Module 3 unchanged. `song_notes` is a 1 to 2 sentence handwritten description I wrote for each song (e.g. "Driving guitars with no quiet moments. A straight shot of adrenaline for workouts where you'd rather not think.").

Genres represented: pop, lofi, rock, ambient, jazz, synthwave, hip-hop, classical, r&b, metal, folk, edm, soul, reggae, indie pop. Most genres appear in only one song.

Moods represented: happy, chill, intense, focused, energetic, moody, relaxed, romantic, melancholic, angry, nostalgic, euphoric, sad, uplifting.

### Mood guides (14 entries, new in Module 4)
`data/mood_guides.csv`. A short context blurb for each mood label describing what that mood family typically sounds like and what situation it fits (e.g. for "chill": "Low-to-medium energy with a settled valence. Aim is to lower stimulation not to entertain.").

Both CSV files are regenerated deterministically from `build_data.py`, which keeps the RAG corpus versioned alongside the code.

### Whose taste is this catalog?
Mostly mine. I picked songs that I thought had distinctive enough features (specific genre, mood, energy) to test scoring behavior. This is a bias baked into the data: the "right" recommendation is defined by my personal sense of match quality, and that definition is not universal.

## 5. Strengths

- **Deterministic and reproducible.** Anyone cloning the repo can run everything and get the same output. No API keys, no inference costs, no stochastic behavior.

- **Observable reasoning.** Every stage of the agent emits `[PARSER] [SCORER] [CRITIC] [AGENT]` log lines, so a reader can see exactly what the agent decided and why. This is important because the "agentic" aspect of the system is supposed to be legible, not hidden.

- **Honest about its own limits.** The Critic's 1-retry cap plus residual-issue surfacing means the system does not pretend to solve self-contradictory user profiles. Profile D (sad + EDM + non-acoustic + high-energy is not jointly satisfiable in an 18-song catalog) is the best test of this: after retry, the agent reports exactly what trade-off it chose.

- **Measurable RAG impact.** The dual-mode Explainer combined with `evaluate.py` produces a clean before/after comparison. RAG explanations are +104% longer and have +102% more unique vocabulary on average than baseline, and 100% of RAG outputs contain retrieval-sourced content versus 0% of baseline outputs.

## 6. Limitations and Bias

- **Small catalog amplifies ranking errors.** With 18 songs and only one or two songs per genre, a single weight tuning decision can swing rankings. In a real system with thousands of candidates, minor miscalibrations average out; here they dominate.

- **Genre over-prioritization.** Because genre match is worth +3.0 (out of 9), a wrong-genre song almost never wins even when every other feature is a perfect match. This is a Module 3 bias that actually motivated building the Critic in the first place.

- **Valence targets are inferred from mood labels, not asked directly.** The lookup table treats "intense" as valence ≈ 0.6, but Storm Runner (valence 0.48) and Gym Hero (valence 0.77) feel emotionally very different even though both are tagged "intense". The system cannot distinguish.

- **"Silence means False" in the NL parser.** If a query doesn't explicitly mention acoustic preference, the parser defaults `likes_acoustic=False`. The downstream Critic then enforces that default. Result: `"chill lofi for studying"` produces a non-acoustic recommendation set, even though many people saying "chill lofi" probably want something acoustic-leaning. This is a real limitation of rule-based NLU: default values can't reflect unstated intent.

- **Handwritten corpus bakes in my voice.** The `song_notes` and `mood_guides` are mine. They lean on a specific English register (images like "festival-main-stage drops", "library rain", "11pm freeway stretches") that won't translate equally across cultures or musical backgrounds. A different corpus author would produce a different "feel" of recommendation, even with identical scoring.

- **No memory, no feedback.** The same query produces the same output forever. The system has no sense of novelty, repetition fatigue, or what the user liked last time.

- **Critic thresholds were tuned against the existing 6 test profiles.** The numbers (valence gap > 0.4 triggers conflict, acoustic gap > 0.5 triggers violation, top-5 with ≥4/5 same genre is "low diversity") were picked so the test cases behave as expected. On profiles with different edge cases, these thresholds may fire spuriously or miss real issues.

## 7. Misuse Potential

The system itself has a narrow attack surface (deterministic, closed catalog, no user-generated content). But a few ways it could go wrong in a hypothetical deployment:

- **Emotional reinforcement.** The system can recommend music matching any mood, including sad. If a listener is already in a low emotional state, optimally matching that state is not necessarily helpful. A real product would need at minimum a check for patterns suggesting distress, and optionally an "offer uplifting alternative" mode. VibeFinder 2.0 does neither.

- **Scale amplifies the handwritten-corpus bias.** At 18 songs my voice is obvious (and the Module 3 docs openly caveat this). At 18,000 songs the same handwritten-corpus tone would be less visible but would still shape which artists and genres get described most compellingly. Applied to a commercial catalog, this would quietly favor certain types of music.

- **Adversarial inputs could force weird fallbacks.** The NL parser fills in defaults when it cannot extract a genre or mood keyword. A user typing a genuine-looking query outside the parser's vocabulary could get a confusing recommendation that still looks authoritative. Guardrails catch only the extreme case where both genre and mood are unrecognized.

The most important preventive measure is the one already in the system: the Critic is designed to surface problems rather than silently paper over them. If the system cannot meet the user's constraints, it says so.

## 8. Evaluation

`evaluate.py` is the main evaluation harness. It runs two things end-to-end.

**Behavioral assertions (8 test cases).** Each case specifies expected behavior (`success`, `retried`, and required `first_critique` issue codes). Current status:

```
Total: 8 / 8 passed
```

The tests cover: 3 standard profiles (A/B/C), 3 adversarial profiles targeting specific Critic rules (D/E/F), one natural-language query (G), and one guardrail-reject case (H).

**RAG vs baseline comparison (6 profiles × 2 modes).** For each profile the harness runs the agent once with `use_rag=True` and once with `use_rag=False`, then reports aggregates:

| Metric | Baseline | RAG | Δ |
|---|---|---|---|
| Avg explanation length (words) | 34.9 | 71.0 | +104% |
| Unique vocab tokens | 71.7 | 145.0 | +102% |
| Recs referencing song_notes | 0% | 100% | |
| Recs referencing mood_guides | 0% | 100% | |

Per-profile length deltas range from +92% (Profile E) to +118% (Profile B), which I read as RAG's value being consistent rather than driven by one outlier.

**What the test harness caught during development.** A duplicate `score_song` definition at the bottom of `recommender.py` was silently shadowing the real scoring function. My original Module 3 tests did not catch it because the tests imported dead OOP classes, while the live code path used procedural functions. `evaluate.py` calls the full pipeline end-to-end, so a shadowed stub would have crashed on the first run.

**What it did not catch.** The NL parser's "silence means False" behavior on acoustic preference. The system is internally consistent (the default is applied end-to-end), so all behavioral tests pass, but the result may not match user intent when the query is ambiguous. This is a limit of rule-based NLU rather than a test gap, but it's worth flagging.

## 9. What Surprised Me

**How much a rule chain can feel like "reasoning".** When the Critic fires, logs `mood_valence_conflict → retry with valence_penalty_weight=5.0`, then returns a visibly different top-5, it reads as if the system "thought" about the problem. There is no thinking happening. It's four `if` statements and a weight multiplication. The appearance of agency is created by the sequencing of the decision points and the visibility of the logs, not by any actual intelligence. I think this helps explain why people overtrust LLM agents: if a system can show its work in a plausible sequence, it looks smarter than it is.

**Rules force honesty in a way LLMs may not.** The Profile D residual-issue case is the clearest example. The user's profile is mutually unsatisfiable (sad + EDM + non-acoustic + high-energy can't coexist in the 18-song catalog), and a rule-based system has no vocabulary for papering this over. It has to report the trade-off. An LLM in the same situation might produce confident, fluent, and subtly wrong explanation text. My rule chain can only output what it actually has.

**Testing coverage is a lie you tell yourself until you actually run the tests.** My Module 3 `tests/` folder had test files that imported unfinished OOP classes (`Song`, `UserProfile`, `Recommender` with stubbed methods) while the live code path was completely separate procedural functions. The tests were testing dead code. `pytest` had literally never run successfully during Module 3 and I didn't notice because I never ran it. Having tests in the repo is not the same as having a tested system. I won't make this mistake again.

**A mundane technical surprise: macOS inserts narrow no-break space in screenshot filenames.** When I tried to reorganize my Module 3 screenshot files into `docs/module_3_screenshots/`, `git mv` refused with "bad source" even though the file clearly existed on disk. Turns out the "space" between "10.26.30" and "PM" in the file names is U+202F (narrow no-break space), not U+0020 (regular space). macOS's screenshot utility inserts it automatically. This ate 20 minutes of the final documentation step and also surfaced a flawed AI suggestion downstream (see section 10).

## 10. AI Collaboration

I used Claude (Anthropic) extensively throughout this project as a collaborator on design decisions, code review, and debugging. The collaboration was structured as an ongoing chat with shared context, including a `PROJECT_NOTES.md` document where I kept a running record of decisions and AI suggestions (both good and bad) as we went. I think that shared context mattered more than any individual prompt. Claude could re-check what I'd already decided before proposing something new.

### A helpful AI suggestion

Early in the project, I shared my Module 3 `recommender.py` with Claude before we started extending it. Claude immediately noticed that `score_song` was defined twice in the file: a working implementation around line 70 with full scoring logic, and a stub at line 136 that returned `[]`. Because Python's later definition silently overrides the earlier one, the stub was shadowing the real function. This meant `recommend_songs()` was actually calling the stub and would crash at the tuple-unpacking step with `ValueError: not enough values to unpack (expected 2, got 0)`.

I had not noticed this before. My Module 3 project shipped with the bug because the tests I wrote targeted the unfinished OOP class, not the procedural function path the app actually used. If we had started building the Module 4 agent on top of this broken base, my first run of the new pipeline would have blown up with a misleading error, and I would have spent hours debugging the symptom instead of finding the cause.

The catch wasn't because Claude ran my code (it didn't have access). It was because Claude read the whole file carefully and noticed the duplicated `def score_song` pattern, which I had stopped seeing because I'd been staring at that code for weeks.

### A flawed AI suggestion

When I finished writing the new `README.md` and the `docs/MODULE_3_ORIGINAL.md` file, Claude included URL-encoded image paths like `module_3_screenshots/Screenshot%202026-04-12%20at%2010.26.30%20PM.png` in the markdown. When I pushed to GitHub, none of the 7 embedded screenshots rendered. They all showed as broken image icons.

The cause was that `%20` (URL-encoded regular space, U+0020) was wrong for these specific files. My macOS screenshots had file names containing narrow no-break space (U+202F) between "10.26.30" and "PM", which URL-encodes to `%E2%80%AF`. Claude's generated markdown silently assumed all "spaces" in the file names were regular spaces. The generated paths looked correct but resolved to files that didn't exist on the filesystem.

This is a small concrete example of a category of AI failure: confidently-written output based on a plausible but wrong assumption about external state. The markdown was syntactically perfect; it just pointed at the wrong files. Claude had no way to check the actual byte content of the filenames without running something, and neither did I until GitHub's image renderer told me.

The fix was a one-line `sed` command (`s/%20PM/%E2%80%AFPM/g`), but it took a GitHub round-trip to even discover, which cost me real time near the end of the project.

### Other collaboration observations

The collaboration worked best when I had a specific question (catch this bug, is this design sound, does this rubric item require X) and worst when I was under-specific. When Claude lacked context about what I had already tried or already decided against, it sometimes re-proposed things we had previously closed. The running `PROJECT_NOTES.md` helped with this. Claude could read it at the start of each session and know not to re-litigate settled questions.

I also noticed Claude's suggestions were more grounded when it could actually run code (it ran `evaluate.py` in its isolated environment to verify RAG metrics before reporting them back to me) than when it had to reason about runtime behavior from static code. The URL-encoding miss falls in the second category: no code was executed, just markdown was generated, and the wrong-ness wasn't checkable until push time.

## 11. Future Work

If I were to continue this project, roughly in priority order:

1. **Extend the catalog.** 18 songs is too small for the genre bonus to behave sensibly. 200 to 300 songs with proper per-genre variety would be enough to test whether the scoring formula generalizes.

2. **Replace the NL parser's default-False behavior with an explicit "unspecified" tri-state.** Right now silence on acoustic preference becomes `False`, which is wrong. The parser should emit `likes_acoustic=None` and the scorer should skip that term entirely rather than scoring against `target=0.0`.

3. **Learn the scoring weights from user feedback.** Current weights (genre 3.0, mood 2.0, etc.) are hand-tuned against my intuition about what "feels right". A small feedback loop (thumbs up / thumbs down per recommendation) could tune these per user.

4. **More Critic rules.** The current four are the ones that made sense against my 6 test profiles. Other useful ones: "top-5 all have very similar energy", "user's energy target is unusually extreme versus the catalog distribution", "recommendations don't span the mood family's full valence range".

5. **Try a small LLM-powered variant for the Explainer stage only.** The current RAG explainer is template-based; a local small model (via ollama or similar) could produce more natural prose while keeping the rest of the pipeline rule-based and reproducible. Scoring and Critic should stay deterministic.

6. **Cross-cultural evaluation of the handwritten corpus.** Ask people from different musical backgrounds whether the `song_notes` actually match their experience of the songs. Right now the corpus reflects a sample of one.