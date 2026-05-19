#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# === Edit these to change models/providers ===
OPENAI_BASE_URL="${OPENAI_BASE_URL:-}"
# ============================================

# === Dynamic candidate file discovery ===
GOLD_DIR="eval/gold"
mapfile -t CANDIDATE_FILES < <(find "${GOLD_DIR}" -maxdepth 1 -name "*.candidates.jsonl" -type f 2>/dev/null | sort)

if [ ${#CANDIDATE_FILES[@]} -gt 0 ]; then
  echo "=== Existing candidate files (review before using as gold) ==="
  for i in "${!CANDIDATE_FILES[@]}"; do
    echo "  [$((i + 1))] ${CANDIDATE_FILES[$i]}"
  done
  echo ""
fi
# ============================================

PROJECT_ID="${1:-1}"
LOCALE="${2:-ar}"
CHUNKS="${3:-30}"

echo "=== Gold Dataset Generator ==="
echo "Project ID:      ${PROJECT_ID}"
echo "Locale:          ${LOCALE}"
echo "Chunks:          ${CHUNKS}"
echo "OpenAI base URL: ${OPENAI_BASE_URL:-default}"
echo ""

if [ -n "${OPENAI_BASE_URL}" ]; then
  export OPENAI_API_URL="${OPENAI_BASE_URL}"
fi

poetry run python eval/generate_gold.py \
  --project-id "${PROJECT_ID}" \
  --locale "${LOCALE}" \
  --chunks "${CHUNKS}" \
  --questions-per-chunk 1 \
  --min-chars 120 \
  --source postgres \
  --max-retries 8 \
  --retry-delay 5 \
  --delay-between-chunks 3 \
  --output "eval/gold/project_${PROJECT_ID}_${LOCALE}.candidates.jsonl"
