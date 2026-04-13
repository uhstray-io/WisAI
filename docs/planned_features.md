# Improvement Plan

Practical changes to make the WisAI stack more reliable, correct, and production-ready for homelab deployment.

---

## 1. Add container health checks

**Status:** Done

**Why:** `depends_on: ollama` only waits for the container process to start, not for Ollama to be listening on its port. On slower hardware or cold starts (model loading), Open WebUI can start before Ollama is ready, causing connection errors in the UI until the user manually refreshes.

**How:**
- Add a healthcheck to the `ollama` service in `docker-compose.yml`:
  ```yaml
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:11434/"]
    interval: 10s
    timeout: 5s
    retries: 5
    start_period: 30s
  ```
- Update `open-webui` to wait for healthy:
  ```yaml
  depends_on:
    ollama:
      condition: service_healthy
  ```
- Note: The Ollama image includes `curl`, so no extra tooling is needed. If a future image removes it, switch to `wget -q --spider`.

---

## 2. Pin container image versions

**Status:** Done

**Why:** `ollama/ollama:latest` and `ghcr.io/open-webui/open-webui:main` will silently change on every `docker compose pull` or fresh deploy. A bad upstream release could break the stack with no rollback path. Pinning gives reproducible deploys and intentional upgrades.

**How:**
- Check current versions:
  ```bash
  docker exec ollama ollama --version
  docker inspect open-webui --format '{{index .Config.Labels "org.opencontainers.image.version"}}'
  ```
- Replace `latest` / `main` with specific tags in `docker-compose.yml`:
  ```yaml
  image: ollama/ollama:0.6.2        # pin to current stable
  image: ghcr.io/open-webui/open-webui:v0.6.6
  ```
- Add a comment above each image line noting when it was last updated.
- Document the upgrade process: bump the tag, `docker compose pull`, `docker compose up -d`.

---

## 3. Add resource limits to containers

**Status:** Not started

**Why:** Neither container has memory or CPU constraints. Open WebUI runs a Python backend that can spike memory during model indexing or large file uploads. On a homelab node with 16-32 GB RAM shared between the OS, Ollama VRAM mapping, and Open WebUI, an OOM event could kill the entire node.

**How:**
- Add limits to `docker-compose.yml`:
  ```yaml
  open-webui:
    mem_limit: 2g
    cpus: 2.0

  ollama:
    # Ollama manages its own VRAM; CPU/RAM limits prevent runaway CPU inference fallback
    mem_limit: 8g
    cpus: 4.0
  ```
- Make limits configurable via `.env`:
  ```env
  OLLAMA_MEM_LIMIT=8g
  OLLAMA_CPUS=4.0
  WEBUI_MEM_LIMIT=2g
  WEBUI_CPUS=2.0
  ```
- Document recommended values for typical homelab hardware (16 GB, 32 GB, 64 GB nodes).

---

## 4. Auto-pull models on first start

**Status:** Not started

**Why:** After `docker compose up -d`, the user must separately run `pull-models.sh`. A new user following the quickstart will see an empty model list in Open WebUI until they realize they need to pull models. This is a friction point.

**How:**
- Create `scripts/entrypoint-wrapper.sh` that:
  1. Starts Ollama normally in the background.
  2. Waits for Ollama to respond on `:11434`.
  3. Checks if any models are loaded (`ollama list`). If empty, pulls a default model set based on a `VRAM_PROFILE` env var.
  4. Brings Ollama to the foreground (`wait`).
- Wire it into compose:
  ```yaml
  ollama:
    entrypoint: ["/scripts/entrypoint-wrapper.sh"]
    volumes:
      - ./scripts/entrypoint-wrapper.sh:/scripts/entrypoint-wrapper.sh:ro
    environment:
      - VRAM_PROFILE=${VRAM_PROFILE:-8gb}
  ```
- Add `VRAM_PROFILE` to `.env.example` with a comment.
- Keep `pull-models.sh` as-is for manual use.

---

## 5. Add `.env` validation script

**Status:** Not started

**Why:** Misconfigurations are silent. If `MODELS_PATH` points to a directory that doesn't exist, Ollama will start but fail to persist models. If `OLLAMA_NODES` is set but malformed, multi-node won't work. Catching these before `compose up` saves debugging time.

**How:**
- Create `scripts/validate-env.sh` that checks:
  - `.env` file exists (remind user to copy `.env.example` if not).
  - `MODELS_PATH`, if set, is an existing directory with write permissions.
  - `OLLAMA_NODES`, if set, contains valid semicolon-separated URLs (basic regex or `curl` ping each endpoint).
  - `GPU_COUNT` is a positive integer.
  - Ports are in valid range and not already in use (`ss -tlnp` or `netstat`).
