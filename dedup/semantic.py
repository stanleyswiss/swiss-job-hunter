"""
Semantic deduplication — catches same job posted by multiple agencies
or with slightly different titles.

Uses sentence-transformers (MiniLM-L6) for fast CPU embeddings.
Only runs as a second pass after exact dedup.

NOTE: sentence-transformers requires PyTorch >= 2.4.
      If you see import errors, either:
        pip install "torch>=2.4" --upgrade
      or use --no-semantic to skip this module entirely.
"""
from __future__ import annotations

from typing import Optional

from config.settings import settings

_model = None


def _get_model():
    global _model
    if _model is None:
        # Lazy import — only triggered when semantic dedup is actually used.
        # Running with --no-semantic never imports sentence_transformers.
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def _job_text(job) -> str:
    parts = [job.title, job.company, job.location]
    if job.description:
        parts.append(job.description[:300])
    return " | ".join(p for p in parts if p)


def _cosine_similarity(a, b) -> float:
    import numpy as np
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


class SemanticDeduplicator:
    """
    Maintains an in-memory embedding index of known jobs.
    Call `is_duplicate()` before inserting a new job.

    Usage:
        deduper = SemanticDeduplicator()
        deduper.load_from_db()
        if not deduper.is_duplicate(text)[0]:
            deduper.add(text)
    """

    def __init__(self, threshold: Optional[float] = None) -> None:
        self.threshold = threshold or settings.semantic_similarity_threshold
        self._texts: list[str] = []
        self._embeddings: list = []

    def load_from_db(self, limit: int = 5000) -> int:
        from db.models import Job
        from db.session import get_session

        with get_session() as session:
            jobs = (
                session.query(Job)
                .order_by(Job.scraped_at.desc())
                .limit(limit)
                .all()
            )
            texts = [_job_text(j) for j in jobs]

        if texts:
            model = _get_model()
            embeddings = model.encode(texts, batch_size=64, show_progress_bar=False)
            self._texts = texts
            self._embeddings = list(embeddings)

        return len(self._texts)

    def is_duplicate(self, text: str) -> tuple[bool, float]:
        if not self._embeddings:
            return False, 0.0

        model = _get_model()
        emb = model.encode([text], show_progress_bar=False)[0]
        sims = [_cosine_similarity(emb, e) for e in self._embeddings]
        max_sim = max(sims) if sims else 0.0
        return max_sim >= self.threshold, max_sim

    def add(self, text: str) -> None:
        model = _get_model()
        emb = model.encode([text], show_progress_bar=False)[0]
        self._texts.append(text)
        self._embeddings.append(emb)
