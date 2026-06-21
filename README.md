# RSS Digest Agent

Agente autônomo que consome feeds RSS de tecnologia, filtra artigos por relevância usando a **Claude API**, gera resumos em português e entrega um digest diário via webhook.

> Em desenvolvimento — pipeline core completo, faltam rotas, scheduler e Docker.

---

## O que ele faz

1. Lê feeds RSS cadastrados (Hacker News, InfoQ, etc.)
2. Avalia relevância de cada artigo com Claude Haiku (score 0–10)
3. Gera resumos em PT-BR com Claude Sonnet para os artigos acima do threshold
4. Entrega um digest diário via webhook (Slack ou qualquer endpoint HTTP)
5. Persiste todo o histórico no PostgreSQL — sem reprocessar o que já foi visto

---

## Stack

- **FastAPI** — API REST
- **SQLAlchemy 2 async** + **PostgreSQL** — persistência
- **Anthropic Claude API** — relevância e resumos
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
```

---

## Variáveis de ambiente

Copie `.env.example` para `.env` e preencha:

```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/digest_db

ANTHROPIC_API_KEY=sk-ant-...

DELIVERY_WEBHOOK_URL=https://hooks.slack.com/...
```

As demais variáveis têm valores padrão razoáveis — veja `.env.example` para a lista completa.

---

## Como rodar

```bash
cp .env.example .env
# preencha ANTHROPIC_API_KEY e DELIVERY_WEBHOOK_URL

docker-compose up --build
```