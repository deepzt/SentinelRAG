# SentinelRAG — Architecture

> **Status:** Phase 1 (Local MVP). Last updated: 2026-04-15.

## System Overview

SentinelRAG is a role-based access-controlled (RBAC) RAG assistant. It ensures users retrieve only documents their role permits, logs every access decision, and returns source-cited responses.

## System Flow

```
User
  │
  ▼
Streamlit UI (frontend/chat-ui/)
  │  POST /auth/login
  ▼
FastAPI Backend (backend/)
  │  Validate credentials → issue JWT (role claim embedded)
  │
  │  POST /query   {Bearer: <JWT>, query: "..."}
  ▼
auth/          Validate JWT signature + expiry
               Resolve user from `users` table
               Load allowed policies from `access_policies`
  │
  ▼
rag/           Embed query  →  sentence-transformers/all-MiniLM-L6-v2
               pgvector similarity search
               WHERE role_required = :user_role   ← RBAC at DB level
               JOIN access_policies               ← policy table, not hardcode
  │
  ▼
LLM layer      Ollama (local) / hosted LLM (Phase 2)
               Grounded generation with retrieved chunks as context
  │
  ▼
audit/         Write row to `audit_logs`
               Fields: user_id, query, retrieved_doc_ids, latency_ms, access_decision
  │
  ▼
Response       { answer, citations: [{title, section, department}] }
```

## Component Boundaries

| Module | Path | Responsibility |
|--------|------|----------------|
| Route handlers | `backend/app/api/` | Thin HTTP layer. No business logic. |
| Auth | `backend/app/auth/` | JWT encode/decode, user resolution, FastAPI `Depends` injection. |
| RAG service | `backend/app/rag/` | Query embedding + pgvector call. Calls audit service after retrieval. |
| Ingestion | `backend/app/ingestion/` | PDF/Markdown parsing, chunking, embedding, DB insert. |
| Retrieval | `backend/app/retrieval/` | SQL builder for RBAC-filtered vector search. |
| Audit | `backend/app/audit/` | Append-only writes to `audit_logs`. Called by RAG service only. |
| ORM models | `backend/app/models/` | SQLAlchemy model definitions. No logic. |
| Core | `backend/app/core/` | Config (pydantic-settings), DB session factory, shared deps. |
| Frontend | `frontend/chat-ui/` | Streamlit pages. No RBAC decisions. No business logic. |

## Database Schema

```
users
  ↓ uploaded_by
documents
  ↓ document_id
document_chunks  ─── embedding VECTOR(384) ──→ pgvector index
  ↑
access_policies  (role + department + allowed_classification)

audit_logs  ←── written by RAG service after every query
chat_sessions → chat_messages
```

Full DDL: see `data.txt` (canonical source) and Alembic migrations in `backend/alembic/versions/`.

## Infrastructure (Local)

```
docker-compose.yml
  ├── db        pgvector/pgvector:pg16   :5432
  ├── backend   python:3.11-slim         :8000
  └── frontend  python:3.11-slim         :8501
```

pgvector extension enabled via `backend/init_db.sql` on first DB startup.

## Key Design Decisions

### 1. RBAC at SQL level
Filtering happens inside the pgvector query (`WHERE role_required = :user_role`), not in Python post-retrieval. This prevents any timing window where forbidden chunks could be in memory.

### 2. Policy table, not hardcoded roles
`access_policies` table allows role/department/classification rules to evolve without code changes. Mirrors IAM/OpenFGA patterns.

### 3. Append-only audit log
`audit_logs` has no UPDATE or DELETE endpoints. Denied requests are logged with `access_decision = 'denied'`.

### 4. Embedding dimension locked at 384
`all-MiniLM-L6-v2` produces 384-dim vectors. Changing the model requires dropping and re-creating all embeddings. Protected by Architect review.

### 5. JWT algorithm pinned to HS256
`alg: none` is rejected. `SECRET_KEY` must come from environment — never from source code.

## Phase 2 Migration Notes

| Decision | Phase 2 Impact |
|----------|---------------|
| Local JWT auth | Replace `auth/` JWT logic with Cognito/OAuth token validation. Route handlers unchanged (same `Depends(get_current_user)`). |
| Ollama LLM | Swap LLM call in `rag/` service. No other changes needed. |
| Single-tenant DB | Add `tenant_id` column to `documents` + `document_chunks`. Requires Alembic migration + re-ingestion. |
| SQLite audit fallback | Not used — all audit in Postgres. No migration needed. |
