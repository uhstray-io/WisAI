# Local LLM Deployment Plan

**Target:** Single-GPU Proxmox VM running Docker containers for local LLM inference  
**Hardware:** 8–12 GB VRAM NVIDIA GPU (consumer-class, e.g. RTX 3060 12GB, RTX 3080 10GB, RTX 4060 Ti 8GB)  
**Use Cases:** Coding assistant (Python, Rust, Go, C#), general chat/reasoning, API serving for apps/agents, batch processing  
**Date:** March 2026

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Proxmox Host                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Ubuntu Server VM (UEFI/q35)                          │  │
│  │  GPU: Full PCI Passthrough (vfio-pci)                 │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │  Docker + NVIDIA Container Toolkit              │  │  │
│  │  │                                                 │  │  │
│  │  │  ┌───────────────┐  ┌──────────────────────┐    │  │  │
│  │  │  │  TabbyAPI     │  │  Open WebUI          │    │  │  │
│  │  │  │  (ExLlamaV3)  │  │  (Chat Frontend)     │    │  │  │
│  │  │  │  :5000        │  │  :3000               │    │  │  │
│  │  │  └───────────────┘  └──────────────────────┘    │  │  │
│  │  │         ↕ OpenAI-compatible API                 │  │  │
│  │  │  ┌───────────────┐                              │  │  │
│  │  │  │  Ollama       │  ← Fallback / GGUF models    │  │  │
│  │  │  │  :11434       │                              │  │  │
│  │  │  └───────────────┘                              │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Why This Stack

The plan uses a **two-engine approach**:

**Primary: ExLlamaV3 + TabbyAPI** — for maximum single-GPU inference speed. ExLlamaV3's EXL3 quantization format delivers the best quality-per-bit of any quantization method and the fastest token generation on NVIDIA consumer GPUs. TabbyAPI wraps it in an OpenAI-compatible API server with Docker support.

**Fallback: Ollama** — for quick model switching, GGUF ecosystem access, and drop-in simplicity. Ollama is the easiest way to pull and run any of 135K+ GGUF models from HuggingFace with zero configuration.

> **Important: ExLlamaV3 is NOT production-grade.** As of March 2026, ExLlamaV3 is at v0.0.25 (pre-1.0) and TabbyAPI's own README states it is "a hobby project made for a small amount of users. It is not meant to run on production servers." That said, for a homelab single-user or small-team setup, it is stable, actively developed (commits through March 2026), and significantly faster than alternatives. If you need battle-tested production serving with concurrent users, use **vLLM** or **SGLang** instead (see Section 9: Alternatives).

---

## 2. Proxmox GPU Passthrough (VM-Bound)

Full PCI passthrough gives the VM exclusive, near-bare-metal GPU access. This is the recommended approach for isolation and maximum performance.

### 2.1 Prerequisites

- **CPU:** VT-d (Intel) or AMD-Vi (AMD) enabled in BIOS
- **Motherboard:** IOMMU support with clean IOMMU groups
- **GPU:** NVIDIA consumer GPU (GTX 10xx or newer for ExLlamaV3)

### 2.2 Host Configuration

**Step 1: Enable IOMMU in GRUB**

Edit `/etc/default/grub`:
```
# For Intel:
GRUB_CMDLINE_LINUX_DEFAULT="quiet intel_iommu=on iommu=pt"

# For AMD:
GRUB_CMDLINE_LINUX_DEFAULT="quiet amd_iommu=on iommu=pt"
```

Then: `update-grub && reboot`

**Step 2: Load VFIO modules**

Edit `/etc/modules`:
```
vfio
vfio_iommu_type1
vfio_pci
vfio_virqfd
```

**Step 3: Blacklist host GPU drivers**

Create `/etc/modprobe.d/blacklist-gpu.conf`:
```
blacklist nouveau
blacklist nvidia
blacklist nvidiafb
blacklist nvidia_drm
```

**Step 4: Bind GPU to vfio-pci**

Find your GPU's vendor:device IDs:
```bash
lspci -nn | grep -i nvidia
# Example output: 01:00.0 VGA compatible controller [0300]: NVIDIA Corporation ... [10de:2684]
# Note BOTH the GPU and its audio device IDs
```

Create `/etc/modprobe.d/vfio.conf`:
```
options vfio-pci ids=10de:2684,10de:22ba
```

Then: `update-initramfs -u && reboot`

**Step 5: Verify IOMMU groups**

```bash
find /sys/kernel/iommu_groups/ -type l | sort -V
# Your GPU should be in its own group (or a group with only its audio device)
```

### 2.3 VM Configuration

Create the VM in Proxmox with these settings:

| Setting | Value | Why |
|---|---|---|
| BIOS | OVMF (UEFI) | Required for GPU passthrough |
| Machine Type | q35 | Modern PCIe topology |
| CPU Type | host | Full CPU feature exposure |
| RAM | 16–32 GB | Model weights spill to RAM during loading |
| OS | Ubuntu Server 24.04 LTS | Broad NVIDIA driver + Docker support |
| Disk | 100+ GB (LVM-thin or ZFS) | Models are 4–15 GB each |

**Add PCI Device in Proxmox UI:**
- Hardware → Add → PCI Device
- Select your GPU
- Check: "All Functions" (passes GPU + audio together)
- Check: "PCI-Express" 
- Check: "Primary GPU" only if this VM has no other display

**Or edit `/etc/pve/qemu-server/<vmid>.conf` directly:**
```
hostpci0: 0000:01:00,pcie=1,x-vga=0
machine: q35
bios: ovmf
cpu: host
```

### 2.4 Inside the VM: NVIDIA Driver Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install NVIDIA driver (headless for server use)
sudo apt install -y nvidia-headless-570-server nvidia-utils-570-server

# Verify
nvidia-smi
# Should show your GPU with correct VRAM
```

---

## 3. Docker + NVIDIA Container Toolkit

### 3.1 Install Docker

```bash
# Docker official install
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in
```

### 3.2 Install NVIDIA Container Toolkit

```bash
# Add NVIDIA container toolkit repo
distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update
sudo apt install -y nvidia-container-toolkit

# Configure Docker runtime
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Verify GPU access in Docker
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu24.04 nvidia-smi
```

---

## 4. Primary Engine: ExLlamaV3 + TabbyAPI

### 4.1 Why ExLlamaV3

ExLlamaV3 is purpose-built for consumer GPUs with limited VRAM. Key advantages over vLLM/SGLang for your hardware:

- **EXL3 quantization** achieves state-of-the-art quality at any bit width (1.5–8 bpw). A 70B model remains coherent at 1.6 bits per weight, fitting in ~16 GB.
- **Fastest single-user inference** on NVIDIA consumer GPUs — ~85% faster than llama.cpp and ~147% faster than bitsandbytes at equivalent quantization.
- **Variable bit-rate allocation** — EXL3 assigns more bits to sensitive layers and fewer to robust ones, unlike uniform quantization (GGUF Q4_K_M).
- **Paged attention** with dynamic batching (on Ampere+).
- **Speculative decoding** support for additional speed.

### 4.2 TabbyAPI Docker Deployment

TabbyAPI provides an official Docker image. Create a directory structure:

```bash
mkdir -p ~/llm-server/{models,config}
cd ~/llm-server
```

**Create `config/config.yml`:**

```yaml
# TabbyAPI Configuration
network:
  host: "0.0.0.0"
  port: 5000

model:
  model_dir: /models
  # Default model loaded on startup (set to your most-used model)
  # model_name: Qwen3.5-9B-Instruct-exl3-4.0bpw

logging:
  log_prompt: false

developer:
  unsafe_launch: false
```

**Create `docker-compose.yml`:**

```yaml
version: "3.8"

services:
  tabbyapi:
    image: ghcr.io/theroyallab/tabbyapi:latest
    container_name: tabbyapi
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - ./models:/models
      - ./config:/app/config
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - NVIDIA_VISIBLE_DEVICES=all

  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: open-webui
    restart: unless-stopped
    ports:
      - "3000:8080"
    volumes:
      - open-webui-data:/app/backend/data
    environment:
      # Point to TabbyAPI as the OpenAI-compatible backend
      - OPENAI_API_BASE_URL=http://tabbyapi:5000/v1
      - OPENAI_API_KEY=your-tabbyapi-key
    depends_on:
      - tabbyapi

volumes:
  open-webui-data:
```

**Launch:**

```bash
docker compose up -d
```

### 4.3 Downloading EXL3 Models

TabbyAPI includes a built-in HuggingFace downloader. You can also download models manually:

```bash
# Option A: Use TabbyAPI's built-in downloader via API
curl -X POST http://localhost:5000/v1/download \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "turboderp/Qwen3.5-9B-Instruct-exl3-4.0bpw", "output_dir": "/models"}'

# Option B: Manual download with huggingface-cli
pip install huggingface-hub
huggingface-cli download turboderp/Qwen3.5-9B-Instruct-exl3-4.0bpw \
  --local-dir ~/llm-server/models/Qwen3.5-9B-Instruct-exl3-4.0bpw
```

### 4.4 Loading and Switching Models via API

```bash
# Load a model
curl -X POST http://localhost:5000/v1/model/load \
  -H "Content-Type: application/json" \
  -d '{"name": "Qwen3.5-9B-Instruct-exl3-4.0bpw"}'

# Unload current model
curl -X POST http://localhost:5000/v1/model/unload

# List available models
curl http://localhost:5000/v1/models

# Chat completion (OpenAI-compatible)
curl http://localhost:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen3.5-9B-Instruct-exl3-4.0bpw",
    "messages": [{"role": "user", "content": "Write a Rust function to reverse a linked list"}],
    "max_tokens": 2048,
    "temperature": 0.7
  }'
