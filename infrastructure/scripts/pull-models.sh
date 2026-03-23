#!/bin/bash
# Pull recommended Ollama models for this node's VRAM profile.
#
# Usage:
#   ./scripts/pull-models.sh 8gb    # 8 GB VRAM profile
#   ./scripts/pull-models.sh 12gb   # 12 GB VRAM profile
#
# Models are pulled into the running ollama container.
# Verify tags at https://ollama.com/library if a pull fails — tags can change.

set -euo pipefail

CONTAINER="${OLLAMA_CONTAINER:-ollama}"

pull() {
  echo ">>> Pulling $1"
  docker exec "$CONTAINER" ollama pull "$1"
}

usage() {
  echo "Usage: $0 [8gb|12gb]"
  exit 1
}

case "${1:-}" in
  8gb)
    echo "== 8 GB VRAM profile =="
    pull qwen2.5-coder:7b      # FIM / autocomplete (5.5 GB)
    pull qwen3.5:9b            # Daily driver (6.6 GB) — verify tag at ollama.com/library
    pull deepseek-r1:8b        # Deep reasoning (5.5 GB)
    ;;
  12gb)
    echo "== 12 GB VRAM profile =="
    pull qwen2.5-coder:14b     # FIM / autocomplete (9 GB)
    pull qwen3.5:9b            # Daily driver — verify tag at ollama.com/library
    pull deepseek-r1:8b        # Deep reasoning (5.5 GB)
    pull gemma3:12b            # Chat alternative (8 GB)
    ;;
  *)
    usage
    ;;
esac

echo ""
echo "Done. Loaded models:"
docker exec "$CONTAINER" ollama list
