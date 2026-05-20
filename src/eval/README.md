# Evaluation Data

This folder contains offline evaluation helpers and local gold datasets for mini-RAG.

## Install Dependencies

```bash
cd src
poetry install --with eval
```

## Generate Candidate Gold Rows

Use `generate_gold.py` to sample indexed chunks from PostgreSQL/PGVector or Qdrant and ask an LLM to draft grounded question/answer pairs.

```bash
cd src
poetry run python eval/generate_gold.py \
  --project-id 1 \
  --locale en \
  --chunks 30 \
  --output eval/gold/project_1_en.candidates.jsonl
```

Or use the convenience script:

```bash
./scripts/run_generate_gold.sh 1 en 30
```

## Run Evaluation

Make sure mini-RAG is running first (`http://localhost:8000`).

```bash
cd src
poetry run python eval/run_eval.py \
  --gold eval/gold/project_1.jsonl \
  --base-url http://localhost:8000 \
  --metrics faithfulness answer_relevancy context_precision \
  --query-adapter none \
  --rerank none \
  --top-k 5 \
  --output eval/reports/baseline.json
```

Or use the convenience script:

```bash
# Baseline: no adapter, no reranker
./scripts/run_eval.sh eval/gold/project_1.jsonl http://localhost:8000 "faithfulness answer_relevancy" none none 5

# With cross-encoder reranker
./scripts/run_eval.sh eval/gold/project_1.jsonl http://localhost:8000 "faithfulness answer_relevancy context_precision" none cross_encoder 5

# With query rewrite
./scripts/run_eval.sh eval/gold/project_1.jsonl http://localhost:8000 "faithfulness answer_relevancy context_precision" rewrite none 5
```

Notes:

1. `run_eval.py` uses the API for search + answer generation, so the server must be running.
1. The API also exposes `POST /api/v1/nlp/index/batch-search/{project_id}` to embed all eval queries in one call (helps avoid Cohere 429s).

## Compare Reports

```bash
cd src
poetry run python eval/compare_runs.py \
  eval/reports/eval_none_none_20250101_120000.json \
  eval/reports/eval_none_cross_encoder_20250101_120500.json
```

## Suggested Baselines

Run eval with each pipeline config and compare:

| Config | Command |
|--------|---------|
| `adapter=none`, `rerank=none` | `./scripts/run_eval.sh ... none none 5` |
| `adapter=rewrite`, `rerank=none` | `./scripts/run_eval.sh ... rewrite none 5` |
| `adapter=hyde`, `rerank=none` | `./scripts/run_eval.sh ... hyde none 5` |
| `adapter=none`, `rerank=cross_encoder` | `./scripts/run_eval.sh ... none cross_encoder 5` |
| `adapter=rewrite`, `rerank=cross_encoder` | `./scripts/run_eval.sh ... rewrite cross_encoder 5` |
| `adapter=none`, `rerank=llm` | `./scripts/run_eval.sh ... none llm 5` |

## Report Output Shape

Each run produces a JSON report with:

```json
{
  "run_at": "2025-01-01T12:00:00+00:00",
  "gold_file": "eval/gold/project_1.jsonl",
  "base_url": "http://localhost:8000",
  "config": {"query_adapter": "none", "rerank": "none", "candidates_n": 20, "top_k": 5},
  "num_queries": 30,
  "num_failed": 0,
  "error_rate": 0.0,
  "scores": {
    "ragas": {"faithfulness": 0.85, "answer_relevancy": 0.90},
    "deterministic": {"recall_at_k": 0.80, "mrr_at_k": 0.75},
    "latency": {"search_latency_p50_ms": 120.5, "answer_latency_p50_ms": 2500.0},
    "locale": {"faithfulness_by_locale": {"en": 0.85, "ar": 0.78}},
    "difficulty": {"faithfulness_by_difficulty": {"easy": 0.92, "medium": 0.80}},
    "answer_success_rate": 0.83
  },
  "per_query": [...]
}
```

## Metric Targets

| Metric | Minimum | Good |
|--------|---------|------|
| `faithfulness` | > 0.75 | > 0.90 |
| `answer_relevancy` | > 0.75 | > 0.90 |
| `context_precision` | > 0.60 | > 0.80 |
| `context_recall` | > 0.65 | > 0.85 |
| `recall_at_k` | > 0.70 | > 0.90 |
| `mrr_at_k` | > 0.60 | > 0.85 |
| `duplicate_context_rate` | < 0.20 | < 0.10 |
| `empty_retrieval_rate` | 0.00 | 0.00 |