```

---

## 5. Fallback Engine: Ollama

Ollama is useful for quickly testing GGUF models, using models that don't have EXL3 quants yet, or when you want zero-config simplicity.

### 5.1 Docker Deployment

Add to your `docker-compose.yml`:

```yaml
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

> **Note:** Only one engine should hold the GPU at a time. If TabbyAPI has a model loaded, Ollama will fall back to CPU (extremely slow). Unload TabbyAPI's model before using Ollama, or configure them for different use cases.

### 5.2 Pulling Models

```bash
# Pull models (these download GGUF Q4_K_M by default)
docker exec -it ollama ollama pull qwen3.5:9b
docker exec -it ollama ollama pull qwen2.5-coder:7b
docker exec -it ollama ollama pull deepseek-r1:8b

# Run interactive chat
docker exec -it ollama ollama run qwen3.5:9b

# API usage (OpenAI-compatible)
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen3.5:9b", "messages": [{"role": "user", "content": "hello"}]}'
```

---

## 6. Model Selection Guide

### 6.1 Models for Coding (Python, Rust, Go, C#)

| Model | Params | VRAM (EXL3 4bpw) | VRAM (GGUF Q4_K_M) | Best For | Notes |
|---|---|---|---|---|---|
| **Qwen 2.5 Coder 7B** | 7B | ~4.5 GB | ~5.5 GB | Autocomplete / FIM | FIM king at 7B. 88.4% HumanEval. Supports Fill-in-the-Middle for tab completion. Best paired with a chat model. |
| **Qwen 3.5 9B** | 9B | ~5.5 GB | ~6.6 GB | Chat-based coding + reasoning | Released March 2026. 262K context, native multimodal (reads screenshots/diagrams), thinking mode. Not FIM-trained but excellent for code review, debugging, refactoring. |
| **DeepSeek Coder V2 Lite** | 16B (2.4B active) | N/A (MoE) | ~5 GB | Reasoning-heavy code tasks | MoE architecture — only 2.4B params active per token, so it's fast and memory-efficient. 128K context. 300+ languages. |
| **Qwen 2.5 Coder 14B** | 14B | ~8.5 GB | ~9 GB | Serious coding (12 GB GPU) | Major step up from 7B. Strong on multi-file refactors, architecture questions. FIM support. Needs 12 GB card. |

