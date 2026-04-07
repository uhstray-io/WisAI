#!/bin/bash
# Send a prompt to Ollama and stream the response to stdout.
#
# Usage:
#   ./scripts/prompt.sh "Your prompt here"
#   ./scripts/prompt.sh --model deepseek-r1:8b "Explain recursion"
#   ./scripts/prompt.sh --model qwen3.5:9b "Summarise this" < file.txt
#
# Environment:
#   OLLAMA_HOST  - Ollama base URL (default: http://localhost:11434)
#   OLLAMA_MODEL - Default model (default: qwen2.5-coder:7b)

set -euo pipefail

HOST="${OLLAMA_HOST:-http://localhost:11434}"
MODEL="${OLLAMA_MODEL:-qwen2.5-coder:7b}"

# Parse --model flag
while [[ $# -gt 0 ]]; do
  case "$1" in
    --model|-m)
      MODEL="$2"
      shift 2
      ;;
    *)
      break
      ;;
  esac
done

# Prompt from argument or stdin
if [[ $# -gt 0 ]]; then
  PROMPT="$*"
elif ! [ -t 0 ]; then
  PROMPT=$(cat)
else
  echo "Usage: $0 [--model <model>] \"<prompt>\""
  echo "       echo \"<prompt>\" | $0 [--model <model>]"
  exit 1
fi

curl -s "$HOST/api/generate" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg model "$MODEL" --arg prompt "$PROMPT" \
    '{model: $model, prompt: $prompt, stream: true}')" \
  | jq -r --unbuffered '.response // empty'
