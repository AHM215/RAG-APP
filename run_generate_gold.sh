#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/src"

PROJECT_ID="${1:-1}"
LOCALE="${2:-en}"
CHUNKS="${3:-30}"

echo "=== Gold Dataset Generator ==="
echo "Project ID: ${PROJECT_ID}"
echo "Locale:     ${LOCALE}"
echo "Chunks:     ${CHUNKS}"
echo ""

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
