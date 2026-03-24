# Podman GPU Passthrough on Windows (WSL2)

## Summary

GPU passthrough for Podman containers on Windows requires the NVIDIA Container Toolkit installed inside the Podman machine and a CDI (Container Device Interface) spec generated. Once configured, Ollama detects the RTX 3080 and achieves full GPU inference speeds.

**Result:** ~107 tok/s on `qwen2.5-coder:7b` with GPU vs 3.6 tok/s CPU-only (30× improvement).

---

## Root Cause

The `deploy.resources` GPU spec in Docker Compose is a Docker/NVIDIA Container Toolkit convention. Podman-compose silently ignores it — a known open issue ([containers/podman#19338](https://github.com/containers/podman/issues/19338), [containers/podman#25196](https://github.com/containers/podman/issues/25196)).

On Windows, Podman runs inside a WSL2 Fedora VM (the "Podman machine"). GPU passthrough goes through two layers:

```
Windows NVIDIA driver → WSL2 (/usr/lib/wsl/lib/) → Podman machine → Container
```

The fix is to:
1. Install `nvidia-container-toolkit` inside the Podman machine
2. Generate a CDI spec (`/etc/cdi/nvidia.yaml`) — detects the GPU via WSL's `/dev/dxg` device
3. Add `devices: ["nvidia.com/gpu=all"]` to the compose service — Podman uses CDI; Docker ignores this key and uses `deploy.resources` instead

In WSL2 mode, the GPU is exposed via `/dev/dxg` (DirectX Graphics), not the traditional `/dev/nvidia0`. The CDI spec handles this automatically.

---

## One-Time Setup (Per Podman Machine)

Run these commands once. If the Podman machine is recreated, repeat from step 1.

```bash
# 1. SSH into the Podman machine
podman machine ssh

# 2. Add NVIDIA Container Toolkit repo and install
curl -s -L https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo | \
  sudo tee /etc/yum.repos.d/nvidia-container-toolkit.repo
sudo dnf install -y nvidia-container-toolkit

# 3. Generate the CDI spec (auto-detects WSL2 mode)
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml

# 4. Verify
nvidia-ctk cdi list   # should show nvidia.com/gpu=0

# 5. Exit
exit
```

Verify GPU access works before starting compose:

```bash
podman run --rm --device nvidia.com/gpu=all --security-opt=label=disable ubuntu nvidia-smi
```

---

## Compose File Fix

The `docker-compose.yml` now includes both GPU specs so the same file works on Docker (Linux/Proxmox) and Podman (Windows/WSL2):

```yaml
services:
  ollama:
    ...
    # Docker + NVIDIA Container Toolkit (Linux/Proxmox target)
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    # Podman + CDI (Windows/WSL2)
    devices:
      - nvidia.com/gpu=all
```

- **Docker** uses `deploy.resources` and ignores `devices` with CDI names
- **Podman** uses `devices` and ignores `deploy.resources`

---

## Verification

After starting with `podman compose up -d`:

```bash
# Check GPU is mounted in the container
podman inspect ollama --format '{{.HostConfig.Devices}}'
# Expected: [{/dev/dxg /dev/dxg }]

# Check Ollama logs for GPU detection
podman logs ollama | grep "inference compute"
# Expected: library=CUDA name=CUDA0 description="NVIDIA GeForce RTX 3080"

# Run inference and check speed
curl -s http://localhost:11434/api/generate \
  -d '{"model":"qwen2.5-coder:7b","prompt":"Hello","stream":false}' \
  | grep eval_duration
# Then calculate: eval_count / eval_duration * 1e9 = tok/s
# On RTX 3080: ~107 tok/s for qwen2.5-coder:7b
```

---

## Observed Results (RTX 3080 10 GB, Windows 11, Podman 5.6.2)

| Condition | tok/s | Notes |
|---|---|---|
| CPU only (before fix) | 3.6 | `deploy.resources` silently ignored |
| GPU via CDI (after fix) | ~100–107 | All 29 layers on CUDA0 |

The RTX 3080 benchmark from `architecture/high_level_context.md` estimates ~74 tok/s for this model at Q4_K_M. The higher observed speed (~100–107 tok/s) is consistent with Ollama's CUDA backend on the 3080's 10 GB variant running a single-user workload with no concurrency overhead.

---

## Notes

- The CDI spec must be regenerated if the Windows NVIDIA driver is updated: `podman machine ssh` → `sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml`
- The `libnvidia-sandboxutils.so.1` warning during CDI generation is harmless — it's a WSL2 limitation, not an error
- This setup is for local development on Windows. The Proxmox VM target uses Docker + NVIDIA Container Toolkit on Linux, where `deploy.resources` works natively without CDI
