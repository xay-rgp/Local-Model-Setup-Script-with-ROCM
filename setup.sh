#!/usr/bin/env bash
# Arch Linux + AMD ROCm installer. Run as your regular user, NOT with sudo.
# Works from Bash or Fish: bash /path/to/setup.sh
set -Eeuo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=config.sh
source "$SCRIPT_DIR/config.sh"

MODE=install
case "${1:-}" in
  --dry-run) MODE=dry-run ;;
  --configure-only) MODE=configure-only ;;
  --tune-only) MODE=tune-only ;;
  --help|-h)
    echo 'Usage: bash setup.sh [--dry-run | --configure-only | --tune-only]'
    echo 'Edit config.sh to choose models, default model, context, and Pi version.'
    echo '--dry-run: print the plan without modifying files or downloading anything.'
    echo '--configure-only: update agent JSON and shell PATH files; no installs or service changes.'
    echo '--tune-only: configure/restart existing Ollama, update Pi, verify inference; no installs or downloads.'
    exit 0 ;;
  '') ;;
  *) echo "Unknown option: $1" >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || { echo 'Only one option is supported.' >&2; exit 2; }
[[ ${#MODELS[@]} -gt 0 ]] || { echo 'MODELS must not be empty.' >&2; exit 2; }
found=false
for model in "${MODELS[@]}"; do
  [[ "$model" =~ ^[A-Za-z0-9][A-Za-z0-9._:/-]*$ ]] || { echo "Invalid model name: $model" >&2; exit 2; }
  [[ "$model" != *:cloud ]] || { echo 'This installer is for local models, not :cloud models.' >&2; exit 2; }
  if [[ "$model" == "$DEFAULT_MODEL" ]]; then found=true; fi
done
[[ "$found" == true ]] || { echo 'DEFAULT_MODEL must be in MODELS.' >&2; exit 2; }
[[ "$CONTEXT_LENGTH" =~ ^[1-9][0-9]*$ && "$MAX_OUTPUT_TOKENS" =~ ^[1-9][0-9]*$ ]] || {
  echo 'Context and output limits must be positive integers.' >&2; exit 2;
}
(( MAX_OUTPUT_TOKENS < CONTEXT_LENGTH )) || { echo 'Output limit must be smaller than context.' >&2; exit 2; }
[[ "$KEEP_ALIVE" =~ ^[0-9]+[smh]$ ]] || { echo 'KEEP_ALIVE must look like 10m or 1h.' >&2; exit 2; }

[[ "$FLASH_ATTENTION" == 1 || "$FLASH_ATTENTION" == 0 ]] || { echo 'FLASH_ATTENTION must be 0 or 1.' >&2; exit 2; }
[[ "$KV_CACHE_TYPE" == f16 || "$KV_CACHE_TYPE" == q8_0 || "$KV_CACHE_TYPE" == q4_0 ]] || { echo 'Invalid KV_CACHE_TYPE.' >&2; exit 2; }
[[ "$KV_CACHE_TYPE" == f16 || "$FLASH_ATTENTION" == 1 ]] || { echo 'Quantized KV cache requires Flash Attention.' >&2; exit 2; }

if [[ "$MODE" == dry-run ]]; then
  cat <<PLAN
Target: Arch Linux x86_64 with an AMD ROCm-supported GPU.
1. Run a normal full Arch upgrade and install ollama, ollama-rocm,
   nodejs, npm, git, curl, python (sudo pacman -Syu --needed ...).
2. Write a backed-up systemd drop-in: ROCm only, context=$CONTEXT_LENGTH,
   one parallel request, one loaded model, keep-alive=$KEEP_ALIVE,
   Flash Attention=$FLASH_ATTENTION, KV cache=$KV_CACHE_TYPE.
   Enable and restart ollama.service (interrupts active generations).
3. Pull these models (existing downloads are reused):
PLAN
  printf '   %s\n' "${MODELS[@]}"
  cat <<PLAN
4. Install Pi ($PI_PACKAGE) as this user.
5. Configure Pi for local Ollama; default=$DEFAULT_MODEL.
   Add shell PATH entries for Bash and Fish; back up changed existing files.
6. Install $PONYTAIL_PI_PACKAGE in Pi.
7. Generate a short response with the default model and verify ROCm GPU use.
Other downloaded models are never deleted. No changes made by this dry run.
PLAN
  exit 0
fi

(( EUID != 0 )) || { echo 'Run as your normal user; the script uses sudo only for system changes.' >&2; exit 1; }
export PATH="$HOME/.local/bin:$HOME/.local/npm/bin:$PATH"
export OLLAMA_HOST=127.0.0.1:11434

configure_pi() {
  python "$SCRIPT_DIR/configure.py" --home "$HOME" \
    --default "$DEFAULT_MODEL" --context "$CONTEXT_LENGTH" \
    --max-output "$MAX_OUTPUT_TOKENS" --models "${MODELS[@]}"
}

if [[ "$MODE" == configure-only ]]; then
  configure_pi
  echo 'Pi settings updated. Ollama service context and model downloads were not changed.'
  exit 0
fi

[[ -f /etc/arch-release && $(uname -m) == x86_64 ]] || {
  echo 'This installer targets Arch Linux x86_64. It does not support other distributions.' >&2; exit 1;
}
command -v sudo >/dev/null || { echo 'Install/configure sudo first.' >&2; exit 1; }

temp_dir=$(mktemp -d)
trap 'rm -rf -- "$temp_dir"' EXIT
trap 'echo "Setup stopped at line $LINENO. Fix the reported error and rerun; completed downloads are reused." >&2' ERR

if [[ "$MODE" == install ]]; then
  echo 'Installing system packages with a full Arch upgrade (pacman will show its normal confirmation)...'
  sudo pacman -Syu --needed ollama ollama-rocm nodejs npm git curl python
  # Check the Node that Pi will actually use, including an active nvm version.
  node -e 'const [a,b]=process.versions.node.split(".").map(Number); if(a<22 || (a===22 && b<19)) process.exit(1)' || {
    echo 'Pi requires Node.js >=22.19.0. Update your active nvm version or use /usr/bin/node.' >&2; exit 1;
  }

fi

echo 'Configuring the system Ollama service for ROCm...'
cat > "$temp_dir/ollama.conf" <<CONF
# Managed by LocalModelSetupScript/config.sh. Change that file and rerun setup.
[Service]
Environment="OLLAMA_HOST=127.0.0.1:11434"
Environment="OLLAMA_VULKAN=0"
Environment="OLLAMA_CONTEXT_LENGTH=$CONTEXT_LENGTH"
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_KEEP_ALIVE=$KEEP_ALIVE"
Environment="OLLAMA_FLASH_ATTENTION=$FLASH_ATTENTION"
Environment="OLLAMA_KV_CACHE_TYPE=$KV_CACHE_TYPE"
CONF
# Sort after existing context.conf and the older 90-local-model-setup.conf.
dropin=/etc/systemd/system/ollama.service.d/zz-local-model-setup.conf
sudo install -d -m 0755 /etc/systemd/system/ollama.service.d
if sudo test -e "$dropin" && ! sudo cmp -s "$temp_dir/ollama.conf" "$dropin"; then
  sudo cp -p -- "$dropin" "$dropin.backup-$(date +%Y%m%d-%H%M%S-%N)"
fi
sudo install -m 0644 "$temp_dir/ollama.conf" "$dropin"
sudo systemctl daemon-reload
sudo systemctl enable ollama.service
sudo systemctl restart ollama.service
ready=false
for ((attempt=0; attempt<60; attempt++)); do
  if curl --noproxy '*' --fail --silent http://127.0.0.1:11434/api/version >/dev/null; then
    ready=true
    break
  fi
  sleep 1
done
[[ "$ready" == true ]] || { echo 'Ollama failed to start. Run: journalctl -u ollama -n 100' >&2; exit 1; }

if [[ "$MODE" == tune-only ]]; then
  # Verify the service before reducing Pi's advertised windows.
  python "$SCRIPT_DIR/verify.py" --model "$DEFAULT_MODEL" --context "$CONTEXT_LENGTH" \
    --kv-cache "$KV_CACHE_TYPE" --flash-attention "$FLASH_ATTENTION"
  configure_pi
  echo 'Tuning applied. Restart Pi; use a new session or /compact before continuing old work.'
  exit 0
fi

echo 'Pulling the models listed in config.sh...'
for model in "${MODELS[@]}"; do
  ollama pull "$model"
done

echo 'Installing Pi for the current user...'
PATH="/usr/bin:$PATH" /usr/bin/npm install --global --ignore-scripts \
  --prefix "$HOME/.local/npm" "$PI_PACKAGE"
configure_pi

echo 'Installing Ponytail in Pi...'
# Run package commands outside a project, so project settings cannot redirect them.
(
  cd "$temp_dir"
  pi install "$PONYTAIL_PI_PACKAGE" --no-approve
)

echo 'Checking the installed programs, models and GPU inference...'
pi --version
ollama list
python "$SCRIPT_DIR/verify.py" --model "$DEFAULT_MODEL" --context "$CONTEXT_LENGTH" \
    --kv-cache "$KV_CACHE_TYPE" --flash-attention "$FLASH_ATTENTION"
echo 'Setup complete. Open a new terminal, then run pi; use /model to switch models.'
echo 'Start new Pi sessions to load Ponytail. Its help command is /ponytail-help.'
