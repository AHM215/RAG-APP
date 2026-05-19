"""
Full RAG evaluation using RAGAS plus deterministic metrics.

Measures retrieval quality (context_precision, context_recall, recall@k, MRR@k)
and generation quality (faithfulness, answer_relevancy, answer_correctness).

Usage:
  python eval/run_eval.py \
    --gold eval/gold/project_1.jsonl \
    --base-url http://localhost:8000 \
    --metrics faithfulness answer_relevancy context_precision \
    --top-k 5 \
    --output eval/reports/eval_{timestamp}.json

Notes:
  - context_recall and answer_correctness require reference_answer in gold file.
  - Each metric triggers LLM judge calls — cost scales with num_queries x num_metrics.
  - OPENAI_API_KEY (or COHERE_API_KEY) must be set in environment.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from helpers.config import get_settings
settings = get_settings()

# ---------------------------------------------------------------------------
# Cohere embeddings wrapper for RAGAS 0.4.x
# ---------------------------------------------------------------------------
import cohere
from ragas.embeddings.base import BaseRagasEmbedding
from typing import List, Optional

class CohereEmbeddings(BaseRagasEmbedding):
    def __init__(self, api_key: str, model: str = "embed-multilingual-light-v3.0"):
        super().__init__()
        self.client = cohere.Client(api_key=api_key)
        self.model = model

    def embed_text(self, text: str, **kwargs) -> List[float]:
        input_type = kwargs.get("input_type", "search_query")
        resp = self.client.embed(
            model=self.model,
            texts=[text],
            input_type=input_type,
            embedding_types=["float"],
        )
        return resp.embeddings.float[0]

    def embed_query(self, text: str, **kwargs) -> List[float]:
        return self.embed_text(text, input_type="search_query")

    def embed_documents(self, texts: List[str], **kwargs) -> List[List[float]]:
        resp = self.client.embed(
            model=self.model,
            texts=texts,
            input_type="search_document",
            embedding_types=["float"],
        )
        return resp.embeddings.float

    async def aembed_text(self, text: str, **kwargs) -> List[float]:
        import asyncio
        return await asyncio.to_thread(self.embed_text, text, **kwargs)


class _RateLimitTransport(httpx.HTTPTransport):
    """Simple client-side pacing to avoid provider rate limits."""

    def __init__(self, delay_s: float = 1.0, **kwargs):
        super().__init__(**kwargs)
        self._delay_s = float(delay_s)
        self._last_request_at = 0.0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        now = time.monotonic()
        elapsed = now - self._last_request_at
        if elapsed < self._delay_s:
            time.sleep(self._delay_s - elapsed)
        self._last_request_at = time.monotonic()
        return super().handle_request(request)

# ---------------------------------------------------------------------------
# RAGAS imports (0.4.x compatible)
# ---------------------------------------------------------------------------
try:
    from datasets import Dataset
    from openai import OpenAI
    from ragas import evaluate as ragas_evaluate
    from ragas.llms import llm_factory
    from ragas.embeddings import OpenAIEmbeddings as RagasOpenAIEmbeddings
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
        answer_correctness,
    )

    METRIC_MAP = {
        "faithfulness": faithfulness,
        "answer_relevancy": answer_relevancy,
        "context_precision": context_precision,
        "context_recall": context_recall,
        "answer_correctness": answer_correctness,
    }
    HAS_RAGAS = True
except ImportError:
    METRIC_MAP = {}
    HAS_RAGAS = False

NEEDS_REFERENCE = {"context_recall", "answer_correctness"}

# ---------------------------------------------------------------------------
# Deterministic metric helpers
# ---------------------------------------------------------------------------


def recall_at_k(retrieved_ids: list[int], relevant_ids: list[int], k: int) -> float | None:
    if not relevant_ids:
        return None
    retrieved_top_k = set(x for x in retrieved_ids[:k] if x is not None)
    relevant = set(relevant_ids)
    return len(retrieved_top_k & relevant) / len(relevant)


def mrr_at_k(retrieved_ids: list[int], relevant_ids: list[int], k: int) -> float | None:
    if not relevant_ids:
        return None
    relevant = set(relevant_ids)
    for rank, chunk_id in enumerate(retrieved_ids[:k], start=1):
        if chunk_id in relevant:
            return 1.0 / rank
    return 0.0


def dcg_at_k(relevance_scores: list[float], k: int) -> float:
    return sum(((2 ** rel) - 1) / math.log2(rank + 1) for rank, rel in enumerate(relevance_scores[:k], start=1))


def ndcg_at_k(retrieved_ids: list[int], relevance_by_chunk_id: dict[str, int], k: int) -> float | None:
    if not relevance_by_chunk_id:
        return None
    gains = [float(relevance_by_chunk_id.get(str(chunk_id), 0)) for chunk_id in retrieved_ids[:k]]
    ideal_gains = sorted([float(s) for s in relevance_by_chunk_id.values()], reverse=True)
    ideal_dcg = dcg_at_k(ideal_gains, k)
    if ideal_dcg == 0:
        return 0.0
    return dcg_at_k(gains, k) / ideal_dcg


def duplicate_context_rate(contexts: list[str]) -> float:
    if not contexts:
        return 0.0
    normalized = [c.strip().lower() for c in contexts]
    return 1.0 - (len(set(normalized)) / len(normalized))


def mean_present(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return round(sum(present) / len(present), 4)


def percentile(values: list[float | None], pct: float) -> float | None:
    present = sorted(v for v in values if v is not None)
    if not present:
        return None
    idx = min(round((pct / 100) * (len(present) - 1)), len(present) - 1)
    return round(present[idx], 2)


def is_success(row: dict) -> bool:
    return (
        row.get("faithfulness", 0) >= 0.75
        and row.get("answer_relevancy", 0) >= 0.75
        and row.get("context_precision", 0) >= 0.60
        and (row.get("_recall_at_k") is None or row.get("_recall_at_k", 0) >= 0.70)
    )


def success_rate(per_query_rows: list[dict]) -> float:
    if not per_query_rows:
        return 0.0
    return sum(1 for row in per_query_rows if is_success(row)) / len(per_query_rows)


def slice_scores(records: list[dict], metric_name: str, metadata_key: str) -> dict[str, float | None]:
    groups = defaultdict(list)
    for row in records:
        metadata = row.get("_metadata", {}) or {}
        group = metadata.get(metadata_key, "unknown")
        groups[group].append(row.get(metric_name))
    return {group: mean_present(values) for group, values in groups.items()}


def compare_score_blocks(base_scores: dict, candidate_scores: dict) -> dict:
    metric_names = sorted(set(base_scores) | set(candidate_scores))
    deltas = {}
    for metric in metric_names:
        base_value = base_scores.get(metric)
        candidate_value = candidate_scores.get(metric)
        if base_value is None or candidate_value is None:
            deltas[metric] = None
            continue
        deltas[metric] = round(candidate_value - base_value, 4)
    return deltas


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


async def timed_post_with_retry(
    client: httpx.AsyncClient,
    url: str,
    payload: dict,
    timeout: int,
    max_retries: int = 3,
    initial_delay: float = 2.0,
) -> tuple[dict, float]:
    """POST with exponential backoff for 500/429 errors."""
    delay = initial_delay
    last_error = None

    for attempt in range(1, max_retries + 1):
        t0 = time.perf_counter()
        try:
            resp = await client.post(url, json=payload, timeout=timeout)
            latency_ms = (time.perf_counter() - t0) * 1000

            if resp.status_code in (429, 500, 502, 503, 504):
                if attempt == max_retries:
                    resp.raise_for_status()
                print(f"[RETRY] {resp.status_code} from {url}, waiting {delay:.0f}s (attempt {attempt}/{max_retries})")
                await asyncio.sleep(delay)
                delay *= 2
                continue

            resp.raise_for_status()
            return resp.json(), round(latency_ms, 2)

        except (httpx.HTTPError, OSError) as exc:
            last_error = exc
            if attempt == max_retries:
                raise
            print(f"[RETRY] {exc}, waiting {delay:.0f}s (attempt {attempt}/{max_retries})")
            await asyncio.sleep(delay)
            delay *= 2

    raise last_error


async def batch_search_queries(
    client: httpx.AsyncClient,
    base_url: str,
    project_id: int,
    queries: list[str],
    limit: int,
    candidates_n: int,
    top_k: int,
    query_adapter: str,
    rerank: str,
    max_retries: int = 3,
) -> list[dict]:
    """Call /index/batch-search for all queries in one request (single Cohere embed call)."""
    payload = {
        "queries": queries,
        "limit": limit,
        "candidates_n": candidates_n,
        "top_k": top_k,
        "query_adapter": query_adapter,
        "rerank": rerank,
    }
    url = f"{base_url}/api/v1/nlp/index/batch-search/{project_id}"
    data, _ = await timed_post_with_retry(
        client, url, payload, timeout=120, max_retries=max_retries
    )
    return data.get("results", [])


async def fetch_answer(
    client: httpx.AsyncClient,
    base_url: str,
    project_id: int,
    query: str,
    candidates_n: int,
    top_k: int,
    query_adapter: str,
    rerank: str,
    max_retries: int = 3,
) -> dict:
    """Call /index/answer for the final generated answer."""
    payload = {
        "text": query,
        "limit": top_k,
        "candidates_n": candidates_n,
        "top_k": top_k,
        "query_adapter": query_adapter,
        "rerank": rerank,
    }
    answer_url = f"{base_url}/api/v1/nlp/index/answer/{project_id}"
    answer_data, answer_latency_ms = await timed_post_with_retry(
        client, answer_url, payload, timeout=120, max_retries=max_retries
    )
    return {
        "answer": answer_data.get("answer", ""),
        "answer_latency_ms": answer_latency_ms,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main(args: argparse.Namespace) -> None:
    if not HAS_RAGAS:
        raise SystemExit(
            "RAGAS is not installed. Run: cd src && poetry add --group eval ragas datasets langchain-openai langchain-cohere"
        )

    gold_rows = [json.loads(l) for l in Path(args.gold).read_text().splitlines() if l.strip()]

    selected_metric_names = args.metrics
    needs_reference = bool(NEEDS_REFERENCE & set(selected_metric_names))
    selected_metrics = [METRIC_MAP[m] for m in selected_metric_names if m in METRIC_MAP]

    records: list[dict[str, Any]] = []
    skipped: list[str] = []
    failed: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        # Batch search all queries in ONE request (single Cohere embed call)
        all_queries = [row["query"] for row in gold_rows]
        print(f"\nBatch searching {len(all_queries)} queries (1 Cohere embed call)...")
        try:
            batch_results = await batch_search_queries(
                client=client,
                base_url=args.base_url,
                project_id=gold_rows[0]["project_id"],
                queries=all_queries,
                limit=args.top_k,
                candidates_n=args.candidates_n,
                top_k=args.top_k,
                query_adapter=args.query_adapter,
                rerank=args.rerank,
                max_retries=args.max_retries,
            )
        except httpx.HTTPError as e:
            print(f"[ERROR] Batch search failed: {e}")
            return

        for i, row in enumerate(gold_rows):
            if needs_reference and not row.get("reference_answer"):
                skipped.append(row["id"])
                continue

            search_result = batch_results[i] if i < len(batch_results) else {}
            contexts = [r.get("text", "") for r in search_result.get("results", [])]
            retrieved_chunk_ids = [r.get("chunk_id") for r in search_result.get("results", [])]
            scores = [r.get("score") for r in search_result.get("results", [])]
            rerank_scores = [r.get("rerank_score") for r in search_result.get("results", [])]

            try:
                answer_result = await fetch_answer(
                    client=client,
                    base_url=args.base_url,
                    project_id=row["project_id"],
                    query=row["query"],
                    candidates_n=args.candidates_n,
                    top_k=args.top_k,
                    query_adapter=args.query_adapter,
                    rerank=args.rerank,
                    max_retries=args.max_retries,
                )
            except httpx.HTTPError as e:
                print(f"[WARN] HTTP error for query {row['id']}: {e}")
                failed.append({"id": row.get("id"), "project_id": row.get("project_id"), "query": row.get("query"), "error": str(e)})
                continue
            except Exception as e:
                print(f"[WARN] Unexpected error for query {row['id']}: {e}")
                failed.append({"id": row.get("id"), "project_id": row.get("project_id"), "query": row.get("query"), "error": str(e)})
                continue

            if args.delay_between_queries > 0:
                await asyncio.sleep(args.delay_between_queries)

            retrieved_ids = retrieved_chunk_ids
            relevant_ids = row.get("relevant_chunk_ids", [])

            record: dict[str, Any] = {
                "user_input": row["query"],
                "response": answer_result["answer"],
                "retrieved_contexts": contexts,
            }
            if row.get("reference_answer"):
                record["reference"] = row["reference_answer"]

            record["_id"] = row["id"]
            record["_retrieved_chunk_ids"] = retrieved_chunk_ids
            record["_relevant_chunk_ids"] = relevant_ids
            record["_metadata"] = row.get("metadata", {})

            record["_recall_at_k"] = recall_at_k(retrieved_ids, relevant_ids, args.top_k)
            record["_mrr_at_k"] = mrr_at_k(retrieved_ids, relevant_ids, args.top_k)
            record["_duplicate_context_rate"] = duplicate_context_rate(contexts)
            record["_search_latency_ms"] = None
            record["_answer_latency_ms"] = answer_result.get("answer_latency_ms")
            record["_ndcg_at_k"] = ndcg_at_k(retrieved_ids, row.get("relevance_by_chunk_id", {}), args.top_k)

            records.append(record)

    if not records:
        print("No eligible rows. Check reference_answer fields or server connection.")
        return

    ragas_records = [{k: v for k, v in r.items() if not k.startswith("_")} for r in records]
    dataset = Dataset.from_list(ragas_records)

    transport = _RateLimitTransport(delay_s=1.0)
    http_client = httpx.Client(transport=transport)
    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_API_URL,
        http_client=http_client,
    )
    llm = llm_factory(args.judge_model, client=client)

    if "embed-" in args.judge_embedding_model:
        embeddings = CohereEmbeddings(api_key=settings.COHERE_API_KEY, model=args.judge_embedding_model)
    else:
        embeddings = RagasOpenAIEmbeddings(client=client, model=args.judge_embedding_model)

    print(f"\nRunning RAGAS evaluation on {len(records)} queries with {len(selected_metric_names)} metrics...")
    ragas_result = ragas_evaluate(
        dataset,
        metrics=selected_metrics,
        llm=llm,
        embeddings=embeddings,
        raise_exceptions=False,
        batch_size=1,
    )

    scores_df = ragas_result.to_pandas()

    for m in selected_metric_names:
        if m in scores_df.columns:
            for i, row in enumerate(records):
                row[m] = float(scores_df[m].iloc[i])

    aggregate = {m: round(float(scores_df[m].mean()), 4) for m in selected_metric_names if m in scores_df.columns}

    deterministic_scores = {
        "recall_at_k": mean_present([r.get("_recall_at_k") for r in records]),
        "mrr_at_k": mean_present([r.get("_mrr_at_k") for r in records]),
        "ndcg_at_k": mean_present([r.get("_ndcg_at_k") for r in records]),
        "duplicate_context_rate": mean_present([r.get("_duplicate_context_rate") for r in records]),
        "search_latency_ms": mean_present([r.get("_search_latency_ms") for r in records]),
        "answer_latency_ms": mean_present([r.get("_answer_latency_ms") for r in records]),
        "empty_retrieval_rate": mean_present([1.0 if not r.get("retrieved_contexts") else 0.0 for r in records]),
    }

    latency_scores = {
        "search_latency_p50_ms": percentile([r.get("_search_latency_ms") for r in records], 50),
        "search_latency_p95_ms": percentile([r.get("_search_latency_ms") for r in records], 95),
        "answer_latency_p50_ms": percentile([r.get("_answer_latency_ms") for r in records], 50),
        "answer_latency_p95_ms": percentile([r.get("_answer_latency_ms") for r in records], 95),
    }

    locale_scores = {
        "faithfulness_by_locale": slice_scores(records, "faithfulness", "locale"),
        "recall_at_k_by_locale": slice_scores(records, "_recall_at_k", "locale"),
    }

    difficulty_scores = {
        "faithfulness_by_difficulty": slice_scores(records, "faithfulness", "difficulty"),
        "recall_at_k_by_difficulty": slice_scores(records, "_recall_at_k", "difficulty"),
    }

    error_rate = len(failed) / max(len(gold_rows), 1)

    env_snapshot = {
        "EMBEDDING_BACKEND": os.getenv("EMBEDDING_BACKEND", ""),
        "EMBEDDING_MODEL_ID": os.getenv("EMBEDDING_MODEL_ID", ""),
        "GENERATION_BACKEND": os.getenv("GENERATION_BACKEND", ""),
        "GENERATION_MODEL_ID": os.getenv("GENERATION_MODEL_ID", ""),
        "VECTOR_DB_BACKEND": os.getenv("VECTOR_DB_BACKEND", ""),
        "RERANKER_MODE": os.getenv("RERANKER_MODE", args.rerank),
        "RERANKER_MODEL": os.getenv("RERANKER_MODEL", ""),
        "QUERY_ADAPTER_MODE": os.getenv("QUERY_ADAPTER_MODE", args.query_adapter),
        "CONTEXT_TOP_K": os.getenv("CONTEXT_TOP_K", str(args.top_k)),
    }

    per_query_rows = []
    for r in records:
        per_query_row = {
            "id": r["_id"],
            "user_input": r["user_input"],
            "response": r["response"],
        }
        for m in selected_metric_names:
            per_query_row[m] = r.get(m)
        per_query_row["recall_at_k"] = r.get("_recall_at_k")
        per_query_row["mrr_at_k"] = r.get("_mrr_at_k")
        per_query_row["ndcg_at_k"] = r.get("_ndcg_at_k")
        per_query_row["duplicate_context_rate"] = r.get("_duplicate_context_rate")
        per_query_row["search_latency_ms"] = r.get("_search_latency_ms")
        per_query_row["answer_latency_ms"] = r.get("_answer_latency_ms")
        per_query_rows.append(per_query_row)

    output = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "gold_file": args.gold,
        "base_url": args.base_url,
        "config": {
            "query_adapter": args.query_adapter,
            "rerank": args.rerank,
            "candidates_n": args.candidates_n,
            "top_k": args.top_k,
        },
        "num_queries": len(records),
        "num_failed": len(failed),
        "num_skipped": len(skipped),
        "error_rate": round(error_rate, 4),
        "metrics_requested": selected_metric_names,
        "env": env_snapshot,
        "scores": {
            "ragas": aggregate,
            "deterministic": deterministic_scores,
            "latency": latency_scores,
            "locale": locale_scores,
            "difficulty": difficulty_scores,
            "answer_success_rate": success_rate(records),
        },
        "failed": failed,
        "skipped": skipped,
        "per_query": per_query_rows,
    }

    out_path = Path(args.output or f"eval/reports/eval_{datetime.now():%Y%m%d_%H%M%S}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    print("\n=== Aggregate RAGAS scores ===")
    print(json.dumps(aggregate, indent=2))
    print("\n=== Deterministic scores ===")
    print(json.dumps(deterministic_scores, indent=2))
    print("\n=== Latency (p50/p95) ===")
    print(json.dumps(latency_scores, indent=2))
    print(f"\nAnswer success rate: {success_rate(records):.2%}")
    print(f"Error rate: {error_rate:.2%} ({len(failed)} failed, {len(skipped)} skipped)")
    print(f"\nFull report saved: {out_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate mini-RAG pipeline with RAGAS + deterministic metrics.")
    parser.add_argument("--gold", required=True, help="Path to gold JSONL file")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--metrics",
        nargs="+",
        default=["faithfulness", "answer_relevancy"],
        choices=list(METRIC_MAP.keys()) if METRIC_MAP else ["faithfulness", "answer_relevancy", "context_precision", "context_recall", "answer_correctness"],
    )
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks returned and passed to LLM context")
    parser.add_argument("--candidates-n", type=int, default=20, help="Number of first-stage candidates for reranking")
    parser.add_argument("--query-adapter", choices=["none", "rewrite", "hyde"], default="none")
    parser.add_argument("--rerank", choices=["none", "cross_encoder", "llm"], default="none")
    parser.add_argument("--judge-model", default="gpt-4o-mini", help="LLM model for RAGAS judging")
    parser.add_argument("--judge-embedding-model", default="text-embedding-3-small", help="Embedding model for RAGAS")
    parser.add_argument("--max-retries", type=int, default=3, help="Max retries for 500/429 errors per query")
    parser.add_argument("--delay-between-queries", type=float, default=0.0, help="Pause between queries (seconds)")
    parser.add_argument("--output", default=None)
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
