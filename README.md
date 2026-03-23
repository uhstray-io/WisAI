# WisAI

Self-hosted local LLM inference stack for Proxmox VMs with consumer NVIDIA GPUs (8–12 GB VRAM). Designed for coding assistance, general chat, and API serving — no cloud dependency.

## Stack

| Component | Role | Port |
|---|---|---|
| **Ollama** | Primary inference engine | 11434 |
| **Open WebUI** | Chat frontend | 3000 |

**Why Ollama?** Widest model selection (GGUF, 135K+ models), works on any consumer GPU, and multi-node expansion requires no orchestration layer — just run Ollama on each node behind a load balancer.

## Hardware Target

- Proxmox host with one or more NVIDIA consumer GPUs (GTX 10xx or newer)
- 8–12 GB VRAM per GPU
- GPU exposed to a Ubuntu Server VM via PCI passthrough (`vfio-pci`)
- Docker + NVIDIA Container Toolkit inside the VM

## Architecture

```
Proxmox Host
└── Ubuntu Server VM (UEFI/q35, GPU PCI passthrough)
    └── Docker + NVIDIA Container Toolkit
        ├── Ollama      :11434
        └── Open WebUI  :3000
```

Ollama exposes an OpenAI-compatible API, so any IDE extension that supports a custom OpenAI endpoint works out of the box (Continue.dev, avante.nvim, CodeGPT, etc.).

## Model Selection

**8 GB VRAM**
- Daily driver: Qwen 3.5 9B @ Q4_K_M (~6.6 GB)
- Coding/FIM: Qwen 2.5 Coder 7B @ Q4_K_M (~5.5 GB)
- Reasoning: DeepSeek R1 8B @ Q4_K_M (~5.5 GB)

**12 GB VRAM**
- Coding: Qwen 2.5 Coder 14B @ Q4_K_M (~9 GB)
- Chat: Gemma 3 12B @ Q4_K_M (~8 GB)

## Status

Early planning phase. See [`architecture/plan.md`](architecture/plan.md) for the full deployment guide and [`architecture/high_level_context.md`](architecture/high_level_context.md) for the 2026 inference engine landscape.

## Multi-GPU Expansion

When ready to combine GPUs across Proxmox nodes, use **llama.cpp RPC** (simplest) or **GPUStack** (management UI). Two 12 GB GPUs combined unlock 27–30B models at Q4_K_M. Use pipeline parallelism over standard Ethernet — tensor parallelism requires 100+ Gbps interconnect.