**Recommendation for 8 GB GPU:** Run **Qwen 2.5 Coder 7B** for autocomplete/FIM via your IDE, swap to **Qwen 3.5 9B** for chat-based coding discussions. They don't need to run simultaneously.

**Recommendation for 12 GB GPU:** Run **Qwen 2.5 Coder 14B** as your primary coding model. It handles both FIM and chat well enough to be a single-model solution.

### 6.2 Models for General Chat / Reasoning

| Model | Params | VRAM (EXL3 4bpw) | VRAM (GGUF Q4_K_M) | Best For | Notes |
|---|---|---|---|---|---|
| **Qwen 3.5 9B** | 9B | ~5.5 GB | ~6.6 GB | All-rounder | Best capability-per-VRAM-byte in 2026. Multimodal, 262K context, thinking mode toggle. |
| **Gemma 3 12B** | 12B | ~7 GB | ~8 GB | Conversational quality | Google's offering. Strong instruction following, good creative writing. Fits on 12 GB. |
| **DeepSeek R1 0528 Qwen3 8B** | 8B | ~5 GB | ~5.5 GB | Deep reasoning / math | Distilled from full DeepSeek R1 (671B). Chain-of-thought by default. Slower but thinks harder. Great for complex logic. |
| **Phi-4 14B** | 14B | ~8.5 GB | ~9 GB | Balanced reasoning (12 GB) | Microsoft's compact powerhouse. Strong on math, science, coding. |
| **Llama 3.1 8B** | 8B | ~5 GB | ~5.5 GB | Baseline / ecosystem | Meta's reliable workhorse. Huge fine-tune ecosystem. 128K context. |
| **NVIDIA Nemotron Nano 9B** | 9B | ~5.5 GB | ~6.6 GB | Coding + reasoning hybrid | Highest LiveCodeBench scores at 8–9B size. Reasoning variant available. |

