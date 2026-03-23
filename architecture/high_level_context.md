# The complete landscape of local LLM inference in early 2026

**The open-source LLM inference ecosystem has consolidated around two tiers: high-throughput serving engines (vLLM, SGLang) for API/batch workloads and llama.cpp-based tools (Ollama, LM Studio, KoboldCpp) for single-user local inference.** For your setup of multiple Proxmox VMs with 8–12 GB VRAM GPUs, the optimal strategy depends heavily on use case: Ollama or llama.cpp for interactive chat, vLLM or SGLang for API serving, and llama.cpp's RPC backend or GPUStack for distributed inference across machines. The GGUF Q4_K_M quantization format remains the universal default, fitting 7–8B models on 8 GB cards and 13–14B models on 12 GB cards. ExLlamaV3's new EXL3 format is the most exciting 2025–2026 development, achieving coherent 70B inference in under 16 GB VRAM at 1.6 bits per weight.

---

## Every major inference engine at a glance

The table below captures the full landscape. Each engine occupies a distinct niche — no single tool wins everywhere.

| Engine | Version | Stars | License | Primary Use Case | 8–12 GB VRAM | OpenAI API | Multi-GPU |
|---|---|---|---|---|---|---|---|
| **vLLM** | v0.18.0 | 48K | Apache 2.0 | Production API serving | Limited (quantized 7B) | ✅ Full | TP + PP + Ray |
| **SGLang** | v0.5.9 | 25K | Apache 2.0 | High-throughput + agents | Limited (quantized 7B) | ✅ Full | TP + PP + EP |
| **Ollama** | v0.18.2 | 166K | MIT | Local chat, easy setup | ✅ Excellent | ✅ Native | Auto split |
| **LM Studio** | v0.4.x | Proprietary | Free/Commercial | Desktop + headless | ✅ Excellent | ✅ + Anthropic | Advanced controls |
| **llama.cpp** | b8457 | 98K | MIT | Foundation / maximum control | ✅ Excellent | ✅ (server) | PP + RPC |
| **ExLlamaV2/V3** | v0.3.2 / new | 6K | MIT | Fastest single-GPU speed | ✅ Purpose-built | Via TabbyAPI | TP |
| **Aphrodite** | v0.10.0 | 2.5K | AGPL | Consumer GPU + widest quant | ✅ Best-in-class | ✅ Full | TP + PP |
| **LocalAI** | v3.10+ | 31K | MIT | Multi-modal local platform | ✅ Docker-first | ✅ Drop-in | P2P federation |
| **KoboldCpp** | v1.106 | 9.8K | AGPL | Creative writing / all-in-one | ✅ Starter packs | ✅ + Ollama API | Single GPU |
| **TGI** | v3.3.5 | 9.5K | HFOIL | Legacy HF deployments | ✅ (bitsandbytes) | ✅ Full | TP |
| **TensorRT-LLM** | v1.0 | 12K | Apache 2.0 | Max NVIDIA throughput | ❌ Datacenter only | ✅ (trtllm-serve) | Full stack |
| **GPT4All** | v3.10.0 | 77K | MIT | Non-technical desktop | ✅ Simple | ✅ (Docker) | ❌ |
| **Jan.ai** | v0.7.6 | 41K | AGPL | Teams + enterprise | ✅ Auto-tune | ✅ Full | Via Cortex |
| **Mistral.rs** | Active | 6.3K | Apache 2.0 | Rust-native multimodal | ✅ Auto-tuning | ✅ Built-in | TP |
| **MLC LLM** | Active | Medium | Apache 2.0 | Cross-platform / browser | ✅ (4-bit 8B ≈ 6 GB) | ✅ All platforms | TP |
| **Petals** | Degraded | Small | MIT | Swarm distributed | ✅ (per node) | Via wrapper | Decentralized |
| **Llamafile** | v0.10+ | Medium | Apache 2.0 | Zero-setup portable | ✅ (llama.cpp backend) | ✅ Built-in | ❌ |
| **PowerInfer** | Active | Research | MIT | Sparse model acceleration | ✅ Designed for it | Via llama.cpp | ❌ |

**HuggingFace TGI entered maintenance mode in December 2025.** The project recommends migrating to vLLM or SGLang. NVIDIA Dynamo (v1.0, March 2026) is not an inference engine but an orchestration layer that coordinates vLLM, SGLang, or TensorRT-LLM across datacenter GPU fleets — irrelevant for consumer hardware.

