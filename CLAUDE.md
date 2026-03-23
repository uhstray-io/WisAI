# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Jacob is building a self-hosted local LLM inference stack across his Proxmox homelab — no cloud dependency. The stack targets NVIDIA consumer GPUs (8–12 GB VRAM per node) and serves coding assistance, general chat/reasoning, and an OpenAI-compatible API for apps and agents.

**Use cases:** Coding assistant (Python, Rust, Go, C#), general chat/reasoning, API serving for apps/agents, batch inference.

**Current state:** Infrastructure files are in place in `infrastructure/`. Not yet deployed.

## Architecture

```
Proxmox Host
└── Ubuntu Server VM (UEFI/q35, GPU PCI passthrough via vfio-pci)
    └── Docker + NVIDIA Container Toolkit
        ├── Ollama      :11434  ← Primary inference engine
        └── Open WebUI  :3000   ← Chat frontend
```

**Multi-node expansion:** Run `docker-compose.yml` on each node. On a coordinator node, set `OLLAMA_NODES` in `.env` and run `docker-compose.multi.yml`. Open WebUI load-balances across all nodes. No orchestration layer needed.

**Why Ollama over TabbyAPI or vLLM:**
- Widest model selection (GGUF, 135K+ models on HuggingFace)
- Works on any consumer GPU VRAM size — flexible for mixed hardware
- Multi-node expansion is additive: add nodes, update `OLLAMA_NODES`
- No Python orchestration layer to maintain
- TabbyAPI is pre-1.0 and explicitly not production-grade
- vLLM's multi-node story (Ray) is heavier to operate and lacks GGUF support

## Infrastructure Files

```
infrastructure/
├── .env.example             # Configuration template — copy to .env
├── docker-compose.yml       # Single-node: Ollama + Open WebUI
├── docker-compose.multi.yml # Multi-node: Open WebUI routing to multiple Ollama nodes
└── scripts/
    └── pull-models.sh       # Pull recommended models by VRAM profile (8gb|12gb)
```

Ollama has no config file — all tuning is via environment variables in `.env`.

**Key `.env` settings:**
- `MODELS_PATH` — leave empty for a named Docker volume, or set an absolute host path (e.g. `/mnt/models`) for a dedicated disk
- `OLLAMA_KEEP_ALIVE` — how long a model stays in VRAM when idle (`-1` to never unload, `5m` for shared use)
- `OLLAMA_NODES` — semicolon-separated Ollama endpoints for multi-node (used by `docker-compose.multi.yml` only)

**Common commands:**
```bash
cd infrastructure
cp .env.example .env
docker compose up -d
docker compose down
./scripts/pull-models.sh 8gb   # or 12gb
docker exec ollama ollama list
docker logs -f ollama
```

## Model Strategy

| Role | 8 GB VRAM | 12 GB VRAM |
|---|---|---|
| Coding / autocomplete (FIM) | Qwen 2.5 Coder 7B | Qwen 2.5 Coder 14B |
| Daily driver / all-rounder | Qwen 3.5 9B | Qwen 3.5 9B @ Q6_K |
| Deep reasoning | DeepSeek R1 0528 Qwen3 8B | DeepSeek R1 0528 Qwen3 8B |
| Chat alternative | — | Gemma 3 12B or Phi-4 14B |

Qwen 3.5 9B is the recommended daily driver — multimodal, 262K context, toggleable thinking mode.

**Quantization baseline:** GGUF Q4_K_M. Use Q6_K or higher for non-English languages (4-bit drops multilingual quality to 90–95%).

**VRAM rule of thumb:** `VRAM ≈ (params_B × 0.56) + 1 GB overhead + KV cache`. Keep context ≤ 8K tokens on 8 GB cards, ≤ 16K on 12 GB cards.

## Key Decisions

- **PCI passthrough over LXC** — full VM isolation via `vfio-pci` (UEFI/q35 machine type, `host` CPU). LXC is viable for GPU sharing between containers but not the primary target here.
- **Ollama as sole inference engine** — no TabbyAPI or vLLM in the stack. Keep it simple.
- **Multi-node via load balancer, not distributed inference** — each node runs its own model independently. When a model needs to span multiple GPUs, use llama.cpp RPC (pipeline parallelism over Ethernet) or GPUStack.
- **IDE integration via Continue extension** — points at `http://<vm-ip>:11434`. Qwen 2.5 Coder for FIM/autocomplete, Qwen 3.5 9B for chat.

## Reference Docs

- `architecture/plan.md` — Full deployment guide (Proxmox setup, Docker config, model selection, IDE integration)
- `architecture/high_level_context.md` — 2026 inference engine landscape and benchmarks
