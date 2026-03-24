# AI of Qumta — Product Intelligence Platform

A production-grade **FastAPI** backend for an AI-powered product intelligence platform.
Built with a Laravel-inspired layered architecture: Models → Repositories → Services → API.

---

## Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.115+ |
| ORM | SQLAlchemy 2.0 async (asyncpg) |
| Validation | Pydantic v2 |
| Auth | JWT via python-jose + bcrypt |
| Task Queue | Celery 5 + Redis |
| Storage | Abstract driver — Local or AWS S3 |
| Migrations | Alembic |
| Tests | pytest-asyncio + httpx |

---

## Laravel → FastAPI Layer Map

| Laravel concept | FastAPI equivalent |
|---|---|
| `app/Models/` | `app/models/` (SQLAlchemy ORM) |
| `app/Http/Requests/` | `app/schemas/` (Pydantic) |
| Eloquent Repository | `app/repositories/` |
| `app/Services/` | `app/services/` |
| `routes/api.php` | `app/api/v1/router.py` |
| `app/Http/Controllers/` | `app/api/v1/*.py` route functions |
| Middleware | FastAPI `Depends()` in `app/core/dependencies.py` |
| `config/*.php` | `app/core/config.py` (pydantic-settings) |
| `bootstrap/app.php` | `app/main.py` `create_app()` |
| Queued Jobs | `app/tasks/*.py` (Celery tasks) |
| Custom Exceptions | `app/core/exceptions.py` |

---

## Quick Start

### 1. Clone & install dependencies

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set DATABASE_URL, DATABASE_URL_SYNC, SECRET_KEY, etc.
```

### 3. Set up PostgreSQL

```sql
CREATE DATABASE qumta_db;
```

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Start the API server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at: `http://localhost:8000/docs`

### 6. Start the Celery worker

```bash
celery -A app.tasks.celery_app worker --loglevel=info
```

---

## pgvector Setup (optional — for AI product matching)

1. Install the PostgreSQL pgvector extension:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

2. In `app/models/product_alias.py`, uncomment the embedding column:
   ```python
   # embedding: Mapped[Vector | None] = mapped_column(Vector(1536), nullable=True)
   ```
   → Remove the leading `#`.

3. Generate and apply a new migration:
   ```bash
   alembic revision --autogenerate -m "add_product_alias_embedding"
   alembic upgrade head
   ```

---

## Project Structure

```
app/
├── main.py                  # App factory (lifespan, middleware, routers)
├── core/
│   ├── config.py            # Settings (pydantic-settings)
│   ├── database.py          # Async SQLAlchemy engine + session
│   ├── security.py          # JWT + password helpers
│   ├── exceptions.py        # Custom exception hierarchy
│   ├── response.py          # Standardised JSON envelope helpers
│   └── dependencies.py      # FastAPI Depends() callables
├── models/                  # SQLAlchemy 2.0 ORM models
├── schemas/                 # Pydantic v2 I/O schemas
├── repositories/            # Data-access layer (BaseRepository + domain repos)
├── services/                # Business logic layer
├── api/
│   └── v1/                  # REST endpoint modules
├── ai/
│   ├── interfaces/          # Abstract base classes for AI components
│   ├── parsers/             # Document parsers (stubs — plug in your LLM)
│   └── pipelines/           # Orchestration pipelines (stubs)
├── storage/
│   ├── base.py              # StorageDriver ABC
│   ├── local_driver.py      # Local filesystem driver
│   └── s3_driver.py         # AWS S3 driver
├── tasks/
│   ├── celery_app.py        # Celery configuration
│   ├── document_tasks.py
│   ├── product_tasks.py
│   └── price_tasks.py
└── utils/
    ├── slugify.py
    ├── file_helpers.py
    ├── pagination.py
    └── datetime_helpers.py

alembic/
├── env.py                   # Async-compatible Alembic env
└── versions/                # Migration files

tests/
├── conftest.py              # Fixtures (in-memory SQLite)
├── test_product_service.py
├── test_product_repository.py
└── test_product_api.py
```

---

## Running Tests

```bash
pytest -v
```

Tests use an in-memory SQLite database — no running Postgres or Redis required.

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | postgresql+asyncpg://... | Async DB URL (used by the app) |
| `DATABASE_URL_SYNC` | postgresql+psycopg2://... | Sync DB URL (used by Alembic) |
| `SECRET_KEY` | change-this | JWT signing secret |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 60 | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 30 | Refresh token TTL |
| `ENABLE_TOKEN_BLACKLIST` | true | Enable Redis-backed token revocation |
| `REDIS_URL` | redis://localhost:6379/0 | Redis broker URL |
| `STORAGE_DRIVER` | local | `local` or `s3` |
| `STORAGE_LOCAL_PATH` | storage/uploads | Base path for local storage |
| `AWS_ACCESS_KEY_ID` | | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | | AWS credentials |
| `AWS_DEFAULT_REGION` | us-east-1 | S3 region |
| `AWS_S3_BUCKET` | qumta-uploads | S3 bucket name |
| `OPENAI_API_KEY` | | OpenAI key for AI parsers |
| `EMBEDDING_DIMENSIONS` | 1536 | Vector embedding size |

---

## Multi-Tenancy

Every tenant-scoped model carries `org_id` (FK → `organizations`) and `owner_id` (FK → `users`).
`BaseRepository` automatically filters all queries by `org_id`, ensuring complete data isolation
between organizations without any per-query boilerplate.

---

## Implementing AI Parsers

The `app/ai/parsers/` stubs return empty data. Replace the `parse()` method body with your
preferred extraction strategy:

- **LLM extraction** — send the file text to OpenAI / Anthropic and parse the JSON response.
- **PDF/OCR** — use `pdfplumber`, `pytesseract`, or an Azure Form Recognizer call.
- **Structured files** — use `pandas` for CSV/Excel price lists.

Each parser returns a normalized dict; the pipeline layer handles persistence.
