# Import all models so Alembic autogenerate can detect them.
# When adding a new model, register it here.
from app.models.access_policy import AccessPolicy
from app.models.audit_log import AuditLog
from app.models.chat import ChatMessage, ChatSession
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.user import User

__all__ = [
    "User",
    "Document",
    "DocumentChunk",
    "AccessPolicy",
    "AuditLog",
    "ChatSession",
    "ChatMessage",
]
