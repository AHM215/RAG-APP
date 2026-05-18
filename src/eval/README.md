# Evaluation Data

This folder contains offline evaluation helpers and local gold datasets for mini-RAG.

## Generate Candidate Gold Rows

Use `generate_gold.py` to sample indexed chunks from PostgreSQL/PGVector or Qdrant and ask an LLM to draft grounded question/answer pairs.

The script uses the project's `LLMProviderFactory` and `get_settings()`, so it reads `GENERATION_BACKEND`, `GENERATION_MODEL_ID`, `OPENAI_API_KEY`, `OPENAI_API_URL`, and `COHERE_API_KEY` directly from `docker/env/.env.app`.

```bash
cd src
python eval/generate_gold.py \
  --project-id 1 \
  --source postgres \
  --chunks 30 \
  --questions-per-chunk 1 \
  --output eval/gold/project_1.candidates.jsonl
```

You can also pass a database DSN directly:

```bash
cd src
python eval/generate_gold.py \
  --project-id 1 \
  --source postgres \
  --database-url postgresql://user:password@localhost:5432/minirag \
  --chunks 30 \
  --output eval/gold/project_1.candidates.jsonl
```

To sample from Qdrant instead, use `--source qdrant`. The script reads `VECTOR_DB_PATH` and `EMBEDDING_MODEL_SIZE` from `docker/env/.env.app` by default and builds the mini-RAG collection name as `collection_<embedding_size>_<project_id>`.

```bash
cd src
python eval/generate_gold.py \
  --project-id 1 \
  --source qdrant \
  --qdrant-url http://localhost:6333 \
  --embedding-size 1024 \
  --chunks 30 \
  --output eval/gold/project_1.candidates.jsonl
```

If your collection name is different, pass it directly:

```bash
cd src
python eval/generate_gold.py \
  --project-id 1 \
  --source qdrant \
  --qdrant-collection collection_1024_1
```

## Review Before Use

Generated rows are candidates, not trusted gold data. Review every row before copying accepted examples into `eval/gold/project_1.jsonl`.

Check that each row:

- Is answerable from the listed `relevant_chunk_ids`.
- Has a concise `reference_answer` supported by the chunk.
- Does not contain invented facts.
- Is not too generic, such as `What is this document about?`.
- Matches the intended `locale` and `difficulty`.

After review, set metadata to reflect that status, for example:

```json
{"source":"synthetic_reviewed","reviewed":true}
```

## Gold JSONL Shape

Each accepted line should look like this:

```json
{"id":"q001","project_id":1,"query":"What is the refund policy?","reference_answer":"Digital products are non-refundable after download.","relevant_chunk_ids":[12],"metadata":{"locale":"en","difficulty":"easy","source":"manual"}}
```

Real `eval/gold/*.jsonl` files are gitignored because they may contain private project content. Commit only `*.jsonl.example` templates.
