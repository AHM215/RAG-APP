"""
Generate reviewable candidate gold rows from indexed mini-RAG chunks.

The output is intentionally a candidate JSONL file. Review and edit rows before
copying accepted examples into eval/gold/project_<id>.jsonl.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import asyncpg


DEFAULT_ENV_FILE = Path("docker/env/.env.app")


@dataclass(frozen=True)
class Chunk:
    id: int
    text: str
    metadata: dict[str, Any]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def build_database_url(args: argparse.Namespace) -> str:
    if args.database_url:
        return args.database_url

    env_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DATABASE_URL")
    if env_url:
        return env_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    required = [
        "POSTGRES_USERNAME",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_MAIN_DATABASE",
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise SystemExit(
            "Missing database settings: "
            + ", ".join(missing)
            + ". Pass --database-url or provide docker/env/.env.app."
        )

    return (
        f"postgresql://{os.environ['POSTGRES_USERNAME']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}"
        f"/{os.environ['POSTGRES_MAIN_DATABASE']}"
    )


async def fetch_chunks(
    database_url: str,
    project_id: int,
    limit: int,
    min_chars: int,
) -> list[Chunk]:
    conn = await asyncpg.connect(database_url)
    try:
        rows = await conn.fetch(
            """
            SELECT id, chunk_text, chunk_metadata
            FROM data_chunks
            WHERE chunk_project_id = $1
              AND length(chunk_text) >= $2
            ORDER BY random()
            LIMIT $3
            """,
            project_id,
            min_chars,
            limit,
        )
    finally:
        await conn.close()

    return [
        Chunk(
            id=int(row["id"]),
            text=str(row["chunk_text"]),
            metadata=dict(row["chunk_metadata"] or {}),
        )
        for row in rows
    ]


def build_qdrant_url(args: argparse.Namespace) -> str:
    qdrant_url = args.qdrant_url or os.getenv("QDRANT_URL") or os.getenv("VECTOR_DB_PATH")
    if not qdrant_url:
        raise SystemExit(
            "Missing Qdrant URL. Pass --qdrant-url or set VECTOR_DB_PATH/QDRANT_URL."
        )
    return qdrant_url


def build_qdrant_collection_name(args: argparse.Namespace) -> str:
    if args.qdrant_collection:
        return args.qdrant_collection

    vector_size = args.embedding_size or os.getenv("EMBEDDING_MODEL_SIZE")
    if not vector_size:
        raise SystemExit(
            "Missing Qdrant collection name. Pass --qdrant-collection or provide --embedding-size/EMBEDDING_MODEL_SIZE."
        )
    return f"collection_{vector_size}_{args.project_id}"


def fetch_chunks_from_qdrant_sync(
    qdrant_url: str,
    collection_name: str,
    limit: int,
    min_chars: int,
    seed: int | None,
    scan_limit: int,
) -> list[Chunk]:
    from qdrant_client import QdrantClient

    client = QdrantClient(url=qdrant_url)
    points, _ = client.scroll(
        collection_name=collection_name,
        limit=scan_limit,
        with_payload=True,
        with_vectors=False,
    )

    chunks = []
    for point in points:
        payload = point.payload or {}
        text = str(payload.get("text") or "")
        if len(text) < min_chars:
            continue

        chunk_id = payload.get("chunk_id") or point.id
        try:
            chunk_id = int(chunk_id)
        except (TypeError, ValueError):
            continue

        metadata = payload.get("metadata") or {}
        chunks.append(Chunk(id=chunk_id, text=text, metadata=dict(metadata)))

    rng = random.Random(seed)
    rng.shuffle(chunks)
    return chunks[:limit]


async def fetch_chunks_from_qdrant(
    qdrant_url: str,
    collection_name: str,
    limit: int,
    min_chars: int,
    seed: int | None,
    scan_limit: int,
) -> list[Chunk]:
    return await asyncio.to_thread(
        fetch_chunks_from_qdrant_sync,
        qdrant_url,
        collection_name,
        limit,
        min_chars,
        seed,
        scan_limit,
    )


async def fetch_source_chunks(args: argparse.Namespace) -> list[Chunk]:
    if args.source == "postgres":
        database_url = build_database_url(args)
        return await fetch_chunks(database_url, args.project_id, args.chunks, args.min_chars)

    qdrant_url = build_qdrant_url(args)
    collection_name = build_qdrant_collection_name(args)
    return await fetch_chunks_from_qdrant(
        qdrant_url=qdrant_url,
        collection_name=collection_name,
        limit=args.chunks,
        min_chars=args.min_chars,
        seed=args.seed,
        scan_limit=args.qdrant_scan_limit,
    )


def extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start_candidates = [idx for idx in [text.find("["), text.find("{")] if idx != -1]
    if not start_candidates:
        raise ValueError("LLM response did not contain JSON")

    start = min(start_candidates)
    end = max(text.rfind("]"), text.rfind("}"))
    if end < start:
        raise ValueError("LLM response contained incomplete JSON")

    return json.loads(text[start : end + 1])


def normalize_examples(raw: Any) -> list[dict[str, str]]:
    if isinstance(raw, dict):
        if isinstance(raw.get("examples"), list):
            raw = raw["examples"]
        else:
            raw = [raw]

    if not isinstance(raw, list):
        raise ValueError("LLM JSON must be an object or list of objects")

    examples = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        query = str(item.get("query", "")).strip()
        answer = str(item.get("reference_answer", "")).strip()
        difficulty = str(item.get("difficulty", "medium")).strip().lower()
        if query and answer:
            examples.append(
                {
                    "query": query,
                    "reference_answer": answer,
                    "difficulty": difficulty if difficulty in {"easy", "medium", "hard"} else "medium",
                }
            )
    return examples


def build_prompt(chunk: Chunk, questions_per_chunk: int, locale: str) -> str:
    return f"""
