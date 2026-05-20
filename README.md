# mini-RAG

`mini-RAG` is a small FastAPI-based Retrieval-Augmented Generation service. It can upload and process documents, chunk them into a database, index chunks into a vector store, search relevant context, and generate answers with an LLM.

## Features

- File upload and document processing.
- Chunk storage in PostgreSQL.
- Vector indexing with PGVector or Qdrant.
- OpenAI and Cohere generation/embedding providers.
- Query adaptation with rewrite and HyDE modes.
- Reranking with a cross-encoder or an LLM.
- Celery workers for background processing support.
- Docker Compose stack with PostgreSQL, Redis, RabbitMQ, Prometheus, Grafana, and supporting services.

## Tech Stack

- Python `3.12+`
- FastAPI and Uvicorn
- Poetry
- PostgreSQL with PGVector
- Qdrant
- SQLAlchemy and Alembic
- OpenAI and Cohere SDKs
- LangChain prompt templates
- Sentence Transformers cross-encoders
- Celery, Redis, and RabbitMQ

## Project Layout

```text
mini-RAG/
├── docker/                 # Docker Compose, service configs, env examples
├── src/                    # FastAPI application source
│   ├── controllers/        # Data, processing, and NLP orchestration
│   ├── helpers/            # App settings and shared helpers
│   ├── models/             # Database models and schemas
│   ├── routes/             # API endpoints and request schemas
│   └── stores/             # LLM, vector DB, and template integrations
└── README.md
```

## Requirements

- Python `3.12+`
- Poetry
- Docker and Docker Compose for the full stack
- API keys for the LLM providers you enable

Install OS packages commonly needed by PostgreSQL and Python database dependencies:

```bash
sudo apt update
sudo apt install libpq-dev gcc python3-dev
```

## Quick Start With Docker

Create environment files from the examples:

```bash
cp docker/env/.env.example.app docker/env/.env.app
cp docker/env/.env.example.postgres docker/env/.env.postgres
cp docker/env/.env.example.rabbitmq docker/env/.env.rabbitmq
cp docker/env/.env.example.redis docker/env/.env.redis
cp docker/env/.env.example.grafana docker/env/.env.grafana
cp docker/env/.env.example.postgres-exporter docker/env/.env.postgres-exporter
cp docker/minirag/alembic.example.ini docker/minirag/alembic.ini
```

Update `docker/env/.env.app` with your provider keys and model settings.

Start the stack:

```bash
docker compose -f docker/docker-compose.yml up --build -d
```

If the app starts before the databases are ready, start infrastructure first:

```bash
docker compose -f docker/docker-compose.yml up -d pgvector qdrant redis rabbitmq
docker compose -f docker/docker-compose.yml up --build -d fastapi nginx prometheus grafana
```

Stop and remove containers:

```bash
docker compose -f docker/docker-compose.yml down
```

Remove containers and volumes:

```bash
docker compose -f docker/docker-compose.yml down -v --remove-orphans
```

## Local Development

Create and activate a Python environment:

```bash
conda create -n mini-rag python=3.12
conda activate mini-rag
```

Install dependencies from `src/`:

```bash
cd src
poetry install
```

Make sure `docker/env/.env.app` exists and points to reachable services. The app loads settings from `../docker/env/.env.app` when started from `src/`.

Run database migrations:

```bash
cd src/models/minirag
alembic upgrade head
```

Start the API in development mode:

```bash
cd src
poetry run uvicorn main:app --reload --host 0.0.0.0 --port 5000
```

## Service URLs

- FastAPI via Docker: `http://localhost:8000`
- FastAPI docs: `http://localhost:8000/docs`
- Local development API: `http://localhost:5000`
- Nginx: `http://localhost`
- Qdrant UI: `http://localhost:6333/dashboard`
- RabbitMQ UI: `http://localhost:15672`
- Flower: `http://localhost:5555`
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`

## Configuration

Main application settings live in `docker/env/.env.app`.

Common settings:

```env
GENERATION_BACKEND="OPENAI"
EMBEDDING_BACKEND="COHERE"

OPENAI_API_KEY="..."
OPENAI_API_URL=""
COHERE_API_KEY="..."

GENERATION_MODEL_ID="gpt-4o-mini"
EMBEDDING_MODEL_ID="embed-multilingual-v3.0"
EMBEDDING_MODEL_SIZE=1024

VECTOR_DB_BACKEND="PGVECTOR"
PRIMARY_LANG="en"
DEFAULT_LANG="en"
```

Supported query adapter modes:

- `none`: use the original user query.
- `rewrite`: rewrite the query with the generation model before vector search.
- `hyde`: generate a hypothetical answer paragraph and use it for vector search.

Supported reranker modes:

- `none`: return vector search results directly.
- `cross_encoder`: rerank candidates with a Sentence Transformers cross-encoder.
- `llm`: ask the generation model to rank retrieved passages.

Retrieval settings:

```env
QUERY_ADAPTER_MODE="none"
RERANKER_MODE="none"
RERANKER_MODEL="cross-encoder/ms-marco-MiniLM-L-6-v2"
RETRIEVAL_CANDIDATES_N=20
CONTEXT_TOP_K=5
```

When reranking is enabled, the API retrieves `RETRIEVAL_CANDIDATES_N` vector candidates, reranks them, and returns the final `CONTEXT_TOP_K` documents.

## Offline Evaluation

Offline evaluation lives in `src/eval/` and produces JSON reports under `src/eval/reports/`.

Requirements:

1. mini-RAG must be running (default: `http://localhost:8000`).
1. Install eval deps from `src/`: `poetry install --with eval`