**Recommendation for 8 GB GPU:** **Qwen 3.5 9B** as the daily driver. Swap to **DeepSeek R1 8B** when you need deliberate reasoning on hard problems.

**Recommendation for 12 GB GPU:** **Qwen 3.5 9B** at higher quantization (Q6_K / 6bpw) for near-lossless quality, or **Gemma 3 12B** at Q4_K_M for a different flavor.

### 6.3 Models for Creative Writing / Long-Form

| Model | Params | VRAM (Q4_K_M) | Notes |
|---|---|---|---|
| **Qwen 3.5 9B** | 9B | ~6.6 GB | 262K context, good narrative coherence |
| **Mistral Small 3.1 24B** | 24B | ~15 GB | Needs aggressive quant on 12 GB (Q2/Q3). Better as a distributed target. |
| **Gemma 3 12B** | 12B | ~8 GB | Known for engaging, natural conversation style |

### 6.4 Quick Reference: What Fits Where

```
8 GB VRAM Budget
├── Qwen 3.5 9B @ Q4_K_M          → 6.6 GB  ← RECOMMENDED daily driver
├── Qwen 2.5 Coder 7B @ Q4_K_M    → 5.5 GB  ← Best FIM/autocomplete
├── DeepSeek R1 8B @ Q4_K_M        → 5.5 GB  ← Reasoning specialist
├── Llama 3.1 8B @ Q4_K_M          → 5.5 GB  ← Reliable baseline
├── Qwen 3.5 4B @ Q6_K             → 3.4 GB  ← Ultra-light, still capable
└── Context budget: ~1.5 GB remaining for KV cache (~8K tokens)

12 GB VRAM Budget
├── Qwen 2.5 Coder 14B @ Q4_K_M   → 9 GB    ← RECOMMENDED coding model
├── Gemma 3 12B @ Q4_K_M           → 8 GB    ← Strong chat alternative
├── Phi-4 14B @ Q4_K_M             → 9 GB    ← Math/science focused
├── Qwen 3.5 9B @ Q6_K             → 8.5 GB  ← Near-lossless quality
├── Nemotron Nano 9B @ Q5_K_M      → 7.5 GB  ← Code + reasoning
└── Context budget: ~3 GB remaining for KV cache (~16K tokens)
```

---

## 7. IDE Integration for Code Completion

### 7.1 VS Code with Continue Extension

