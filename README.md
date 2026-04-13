# WisAI

Self-hosted local LLM inference stack for Proxmox VMs with consumer NVIDIA GPUs (8–16 GB VRAM). Designed for coding assistance, general chat, and API serving — no cloud dependency.

## Stack

| Component | Role | Port |
|---|---|---|
| **Ollama** | Primary inference engine (OpenAI-compatible API) | 11434 |
| **Open WebUI** | Chat frontend | 3000 |

**Pinned versions:** `ollama/ollama:0.20.6` · `open-webui:v0.8.12` (last updated 2026-04-13). To upgrade: bump the tags in `docker-compose.yml`, then `docker compose pull && docker compose up -d`.

**Why Ollama?** Widest model selection (GGUF, 135K+ models), works on any consumer GPU, and multi-node expansion requires no orchestration layer — just run Ollama on each node behind a load balancer.

## Hardware Target

- Proxmox host with NVIDIA consumer GPU (GTX 10xx or newer)
- 8–16 GB VRAM per node
- Ubuntu Server VM with full PCI GPU passthrough (`vfio-pci`, UEFI/q35)
- Docker + NVIDIA Container Toolkit inside the VM

## Quick Start

```bash
cd infrastructure
cp .env.example .env                    # configure ports, GPU count, model path
docker compose up -d                    # start Ollama + Open WebUI (or: podman compose up -d)
./scripts/pull-models.sh 8gb            # pull recommended models (8gb, 12gb, or 16gb)
```

Open WebUI is available at `http://<vm-ip>:3000`.
Ollama API at `http://<vm-ip>:11434` (OpenAI-compatible).

**Using Podman on Windows?** One-time GPU setup is required — see [`docs/podman-gpu-windows.md`](docs/podman-gpu-windows.md).

For full usage instructions including the one-line prompt command, see [`docs/running.md`](docs/running.md).

## Architecture

```
Proxmox Host
└── Ubuntu Server VM (UEFI/q35, GPU PCI passthrough)
    └── Docker + NVIDIA Container Toolkit
        ├── Ollama      :11434
        └── Open WebUI  :3000
```

## Model Selection

| Role | 8 GB VRAM | 12 GB VRAM | 16 GB VRAM |
|---|---|---|---|
| Coding / FIM | Qwen 2.5.1 Coder 7B Q5_K_M (~5.4 GB) | Qwen 2.5 Coder 14B Q5_K_M (~10.5 GB) | Qwen 2.5 Coder 14B Q6_K (~12.1 GB) |
| Daily driver | Qwen 3.5 9B Q4_K_M (~5.7 GB) | Qwen 3.5 9B Q6_K (~7.7 GB) | Qwen 3.5 9B Q8_0 (~9.6 GB) |
| Deep reasoning | DeepSeek R1 0528 8B Q5_K_M (~5.9 GB) | DeepSeek R1 0528 8B Q6_K (~6.7 GB) | DeepSeek R1 14B Q6_K (~12.1 GB) |
| Chat alternative | — | Gemma 3 12B Q5_K_M (~8.4 GB) | Phi-4 14B Q6_K (~12.0 GB) |

Models are sourced from HuggingFace (bartowski, unsloth) for optimal quantization at each tier. See [`docs/running.md`](docs/running.md) for pull commands.

## IDE Integration

Any extension supporting a custom OpenAI endpoint works (Continue.dev, avante.nvim, CodeGPT):

```json
{
  "apiBase": "http://<vm-ip>:11434",
  "provider": "ollama"
}
```

Use Qwen 2.5 Coder for FIM/autocomplete and Qwen 3.5 9B for chat.

## Multi-Node Expansion

Run `docker-compose.yml` on each GPU node. On the coordinator node, set `OLLAMA_NODES` in `.env` (semicolon-separated endpoints) and start `docker-compose.multi.yml`. Open WebUI merges model lists from all backends and randomly distributes requests across nodes that have the requested model.

When a single model needs to span multiple GPUs, use **llama.cpp RPC** (pipeline parallelism over standard Ethernet) or **GPUStack** (web UI for multi-node management).