Generate candidate gold rows (LLM-drafted Q/A grounded in sampled chunks):

```bash
cd src
poetry run python eval/generate_gold.py --project-id 1 --locale ar --chunks 30 \
  --output eval/gold/project_1_ar.candidates.jsonl
```

Run evaluation (RAGAS + deterministic retrieval metrics):

```bash
cd src
./scripts/run_eval.sh eval/gold/project_1_ar.candidates.jsonl http://localhost:8000 \
  "faithfulness answer_relevancy" none cross_encoder 5
```

What you get:

1. `scores.ragas`: judge metrics like `faithfulness`, `answer_relevancy`
1. `scores.deterministic`: retrieval metrics like `recall_at_k`, `mrr_at_k`, `duplicate_context_rate`
1. `per_query`: per-question breakdown (useful for debugging regressions)

More details and additional commands are documented in `src/eval/README.md`.

## API Workflow

Use one `project_id` to group uploaded files, chunks, vectors, searches, and answers.

### 1. Health Check

```bash
curl http://localhost:8000/api/v1/
```

### 2. Upload A File

```bash
curl -X POST "http://localhost:8000/api/v1/data/upload/1" \
  -F "file=@./example.txt"
```

The response includes a `file_id`.

### 3. Process Uploaded Files

Process all files in the project:

```bash
curl -X POST "http://localhost:8000/api/v1/data/process/1" \
  -H "Content-Type: application/json" \
  -d '{
    "chunk_size": 100,
    "overlap_size": 20,
    "do_reset": 0
  }'
```

Process a specific uploaded file:

```bash
curl -X POST "http://localhost:8000/api/v1/data/process/1" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID_FROM_UPLOAD",
    "chunk_size": 100,
    "overlap_size": 20,
    "do_reset": 0
  }'
```

### 4. Push Chunks To The Vector Index

```bash
curl -X POST "http://localhost:8000/api/v1/nlp/index/push/1" \
  -H "Content-Type: application/json" \
  -d '{"do_reset": 0}'
```

### 5. Inspect The Vector Index

```bash
curl http://localhost:8000/api/v1/nlp/index/info/1
```

### 6. Search The Index

```bash
curl -X POST "http://localhost:8000/api/v1/nlp/index/search/1" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "What is this document about?",
    "limit": 10,
    "candidates_n": 20,
    "top_k": 5,
    "query_adapter": "rewrite",
    "rerank": "cross_encoder"
  }'
```

Search request fields:

- `text`: user query.
- `limit`: fallback raw vector search limit.
- `candidates_n`: number of vector candidates to fetch before reranking.
- `top_k`: final number of returned documents.
- `query_adapter`: optional override, one of `none`, `rewrite`, or `hyde`.
- `rerank`: optional override, one of `none`, `cross_encoder`, or `llm`.

Search responses include `score` from vector search and may include `rerank_score` when reranking is used.

### 7. Generate A RAG Answer

```bash
curl -X POST "http://localhost:8000/api/v1/nlp/index/answer/1" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "What are the key points?",
    "candidates_n": 20,
    "top_k": 5,
    "query_adapter": "hyde",
    "rerank": "llm"
  }'
```

The response includes:

- `answer`: generated answer.
- `full_prompt`: retrieved context used for the answer.
- `chat_history`: provider-formatted prompt messages.

## Celery Development Commands

Run the worker:

```bash
cd src
poetry run python -m celery -A celery_app worker --queues=default,file_processing,data_indexing --loglevel=info
```

Run the beat scheduler:

```bash
cd src
poetry run python -m celery -A celery_app beat --loglevel=info
```

Run Flower:

```bash
cd src
poetry run python -m celery -A celery_app flower --conf=flowerconfig.py
```

## Troubleshooting

Check container status:

```bash
docker compose -f docker/docker-compose.yml ps
```

View logs:

```bash
docker compose -f docker/docker-compose.yml logs --tail=100 fastapi
docker compose -f docker/docker-compose.yml logs --tail=100 pgvector
docker compose -f docker/docker-compose.yml logs --tail=100 qdrant
```

Restart the API after databases are healthy:

```bash
docker compose -f docker/docker-compose.yml restart fastapi
```

If cross-encoder startup fails, check that `sentence-transformers` is installed and that `RERANKER_MODEL` points to a valid model. If you do not need cross-encoder reranking, set:

```env
RERANKER_MODE="none"
```

If LLM calls fail, verify provider backend names, API keys, model IDs, and network access.

## Notes

- The application expects environment values in `docker/env/.env.app`.
- For Docker-specific details, see `docker/README.md`.
- API documentation is available at `/docs` when FastAPI is running.
