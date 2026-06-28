# RSS Digest Agent

![CI](https://github.com/vitorcrl/rss-digest-agent/actions/workflows/ci.yml/badge.svg)
[![codecov](https://codecov.io/gh/vitorcrl/rss-digest-agent/branch/main/graph/badge.svg)](https://codecov.io/gh/vitorcrl/rss-digest-agent)

Autonomous agent that consumes RSS feeds, filters articles by relevance using the **Claude API**, generates summaries in Portuguese, and delivers a daily digest via webhook.

Built with Clean Architecture — ports & adapters pattern, fully async, 97% test coverage.

---

## How it works

```
FETCH → DEDUP → FILTER → SUMMARIZE → PERSIST → COMPILE → DELIVER → LOG
```

1. **FETCH** — pulls articles from all active RSS feeds
2. **DEDUP** — drops already-processed articles (SHA-256 of title + URL)
3. **FILTER** — Claude Haiku scores relevance in batch (0–10)
4. **SUMMARIZE** — Claude Sonnet generates PT-BR summaries for score ≥ threshold
5. **PERSIST** — saves all articles to PostgreSQL
6. **COMPILE** — selects top N by relevance score
7. **DELIVER** — sends webhook with exponential retry (1s → 2s → 4s)
8. **LOG** — records `delivered` or `failed` status

Zero Claude tokens used when there are no relevant articles.

---

## Architecture

Ports & adapters (Dependency Inversion). The pipeline is decoupled from its implementations — swap any adapter without touching business logic.

```
app/
├── core/          # config (.env) and async database engine
├── domain/        # SQLAlchemy models + enums
├── repositories/  # data access (Feed, Article, DigestRun)
├── services/      # rss, ai, digest, delivery
├── api/v1/        # FastAPI routes + Pydantic schemas
└── scheduler/     # daily cron job
migrations/        # Alembic async migrations
tests/
├── unit/          # 67 tests, no database required
└── integration/   # 9 tests, require PostgreSQL
```

---

## Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI |
| Database | PostgreSQL 16 + SQLAlchemy 2 async + asyncpg |
| AI | Anthropic Claude API (Haiku + Sonnet) |
| Scheduler | APScheduler (daily at 07h São Paulo) |
| Migrations | Alembic |
| Infra | Docker Compose |
| CI | GitHub Actions (unit + integration jobs) |
| Coverage | Codecov |

---

## CI/CD

Two separate jobs on every pull request — both required to merge:

- **Unit Tests** — 67 tests, no external dependencies, runs in ~36s
- **Integration Tests** — 9 tests against a real PostgreSQL 16 container

Branch protection enforces green CI before merge.

---

## Quick start

```bash
cp .env.example .env
# fill in ANTHROPIC_API_KEY and DELIVERY_WEBHOOK_URL

docker compose up --build
```

App runs on port `8000`. Migrations run automatically on startup.

### Local (without Docker)

```bash
poetry install
alembic upgrade head
uvicorn app.main:app --reload
```

---

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/feeds` | Register an RSS feed |
| `GET` | `/api/v1/feeds` | List all feeds |
| `PATCH` | `/api/v1/feeds/{id}` | Enable/disable a feed |
| `POST` | `/api/v1/digest/run` | Trigger digest manually |
| `GET` | `/api/v1/digest/runs` | List recent runs |
| `GET` | `/api/v1/digest/runs/{id}` | Run details |
| `GET` | `/api/v1/articles` | List articles (filters: `run_date`, `relevant_only`, `feed_id`) |

Interactive docs at `http://localhost:8000/docs`.

---

## Environment variables

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...
DELIVERY_WEBHOOK_URL=https://hooks.slack.com/...

# Optional (defaults shown)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/digest_db
AI_RELEVANCE_MODEL=claude-haiku-4-5-20251001
AI_SUMMARY_MODEL=claude-sonnet-4-6
AI_MIN_RELEVANCE_SCORE=6
AI_MAX_ARTICLES_PER_DIGEST=10
DELIVERY_RETRY_ATTEMPTS=3
DIGEST_CRON_HOUR=7
DIGEST_CRON_TIMEZONE=America/Sao_Paulo
```

---

## Tests

```bash
# unit (no database)
pytest tests/unit/ -v

# integration (requires database)
docker compose up -d db
pytest tests/integration/ -v

# all with coverage
pytest tests/ -v --cov=app --cov-branch --cov-report=term-missing
```

Current coverage: **97%** — 67 unit tests + 9 integration tests.