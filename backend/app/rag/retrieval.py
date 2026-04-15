"""RAG-layer retrieval shim.

Delegates to app.retrieval.service which is owned by RAG Engineer.
BackendDev calls this module; RAG Engineer enhances retrieval/service.py.
"""

from app.retrieval.service import rbac_vector_search

__all__ = ["rbac_vector_search"]
