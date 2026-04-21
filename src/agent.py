"""
agent.py — Module 4 Extension

Orchestrates the full agentic chain end-to-end:

    Parser → Retriever → 1st Critic → [rerank if retryable] → 2nd Critic → Explainer

Pure library: emits progress exclusively through the `logging` module and
returns a structured `AgentResult`. No printing. The CLI runner
(agent_runner.py) and the test harness (evaluate.py) each decide for
themselves how to surface this information.

Retry policy: 1 retry maximum. If residual issues remain after retry,
they are not suppressed — they travel back with the result so the caller
can surface them honestly.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

from src.parser import ParseResult, parse, build_catalog_genres
from src.recommender import recommend_songs
from src.explainer import explain_all
from src.critic import CritiqueResult, critique, rerank_with_hints

logger = logging.getLogger(__name__)

MAX_RETRIES = 1


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class AgentResult:
    """
    End-to-end output of one agent run. Includes the full chain of metadata
    so that evaluate.py can make assertions about intermediate behavior
    (did the critic fire? did retry trigger? were warnings suppressed?).
    """
    success: bool                                                                  # pipeline completed; may still carry warnings
    recommendations: List[Tuple[Dict, float, str, str]] = field(default_factory=list)  # (song, score, raw_reasons, prose)
    parser_result: Optional[ParseResult] = None
    first_critique: Optional[CritiqueResult] = None
    retried: bool = False
    second_critique: Optional[CritiqueResult] = None
    error: Optional[str] = None   # populated only on parser-level reject
    used_rag: bool = True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_agent(user_input: Union[str, Dict],
              songs: List[Dict],
              mood_guides: Dict[str, str],
              use_rag: bool = True,
              k: int = 5) -> AgentResult:
    """
    Execute the full chain for one user input.

    Args:
        user_input : structured prefs dict OR free-form NL string
        songs      : catalog loaded by recommender.load_songs()
        mood_guides: mood → guide dict loaded by explainer.load_mood_guides()
        use_rag    : True for RAG-enhanced explanations, False for baseline
        k          : number of final recommendations

    Caller loads songs / mood_guides once and reuses across runs. This keeps
    evaluate.py from re-reading CSV files per profile.
    """
    logger.info("[AGENT] ━━━━━━━━━━━━━━━━━━━━━━ begin ━━━━━━━━━━━━━━━━━━━━━━")
    catalog_genres = build_catalog_genres(songs)

    # ── Stage 1: Parser ───────────────────────────────────────────────
    parser_result = parse(user_input, catalog_genres=catalog_genres)

    if not parser_result.is_valid:
        logger.warning(f"[AGENT] parser rejected input → aborting pipeline")
        return AgentResult(
            success=False,
            parser_result=parser_result,
            error="; ".join(parser_result.errors),
            used_rag=use_rag,
        )

    prefs = parser_result.prefs
    if parser_result.warnings:
        for w in parser_result.warnings:
            logger.info(f"[AGENT] parser warning: {w}")

    # ── Stage 2: Retrieve / Score (Module 3 baseline treated as a tool) ──
    # Ask for the full catalog so rerank has candidates to promote on retry.
    candidates = recommend_songs(prefs, songs, k=len(songs))
    top_k = candidates[:k]
    logger.info(
        f"[SCORER] scored {len(songs)} songs; top-1 = "
        f"'{top_k[0][0]['title']}' score={top_k[0][1]:.2f}"
    )

    # ── Stage 3: First critique ──────────────────────────────────────
    first_critique = critique(top_k, prefs, catalog_genres)

    retried = False
    second_critique: Optional[CritiqueResult] = None
    final_top_k = top_k

    # ── Stage 4: Retry (1 max) ───────────────────────────────────────
    if first_critique.should_retry:
        logger.info(f"[AGENT] retry 1/{MAX_RETRIES} — applying hints")
        reranked = rerank_with_hints(
            candidates, prefs, first_critique.retry_hints, k=k
        )
        final_top_k = reranked
        retried = True
        # Re-critique for transparency, not to trigger another retry.
        second_critique = critique(reranked, prefs, catalog_genres)
        if not second_critique.passed:
            logger.info(
                "[AGENT] residual issues after retry — 1-retry cap honored, "
                "surfacing to user without suppression"
            )

    # ── Stage 5: Explain ─────────────────────────────────────────────
    explained = explain_all(
        final_top_k, prefs, mood_guides=mood_guides, use_rag=use_rag
    )

    logger.info("[AGENT] ━━━━━━━━━━━━━━━━━━━━━━  end  ━━━━━━━━━━━━━━━━━━━━━━\n")

    return AgentResult(
        success=True,
        recommendations=explained,
        parser_result=parser_result,
        first_critique=first_critique,
        retried=retried,
        second_critique=second_critique,
        used_rag=use_rag,
    )