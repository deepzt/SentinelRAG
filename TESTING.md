# SentinelRAG — Step-by-Step Testing Guide

This guide walks you through setting up and manually testing every feature of SentinelRAG from scratch. Follow the sections in order on a first run.

---

## Prerequisites

| Requirement | Version | Check |
|---|---|---|
| Docker Desktop | 4.x+ | `docker --version` |
| Docker Compose | v2+ | `docker compose version` |
| 4 GB free RAM | — | For pgvector + backend + frontend |
| Port 8000, 8501, 5432 free | — | Nothing else running on these ports |

---

## Part 1 — First-Time Setup

### Step 1.1 — Create your `.env` file

```bash
cp .env.example .env
```

Generate a real secret key and paste it in:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Open `.env` and replace `CHANGE_ME_generate_a_real_secret` with the output.

**Your `.env` should look like:**
```
POSTGRES_USER=sentinelrag
POSTGRES_PASSWORD=sentinelrag_secret
POSTGRES_DB=sentinelrag_db
DATABASE_URL=postgresql+asyncpg://sentinelrag:sentinelrag_secret@localhost:5432/sentinelrag_db
SECRET_KEY=abc123...your_generated_key_here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
ENVIRONMENT=development
```

### Step 1.2 — Build and start all services

```bash
docker compose up --build
```

Wait until you see all three services ready:
- `sentinelrag_db` — `database system is ready to accept connections`
- `sentinelrag_backend` — `Application startup complete`
- `sentinelrag_frontend` — `You can now view your Streamlit app`

> First build takes 3–5 minutes (downloads images, installs Python packages, downloads the embedding model).

### Step 1.3 — Run database migrations

Open a **new terminal** in the project root:

```bash
docker compose exec backend alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, Initial schema
```

### Step 1.4 — Seed demo users and access policies

```bash
docker compose exec backend python -m app.scripts.seed_db
```

Expected output:
```
  [create] user 'alice' (role=engineer)
  [create] user 'bob' (role=hr)
  [create] user 'charlie' (role=manager)
  [create] policy engineer → engineering (internal)
  [create] policy hr → hr (internal,confidential)
  [create] policy manager → engineering (internal)
  [create] policy manager → hr (internal)
  [create] policy manager → legal (internal)
Seed complete.
```

### Step 1.5 — Ingest sample enterprise documents

```bash
docker compose exec backend python -m app.scripts.ingest_samples
```

Expected output (abridged):
```
INFO  Ingesting: AWS Incident Response Runbook
INFO  'AWS Incident Response Runbook' → 8 chunks
INFO  Ingested 'AWS Incident Response Runbook' → 8 chunks [dept=engineering, role=engineer]
...
INFO  Ingested 8 documents / ~55 chunks
INFO  Total embedded chunks in DB: 55
INFO  Index status: {'action': 'skipped', 'reason': '...minimum 50...'}
```

> The ivfflat index is skipped for small datasets (flat scan is faster). That's expected.

---

## Part 2 — Verify Services Are Running

Open these URLs and confirm each responds:

| Service | URL | Expected |
|---|---|---|
| Backend health | http://localhost:8000/health | `{"status":"ok","service":"sentinelrag-backend"}` |
| API docs | http://localhost:8000/docs | Swagger UI with 5 endpoints |
| Frontend | http://localhost:8501 | SentinelRAG login page |

If any service is not responding, check logs:
```bash
docker compose logs backend --tail=50
docker compose logs frontend --tail=50
```

---

## Part 3 — Login Page Tests

Open **http://localhost:8501** in your browser.

### Test 3.1 — Wrong password shows a clear error

1. Enter username: `alice`, password: `wrongpassword`
2. Click **Sign In**
3. **Expected:** Red error message "Invalid username or password." — no stack trace, no technical details

### Test 3.2 — Empty field validation

1. Leave both fields blank, click **Sign In**
2. **Expected:** "Please enter both username and password." — form does not submit

### Test 3.3 — Quick login buttons (demo accounts)

1. Expand the **"Demo accounts"** section at the bottom of the login page
2. Click **"Alice — Engineer"**
3. **Expected:** Instantly logs in as Alice and redirects to the chat page

---

## Part 4 — Alice (Engineer) Chat Tests

