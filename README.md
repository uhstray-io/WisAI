# WisAI

Self-hosted local LLM inference stack for Proxmox VMs with consumer NVIDIA GPUs (8–12 GB VRAM). Designed for coding assistance, general chat, and API serving — no cloud dependency.

## Stack

| Component | Role | Port |
|---|---|---|
| **Ollama** | Primary inference engine (OpenAI-compatible API) | 11434 |
| **Open WebUI** | Chat frontend | 3000 |

**Why Ollama?** Widest model selection (GGUF, 135K+ models), works on any consumer GPU, and multi-node expansion requires no orchestration layer — just run Ollama on each node behind a load balancer.

## Hardware Target

- Proxmox host with NVIDIA consumer GPU (GTX 10xx or newer)
- 8–12 GB VRAM per node
- Ubuntu Server VM with full PCI GPU passthrough (`vfio-pci`, UEFI/q35)
- Docker + NVIDIA Container Toolkit inside the VM

## Quick Start

```bash
cd infrastructure
cp .env.example .env          # configure ports, GPU count, model path
docker compose up -d          # start Ollama + Open WebUI
./scripts/pull-models.sh 8gb  # pull recommended models (8gb or 12gb profile)
```

Open WebUI is available at `http://<vm-ip>:3000`.
Ollama API at `http://<vm-ip>:11434` (OpenAI-compatible).

## Architecture

```
Proxmox Host
└── Ubuntu Server VM (UEFI/q35, GPU PCI passthrough)
    └── Docker + NVIDIA Container Toolkit
        ├── Ollama      :11434
        └── Open WebUI  :3000
```

## Model Selection

| Role | 8 GB VRAM | 12 GB VRAM |
|---|---|---|
| Coding / FIM | Qwen 2.5 Coder 7B (~5.5 GB) | Qwen 2.5 Coder 14B (~9 GB) |
| Daily driver | Qwen 3.5 9B (~6.6 GB) | Qwen 3.5 9B @ Q6_K (~8.5 GB) |
| Deep reasoning | DeepSeek R1 8B (~5.5 GB) | DeepSeek R1 8B (~5.5 GB) |
| Chat alternative | — | Gemma 3 12B (~8 GB) |

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

Run `docker-compose.yml` on each GPU node. On the coordinator node, configure `OLLAMA_NODES` in `.env` and start `docker-compose.multi.yml` — Open WebUI will load-balance across all nodes.

When a single model needs to span multiple GPUs, use **llama.cpp RPC** (pipeline parallelism over standard Ethernet) or **GPUStack** (web UI for multi-node management).
