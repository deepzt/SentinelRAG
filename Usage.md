# Usage Guide

Step-by-step instructions for getting SentinelRAG running and testing it with all three demo personas.

---

## 1. Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- [Ollama](https://ollama.com/) installed locally with `llama3.1:latest` pulled:

```bash
ollama pull llama3.1:latest
```

> If `llama3.1` is unavailable, the system automatically falls back to `gemma4:e2b`. Pull that instead with `ollama pull gemma4:e2b`.

---

## 2. Start the Stack

```bash
git clone https://github.com/deepzt/SentinelRAG.git
cd SentinelRAG

# Copy environment file (edit SECRET_KEY to a random value for production)
cp .env.example .env

# Build and start all three services (DB, backend, frontend)
docker compose up --build
```

Wait until you see:
```
sentinelrag_backend  | INFO:     Application startup complete.
sentinelrag_frontend | You can now view your Streamlit app in your browser.
```

Services available at:
- **Chat UI:** http://localhost:8501
- **Backend API:** http://localhost:8000
- **API docs (Swagger):** http://localhost:8000/docs

---

## 3. Seed the Database

Run once after the first `docker compose up`:

```bash
# Create demo users (alice, bob, charlie) and access policies
docker compose exec backend python -m app.scripts.seed_db

# Ingest the 8 sample enterprise documents into pgvector
docker compose exec backend python -m app.scripts.ingest_samples
```

Expected output from `ingest_samples`:
```
INFO  Found 8 documents in manifest
INFO  Ingested : 8 documents / 139 chunks
INFO  Total embedded chunks in DB: 139
INFO  Index status: {'action': 'created', ...}
INFO  Done.
```

If you see `Skipped: 8 documents — already ingested`, the data is already there. That's fine.

---

## 4. Verify Everything Is Running

```bash
# Check all three containers are healthy
docker compose ps

# Check the database has data
docker compose exec db psql -U sentinelrag -d sentinelrag_db -c \
  "SELECT 'users', COUNT(*) FROM users UNION ALL SELECT 'documents', COUNT(*) FROM documents UNION ALL SELECT 'document_chunks', COUNT(*) FROM document_chunks UNION ALL SELECT 'access_policies', COUNT(*) FROM access_policies;"

# Hit the health endpoint
curl http://localhost:8000/health
```

---

## 5. Demo Users

All passwords are `password123`.

| Username | Role | Department | Document Access |
|----------|------|------------|-----------------|
| `alice` | engineer | platform | Engineering docs only |
| `bob` | hr | people_ops | HR docs (internal + confidential) |
| `charlie` | manager | engineering | Engineering + HR + Legal (internal) |

---

## 6. Example Queries to Test

### Alice — Engineer

Log in as `alice` / `password123`. These queries should return answers with citations:

```
What are the steps to roll back an ECS deployment?
How do I triage a P1 incident on AWS?
What should I check before deploying a microservice to production?
What is the deployment freeze policy?
Who do I escalate to during a database outage?
```

**RBAC denial test** — Alice has no HR access. Ask:
```
How many days of annual leave do I get?
```
Expected: access denied message, zero citations.

---

### Bob — HR

Log in as `bob` / `password123`. These queries should return answers with citations:

```
What types of leave are available to employees?
How do I submit an expense reimbursement?
What happens if I don't submit receipts for reimbursement?
What does a new hire do in their first week?
What is the probation period for new employees?
```

**RBAC denial test** — Bob has no engineering access. Ask:
```
How do I roll back an AWS ECS deployment?
```
Expected: access denied message, zero citations.

---

### Charlie — Manager

Log in as `charlie` / `password123`. Charlie sees engineering + HR + legal documents:

```
Summarize the incident response process
What are the key clauses in our NDA template?
Walk me through the vendor onboarding process
What leave types does the company offer and what are the approval steps?
What are the pre-deployment checklist items for a microservice release?
```

Charlie also has access to the **Analytics dashboard** (Admin tab in the sidebar) which shows query volume, denied access logs, and active users by role.

---

## 7. The Core RBAC Demo

The most compelling demo: send the **same query** as different users and observe the results.

1. Log in as `alice` — ask: `"How do I roll back an ECS deployment?"`  
   → Grounded answer with citations from the AWS Incident Runbook.

2. Log out. Log in as `bob` — ask the same question.  
   → Access denied. No document titles, no content, no hints about what engineering docs exist.

This demonstrates that RBAC is enforced at the SQL/vector-search layer — not just in the UI.

---

## 8. Run the Automated Test Suite

```bash
# Run all 34 tests against the live database
docker compose exec backend pytest tests/ -v

# Run a specific test file
docker compose exec backend pytest tests/test_security.py -v
docker compose exec backend pytest tests/test_query.py -v
docker compose exec backend pytest tests/test_admin.py -v
```

Expected: `34 passed` (runtime ~3-4 minutes — sentence-transformer model loads per test).

---

## 9. Useful Commands

```bash
# View backend logs
docker compose logs backend -f

# View all service logs
docker compose logs -f

# Re-ingest documents (force re-embed)
docker compose exec backend python -m app.scripts.ingest_samples --force

# Access the database directly
docker compose exec db psql -U sentinelrag -d sentinelrag_db

# Stop the stack
docker compose down

# Stop and wipe all data (including the database volume)
docker compose down -v
```

---

## 10. Troubleshooting

**LLM returns "not available — retrieval-only mode"**  
Ollama is not reachable. Make sure Ollama is running locally (`ollama serve`) and that the model is pulled (`ollama pull llama3.1:latest`).

**`ingest_samples` fails with a file not found error**  
Make sure the `docs/sample/` directory is present at the repo root and the volume mount in `docker-compose.yml` points to `./docs/sample:/app/docs/sample:ro`.

**Tests fail with "engineer access policy missing"**  
Run `docker compose exec backend python -m app.scripts.seed_db` before running tests.

**Frontend shows a blank page or connection error**  
Wait ~10 seconds after `docker compose up` — the backend takes a moment to load the sentence-transformer model on first start.
