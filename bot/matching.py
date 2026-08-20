"""
Matches an incoming message against the stored QAPair questions.

Two layers, used automatically depending on what's available:

1. SEMANTIC (preferred, when available) - bot/semantic_matching.py, using
   a sentence-transformers model. This understands MEANING, not just
   words, so it can match true synonym swaps like "who will PAY for
   repairs" against a stored "who will BEAR THE COST of repairs" - cases
   the word-overlap layer below cannot reliably solve, verified by
   extensive testing (see semantic_matching.py's docstring for why raw
   word vectors / raw transformer output do NOT work for this, and why a
   sentence-transformers model specifically is needed).

2. WORD-OVERLAP HYBRID (always available, no extra dependencies) - a
   blend of TF-IDF cosine similarity (weighs rare/distinctive words like
   "BVS"/"Issuance"/"TAT" much more than common words) and rapidfuzz
   token_set_ratio (typo-tolerant, handles short queries like a bare
   "TAT" well). This is the fallback used automatically whenever the
   semantic model isn't installed or couldn't load (e.g. no internet
   access on first run to download it) - see semantic_available() in
   semantic_matching.py.

When semantic IS available, its score is blended with the word-overlap
score (weighted toward semantic, since it's the more capable signal) so
the word-overlap layer still acts as a sanity check / tiebreaker rather
than being discarded.

Ambiguity handling: when two stored questions are topically close, their
scores can land within a few points of each other. Rather than guessing
and risking a confidently WRONG answer, if the top two scores are within
AMBIGUITY_MARGIN of each other, both are surfaced so the caller can ask
the user to clarify.

TUNING NOTE: SEMANTIC_MATCH_THRESHOLD below is a reasonable starting
point based on typical sentence-transformers cosine-similarity
distributions, but wasn't empirically tunable in the environment this
was built in (no internet access to the model host). Once deployed
somewhere with real internet access, run the verification script in
README.md's semantic matching section and adjust the threshold if real
results run higher/lower than expected.
"""
from dataclasses import dataclass
from typing import List, Optional

from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from . import semantic_matching

MATCH_THRESHOLD = 38            # 0-100, used when semantic matching is unavailable (word-overlap only)
SEMANTIC_MATCH_THRESHOLD = 45   # 0-100, used when semantic matching is available (blended score) - TUNE THIS, see note above
AMBIGUITY_MARGIN = 3            # 0-100. If top two scores differ by less than this, it's a toss-up.
TFIDF_WEIGHT = 0.65             # blend weight for TF-IDF vs token_set_ratio, within the word-overlap layer
SEMANTIC_WEIGHT = 0.75          # blend weight for semantic vs word-overlap, when semantic is available


@dataclass
class MatchResult:
    question: str
    answer: str
    score: float


@dataclass
class MatchOutcome:
    match: Optional[MatchResult]             # a confident single match, or None
    ambiguous_candidates: List[MatchResult]   # populated only when ambiguous
    used_semantic: bool = False               # for debugging/logging - which layer produced this result


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _word_overlap_scores(user_text: str, questions: List[str]) -> List[float]:
    """TF-IDF + token_set_ratio hybrid. Always available, no extra dependencies."""
    normalized_query = _normalize(user_text)
    try:
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        matrix = vectorizer.fit_transform(questions)
        qvec = vectorizer.transform([user_text])
        tfidf_sims = cosine_similarity(qvec, matrix)[0] * 100
    except ValueError:
        # Can happen if the query is empty/only stopwords after vectorization.
        tfidf_sims = [0.0] * len(questions)

    scores = []
    for question, tfidf_sim in zip(questions, tfidf_sims):
        token_set_score = fuzz.token_set_ratio(normalized_query, _normalize(question))
        scores.append(TFIDF_WEIGHT * tfidf_sim + (1 - TFIDF_WEIGHT) * token_set_score)
    return scores


def _score_all(user_text: str, qa_list):
    """
    qa_list: list of objects/tuples with .question / .answer (or (q, a) tuples).
    Returns (ranked list of MatchResult, used_semantic bool).
    Recomputes from scratch each call - fine for FAQ-sized datasets (tens
    to low hundreds of Q&A pairs); not meant for huge corpora.
    """
    items = [
        (qa.question, qa.answer) if hasattr(qa, "question") else (qa[0], qa[1])
        for qa in qa_list
    ]
    if not items:
        return [], False

    questions = [q for q, _ in items]
    word_scores = _word_overlap_scores(user_text, questions)

    semantic_scores = semantic_matching.semantic_scores(user_text, questions)
    used_semantic = semantic_scores is not None

    results = []
    if used_semantic:
        for (question, answer), sem, word in zip(items, semantic_scores, word_scores):
            combined = SEMANTIC_WEIGHT * sem + (1 - SEMANTIC_WEIGHT) * word
            results.append(MatchResult(question=question, answer=answer, score=combined))
    else:
        for (question, answer), word in zip(items, word_scores):
            results.append(MatchResult(question=question, answer=answer, score=word))

    results.sort(key=lambda r: r.score, reverse=True)
    return results, used_semantic


def find_best_match(user_text: str, qa_pairs) -> Optional[MatchResult]:
    """Simple lookup: best MatchResult above the active threshold, or None."""
    if not _normalize(user_text):
        return None
    ranked, used_semantic = _score_all(user_text, qa_pairs)
    threshold = SEMANTIC_MATCH_THRESHOLD if used_semantic else MATCH_THRESHOLD
    if ranked and ranked[0].score >= threshold:
        return ranked[0]
    return None


def resolve_match(user_text: str, qa_pairs) -> MatchOutcome:
    """
    Full resolution used by views: distinguishes a confident match from
    an ambiguous one (top two candidates too close to call), so the
    caller can ask the user to clarify instead of guessing wrong.
    """
    if not _normalize(user_text):
        return MatchOutcome(match=None, ambiguous_candidates=[])

    ranked, used_semantic = _score_all(user_text, qa_pairs)
    threshold = SEMANTIC_MATCH_THRESHOLD if used_semantic else MATCH_THRESHOLD

    if not ranked or ranked[0].score < threshold:
        return MatchOutcome(match=None, ambiguous_candidates=[], used_semantic=used_semantic)

    top = ranked[0]
    close_runners_up = [
        r for r in ranked[1:]
        if r.score >= threshold and (top.score - r.score) < AMBIGUITY_MARGIN
    ]

    if close_runners_up:
        candidates = [top] + close_runners_up
        return MatchOutcome(match=None, ambiguous_candidates=candidates[:3], used_semantic=used_semantic)

    return MatchOutcome(match=top, ambiguous_candidates=[], used_semantic=used_semantic)
