"""
Optional semantic matching layer using sentence-transformers - a genuine
sentence-embedding model (fine-tuned specifically for semantic similarity,
unlike raw word vectors or raw transformer output, both of which perform
poorly for this without that fine-tuning).

This is a LOCAL model that runs entirely on your own machine/server after
a one-time download - no per-message API calls, no data sent anywhere,
no ongoing cost. It's not a hosted AI API like Gemini/OpenAI.

Trade-off: adds ~500MB of dependencies (PyTorch + the model itself) and
needs more RAM at runtime than the lightweight TF-IDF/fuzzy approach in
matching.py. Likely too heavy for Render's free tier without upgrading.

Designed to fail gracefully: if sentence-transformers isn't installed, or
the model can't load (e.g. no internet access on first run to download
it), semantic_available() returns False and the caller falls back to the
TF-IDF + fuzzy hybrid in matching.py automatically.
"""
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False

MODEL_NAME = "all-MiniLM-L6-v2"

_model = None
_load_attempted = False


def _get_model():
    global _model, _load_attempted
    if not _IMPORT_OK:
        return None
    if _model is not None:
        return _model
    if _load_attempted:
        return None  # already tried and failed this process - don't retry every request

    _load_attempted = True
    try:
        _model = SentenceTransformer(MODEL_NAME)
        logger.info("Loaded semantic matching model '%s'", MODEL_NAME)
    except Exception:
        logger.exception(
            "Could not load sentence-transformers model '%s' - "
            "falling back to TF-IDF/fuzzy matching. This usually means "
            "no internet access was available on first run to download it.",
            MODEL_NAME,
        )
        _model = None
    return _model


def semantic_available() -> bool:
    """Whether semantic matching can actually be used right now."""
    return _get_model() is not None


def semantic_scores(query: str, questions: List[str]) -> Optional[List[float]]:
    """
    Returns a list of similarity scores (0-100) aligned with `questions`,
    or None if the semantic model isn't available (caller should fall
    back to matching.py's TF-IDF/fuzzy hybrid in that case).
    """
    model = _get_model()
    if model is None or not questions:
        return None

    try:
        embeddings = model.encode(
            [query] + list(questions),
            normalize_embeddings=True,  # so dot product == cosine similarity
        )
    except Exception:
        logger.exception("Semantic encoding failed at request time")
        return None

    query_vec = embeddings[0]
    question_vecs = embeddings[1:]
    sims = question_vecs @ query_vec
    return [float(s) * 100 for s in sims]