---

## High-performance serving engines for API and batch workloads

**vLLM** (v0.18.0, March 2026) remains the safest production choice, supporting **218 model architectures** — more than any competitor. Its PagedAttention reduces KV cache waste from 60–80% to under 4%, and the new V1 engine disaggregates prefill and decode phases for independent optimization. At 64 concurrent users on an H200, vLLM delivers **35–44× more throughput than llama.cpp**. It supports AWQ, GPTQ, FP8, and INT4 quantization but notably lacks GGUF and EXL2 support. On 8–12 GB GPUs, vLLM can run 7B models with 4-bit quantization (AWQ or GPTQ via Marlin kernels), though it was designed primarily for datacenter hardware.

**SGLang** (v0.5.9) is vLLM's fastest competitor, achieving **~16,200 tokens/sec** on H100 with Llama 3.1 8B — roughly **29% faster** than vLLM in batch throughput. Its RadixAttention stores cached prefixes in a radix tree, delivering 75–95% cache hit rates and an additional 10–20% speedup for multi-turn conversations. In a concurrent serving benchmark, SGLang processed 16 requests in 2.47 seconds versus vLLM's 11.26 seconds — a **4.6× advantage**. SGLang also leads in structured generation (JSON constrained decoding), making it ideal for agent workflows. Both engines require quantization to fit on 8–12 GB GPUs and are primarily optimized for server-class hardware.

**Aphrodite Engine** (v0.10.0) deserves special attention for your hardware. A vLLM fork designed explicitly for consumer GPUs, it supports **the widest range of quantization formats** of any engine: GGUF, GPTQ, AWQ, FP8, FP2–FP12, AQLM, QuIP#, bitsandbytes, and more. Its `--single-user-mode` allocates only the memory needed for one sequence, and it runs on GPUs as old as Pascal (GTX 10xx). For someone with 8–12 GB cards wanting vLLM-class serving with maximum format flexibility, Aphrodite is the strongest option.

---

## Local-first tools that shine on consumer GPUs

**Ollama** (v0.18.2, 166K GitHub stars, 52 million monthly downloads) is the ecosystem's gravity well. One-line installation, Docker-like model management (`ollama pull`, `ollama run`), and a systemd service make it ideal for headless Proxmox VMs. It exposes an OpenAI-compatible API at port 11434 and supports automatic GPU layer splitting with `OLLAMA_GPU_SPLIT`. A **Qwen 3.5 9B at Q4_K_M uses ~6.6 GB** and runs at 42+ tok/s, fitting comfortably on an 8 GB card. Limitations: multi-GPU on mixed GPU systems has known bugs, and partial CPU offloading degrades speed by 5–20×. Ollama wraps llama.cpp, so raw performance is essentially identical.

**llama.cpp** (b8457, 98K stars) is the foundation that Ollama, LM Studio, KoboldCpp, GPT4All, and LocalAI all build upon. It joined HuggingFace in February 2026 and supports 50+ model architectures with the GGUF format (135K+ models on HuggingFace). The key advantage over wrappers is **precise control**: the `-ngl` flag lets you offload exactly N layers to GPU, and the built-in `llama-server` provides OpenAI-compatible endpoints with speculative decoding, grammar-constrained output, and continuous batching. For distributed inference, its **RPC backend** (`GGML_RPC=ON`) lets you run `rpc-server` on each machine and combine GPUs across the network — the simplest path to multi-machine inference for your Proxmox setup.

**LM Studio** (v0.4.x) added **llmster**, a headless deployment daemon that runs without a GUI — making it viable for Proxmox VMs. It now offers both OpenAI and Anthropic-compatible API endpoints, memory estimation tools (`lms load --estimate-only`), and per-GPU enable/disable controls. The trade-off is that it's proprietary (source not auditable) and requires a commercial license for non-personal use.

**KoboldCpp** (v1.106) stands out as a **zero-installation single executable** that bundles LLM inference, Stable Diffusion image generation, TTS, speech-to-text, and a creative writing UI. It exposes KoboldAI, OpenAI, Ollama, and ComfyUI APIs simultaneously. The 12 GB Starter Pack runs Gemma3-4B plus image generation, embeddings, TTS, and Whisper all at once — an all-in-one solution for multimodal workloads on constrained hardware.

