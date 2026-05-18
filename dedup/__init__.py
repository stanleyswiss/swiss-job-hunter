from .exact import get_or_create_job, is_exact_duplicate

# SemanticDeduplicator is imported lazily in cli.py to avoid
# triggering sentence-transformers at startup when --no-semantic is used.
__all__ = ["get_or_create_job", "is_exact_duplicate"]
