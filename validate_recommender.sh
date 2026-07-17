#!/usr/bin/env bash
# End-to-end recommendation validation.
#
# This wrapper deliberately uses seed_and_validate.py. Creating empty sessions alone
# cannot produce different learner profiles; the Python validator inserts differentiated
# execution and hint history before checking recommendation divergence.
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if ! curl --fail --silent --show-error "$BASE/health" >/dev/null; then
  echo "API is not reachable at $BASE. Start it first with:" >&2
  echo "  uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload" >&2
  exit 1
fi

if [[ ! -s artifacts/recommender/bi_encoder.json || \
      ! -s artifacts/recommender/problem_embeddings.json || \
      ! -s artifacts/recommender/problem_index.json ]]; then
  echo "Recommendation artifacts are missing. Train them first with:" >&2
  echo "  uv run python -m app.ml.train_recommender --epochs 30" >&2
  exit 1
fi

exec uv run python "$ROOT_DIR/seed_and_validate.py"
