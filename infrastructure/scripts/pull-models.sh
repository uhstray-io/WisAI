#!/bin/bash
# Pull recommended models for this node's VRAM profile.
#
# Usage:
#   ./scripts/pull-models.sh 8gb    # 8 GB VRAM profile
#   ./scripts/pull-models.sh 12gb   # 12 GB VRAM profile
#   ./scripts/pull-models.sh 16gb   # 16 GB VRAM profile
#
# Models are pulled into the running ollama container.
# 8gb/12gb/16gb profiles use HuggingFace GGUF models (via hf.co/) for
# optimal quantization at each VRAM tier. Ollama's library only ships
# Q4_K_M and Q8_0 — HuggingFace community quantizers (bartowski, unsloth)
# provide the Q5_K_M and Q6_K sweet spots in between.

set -euo pipefail

CONTAINER="${OLLAMA_CONTAINER:-ollama}"

# Use podman if docker is not available
if command -v docker &>/dev/null; then
  RUNTIME="docker"
elif command -v podman &>/dev/null; then
  RUNTIME="podman"
else
  echo "Error: neither docker nor podman found in PATH" && exit 1
fi

pull() {
  echo ">>> Pulling $1"
  "$RUNTIME" exec "$CONTAINER" ollama pull "$1"
}

usage() {
  echo "Usage: $0 [8gb|12gb|16gb]"
  exit 1
}

case "${1:-}" in
  8gb)
    echo "== 8 GB VRAM profile (Q5_K_M where possible) =="
    pull hf.co/bartowski/Qwen2.5.1-Coder-7B-Instruct-GGUF:Q5_K_M    # FIM / autocomplete (5.4 GB)
    pull hf.co/unsloth/Qwen3.5-9B-GGUF:Q4_K_M                       # Daily driver (5.7 GB) — Q5 too tight at 8GB
    pull hf.co/bartowski/deepseek-ai_DeepSeek-R1-0528-Qwen3-8B-GGUF:Q5_K_M  # Deep reasoning (5.9 GB)
    ;;
  12gb)
    echo "== 12 GB VRAM profile (Q5_K_M / Q6_K) =="
    pull hf.co/bartowski/Qwen2.5-Coder-14B-Instruct-GGUF:Q5_K_M     # FIM / autocomplete (10.5 GB)
    pull hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q6_K                  # Daily driver (7.7 GB)
    pull hf.co/unsloth/DeepSeek-R1-0528-Qwen3-8B-GGUF:Q6_K          # Deep reasoning (6.7 GB)
    pull hf.co/bartowski/google_gemma-3-12b-it-GGUF:Q5_K_M           # Chat alternative (8.4 GB)
    ;;
  16gb)
    echo "== 16 GB VRAM profile (Q6_K / Q8_0) =="
    pull hf.co/bartowski/Qwen2.5-Coder-14B-Instruct-GGUF:Q6_K       # FIM / autocomplete (12.1 GB)
    pull qwen3.5:9b-q8_0                                             # Daily driver (9.6 GB) — Ollama tag is fine here
    pull hf.co/bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF:Q6_K     # Deep reasoning (12.1 GB)
    pull hf.co/bartowski/phi-4-GGUF:Q6_K                             # Chat alternative (12.0 GB)
    ;;
  *)
    usage
    ;;
esac

echo ""
echo "Done. Loaded models:"
"$RUNTIME" exec "$CONTAINER" ollama list
