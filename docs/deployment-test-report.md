# Deployment Test Report

Tested 2026-04-11. Stack ran on local Windows 11 box with Podman. GPU worked. Models worked. Everything below is what happened.

---

## What Is This

Ollama + Open WebUI running in containers on Podman. Ollama does the LLM inference on the GPU. Open WebUI gives you a chat interface in the browser. That's it.

```
Your PC
└── Podman Machine (WSL2 Linux VM)
    ├── Ollama container   → port 11434 (API)
    └── Open WebUI container → port 3000  (chat UI)
```

GPU gets passed from Windows through WSL2 into the containers using CDI (Container Device Interface). The NVIDIA driver on Windows talks to WSL2 which talks to the container.

---

## Hardware

- **GPU:** NVIDIA GeForce RTX 5080, 16 GB VRAM
- **OS:** Windows 11 Home 10.0.26200
- **CUDA:** 13.2
- **Driver:** 595.97

---

## How To Start It

### One-time setup (do this once, ever)

```bash
# Install Podman CLI
winget install RedHat.Podman

# Install podman-compose
pip install podman-compose

# Create and start a Podman machine
podman machine init --cpus 4 --memory 8192 --disk-size 60
podman machine start

# SSH into the machine and set up GPU passthrough
podman machine ssh

# Inside the machine:
curl -s -L https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo | \
  sudo tee /etc/yum.repos.d/nvidia-container-toolkit.repo
sudo dnf install -y nvidia-container-toolkit
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
nvidia-ctk cdi list   # should show nvidia.com/gpu=all
exit

# Test GPU works in a container
podman run --rm --device nvidia.com/gpu=all --security-opt=label=disable ubuntu nvidia-smi
```

You should see your GPU in the nvidia-smi output. If you don't, something went wrong with the CDI setup.

### Start the stack

```bash
cd infrastructure
cp .env.example .env    # only first time
podman compose up -d
```

### Pull models

```bash
# Use the pull script for your VRAM size
./scripts/pull-models.sh 16gb    # or 8gb, 12gb
```

Or pull individually:
```bash
podman exec ollama ollama pull qwen3.5:9b-q8_0
podman exec ollama ollama pull hf.co/bartowski/Qwen2.5-Coder-14B-Instruct-GGUF:Q6_K
```

### Use it

- **Chat UI:** Open http://localhost:3000 in your browser
- **API:** `curl http://localhost:11434/api/generate -d '{"model":"qwen3.5:9b-q8_0","prompt":"hello","stream":false}'`

### Stop it

```bash
cd infrastructure
podman compose down
```

---

## What Was Tested

### Test 1: GPU Passthrough

Ran `nvidia-smi` inside a container. GPU showed up.

```
NVIDIA GeForce RTX 5080  |  16303MiB VRAM  |  CUDA 13.2  |  Driver 595.97
```

Pass.

### Test 2: Ollama Starts With GPU

Checked container logs after `podman compose up -d`:

```
inference compute  library=CUDA  name=CUDA0  description="NVIDIA GeForce RTX 5080"
                   total="15.9 GiB"  available="13.1 GiB"
```

Ollama found the GPU and is using CUDA. Pass.

### Test 3: Healthcheck Works

Ollama container reports `healthy` status. Healthcheck runs `ollama list` every 10 seconds.

```bash
podman ps
# STATUS: Up 38 minutes (healthy)
```

Pass.

### Test 4: Open WebUI Accessible

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/
# 200
```

Pass.

### Test 5: Model Pulling

Pulled all 16 GB VRAM profile models:

| Model | Quant | Size |
|---|---|---|
| Qwen 3.5 9B | Q8_0 | 10.7 GB |
| Qwen 2.5 Coder 14B | Q6_K | 12.1 GB |
| DeepSeek R1 14B | Q6_K | 12.1 GB |
| Phi-4 14B | Q6_K | 12.0 GB |

All pulled successfully. Pass.

### Test 6: Inference Speed

Ran prompts against each model with `stream: false` and measured tok/s from the response metadata.

| Model | Role | tok/s |
|---|---|---|
| Qwen 3 8B (Q4_K_M) | Quick test | 108.9 |
| Qwen 3.5 9B (Q8_0) | Daily driver | 51.5 |
| Qwen 2.5 Coder 14B (Q6_K) | Coding | 54.1 |
| DeepSeek R1 14B (Q6_K) | Reasoning | 55.6 |
| Phi-4 14B (Q6_K) | Chat alt | 60.5 |

All models generated correct, coherent output. GPU utilized for all inference. Pass.

### Test 7: API Compatibility

```bash
curl http://localhost:11434/api/tags
```

Returns JSON list of all loaded models with sizes and metadata. Any OpenAI-compatible client can point at this endpoint. Pass.

---

## Bugs Found and Fixed

### Bug 1: Healthcheck Used `curl` But Ollama Container Doesn't Have It

The `docker-compose.yml` healthcheck was:
```yaml
test: ["CMD", "curl", "-f", "http://localhost:11434/"]
```

Ollama's container image is minimal and doesn't include `curl`. Healthcheck always failed, which meant Open WebUI never started (it waits for Ollama to be healthy).

**Fix:** Changed healthcheck to `["CMD", "ollama", "list"]` which is always available inside the container.

### Bug 2: podman-compose Chokes on Docker's GPU Deploy Block

The compose file had both Docker and Podman GPU configs:
```yaml
deploy:          # Docker uses this
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
devices:         # Podman uses this
  - nvidia.com/gpu=all
```

`podman-compose` v1.5.0 tried to process BOTH. It converted `count: 1` into a CDI device request `nvidia.com/gpu=0`, but WSL2's CDI only exposes `nvidia.com/gpu=all`. Crashed with `TypeError: 'str' object cannot be interpreted as an integer` and then `unresolvable CDI devices nvidia.com/gpu=0`.

**Fix:** Commented out the Docker `deploy` block. For Docker/Proxmox deployment, uncomment it and it works. The `devices` key is ignored by Docker.

### Bug 3: HuggingFace Qwen 3.5 GGUF Not Supported Yet

`hf.co/unsloth/Qwen3.5-9B-GGUF:Q4_K_M` uses architecture tag `qwen35` which Ollama v0.20.5's llama.cpp backend doesn't recognize yet:
```
error loading model architecture: unknown model architecture: 'qwen35'
```

**Fix:** Use the official Ollama library tag `qwen3.5:9b-q8_0` instead. It works fine. The HuggingFace GGUF will work once Ollama updates its llama.cpp to support the `qwen35` architecture.

---

## Current State

Stack is running. Both containers healthy. All four 16gb-profile models loaded and tested. Open WebUI accessible at http://localhost:3000. API at http://localhost:11434.

To stop: `podman compose down` from the `infrastructure/` directory.
To restart: `podman compose up -d`.