[Continue](https://continue.dev) is an open-source AI code assistant that connects to any OpenAI-compatible API.

**Install:** Search "Continue" in VS Code extensions.

**Configure `~/.continue/config.json`:**

```json
{
  "models": [
    {
      "title": "Qwen 3.5 9B (TabbyAPI)",
      "provider": "openai",
      "model": "Qwen3.5-9B-Instruct-exl3-4.0bpw",
      "apiBase": "http://<your-vm-ip>:5000/v1",
      "apiKey": "your-tabbyapi-key"
    },
    {
      "title": "Qwen 2.5 Coder 7B (Ollama)",
      "provider": "ollama",
      "model": "qwen2.5-coder:7b",
      "apiBase": "http://<your-vm-ip>:11434"
    }
  ],
  "tabAutocompleteModel": {
    "title": "Qwen 2.5 Coder 7B (FIM)",
    "provider": "ollama",
    "model": "qwen2.5-coder:7b",
    "apiBase": "http://<your-vm-ip>:11434"
  }
}
```

### 7.2 Neovim with avante.nvim or codecompanion.nvim

Both plugins support OpenAI-compatible endpoints. Point them at `http://<vm-ip>:5000/v1`.

### 7.3 JetBrains with Continue or CodeGPT

Same approach — any plugin that supports custom OpenAI endpoints works with TabbyAPI or Ollama.

---

## 8. Quantization Format Decision Tree

```
Do you need the absolute fastest single-GPU inference?
├── YES → Use EXL3 (ExLlamaV3) via TabbyAPI
│         Best quality-per-bit, fastest NVIDIA inference.
│         Downside: smaller model selection, NVIDIA-only.
│
├── MAYBE → Use GGUF Q4_K_M via Ollama
│           Widest model availability (135K+ on HuggingFace).
│           CPU+GPU hybrid offloading if model doesn't fit.
│           ~85% the speed of EXL3 on pure GPU.
│
└── NO, I need concurrent multi-user serving
    → Use AWQ via vLLM or SGLang
      Best throughput under load. Marlin kernel = 10.9× speedup.
      Not ideal for single-user on 8–12 GB GPUs.
```

**Quantization quality ranking (best to worst at 4-bit equivalent):**
1. EXL3 (ExLlamaV3) — trellis-coded, variable bit-rate
2. Unsloth Dynamic 2.0 GGUF — smart layer-wise bit allocation  
3. AWQ — activation-aware, GPU-optimized
4. GGUF Q4_K_M — universal standard, good balance
5. GPTQ — older, slightly lower quality

**Rule of thumb:** Use Q4_K_M minimum for English tasks. Use Q6_K or higher for non-English languages and code (4-bit drops multilingual quality to 90–95%).

---

## 9. Alternatives: When to Use vLLM or SGLang Instead

TabbyAPI + ExLlamaV3 is the best choice for **single-user, maximum-speed inference on consumer GPUs**. But there are scenarios where you'd want a different engine:

### Use vLLM When:
- You need **concurrent multi-user serving** (TabbyAPI handles batching but isn't designed for high concurrency)
- You want **the widest model architecture support** (218 architectures vs ExLlamaV3's ~30)
- You need **production-grade reliability** with battle-tested continuous batching
- You're deploying **AWQ or GPTQ models** (vLLM's Marlin kernel is extremely fast)

```bash
# vLLM Docker example
docker run --gpus all \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-7B-Instruct-AWQ \
  --quantization awq \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90
```

### Use SGLang When:
- You need **the fastest batch throughput** (~29% ahead of vLLM in benchmarks)
- You're building **agent workflows** with structured JSON output (RadixAttention + constrained decoding)
- You have **multi-turn conversations** where KV cache reuse matters (75–95% cache hit rate)

### Use Aphrodite When:
- You want **vLLM-class serving** but need **GGUF support** on consumer GPUs
- You need the **widest quantization format support** (GGUF, GPTQ, AWQ, FP8, EXL2, AQLM, bitsandbytes)
- You have older GPUs (Pascal/GTX 10xx) that vLLM doesn't optimize for

---

## 10. Operational Playbook

### 10.1 Daily Workflow

```
Morning: TabbyAPI starts with Qwen 3.5 9B loaded (general chat + coding)
Coding session: Switch to Qwen 2.5 Coder via TabbyAPI API, or run alongside via Ollama
Hard problem: Swap to DeepSeek R1 8B for chain-of-thought reasoning
Evening: Load creative/chat model for personal use
```

### 10.2 Model Hot-Swap Script

Create `~/swap-model.sh`:

```bash
#!/bin/bash
# Usage: ./swap-model.sh <model-name>
# Example: ./swap-model.sh Qwen3.5-9B-Instruct-exl3-4.0bpw

TABBY_URL="http://localhost:5000"

echo "Unloading current model..."
curl -s -X POST "$TABBY_URL/v1/model/unload"
sleep 2

echo "Loading $1..."
curl -s -X POST "$TABBY_URL/v1/model/load" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"$1\"}"

echo "Done. Current model:"
curl -s "$TABBY_URL/v1/models" | python3 -m json.tool
```

### 10.3 Monitoring

```bash
# Watch GPU utilization and VRAM in real-time
watch -n 1 nvidia-smi

# Docker logs
docker logs -f tabbyapi
docker logs -f ollama

# Check which model is loaded
curl -s http://localhost:5000/v1/models
```

### 10.4 Backup and Portability

Models are large and slow to re-download. Mount a shared NFS or dedicated disk:

```bash
# In Proxmox: Add a second virtual disk for model storage
# Mount it at /mnt/models in the VM
# Point both TabbyAPI and Ollama volumes here

# Backup your config (small):
tar czf llm-config-backup.tar.gz ~/llm-server/config ~/llm-server/docker-compose.yml
```

---

## 11. Network and Security

### 11.1 Exposing to Your LAN

By default, the services bind to all interfaces. From other machines on your network:

```
Chat UI:     http://<vm-ip>:3000
TabbyAPI:    http://<vm-ip>:5000/v1
Ollama:      http://<vm-ip>:11434/v1
```

### 11.2 Firewall (UFW)

```bash
sudo ufw allow from 192.168.0.0/16 to any port 3000   # Open WebUI
sudo ufw allow from 192.168.0.0/16 to any port 5000   # TabbyAPI
sudo ufw allow from 192.168.0.0/16 to any port 11434  # Ollama
sudo ufw enable
```

### 11.3 TabbyAPI Authentication

TabbyAPI supports API key authentication. Create `config/api_tokens.yml`:

```yaml
- token: "your-secret-key-here"
  admin: true
```

Then pass the key in requests: `Authorization: Bearer your-secret-key-here`

---

## 12. Checklist: Step-by-Step Deployment

```
Phase 1: Proxmox Host Setup
  [ ] Enable VT-d/AMD-Vi in BIOS
  [ ] Add IOMMU kernel parameters to GRUB
  [ ] Load VFIO modules
  [ ] Blacklist NVIDIA drivers on host
  [ ] Bind GPU to vfio-pci with correct IDs
  [ ] Verify IOMMU groups are clean
  [ ] Reboot host

Phase 2: VM Creation
  [ ] Create Ubuntu Server 24.04 VM (UEFI, q35, host CPU)
  [ ] Allocate 16–32 GB RAM, 100+ GB disk
  [ ] Attach GPU via PCI passthrough (All Functions + PCI-Express)
  [ ] Boot VM and install Ubuntu
  [ ] Install NVIDIA headless driver (570-server)
  [ ] Verify nvidia-smi shows correct GPU

Phase 3: Docker Setup
  [ ] Install Docker
  [ ] Install NVIDIA Container Toolkit
  [ ] Verify GPU access in Docker container
  [ ] Create ~/llm-server directory structure

Phase 4: Engine Deployment
  [ ] Create docker-compose.yml with TabbyAPI + Open WebUI
  [ ] Create TabbyAPI config.yml
  [ ] docker compose up -d
  [ ] Download first model (Qwen 3.5 9B EXL3 recommended)
  [ ] Load model via TabbyAPI API
  [ ] Test chat via Open WebUI at :3000

Phase 5: IDE Integration
  [ ] Install Continue extension in VS Code
  [ ] Configure API endpoint to point at VM
  [ ] Test autocomplete with Qwen 2.5 Coder
  [ ] Test chat with Qwen 3.5 9B

Phase 6: Hardening
  [ ] Set up TabbyAPI authentication tokens
  [ ] Configure UFW firewall rules
  [ ] Set up model storage on dedicated disk
  [ ] Create swap-model.sh convenience script
  [ ] Test model hot-swapping workflow
```

---

## 13. Cost and Performance Expectations

### Expected Token Generation Speeds (Single User, Q4 Equivalent)

| GPU | VRAM | Qwen 3.5 9B | Qwen 2.5 Coder 7B | Qwen 14B |
|---|---|---|---|---|
| RTX 3060 | 12 GB | ~42 tok/s | ~55 tok/s | ~28 tok/s |
| RTX 3080 | 10 GB | ~74 tok/s | ~90 tok/s | Tight fit |
| RTX 4060 Ti | 8 GB | ~38 tok/s | ~50 tok/s | Won't fit |
| RTX 4070 | 12 GB | ~52 tok/s | ~65 tok/s | ~35 tok/s |
| RTX 3090 | 24 GB | ~87 tok/s | ~110 tok/s | ~60 tok/s |

> Speeds are approximate, based on llama.cpp GGUF benchmarks. ExLlamaV3 with EXL3 will be ~40–85% faster than these numbers on equivalent quantization. Context length, batch size, and speculative decoding all affect real-world speeds.

**Comfortable interactive chat:** 10–20 tok/s minimum.  
**Good coding experience:** 30+ tok/s (autocomplete feels snappy).  
**Excellent:** 50+ tok/s.

### Storage Requirements

| Model | EXL3 4bpw | GGUF Q4_K_M |
|---|---|---|
| 7B model | ~3.5 GB | ~4.5 GB |
| 9B model | ~4.5 GB | ~6 GB |
| 14B model | ~7 GB | ~9 GB |
| 27B model | ~13 GB | ~17 GB |

Budget **50–100 GB** of disk space for a library of 5–10 models.

---

## 14. Future Expansion: Multi-GPU Distributed Inference

When you're ready to combine GPUs across multiple Proxmox nodes:

- **llama.cpp RPC** — Simplest. Run `rpc-server` on each node, connect from main node with `--rpc ip1:50052,ip2:50052`. Pipeline parallelism over standard Ethernet.
- **GPUStack** — Web UI for managing LLM inference across GPU clusters. Auto-selects backend (vLLM, SGLang, llama.cpp). Best for management at scale.
- **Exo** — Zero-config distributed inference with automatic device discovery via mDNS.

With two 12 GB GPUs combined (24 GB total), you unlock 27–30B models at Q4_K_M — a major capability jump.

---

## Appendix A: Useful Commands

```bash
# Check GPU memory usage
nvidia-smi --query-gpu=memory.used,memory.total --format=csv

# Estimate if a model fits (rough rule of thumb)
# VRAM ≈ (params_billions × bytes_per_weight) + 1 GB overhead + KV cache
# At 4-bit: bytes_per_weight ≈ 0.56
# Example: 9B × 0.56 = 5.04 GB + 1 GB overhead = ~6 GB

# Kill all GPU processes (emergency)
sudo fuser -v /dev/nvidia* 2>/dev/null | awk '{print $2}' | xargs -r kill -9

# Test OpenAI API compatibility
curl http://localhost:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-key" \
  -d '{"model": "any", "messages": [{"role": "user", "content": "Say hello"}], "max_tokens": 50}'
```

## Appendix B: Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| `nvidia-smi` not found in VM | Driver not installed or GPU not passed through | Verify PCI device in Proxmox UI, reinstall driver |
| Docker can't see GPU | NVIDIA Container Toolkit misconfigured | Run `nvidia-ctk runtime configure --runtime=docker`, restart Docker |
| Model won't load (OOM) | Model + KV cache exceeds VRAM | Use smaller quantization, reduce context length, or use smaller model |
| Slow generation (~1–5 tok/s) | Model partially on CPU | Check `nvidia-smi` — if VRAM usage is low, layers are on CPU. Use smaller model or higher quantization. |
| TabbyAPI 500 error on load | Incompatible model format | Ensure you're using EXL3 models for ExLlamaV3 backend, not GGUF |
| IOMMU group contains other devices | Motherboard PCIe layout issue | Try a different PCIe slot, or use ACS override patch (risky) |
| VM freezes on GPU passthrough | Missing UEFI/q35 or driver conflict | Ensure OVMF BIOS, q35 machine, and host drivers are blacklisted |
