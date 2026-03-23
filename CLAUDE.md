# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Jacob is building a self-hosted local LLM inference stack across his Proxmox homelab — no cloud dependency. The stack targets NVIDIA consumer GPUs (8–12 GB VRAM per node) and is designed to serve coding assistance, general chat/reasoning, API serving for apps and agents, and batch inference.

**Use cases:** Coding assistant (Python, Rust, Go, C#), general chat/reasoning, OpenAI-compatible API serving for apps/agents, batch inference.

**Current state:** Infrastructure build-out phase. The `infrastructure/` directory is the active work area.

## Planned Architecture

```
Proxmox Host
└── Ubuntu Server VM (UEFI/q35, GPU PCI passthrough via vfio-pci)
    └── Docker + NVIDIA Container Toolkit
        ├── Ollama      :11434  ← Primary inference engine
        └── Open WebUI  :3000   ← Chat frontend
```

**Multi-node expansion:** Run Ollama on each node. Place a load balancer (Olla or nginx) in front. No orchestration layer needed.

**Why Ollama over TabbyAPI or vLLM:**
- Widest model selection (GGUF, 135K+ models on HuggingFace)
- Works well on any consumer GPU VRAM size
- Multi-node expansion is additive — just add nodes behind a load balancer
- No Python orchestration layer to maintain
- TabbyAPI is pre-1.0, explicitly not production-grade
- vLLM's multi-node story (Ray) is heavier to operate and lacks GGUF support

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

## Infrastructure Directory

`infrastructure/` is where Docker Compose files, config templates, and deployment scripts will live. When building this out, follow the structure from `architecture/plan.md`:

```
infrastructure/
├── .env.example             # Configuration template (copy to .env)
├── docker-compose.yml       # Single-node: Ollama + Open WebUI
├── docker-compose.multi.yml # Multi-node: Open WebUI routing to multiple Ollama nodes
└── scripts/
    └── pull-models.sh       # Pull recommended models by VRAM profile (8gb|12gb)
```

Ollama has no config file — all tuning is via environment variables set in `.env`.

## Key Decisions

- **PCI passthrough over LXC** — full VM isolation via `vfio-pci` (UEFI/q35 machine type, `host` CPU). LXC is noted as an option for GPU sharing but not the primary target.
- **Ollama over TabbyAPI/vLLM** — widest model selection, zero orchestration, straightforward multi-node expansion. TabbyAPI is pre-1.0 and not production-grade; vLLM lacks GGUF and needs Ray for multi-node.
- **Multi-node via load balancer, not distributed inference** — run Ollama independently on each node, route with Olla or nginx. When a single model needs to span multiple GPUs, use llama.cpp RPC (pipeline parallelism over Ethernet) or GPUStack.
- **IDE integration via Continue extension** — points at Ollama's OpenAI-compatible API (`http://<vm-ip>:11434`). Qwen 2.5 Coder handles FIM/autocomplete; Qwen 3.5 9B for chat.

## Reference Docs

- `architecture/plan.md` — Full step-by-step deployment plan (Proxmox setup, Docker config, model selection, IDE integration)
- `architecture/high_level_context.md` — Comprehensive 2026 inference engine landscape and benchmarks