Create {questions_per_chunk} candidate evaluation example(s) from the document chunk below.

Rules:
- The question must be answerable using only this chunk.
- The reference_answer must be concise and fully supported by this chunk.
- Do not invent names, dates, policies, numbers, or facts.
- Avoid generic questions like "What is this document about?".
- Write the question and answer in locale/language: {locale}.
- Return JSON only, as an array of objects with keys: query, reference_answer, difficulty.
- difficulty must be one of: easy, medium, hard.

Chunk ID: {chunk.id}
Chunk metadata: {json.dumps(chunk.metadata, ensure_ascii=False)}
Chunk text:
{chunk.text}
""".strip()


async def generate_with_openai(args: argparse.Namespace, prompt: str) -> str:
    from openai import AsyncOpenAI

    client_kwargs: dict[str, Any] = {"api_key": os.getenv("OPENAI_API_KEY")}
    base_url = args.openai_base_url or os.getenv("OPENAI_API_URL")
    if base_url:
        client_kwargs["base_url"] = base_url

    if not client_kwargs["api_key"]:
        raise RuntimeError("OPENAI_API_KEY is required for --provider openai")

    client = AsyncOpenAI(**client_kwargs)
    response = await client.chat.completions.create(
        model=args.model,
        temperature=args.temperature,
        messages=[
            {
                "role": "system",
                "content": "You create grounded RAG evaluation datasets and return strict JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content or ""


async def generate_with_cohere(args: argparse.Namespace, prompt: str) -> str:
    import cohere

    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        raise RuntimeError("COHERE_API_KEY is required for --provider cohere")

    client = cohere.AsyncClientV2(api_key=api_key)
    response = await client.chat(
        model=args.model,
        temperature=args.temperature,
        messages=[
            {
                "role": "system",
                "content": "You create grounded RAG evaluation datasets and return strict JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    return "".join(part.text for part in response.message.content if getattr(part, "text", None))


async def generate_examples(args: argparse.Namespace, chunk: Chunk) -> list[dict[str, str]]:
    prompt = build_prompt(chunk, args.questions_per_chunk, args.locale)
    if args.provider == "openai":
        raw = await generate_with_openai(args, prompt)
    elif args.provider == "cohere":
        raw = await generate_with_cohere(args, prompt)
    else:
        raise ValueError(f"Unsupported provider: {args.provider}")

    return normalize_examples(extract_json(raw))


def make_candidate_row(
    row_id: str,
    project_id: int,
    chunk: Chunk,
    example: dict[str, str],
    args: argparse.Namespace,
) -> dict[str, Any]:
    metadata = {
        "locale": args.locale,
        "difficulty": example["difficulty"],
        "source": "synthetic_llm",
        "reviewed": False,
        "generator_provider": args.provider,
        "generator_model": args.model,
        "chunk_source": args.source,
    }
    if args.include_chunk_metadata:
        metadata["chunk_metadata"] = chunk.metadata

    return {
        "id": row_id,
        "project_id": project_id,
        "query": example["query"],
        "reference_answer": example["reference_answer"],
        "relevant_chunk_ids": [chunk.id],
        "metadata": metadata,
    }


async def run(args: argparse.Namespace) -> None:
    load_env_file(args.env_file)
    chunks = await fetch_source_chunks(args)
    if not chunks:
        raise SystemExit("No chunks found. Check --project-id, source settings, and --min-chars.")

    if args.seed is not None:
        random.seed(args.seed)
        random.shuffle(chunks)

    output_path = args.output or Path(f"eval/gold/project_{args.project_id}.candidates.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows_written = 0
    failures: list[dict[str, Any]] = []
    with output_path.open("w", encoding="utf-8") as output_file:
        for chunk in chunks:
            try:
                examples = await generate_examples(args, chunk)
            except Exception as exc:  # keep generation moving across imperfect chunks/provider hiccups
                failures.append({"chunk_id": chunk.id, "error": str(exc)})
                print(f"[WARN] chunk_id={chunk.id}: {exc}")
                continue

            for example in examples[: args.questions_per_chunk]:
                rows_written += 1
                row = make_candidate_row(
                    row_id=f"q_auto_{rows_written:06d}",
                    project_id=args.project_id,
                    chunk=chunk,
                    example=example,
                    args=args,
                )
                output_file.write(json.dumps(row, ensure_ascii=False) + "\n")

    if failures:
        failure_path = output_path.with_suffix(".failures.json")
        failure_path.write_text(json.dumps(failures, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Failures saved: {failure_path}")

    print(f"Candidate rows written: {rows_written}")
    print(f"Output: {output_path}")
    print("Review this file before copying accepted rows into eval/gold/project_<id>.jsonl.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate candidate RAG gold dataset rows from indexed chunks.")
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument("--chunks", type=int, default=30, help="Number of chunks to sample")
    parser.add_argument("--questions-per-chunk", type=int, default=1)
    parser.add_argument("--min-chars", type=int, default=120)
    parser.add_argument("--locale", default="en")
    parser.add_argument("--provider", choices=["openai", "cohere"], default="openai")
    parser.add_argument("--model", default=None, help="Generator model. Defaults depend on --provider.")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--source", choices=["postgres", "qdrant"], default="postgres")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--qdrant-url", default=None)
    parser.add_argument("--qdrant-collection", default=None)
    parser.add_argument("--qdrant-scan-limit", type=int, default=1000)
    parser.add_argument("--embedding-size", default=None)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--openai-base-url", default=None)
    parser.add_argument("--include-chunk-metadata", action="store_true")
    args = parser.parse_args()

    if args.questions_per_chunk < 1:
        parser.error("--questions-per-chunk must be >= 1")
    if args.chunks < 1:
        parser.error("--chunks must be >= 1")
    if args.model is None:
        args.model = "gpt-4o-mini" if args.provider == "openai" else "command-a-03-2025"

    return args


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
