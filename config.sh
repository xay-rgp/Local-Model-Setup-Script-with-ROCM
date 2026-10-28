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
# Use the full 262K window for the bundled models so startup context leaves
# room for conversation instead of triggering compaction immediately.
# Larger context consumes more VRAM and can slow large models on a 16 GB card.
CONTEXT_LENGTH=262144
MAX_OUTPUT_TOKENS=8192
KEEP_ALIVE="10m"

# Change to a version number if you prefer pinned agent versions.
CLAUDE_VERSION="latest"                       # latest, stable, or e.g. 2.1.311
PI_PACKAGE="@earendil-works/pi-coding-agent"  # append @1.4.0 to pin

# Official Ponytail sources for each agent.
PONYTAIL_MARKETPLACE="DietrichGebert/ponytail"
PONYTAIL_PLUGIN="ponytail@ponytail"
PONYTAIL_PI_PACKAGE="git:github.com/DietrichGebert/ponytail"
