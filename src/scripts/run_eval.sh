#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${SCRIPT_DIR}/.."

# Load only the env vars needed for eval (avoids parsing errors from brackets/spaces in .env.app)
ENV_FILE="${SCRIPT_DIR}/../../docker/env/.env.app"
if [ -f "${ENV_FILE}" ]; then
  while IFS='=' read -r key value; do
    case "$key" in
      OPENAI_API_KEY|OPENAI_API_URL|COHERE_API_KEY|GENERATION_MODEL_ID|EMBEDDING_MODEL_ID)
        value="${value%%\#*}"
        value="${value//\"/}"
        value="${value//\'/}"
        value="$(echo "$value" | xargs)"
        export "$key=$value"
        ;;
    esac
  done < "$ENV_FILE"
fi

# === Edit these to change models/providers ===
JUDGE_MODEL="${JUDGE_MODEL:-openai/gpt-5.4-mini-2026-03-17}"
OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://lightning.ai/api/v1/}"
JUDGE_EMBEDDING_MODEL="${JUDGE_EMBEDDING_MODEL:-embed-multilingual-light-v3.0}"
# ============================================

GOLD_DIR="eval/gold"

if [ -n "${1:-}" ]; then
  GOLD="${1}"
  if [ ! -f "${GOLD}" ]; then
    echo "Error: gold file not found: ${GOLD}"
    exit 1
  fi
else
  mapfile -t GOLD_FILES < <(find "${GOLD_DIR}" -maxdepth 1 \( -name "*.jsonl" -o -name "*.candidates.jsonl" \) ! -name "*.example" -type f 2>/dev/null | sort)

  if [ ${#GOLD_FILES[@]} -eq 0 ]; then
    echo "No gold or candidate files found in ${GOLD_DIR}/"
    echo "Run ./scripts/run_generate_gold.sh first."
    exit 1
  fi

  echo "=== Available gold files ==="
  for i in "${!GOLD_FILES[@]}"; do
    count=$(wc -l < "${GOLD_FILES[$i]}")
    echo "  [$((i + 1))] ${GOLD_FILES[$i]}  (${count} queries)"
  done
  echo ""

  if [ ${#GOLD_FILES[@]} -eq 1 ]; then
    GOLD="${GOLD_FILES[0]}"
    echo "Auto-selected: ${GOLD}"
  else
    read -rp "Select gold file [1]: " choice
    choice="${choice:-1}"
    idx=$((choice - 1))
    if [ "$idx" -lt 0 ] || [ "$idx" -ge "${#GOLD_FILES[@]}" ]; then
      echo "Invalid selection."
      exit 1
    fi
    GOLD="${GOLD_FILES[$idx]}"
  fi
fi

BASE_URL="${2:-http://localhost:8000}"
METRICS="${3:-faithfulness answer_relevancy}"
QUERY_ADAPTER="${4:-rewrite}"
RERANK="${5:-cross_encoder}"
TOP_K="${6:-5}"
MAX_RETRIES="${MAX_RETRIES:-5}"
DELAY_BETWEEN="${DELAY_BETWEEN:-2}"

echo ""
echo "=== RAG Evaluation Pipeline ==="
echo "Gold file:          ${GOLD}"
echo "Base URL:           ${BASE_URL}"
echo "Metrics:            ${METRICS}"
echo "Query adapter:      ${QUERY_ADAPTER}"
echo "Rerank:             ${RERANK}"
echo "Top K:              ${TOP_K}"
echo "Judge model:        ${JUDGE_MODEL}"
echo "OpenAI base URL:    ${OPENAI_BASE_URL:-default}"
echo "Embedding model:    ${JUDGE_EMBEDDING_MODEL}"
echo "Max retries:        ${MAX_RETRIES}"
echo "Delay between:      ${DELAY_BETWEEN}s"
echo ""

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT="eval/reports/eval_${QUERY_ADAPTER}_${RERANK}_${TIMESTAMP}.json"

CMD="poetry run python eval/run_eval.py \
  --gold \"${GOLD}\" \
  --base-url \"${BASE_URL}\" \
  --metrics ${METRICS} \
  --query-adapter \"${QUERY_ADAPTER}\" \
  --rerank \"${RERANK}\" \
  --top-k \"${TOP_K}\" \
  --judge-model \"${JUDGE_MODEL}\" \
  --judge-embedding-model \"${JUDGE_EMBEDDING_MODEL}\" \
  --max-retries \"${MAX_RETRIES}\" \
  --delay-between-queries \"${DELAY_BETWEEN}\" \
  --output \"${OUTPUT}\""

if [ -n "${OPENAI_BASE_URL}" ]; then
  export OPENAI_API_URL="${OPENAI_BASE_URL}"
fi

export PYTHONPATH="${SCRIPT_DIR}/..:${PYTHONPATH:-}"
eval ${CMD}

echo ""
echo "=== Report saved: ${OUTPUT} ==="
