# System Architecture — Module 4 Extended

> Visual convention:
> - **Gray / dashed** = Module 3 baseline components retained as-is
> - **Blue** = Module 4 new components (agentic chain, RAG, critic)
> - **Green** = data sources
> - **Yellow diamond** = decision points (agent reasoning)
> - **Pink** = evaluation harness (runs the whole thing end-to-end for testing)

```mermaid
flowchart TD

    %% ============================================================
    %%  USER INPUT
    %% ============================================================
    U["🎧 User Query<br/>e.g. genre=lofi, mood=chill, energy=0.38<br/>or free-form keywords"]:::new

    %% ============================================================
    %%  MODULE 4 — AGENTIC CHAIN (new)
    %% ============================================================
    subgraph AGENT["🤖 Module 4 — Agentic Chain (agent.py orchestrates)"]
        direction TB

        P["<b>Stage 1: Parser</b><br/>─────────────<br/>• Free-form → structured prefs<br/>• <b>Guardrails</b>:<br/>&nbsp;&nbsp;– genre must be in catalog<br/>&nbsp;&nbsp;– energy ∈ [0,1]<br/>&nbsp;&nbsp;– mood in known vocab"]:::new

        subgraph SCORE["<b>Stage 2: Retrieve &amp; Score</b> — from Module 3"]
            R["score_song() per song<br/>genre&nbsp;+3.0 · mood&nbsp;+2.0<br/>energy ×2.0 · acoustic ×1.0 · valence ×1.0<br/><br/>recommend_songs() ranks top K"]:::old
        end

        E["<b>Stage 3: Explainer + RAG</b><br/>─────────────<br/>• Template generation<br/>• Retrieves song_notes per rec<br/>• Retrieves mood guide for context<br/>• Output: prose explanation per song"]:::new

        C["<b>Stage 4: Self-Critic</b><br/>─────────────<br/>Rule-based checks:<br/>• mood–valence conflict<br/>• missing-genre signal<br/>• acoustic violation<br/>• low genre diversity (top-5)"]:::new

        RT{"Critic<br/>verdict"}:::decision
    end

    %% ============================================================
    %%  DATA SOURCES
    %% ============================================================
    subgraph DATA["📚 Data Sources — Multi-Source RAG"]
        SONGS[("<b>songs.csv</b><br/>18 songs<br/>+ song_notes column<br/>(NEW: custom descriptions)")]:::data
        MOODS[("<b>mood_guides.csv</b><br/>NEW<br/>~14 mood context blurbs")]:::data
    end

    %% ============================================================
    %%  OUTPUT
    %% ============================================================
    OUT["📋 Final Output<br/>─────────────<br/>• Top 5 recommendations<br/>• Prose explanations w/ RAG context<br/>• <b>Visible reasoning log</b>:<br/>&nbsp;&nbsp;[PARSER] parsed query…<br/>&nbsp;&nbsp;[SCORER] top 5 candidates…<br/>&nbsp;&nbsp;[CRITIC] ⚠️ diversity fail → retry<br/>&nbsp;&nbsp;[CRITIC] ✅ pass"]:::new

    %% ============================================================
    %%  EVALUATION HARNESS (parallel — runs everything end-to-end)
    %% ============================================================
    subgraph EVAL["🧪 evaluate.py — Test Harness"]
        direction LR
        PROF["6 predefined profiles<br/>(A/B/C standard,<br/>&nbsp;D/E/F adversarial)"]:::eval
        VERIFY["Asserts:<br/>• pass/fail per profile<br/>• critic retry counts<br/>• baseline vs RAG metrics<br/>&nbsp;&nbsp;(vocab diversity, length,<br/>&nbsp;&nbsp;specific-ref rate)"]:::eval
    end

    %% ============================================================
    %%  FLOW
    %% ============================================================
    U --> P
    P -->|"valid prefs"| R
    P -.->|"invalid ❌<br/>guardrail reject"| OUT
    SONGS --> R
    R --> E
    SONGS -.->|"song_notes"| E
    MOODS -.->|"mood context"| E
    E --> C
    C --> RT
    RT -->|"pass ✅"| OUT
    RT ==>|"fail ⚠️ → reweight<br/>(max 1 retry)"| R

    %% Eval harness wraps the whole thing
    PROF -.->|"feeds inputs"| U
    OUT -.->|"captured output"| VERIFY

    %% ============================================================
    %%  STYLING
    %% ============================================================
    classDef old fill:#e5e7eb,stroke:#6b7280,color:#374151,stroke-dasharray: 4 2
    classDef new fill:#dbeafe,stroke:#2563eb,color:#1e3a8a
    classDef data fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef decision fill:#fef3c7,stroke:#d97706,color:#78350f
    classDef eval fill:#fce7f3,stroke:#be185d,color:#500724

    style AGENT fill:#eff6ff,stroke:#2563eb,stroke-width:2px
    style SCORE fill:#f3f4f6,stroke:#6b7280,stroke-width:1px,stroke-dasharray: 5 5
    style DATA fill:#f0fdf4,stroke:#16a34a,stroke-width:2px
    style EVAL fill:#fdf2f8,stroke:#be185d,stroke-width:2px
```

## Reading the diagram

**Happy path** (solid blue arrows):
User query → Parser validates → Baseline scorer ranks songs → Explainer adds RAG context → Critic approves → Output.

**Retry path** (bold arrow back to scorer):
If Critic detects a problem (e.g., 5/5 results are the same genre, or mood conflicts with top result's valence), it adjusts scoring weights and loops back to the scorer once. Max one retry to prevent loops.

**Guardrail path** (dashed reject arrow):
If Parser detects invalid input (genre not in catalog, energy out of range), it short-circuits to Output with an error message — no wasted scoring pass.

**Why the Module 3 core is visually "inside" the agent:**
The baseline scorer is unchanged — it's a tool the agent calls, not something we rewrote. This makes the "substantial new AI feature" obvious: everything blue is new, everything gray is preserved.