**LocalAI** (v3.10+, 31K stars) is the most ambitious multi-modal platform, wrapping llama.cpp, transformers, vLLM, ExLlamaV2, Whisper, Stable Diffusion, and more behind a drop-in OpenAI API replacement. Version 3.11 added agent management and MCP support. Its P2P federation mode using libp2p enables distributed inference across machines without centralized orchestration.

---

## ExLlamaV3 and EXL3 are the breakthrough for VRAM-constrained GPUs

**ExLlamaV2** already delivered the fastest single-GPU quantized inference — **147% more tokens/sec than bitsandbytes** and **85% more than llama.cpp** at equivalent quantization. But **ExLlamaV3**, released in 2025, pushes the boundaries dramatically with the new **EXL3 format**.

EXL3 uses trellis-coded quantization (based on Cornell's QTIP research) with Hadamard transforms to achieve state-of-the-art compression. The headline result: **Llama 3.1 70B remains coherent at just 1.6 bits per weight**, fitting into under 16 GB VRAM with a 4096-token KV cache. Quantization is also remarkably fast — a few minutes for small models, a few hours for 70B on a single RTX 4090 — compared to 720 GPU-hours on A100 for comparable-quality AQLM.

**TabbyAPI** serves as the official API backend for both ExLlamaV2 and V3, providing OpenAI-compatible endpoints. For your 8–12 GB GPUs, EXL2/EXL3's variable bit-rate allocation lets you precisely target available VRAM: a 7B model at 4 bpw fits in ~5 GB, leaving ample room for KV cache. This is the **single fastest option for interactive chat on NVIDIA consumer GPUs**.

---

## What fits in 8 GB and 12 GB of VRAM

Memory is the binding constraint for your hardware. The formula is straightforward: **VRAM ≈ parameters × bytes_per_weight + KV cache + ~1 GB overhead**. At Q4_K_M (~0.56 bytes per parameter), a 7B model needs ~4.5 GB for weights, leaving room for an 8K context KV cache on an 8 GB card.

**8 GB VRAM sweet spots:**
- Qwen 3.5 9B at Q4_K_M (~6.6 GB total, 42+ tok/s) — the best capability per VRAM byte
- Llama 3.1 8B at Q4_K_M (~5.5 GB, comfortable with 8K context)
- 13B models at Q3_K_M (~7.5 GB, barely fits with very short context)

**12 GB VRAM sweet spots:**
- Qwen3 14B or Gemma 3 12B at Q4_K_M (~9 GB, excellent capability)
- 7–8B models at Q6_K or Q8_0 (near-lossless quality)
- 27B models at Q2_K (~10 GB, significant quality loss — marginal)

**The hidden VRAM killer is context length.** For a 7B model, each 1,000 tokens of FP16 KV cache consumes ~0.11 GB. At 32K context, the cache alone can reach 3–4 GB — nearly matching the quantized weights. FP8 KV cache (supported by vLLM) halves this with under 1% accuracy loss. On 8 GB cards, keep context to 8K tokens; on 12 GB cards, 16K is comfortable.

**Quantization quality ranking at 4-bit equivalent** (best to worst): EXL2/EXL3 > AWQ > GGUF Q4_K_M ≈ bitsandbytes NF4 > GPTQ. The practical difference between AWQ and GGUF Q4_K_M is small — both score ~51.8% on HumanEval Pass@1 — while GPTQ drops to ~46%. For non-English languages, **use Q6_K minimum**; 4-bit quantization drops quality to 90–95% for non-English text.

**Unsloth Dynamic 2.0** GGUFs have emerged as the new standard for quality-optimized quantization. Instead of uniform bit allocation, Unsloth assigns 6–8 bits to sensitive layers and 2–4 bits to robust ones. Their Dynamic 3-bit DeepSeek V3.1 GGUF scores 75.6% on Aider Polyglot, surpassing many full-precision models.

---

## Distributed inference across your Proxmox machines

Three parallelism strategies exist, each with different trade-offs for your multi-machine, single-GPU-per-node setup.

**Pipeline Parallelism (PP)** splits consecutive model layers across GPUs. GPU 1 processes layers 1–16, GPU 2 processes layers 17–32, passing activations between stages. This requires **far less inter-node bandwidth** than tensor parallelism — only activation tensors (not weight partials) cross the network. The downside: autoregressive decoding creates "pipeline bubbles" where GPUs sit idle waiting for the previous stage. PP is the recommended approach for consumer multi-machine setups with standard Ethernet.

**Tensor Parallelism (TP)** shards individual matrix multiplications across GPUs, requiring frequent AllReduce synchronization. This demands **100+ Gbps interconnect** (InfiniBand or NVLink) and is impractical over standard Ethernet. With 10 GbE, the communication overhead dominates compute time.

**Petals-style swarm inference** distributes model blocks across volunteer nodes BitTorrent-style. It achieves up to 6 tok/s for Llama 2 70B — usable for interactive chat but far from optimal. However, **the public Petals network is currently degraded** with insufficient volunteers, and the project is pinned to a transformers version with 8 known CVEs.

The practical tools for your setup:

**llama.cpp RPC** is the simplest path. Run `rpc-server` on each Proxmox VM, then connect from the main node with `--rpc 192.168.1.10:50052,192.168.1.11:50052`. It distributes layers proportionally to each device's memory and supports local weight caching. With 10 GbE, expect ~48 tok/s versus ~12 tok/s on WiFi.

**GPUStack** (gpustack.ai) provides a web UI for managing LLM inference across heterogeneous GPU clusters. It automatically selects between vLLM, SGLang, TensorRT-LLM, or llama.cpp backends, distributes model layers across workers when a single GPU can't fit the model, and exposes OpenAI-compatible endpoints with monitoring dashboards. The warning: "inference performance may be constrained by cross-host network bandwidth."

**Exo** (exo-explore/exo) enables zero-configuration distributed inference with automatic device discovery via mDNS. It primarily uses pipeline parallelism and recently added tensor parallelism over Thunderbolt 5 RDMA. A demonstrated setup: 4× Mac Studios running DeepSeek V3.1 671B. For Linux/NVIDIA setups, it's less polished than llama.cpp RPC or GPUStack.

**vLLM with Ray** supports multi-node TP+PP but is overkill for consumer hardware and requires matching environments on all nodes.

---

## Proxmox GPU passthrough done right

GPU passthrough in Proxmox delivers **95–99% of bare-metal GPU performance**. The essential steps: enable VT-d/AMD-Vi in BIOS, add `intel_iommu=on iommu=pt` to GRUB, load VFIO modules, blacklist nouveau/nvidia drivers on the host, and bind the GPU to `vfio-pci` using its vendor:device IDs. VMs must use OVMF (UEFI) BIOS, q35 machine type, and `host` CPU type.

**LXC containers offer a compelling alternative** for your use case. Instead of exclusive GPU passthrough (one GPU per VM), LXC shares the host's NVIDIA driver and can let multiple containers access the same GPU simultaneously. The setup is simpler: install NVIDIA drivers on the Proxmox host, then bind-mount `/dev/nvidia0`, `/dev/nvidiactl`, and `/dev/nvidia-uvm` into the container. Performance is near-native with less overhead than VMs. The trade-off is weaker isolation (shared kernel).

**The recommended architecture for your Proxmox cluster:**
1. Each node: GPU passthrough to a Linux VM (strong isolation) or LXC (simpler, shared GPU possible)
2. Inside each VM/LXC: Docker with NVIDIA Container Toolkit running your inference engine
3. For independent models on each GPU: Run Ollama or llama-server per node, use **Olla** as a load balancer pointing to all instances
4. For a single large model spanning GPUs: Use llama.cpp RPC or GPUStack to combine VRAM across machines
5. Frontend: **Open WebUI** for ChatGPT-style interface connecting to your backend(s)

Consumer NVIDIA GPUs do not support SR-IOV or MIG partitioning — these are datacenter-only features. For sharing a single GPU between workloads, LXC containers are the only reliable approach.

---

## Benchmarks reveal clear winners per workload

Recent head-to-head testing (2025–2026) shows consistent patterns across hardware and models.

**Single-user interactive chat** on consumer GPUs: ExLlamaV2 with EXL2 is the speed champion, generating **85% more tokens/sec than llama.cpp** and **147% more than bitsandbytes** at equivalent quantization. For ease of use, Ollama/llama.cpp delivers roughly **6% faster** single-stream performance than vLLM (which has batching overhead even for single requests).

**Multi-user API serving**: vLLM and SGLang dominate. At 64 concurrent users, vLLM produces **35–44× the throughput** of llama.cpp. SGLang edges ahead with **4.6× faster completion** than vLLM in a 16-request concurrent benchmark, though this gap varies by workload.

**Batch throughput** on datacenter GPUs: SGLang and LMDeploy both achieve ~16,200 tok/s on H100 (Llama 3.1 8B), roughly **29% ahead of vLLM** at 12,500 tok/s.

**Consumer GPU generation speeds** (Q4_K_M, llama.cpp, Qwen3 8B, 16K context): RTX 3060 12 GB achieves **42 tok/s**, RTX 3080 10 GB reaches **74 tok/s**, RTX 4070 12 GB hits **52 tok/s**, and RTX 3090 24 GB delivers **87 tok/s**. Each doubling of context length costs roughly 10–25% speed. The community consensus for comfortable interactive chat is **10–20 tok/s minimum**, with 50+ tok/s preferred for code generation and 100+ tok/s for thinking models.

**Quantization speed impact**: The Marlin kernel is transformative for GPU-only serving. AWQ with Marlin achieves **741 tok/s** versus 68 tok/s without — a **10.9× speedup**. GPTQ with Marlin sees a 2.6× gain. For vLLM/SGLang serving, AWQ with Marlin offers the best throughput-quality combination.

---

## Recommendations by use case and hardware

**For interactive chat on 8–12 GB GPUs:**
Use **Ollama** (simplest) or **ExLlamaV2 + TabbyAPI** (fastest). Run Qwen 3.5 9B or Llama 3.1 8B at Q4_K_M on 8 GB; Qwen3 14B or Gemma 3 12B at Q4_K_M on 12 GB. Connect Open WebUI as your frontend. Deploy in a Proxmox LXC container for simplicity or a VM for isolation.

**For API serving for apps and agents:**
Use **vLLM** (broadest model support, most battle-tested) or **SGLang** (faster throughput, better for structured output and multi-turn). If your GPUs are 8–12 GB, **Aphrodite Engine** is the best compromise — vLLM-class serving with GGUF support and consumer GPU optimizations. Run one instance per GPU node, use Olla or nginx for load balancing.

**For batch inference and data processing:**
Use **vLLM or SGLang** for maximum throughput with concurrent request batching. On consumer GPUs, the advantage over llama.cpp emerges only with multiple concurrent requests — at 16 parallel requests, vLLM is **23% faster**. For simple sequential batch processing, llama.cpp is equally effective and simpler to deploy.

**For running models larger than one GPU can hold:**
Use **llama.cpp RPC** (simplest setup across machines), **GPUStack** (best management UI), or **vLLM with Ray** (production-grade but complex). Two 12 GB GPUs give you 24 GB combined — enough for 30B models at Q4_K_M or 70B at Q2–Q3. Pipeline parallelism over 10 GbE is workable; expect 30–70% of combined GPU performance versus a single card with equivalent total VRAM.

**For maximum flexibility across all workloads:**
Run **Ollama** on each Proxmox node as your always-on default for chat and light API use. Deploy **vLLM or Aphrodite** in Docker for high-concurrency API serving when needed. Use **llama.cpp RPC** to combine GPUs for occasional large-model runs. This layered approach covers every use case without over-engineering any single component.

## Conclusion

The 2026 inference landscape is mature and increasingly stratified. The llama.cpp ecosystem (Ollama, LM Studio, KoboldCpp) owns consumer hardware, where GGUF Q4_K_M quantization is the universal currency. vLLM and SGLang own production serving, with SGLang pulling ahead on raw throughput while vLLM leads in ecosystem breadth. The most underappreciated tools for your specific setup are **Aphrodite Engine** (the only high-performance server that natively handles GGUF on consumer GPUs), **llama.cpp RPC** (the simplest path to combining multiple single-GPU machines), and **ExLlamaV3** (whose EXL3 format makes 70B models viable on 16 GB of VRAM). The quantization landscape has shifted decisively: Unsloth Dynamic 2.0 GGUFs and EXL3 now outperform uniform quantization at every bit budget, and the old perplexity-based quality metrics are being replaced by real-world task benchmarks that tell a different story. For Proxmox deployment, LXC containers with bind-mounted GPU devices offer a lighter-weight alternative to full VM passthrough with nearly identical performance and the unique ability to share a GPU across containers.