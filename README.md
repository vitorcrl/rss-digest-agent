# RSS Digest Agent

Agente autônomo que consome feeds RSS de tecnologia, filtra artigos por relevância usando a **Claude API**, gera resumos em português e entrega um digest diário via webhook.

---

## O que ele faz

1. Lê feeds RSS cadastrados (Hacker News, InfoQ, etc.)
2. Avalia relevância de cada artigo com **Claude Haiku** (score 0–10)
3. Gera resumos em PT-BR com **Claude Sonnet** para os artigos acima do threshold
4. Entrega um digest diário via webhook (Slack ou qualquer endpoint HTTP)
5. Persiste todo o histórico no PostgreSQL — sem reprocessar o que já foi visto

---

## Stack

- **FastAPI** — API REST
- **SQLAlchemy 2 async** + **asyncpg** + **PostgreSQL 16** — persistência
- **Anthropic Claude API** — relevância (Haiku) e resumos (Sonnet)
- **APScheduler** — cron diário às 07h (America/Sao_Paulo)
- **Alembic** — migrations
- **Docker Compose** — infra local

---

## Estrutura

```
app/
├── core/          # config (.env) e database (engine async)
├── domain/        # models SQLAlchemy + enums
├── repositories/  # acesso ao banco (Feed, Article, DigestRun)
├── services/      # rss, ai, digest, delivery
├── api/v1/        # rotas FastAPI + schemas Pydantic
└── scheduler/     # cron job diário
migrations/        # Alembic (versões e env.py async)
tests/
├── unit/          # 66 testes, sem banco
└── integration/   # 3 testes, requerem PostgreSQL
```

---

## Variáveis de ambiente

Copie `.env.example` para `.env` e preencha:

```env
# Obrigatórias
ANTHROPIC_API_KEY=sk-ant-...
DELIVERY_WEBHOOK_URL=https://hooks.slack.com/...

# Opcionais (valores padrão mostrados)
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

## Como rodar

### Docker (recomendado)

```bash
cp .env.example .env
# preencha ANTHROPIC_API_KEY e DELIVERY_WEBHOOK_URL

docker compose up --build
```

A aplicação sobe na porta `8000`. As migrations rodam automaticamente na inicialização.

### Local (sem Docker)

```bash
cp .env.example .env

poetry install
alembic upgrade head
uvicorn app.main:app --reload
```

---

## API

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/api/v1/feeds` | Cadastra um feed RSS |
| `GET` | `/api/v1/feeds` | Lista todos os feeds |
| `PATCH` | `/api/v1/feeds/{id}` | Ativa/desativa um feed |
| `POST` | `/api/v1/digest/run` | Dispara o digest manualmente |
| `GET` | `/api/v1/digest/runs` | Lista execuções recentes |
| `GET` | `/api/v1/digest/runs/{id}` | Detalhe de uma execução |
| `GET` | `/api/v1/articles` | Lista artigos (filtros: `run_date`, `relevant_only`, `feed_id`) |

Documentação interativa em `http://localhost:8000/docs`.

---

## Testes

```bash
# unitários (sem banco)
pytest tests/unit/ -v

# integração (requer banco)
docker compose up -d db
pytest tests/integration/ -v

# todos com cobertura
pytest tests/ -v --cov=app --cov-report=term-missing
```

Cobertura atual: **97%** (66 testes unitários + 3 de integração).

---

## Pipeline de digest

```
FETCH → DEDUP → FILTER → SUMMARIZE → PERSIST → COMPILE → DELIVER → LOG
```

1. **FETCH** — puxa artigos de todos os feeds ativos
2. **DEDUP** — descarta artigos já processados (SHA-256 do título+URL)
3. **FILTER** — Claude Haiku avalia relevância em batch (score 0–10)
4. **SUMMARIZE** — Claude Sonnet gera resumo PT-BR para score ≥ threshold
5. **PERSIST** — salva todos os artigos no banco
6. **COMPILE** — seleciona os top N por relevância
7. **DELIVER** — envia webhook com retry exponencial (1s, 2s, 4s)
8. **LOG** — registra status `delivered` ou `failed`