- Print clear pass/fail messages for each check.
- Optionally call this from the entrypoint wrapper (item 4) or document running it before `compose up`.

---

## 6. Add basic monitoring

**Status:** Not started

**Why:** There is no visibility into GPU utilization, VRAM usage, temperature, or inference throughput. When the stack feels slow, there's no way to tell if the GPU is saturated, thermal throttling, or if the model is falling back to CPU inference.

**How:**

Lightweight approach (no Grafana):
- Create `scripts/monitor.sh` that runs in a `watch` loop:
  ```bash
  watch -n 2 'nvidia-smi; echo "---"; docker exec ollama ollama ps'
  ```
- This gives real-time GPU stats + which models are loaded and their VRAM usage.

Full approach (Grafana stack):
- Add optional services to a new `docker-compose.monitoring.yml`:
  - `nvidia-gpu-exporter` — Prometheus exporter for `nvidia-smi` metrics.
  - `prometheus` — scrapes the exporter.
  - `grafana` — pre-configured dashboard showing GPU temp, VRAM %, power draw, inference rate.
- Keep this file separate so it's opt-in and doesn't bloat the core stack.
- Document with: `docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d`.

**Recommendation:** Start with the script. Add Grafana only if operating multiple nodes.

---

## 7. Backup Open WebUI data

**Status:** Not started

**Why:** Chat history, user accounts, and settings live in the `open-webui-data` Docker volume. Docker volumes are not backed up by default. A `docker system prune`, accidental `docker compose down -v`, or disk failure loses everything.

**How:**
- Create `scripts/backup.sh`:
  ```bash
  BACKUP_DIR="${BACKUP_DIR:-./backups}"
  mkdir -p "$BACKUP_DIR"
  TIMESTAMP=$(date +%Y%m%d-%H%M%S)
  docker run --rm \
    -v open-webui-data:/data:ro \
    -v "$BACKUP_DIR":/backup \
    alpine tar czf "/backup/open-webui-$TIMESTAMP.tar.gz" -C /data .
  echo "Backup: $BACKUP_DIR/open-webui-$TIMESTAMP.tar.gz"
  ```
- Create a matching `scripts/restore.sh` that extracts a backup into the volume.
- Document running this on a cron (weekly or before upgrades).
- Add `backups/` to `.gitignore`.

---

## 8. Improve `urls.sh` reliability

**Status:** Not started

**Why:** The script uses `podman machine ssh` to get the WSL2 IP from `eth0`. The interface name isn't guaranteed to be `eth0` on all WSL2 distros or Podman machine versions. If it fails silently, the script falls through to printing `localhost`, which won't work from Windows.

**How:**
- Use a more robust IP detection method:
  ```bash
  IP=$(podman machine ssh "hostname -I" 2>/dev/null | awk '{print $1}')
  ```
- Add a fallback that checks `wsl hostname -I` directly if running from Windows (Git Bash / PowerShell).
- Print a warning if no IP is detected instead of silently falling through.

---

## 9. Add a `Makefile` or task runner

**Status:** Not started

**Why:** The project has several multi-step workflows (start, stop, pull models, backup, validate, monitor) spread across different scripts. Users need to remember script names and paths. A single entry point reduces friction.

**How:**
- Create a `Makefile` in the project root:
  ```makefile
  .PHONY: up down pull validate monitor backup

  up: validate
  	cd infrastructure && docker compose up -d

  down:
  	cd infrastructure && docker compose down

  pull:
  	cd infrastructure && ./scripts/pull-models.sh $(VRAM)

  validate:
  	cd infrastructure && ./scripts/validate-env.sh

  monitor:
  	cd infrastructure && ./scripts/monitor.sh

  backup:
  	cd infrastructure && ./scripts/backup.sh
  ```
- Then usage becomes: `make up`, `make pull VRAM=12gb`, `make backup`.
- Alternative: a `wisai.sh` wrapper script if `make` isn't available on the target system.

---

## Priority Order

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| 1 | Add health checks (#1) | Small | Eliminates startup race condition |
| 2 | Pin image versions (#2) | Small | Prevents surprise breakage |
| 3 | `.env` validation (#5) | Small | Catches misconfig before it bites |
| 4 | Improve `urls.sh` (#8) | Small | Fixes unreliable Podman IP detection |
| 5 | Resource limits (#3) | Small | Prevents OOM on shared nodes |
| 6 | Backup script (#7) | Small | Protects chat history |
| 7 | Auto-pull models (#4) | Medium | Better first-run experience |
| 8 | Monitoring (#6) | Medium | Visibility into GPU/inference health |
| 9 | Makefile / task runner (#9) | Small | Quality-of-life convenience |
