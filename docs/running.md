# Running WisAI

## Prerequisites

- Docker (Linux/Proxmox) or Podman (Windows) installed
- NVIDIA GPU with drivers installed
- [`jq`](https://jqlang.github.io/jq/download/) installed (used by `scripts/prompt.sh`)
- **Podman on Windows only:** complete the one-time GPU setup in [`docs/podman-gpu-windows.md`](podman-gpu-windows.md)

---

## 1. Start the Stack

```bash
cd infrastructure
cp .env.example .env   # first time only — adjust settings if needed
docker compose up -d   
# or: 
podman compose up -d
```

Verify both containers are running:

```bash
docker ps
# or
podman compose ps
```

Expected output:
```
NAME         STATUS        PORTS
ollama       Up            0.0.0.0:11434->11434/tcp
open-webui   Up            0.0.0.0:3000->8080/tcp
```

---

## 2. Pull Models

On first run, no models are loaded. Pull the set for your GPU:

```bash
./scripts/pull-models.sh 8gb   # RTX 3060/3070/4060 Ti (8–10 GB VRAM)
./scripts/pull-models.sh 12gb  # RTX 3060 12GB/3080/4070 (12 GB VRAM)
./scripts/pull-models.sh 16gb  # RTX 4060 Ti 16GB/4080/5080 (16 GB VRAM)
```

Models are sourced from HuggingFace (bartowski, unsloth) for the best quantization at each tier — Ollama's library only ships Q4_K_M and Q8_0, but Q5_K_M and Q6_K are the sweet spot for most GPUs.

This pulls:
- **8gb** (Q5_K_M): Qwen 2.5.1 Coder 7B, Qwen 3.5 9B (Q4), DeepSeek R1 0528 8B
- **12gb** (Q5_K_M / Q6_K): Qwen 2.5 Coder 14B, Qwen 3.5 9B, DeepSeek R1 0528 8B, Gemma 3 12B
- **16gb** (Q6_K / Q8_0): Qwen 2.5 Coder 14B, Qwen 3.5 9B, DeepSeek R1 14B, Phi-4 14B

Check what's available at any time:

```bash
docker exec ollama ollama list
```

---

## 3. Find Your URLs

**Docker (Linux/Proxmox):** services are always at `http://localhost:3000` and `http://localhost:11434`.

**Podman on Windows:** WSL2 doesn't reliably forward ports to `localhost`. Run this to get the current addresses:

```bash
./scripts/urls.sh
```

The IP changes on reboot, so run this after each restart.

---

## 4. Chat UI

Open the URL from `urls.sh` (or `http://localhost:3000` on Docker) in your browser. Create an account on first visit (local only, no internet).

Select a model from the dropdown:
- **Qwen 2.5 Coder 7B** — coding and autocomplete
- **Qwen 3.5 9B** — general chat, reasoning, multimodal
- **DeepSeek R1 8B** — hard problems that benefit from thinking step-by-step

---

## 5. One-Line Prompt from the Terminal

Send a prompt and stream the response directly to your terminal:

```bash
./scripts/prompt.sh "Write a Rust function to reverse a string"
```

Switch models with `--model`:

```bash
./scripts/prompt.sh --model deepseek-r1:8b "What is the time complexity of quicksort?"
./scripts/prompt.sh --model qwen3.5:9b "Explain what this code does"
```

Pipe a file as input:

```bash
./scripts/prompt.sh "Summarise this document:" < README.md
cat myfile.py | ./scripts/prompt.sh "Review this code for bugs"
```

Set a default model via environment variable:

```bash
export OLLAMA_MODEL=qwen3.5:9b
./scripts/prompt.sh "What is a monad?"
```

Point at a remote Ollama instance:

```bash
export OLLAMA_HOST=http://192.168.1.10:11434
./scripts/prompt.sh "Hello"
```

---

## 6. Raw API

Ollama exposes an OpenAI-compatible API at `:11434`. Use it from any tool that supports a custom OpenAI endpoint.

```bash
# Non-streaming (returns full JSON response)
curl -s http://localhost:11434/api/generate \
  -d '{"model":"qwen2.5-coder:7b","prompt":"Hello","stream":false}'

# OpenAI-compatible chat endpoint
curl -s http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-coder:7b","messages":[{"role":"user","content":"Hello"}]}'

# List available models
curl -s http://localhost:11434/api/tags
```

---

## 7. Stop the Stack

```bash
docker compose down        # stop and remove containers (models are preserved in the volume)
docker compose down -v     # also delete model storage volume (re-download required)
```

---

## 8. Logs and Monitoring

```bash
docker logs -f ollama       # stream Ollama logs (shows GPU detection, model loads)
docker logs -f open-webui   # stream Open WebUI logs

# Watch GPU usage in real time
nvidia-smi dmon -s u        # Windows host
watch -n 1 nvidia-smi       # Linux/Proxmox VM
```

---

## Switching Models at Runtime

Models load on first use and stay in VRAM until idle for `OLLAMA_KEEP_ALIVE` (default: 5 minutes). Only one model is loaded at a time on a single GPU.

```bash
# Manually unload the current model
curl -s http://localhost:11434/api/generate \
  -d '{"model":"qwen2.5-coder:7b","keep_alive":0}' > /dev/null

# Or just wait — Ollama unloads automatically after OLLAMA_KEEP_ALIVE
```

Pull a new model without stopping the stack:

```bash
docker exec ollama ollama pull qwen2.5-coder:14b
```
