# SentinelRAG

> **Enterprise RBAC-aware RAG assistant** — role-based document access, pgvector semantic search, source citations, and compliance-grade audit logging.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql)](https://postgresql.org)
[![pgvector](https://img.shields.io/badge/pgvector-0.2.5-blue)](https://github.com/pgvector/pgvector)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35-FF4B4B?logo=streamlit)](https://streamlit.io)

---

## Problem Statement

Most internal AI tools treat all employees as equals — any user can query any document. In real enterprises, that's a compliance failure. SentinelRAG enforces **role-based document access at the retrieval layer**: HR staff see HR policies, engineers see engineering runbooks, and managers see a controlled union. Every query is logged for audit.

---

## Architecture

```
User → Streamlit UI
  → POST /auth/login  →  JWT issued (role embedded)
  → POST /query (Bearer token)
      → Validate JWT
      → Resolve role from access_policies table
      → Embed query (sentence-transformers/all-MiniLM-L6-v2)
      → pgvector similarity search  WHERE role_required = :role
      → LLM generation (Ollama / hosted LLM)
      → Write audit_log row
      → Return response + citations
```

Full details: [`docs/architecture.md`](docs/architecture.md)

---

## RBAC Demo

Same query — different results per role:

| User | Role | Query | Result |
|------|------|-------|--------|
| alice | engineer | "What is the onboarding process?" | Engineering onboarding checklist |
| bob | hr | "What is the onboarding process?" | HR joining workflow |
| charlie | manager | "What is the onboarding process?" | Both (union of allowed docs) |

Bob cannot see any engineering documents. Alice cannot see any HR documents. Neither can access the other's docs even with direct API calls.

---

## Sample Users

| Username | Role | Department |
|----------|------|------------|
| alice | engineer | platform |
| bob | hr | people_ops |
| charlie | manager | engineering |

---

## Local Setup

### Prerequisites
- Docker + Docker Compose
- Git

### Run

```bash
git clone <repo-url>
cd SentinelRAG
cp .env.example .env
# Edit .env — set SECRET_KEY to a real random value
docker compose up --build
```

Services:
- **Backend API:** http://localhost:8000
- **Frontend UI:** http://localhost:8501
- **API docs:** http://localhost:8000/docs (development only)

### Seed the database

```bash
# After containers are up:
docker compose exec backend python -m app.scripts.seed_db
```

### Run tests

```bash
docker compose exec backend pytest tests/ -v
```

---

## Project Structure

```
SentinelRAG/
├── backend/
│   ├── app/
│   │   ├── api/          Route handlers (thin layer)
│   │   ├── auth/         JWT + user resolution
│   │   ├── rag/          Retrieval service + RBAC filtering
│   │   ├── ingestion/    PDF/Markdown → chunk → embed → store
│   │   ├── retrieval/    pgvector query builder
│   │   ├── audit/        Append-only audit log writes
│   │   ├── models/       SQLAlchemy ORM models
│   │   └── core/         Config, DB session, shared deps
│   ├── alembic/          Database migrations
│   └── tests/            pytest test suite
├── frontend/
│   └── chat-ui/          Streamlit pages (login, chat, admin)
├── docs/
│   ├── architecture.md   System design documentation
│   ├── threat-model.md   Security threat model
│   └── sample/           Sample enterprise documents
└── docker-compose.yml
```

---

## Database Schema

```
users ──────────────────────────────────────────────────────┐
  ↓ uploaded_by                                             │
documents                                                   │
  ↓ document_id                                             │
document_chunks ── embedding VECTOR(384) ──→ pgvector index │
                                                            │
access_policies (role, department, allowed_classification)  │
                                                            │
audit_logs ←── written after every query (allow + deny) ───┘
chat_sessions → chat_messages
```

---

## Security

- JWT authentication with `HS256` — `alg: none` rejected
- `SECRET_KEY` from environment only — never in source code
- RBAC filter applied at SQL level — not post-retrieval in Python
- `access_policies` table as single source of truth — no hardcoded role checks
- Audit log is append-only — denied requests are logged too
- Error responses do not reveal internal details

See [`docs/threat-model.md`](docs/threat-model.md) for full threat analysis.

---

## Roadmap

### Phase 1 (Current — Local MVP)
- [x] Project structure + Docker Compose
- [ ] SQLAlchemy models + Alembic migrations
- [ ] Auth: JWT login endpoint
- [ ] Ingestion pipeline: PDF + Markdown → pgvector
- [ ] RBAC-filtered retrieval
- [ ] Audit logging
- [ ] Streamlit chat UI
- [ ] Sample enterprise documents

### Phase 2 (Cloud)
- AWS/GCP deployment
- Cognito / OAuth SSO replacing local JWT
- Real-time audit dashboard
- Multi-tenant document namespacing
- Hosted LLM replacing Ollama

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, SQLAlchemy 2.0, Alembic |
| Vector DB | PostgreSQL 16 + pgvector |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 (384-dim) |
| LLM | Ollama (local) |
| Frontend | Streamlit |
| Auth | python-jose (JWT), bcrypt |
| Testing | pytest, httpx |
| Infrastructure | Docker Compose |
