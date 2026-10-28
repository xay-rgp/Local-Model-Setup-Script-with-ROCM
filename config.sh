# Edit this file, then run: bash setup.sh
# Bash syntax: one quoted Ollama model name per line. These names are also
# used in the Claude Code and Pi model menus. Old model downloads are NOT deleted.
MODELS=(
  "qwen3-coder:30b"
  "orcarouter/Qwen3.8-27B-Uncensored:latest"
  "huihui_ai/Qwen3.8-abliterated:27b"
)
DEFAULT_MODEL="${MODELS[0]}"

# Match the context seen by both agents to Ollama's actual context allocation.
# 64K balances agent startup/tool context against VRAM on a 16 GB card.
# Pi compacts around 48K; larger values increase cache memory and CPU offload.
CONTEXT_LENGTH=65536
MAX_OUTPUT_TOKENS=8192
KEEP_ALIVE="10m"
FLASH_ATTENTION=1
KV_CACHE_TYPE="q8_0"  # roughly half the f16 KV memory; use f16 if quality regresses

# Change to a version number if you prefer pinned agent versions.
CLAUDE_VERSION="latest"                       # latest, stable, or e.g. 2.1.311
PI_PACKAGE="@earendil-works/pi-coding-agent"  # append @1.4.0 to pin

# Official Ponytail sources for each agent.
PONYTAIL_MARKETPLACE="DietrichGebert/ponytail"
PONYTAIL_PLUGIN="ponytail@ponytail"
PONYTAIL_PI_PACKAGE="git:github.com/DietrichGebert/ponytail"