After logging in as Alice, you should see:
- Sidebar: username `alice`, blue `ENGINEER` badge, department `platform`
- No "Analytics Dashboard" button (engineers don't have admin access)

### Test 4.1 — Alice sees engineering docs

Type this query and press Enter:

```
What are the steps to roll back an ECS service in production?
```

**Expected:**
- Answer contains rollback procedure steps
- Citations section shows cards like:
  ```
  [1] AWS Incident Response Runbook — ECS Service Rollback Procedure
      engineering / runbook · relevance: 94%
  ```
- No HR or Legal documents cited
- `access_decision` is `allowed` in the backend (verify via: `http://localhost:8000/docs` → `/admin/audit-report`)

### Test 4.2 — Alice is blocked from HR content

```
What is the employee leave policy?
```

**Expected:**
- Orange warning banner: "No accessible documents found for your query."
- No citations
- No HR document content appears anywhere on the page

### Test 4.3 — Alice tries another engineering query

```
What is the deployment procedure for microservices?
```

**Expected:** Answer with citations from `Microservice Deployment Checklist` and/or `AWS Deployment SOP`

### Test 4.4 — Alice cannot access admin page

1. In the browser address bar, navigate to: `http://localhost:8501/admin`
2. **Expected:** Warning "Analytics dashboard is only available to managers and admins. Your role is **engineer**." — page stops, no charts rendered

---

## Part 5 — Bob (HR) Chat Tests

1. Click **Sign Out** in the sidebar
2. On the login page, click **"Bob — HR"**
3. Confirm sidebar shows: `BOB`, pink `HR` badge, department `people_ops`

### Test 5.1 — Bob sees HR docs

```
What is the process for submitting an expense reimbursement?
```

**Expected:** Answer with citations from `Expense Reimbursement SOP` (hr / sop)

### Test 5.2 — Bob is blocked from engineering content

```
How do I roll back a failed AWS ECS deployment?
```

**Expected:** Orange denied banner — no engineering runbook content, no AWS-related citations

### Test 5.3 — Bob asking about onboarding

```
What happens on a new hire's first day?
```

**Expected:** Answer with citations from `New Hire Onboarding Checklist` (hr / checklist)

### Test 5.4 — Bob cannot access admin

Navigate to `http://localhost:8501/admin`

**Expected:** Access denied warning — page stops immediately, no charts rendered

---

## Part 6 — Charlie (Manager) Chat Tests

1. Sign out, log in as **"Charlie — Manager"**
2. Confirm sidebar shows: green `MANAGER` badge
3. Confirm **"Analytics Dashboard"** button appears in the sidebar

### Test 6.1 — Charlie sees engineering docs

```
What are the AWS incident response steps for a SEV1 outage?
```

**Expected:** Citations from `AWS Incident Response Runbook`

### Test 6.2 — Charlie sees HR docs

```
What is the parental leave policy?
```

**Expected:** Citations from `Employee Leave Policy 2026`

### Test 6.3 — The RBAC demo scenario

Run the same query for both roles:

**As Bob (HR):**
```
What is the employee onboarding process?
```
→ HR onboarding checklist citations

**As Alice (Engineer):** *(sign out, log in as Alice)*
```
What is the employee onboarding process?
```
→ Orange denied banner — Alice cannot see HR content

**As Charlie (Manager):** *(sign out, log in as Charlie)*
```
What is the employee onboarding process?
```
→ Citations from both HR checklist AND potentially engineering onboarding steps

> This is the key portfolio demo: **same query, different results per role**.

### Test 6.4 — Charlie accesses the Analytics Dashboard

1. Click **"Analytics Dashboard"** in the sidebar
2. **Expected:**
   - 5 metric cards: Total Queries, Allowed, Denied, Allow Rate, Avg Latency
   - Bar chart showing queries by day (should have activity from your tests)
   - "Recent Denied Queries" table showing Bob's and Alice's denied queries
   - "Most Recent Queries" table with the full query log

---

## Part 7 — Edge Case Tests

### Test 7.1 — Very long query

In the chat input, paste a query over 500 characters (the input box caps at 2000):

```
I need comprehensive information about the complete step-by-step process for rolling back a failed deployment in our AWS ECS production environment, including all the specific AWS CLI commands, how to check the deployment status, how to verify the rollback was successful, what to look for in CloudWatch, and what to do if the rollback itself fails. Please include all relevant monitoring steps and escalation procedures.
```

**Expected:** Query submits normally, layout doesn't break, answer returned

### Test 7.2 — Empty query prevention

Click the chat input and press Enter without typing anything.

**Expected:** Nothing happens — `st.chat_input` prevents empty submissions natively

### Test 7.3 — Session expiry simulation

1. Log in as any user
2. In `.env`, change `ACCESS_TOKEN_EXPIRE_MINUTES=1` and restart: `docker compose restart backend`
3. Wait 2 minutes, then type a query
4. **Expected:** Redirected to login page with "Your session has expired" banner

> Reset `ACCESS_TOKEN_EXPIRE_MINUTES=60` and restart again when done.

### Test 7.4 — Backend offline handling

1. Stop the backend: `docker compose stop backend`
2. On the login page, try to log in
3. **Expected:** "Cannot connect to backend. Is the server running?" — no crash
4. Restart: `docker compose start backend`

---

## Part 8 — API Direct Tests (Swagger UI)

Open **http://localhost:8000/docs** to test endpoints directly.

### Test 8.1 — Login via API

1. Click `POST /auth/login` → **Try it out**
2. Body: `{"username": "alice", "password": "alice123"}`
3. Execute
4. **Expected 200:** `{"access_token": "...", "token_type": "bearer", "expires_in": 3600}`
5. Copy the `access_token`

### Test 8.2 — RBAC via API (Bob cannot see engineering docs)

1. Click **Authorize** (top right), paste Bob's token
2. Login as Bob first via `POST /auth/login` with `{"username": "bob", "password": "bob123"}`
3. Then call `POST /query` with `{"query": "AWS ECS rollback steps"}`
4. **Expected:** `"access_decision": "denied"`, `"citations": []`, `"chunks_retrieved": 0`

### Test 8.3 — Audit log confirms denied request was logged

1. Login as Charlie (manager): `{"username": "charlie", "password": "charlie123"}`
2. Authorize with Charlie's token
3. Call `GET /admin/audit-report`
4. **Expected:** The denied queries from Bob's tests appear in the `items` list with `"access_decision": "denied"`

### Test 8.4 — Engineer blocked from admin endpoint

1. Authorize with Alice's token
2. Call `GET /admin/audit-report`
3. **Expected 403:** `{"detail": "Admin access required"}`

---

## Part 9 — Reset for a Clean Demo

To wipe all data and start fresh (e.g., before a demo or screenshot session):

```bash
# Stop everything
docker compose down

# Remove the database volume
docker volume rm sentinelrag_postgres_data

# Restart fresh
docker compose up --build -d

# Re-run setup (wait ~30 seconds for DB to start)
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed_db
docker compose exec backend python -m app.scripts.ingest_samples
```

---

## Part 10 — What to Screenshot for the README

| Screenshot | How to take it | README label |
|---|---|---|
| Login page with demo accounts expanded | Open http://localhost:8501, expand demo section | `login-page` |
| Alice's chat with engineering citations | Log in as Alice, ask "AWS rollback steps" | `alice-engineering-chat` |
| Bob's denied access banner | Log in as Bob, ask "AWS rollback steps" | `bob-denied-access` |
| Charlie's analytics dashboard | Log in as Charlie, click Analytics Dashboard | `admin-dashboard` |
| Side-by-side RBAC demo | Screenshot both Alice and Bob responses to same query | `rbac-demo-comparison` |

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| `Cannot connect to backend` on login | Backend not started | `docker compose up backend` |
| Login succeeds but chat returns errors | Migrations not run | `docker compose exec backend alembic upgrade head` |
| All queries return "No accessible documents" | Ingestion not run | `docker compose exec backend python -m app.scripts.ingest_samples` |
| Citations empty even after ingestion | Embedding model not downloaded yet | Wait 1–2 min after first ingest, model downloads on first run |
| `pgvector` extension error | Old Postgres image | Ensure image is `pgvector/pgvector:pg16` in docker-compose.yml |
| Port already in use | Another app on 8000/8501/5432 | `docker compose down` then check `lsof -i :8000` |
| Frontend shows placeholder pages | Old Docker image cached | `docker compose build --no-cache frontend` |

---

## Demo Script (2-minute recruiter walkthrough)

1. **Open** http://localhost:8501 — show login page with role table
2. **Click "Alice — Engineer"** — login, show ENGINEER badge in sidebar
3. **Ask:** "What are the ECS rollback steps?" — show citations from engineering runbook
4. **Sign out → Click "Bob — HR"** — show HR badge
5. **Ask the same question** — show orange denied banner (no engineering docs)
6. **Ask:** "What is the expense reimbursement process?" — show HR citations
7. **Sign out → Click "Charlie — Manager"** — show MANAGER badge + Analytics button
8. **Click "Analytics Dashboard"** — show the audit log chart with Bob's denied queries highlighted
9. **Point to the audit table** — "Every denied request is logged. This is enterprise-grade."
