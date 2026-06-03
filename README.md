# Receipt Tracker — Backend

FastAPI backend for receipt scanning, storage, and price comparison.

## Setup

### 1. Install dependencies

```bash
make install
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (Supabase transaction pooler recommended) |
| `AI_PROVIDER` | `openai` or `anthropic` |
| `OPENAI_API_KEY` | Required when `AI_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | Required when `AI_PROVIDER=anthropic` |
| `FRONTEND_URL` | URL of the Next.js frontend (for CORS) |

**Supabase connection string** — use the **Transaction** pooler (port 6543), not the Session pooler:
```
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-1-us-east-2.pooler.supabase.com:6543/postgres
```

### 3. Apply schema

```bash
make migrate
```

Safe to re-run — all statements are idempotent (`IF NOT EXISTS` / `ON CONFLICT DO NOTHING`).

### 4. Start the server

```bash
make dev
```

API runs at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## Commands

| Command | Description |
|---|---|
| `make install` | Create virtualenv and install dependencies |
| `make migrate` | Apply `schema.sql` to the configured database |
| `make dev` | Start the API server with hot reload |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/ocr` | Extract receipt data from images (base64) |
| `POST` | `/receipts` | Save a confirmed receipt |
| `GET` | `/receipts` | List receipts (filter by store, date, category) |
| `GET` | `/receipts/{id}` | Get a single receipt with all items |
| `GET` | `/compare?item=` | Compare prices across stores for an item |
| `POST` | `/analyse` | AI-generated buying recommendation |
| `GET` | `/health` | Health check |

## Switching AI providers

Change `AI_PROVIDER` in `.env` — no code changes needed:

```bash
# Use OpenAI
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Use Anthropic
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

## Security

### What's in place

| Area | Implementation |
|---|---|
| **CORS** | Origins split from `FRONTEND_URL` env var (comma-separated); methods restricted to `GET, POST`; headers restricted to `Content-Type` |
| **Rate limiting** | `POST /ocr` → 10 req/min per IP; `POST /analyse` → 10 req/min per IP (via slowapi) |
| **Image size** | Each base64-encoded image capped at 5 MB; 413 returned if exceeded |
| **Input validation** | All Pydantic string fields have `max_length` (e.g. item name → 300, store name → 200, address → 300) |
| **Category enum** | `category` field accepts only the 18 known slugs — invalid values rejected by Pydantic |
| **Query param limits** | `?store=` capped at 200 chars; `?date_from=` / `?date_to=` capped at 10 chars and validated as `YYYY-MM-DD` |
| **Compare results** | `/compare` query capped at 100 rows |
| **Exception handler** | Global handler catches unhandled errors and returns `{"detail": "An internal error occurred"}` — no stack traces leak to clients |
| **DB connection pool** | `pool_size=5`, `max_overflow=10`, `pool_pre_ping=True` |
| **Docker user** | Container runs as a non-root `app` system user |
| **Secrets** | `.env` excluded from git via `.gitignore`; never committed |

### `FRONTEND_URL` format

To allow multiple origins (e.g. local dev + production), use a comma-separated value:

```bash
FRONTEND_URL=http://localhost:3000,https://your-app.vercel.app
```

### What's not yet implemented

See `.claude/plans/security-todo.md` for the outstanding items (authentication, soft deletes, etc.).
