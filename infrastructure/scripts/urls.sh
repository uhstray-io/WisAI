#!/bin/bash
# Print the current service URLs.
# On Windows/Podman the WSL2 IP changes on reboot — run this to get the current addresses.

if command -v podman &>/dev/null && ! command -v docker &>/dev/null; then
  IP=$(podman machine ssh "ip addr show eth0 | grep 'inet '" 2>/dev/null \
    | awk '{print $2}' | cut -d/ -f1)
  if [[ -n "$IP" ]]; then
    echo "Running via Podman (WSL2 IP: $IP)"
    echo ""
    echo "  Open WebUI:  http://$IP:${WEBUI_PORT:-3000}"
    echo "  Ollama API:  http://$IP:${OLLAMA_PORT:-11434}"
    exit 0
  fi
fi

echo "Running via Docker"
echo ""
echo "  Open WebUI:  http://localhost:${WEBUI_PORT:-3000}"
echo "  Ollama API:  http://localhost:${OLLAMA_PORT:-11434}"
