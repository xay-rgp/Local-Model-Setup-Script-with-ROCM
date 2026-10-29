# Local model setup: Arch Linux + AMD ROCm

Installs Ollama with ROCm, your three models, Pi coding agent, and
Ponytail for Pi. Written for your Arch Linux x86_64 / RX 9060 XT setup.
It can also run on another Arch x86_64 machine with a supported AMD GPU;
it is not an Ubuntu, NVIDIA, macOS, or Windows installer.

## Run from Bash or Fish

```sh
bash /home/xay/Local-Model-Setup-Script-with-ROCM/setup.sh --dry-run
bash /home/xay/Local-Model-Setup-Script-with-ROCM/setup.sh
```

Run as your regular user, **not** `sudo bash`. The script requests sudo for
system packages, the service configuration, and reading GPU verification logs.
It performs `pacman -Syu --needed ...` (a full Arch upgrade) with pacman's usual
confirmation, then enables/restarts Ollama. Finish active generations first.
Downloads include the three model files plus ROCm and Pi packages;
existing Ollama blobs are reused. Internet access is required.

Open a fresh terminal afterward and run `pi`. It uses local
Ollama at `127.0.0.1:11434`; `/model` selects a model. Start new sessions to load
Ponytail; `/ponytail-help` shows its commands. No paid API key is needed for
local inference. Agent and plugin behavior still depends on model tool support.

## Change models or settings

Edit **config.sh**, the only file needed for ordinary changes:

```bash
MODELS=(
  "qwen3-coder:30b"
  "orcarouter/Qwen3.8-27B-Uncensored:latest"
  "huihui_ai/Qwen3.8-abliterated:27b"
)
DEFAULT_MODEL="${MODELS[0]}"
CONTEXT_LENGTH=65536
MAX_OUTPUT_TOKENS=8192
```

Add/remove model lines, change the default, and rerun `bash setup.sh`. It pulls
the selected models and rebuilds the Pi model menu. It **never deletes old
model downloads**; remove unwanted ones yourself with `ollama rm NAME`.
Use local models with tool support and a context window at least as large as
CONTEXT_LENGTH. The generated Pi entries default to text input.

The default 65,536-token context balances tool/startup space against memory on
this 16 GB GPU. It configures Ollama's `OLLAMA_CONTEXT_LENGTH` and Pi's model windows together. Pi automatic
compaction is explicitly enabled: it triggers above 49,152 tokens, reserves
16,384 tokens for responses/summaries, and keeps 4,096 recent tokens alongside
the summary. Overrides cover all configured models. Other model overrides
are preserved; a previous global `compaction.enabled=false` is intentionally
changed to `true`. Project-local settings can override global settings.

Ollama uses Flash Attention and a `q8_0` KV cache by default, with one parallel
request and one loaded model. Q8 uses roughly half the KV-cache memory of f16,
with a small precision tradeoff. This frees memory for model layers, but does
not guarantee that a 27B/30B model fits entirely on the GPU or a particular
speed. Set `KV_CACHE_TYPE="f16"` if quality regresses; quantized cache requires
`FLASH_ATTENTION=1`. See the [Ollama FAQ](https://docs.ollama.com/faq).

Apply tuning to an existing installation without upgrades, model downloads,
or agent/plugin reinstalls:

```sh
bash /home/xay/Local-Model-Setup-Script-with-ROCM/setup.sh --tune-only
```

Finish active work first: this restarts Ollama, verifies default-model inference
and context, then updates Pi settings with backups. Restart Pi after
it finishes. Prefer a new session for completed work. If an old conversation
exceeds the new context, compact it **before** reducing the server limit; a
summary request for an oversized transcript may itself exceed that limit.
Compaction summarizes history; it does not delete project files.

`bash setup.sh --configure-only` updates Pi settings and Bash/Fish PATH
files without downloading, installing plugins, or restarting Ollama. Use this
only if the models are already installed and the service already has the
desired context length. Use `--tune-only` when changing server memory settings.

`PI_PACKAGE` can include a version suffix; the default installs the current
release. Pi needs Node >=22.19.0;
if nvm shadows the system Node with an older version, update your active nvm
version first. The installer installs system Node so Ponytail hooks can also
find Node in non-interactive shells.

## What changes

- System packages: Ollama, its ROCm backend, Node/npm, Git, curl, Python.
- `/etc/systemd/system/ollama.service.d/zz-local-model-setup.conf`: disables
  Vulkan to choose ROCm, sets loopback binding, context, one parallel request,
  one loaded model, Flash Attention, Q8 KV cache, and keep-alive. It leaves the existing model-store path
  alone. Its name sorts after the existing `context.conf` and the older
  `90-local-model-setup.conf`, which are preserved. Later overrides can still
  affect the service; verification checks the effective configuration.
- Pi: npm installation under `~/.local/npm` (without dependency install scripts).
- `~/.pi/agent/models.json` and `settings.json`: Ollama model list, default,
  context/output limits, and compaction overrides for every configured model.
- `~/.ollama/config.json`: Pi launch selections.
- Bash startup files plus `~/.config/fish/conf.d/local-model-setup.fish`:
  make the installed Pi command available in new terminals.
- Ponytail: official Pi Git package.

Changed existing configuration files receive timestamped `.backup-*` siblings.
Unrelated JSON settings, permissions, other providers, and existing plugin
entries are preserved. The script does not enable permission bypasses.
Repeated configuration runs make no writes when nothing changes. A failed
installation stops with an error; completed packages/downloads remain and
the script can be rerun. There is no automatic transaction rollback.

To undo the service configuration, remove only the drop-in named above and
run `sudo systemctl daemon-reload` and `sudo systemctl restart ollama`.
Older drop-ins (including `context.conf`) then take effect again.
Restore individual JSON or shell files from their backups as needed.
Ponytail can be removed with `pi remove git:github.com/DietrichGebert/ponytail`.

## Verification and tests

At the end of installation, verify.py generates a short default-model response,
checks `/api/ps` GPU allocation and loaded context against `CONTEXT_LENGTH`,
and checks ROCm detection in the current
systemd invocation's logs. This verifies inference, not agent tool-call quality.
Other models are downloaded and listed but are not loaded for inference tests.

Offline configuration tests, Bash/Python syntax checks, and dry-run are available
below. Live ROCm performance must be checked on the host after applying tuning;
the full installer is not covered by the offline tests.

Offline development checks (no system changes):

```sh
cd /home/xay/Local-Model-Setup-Script-with-ROCM
bash -n setup.sh config.sh
python -B -m unittest -v test_configure.py test_verify.py
bash setup.sh --dry-run
```

Files: config.sh contains preferences; setup.sh orchestrates installation;
configure.py handles backed-up JSON/shell edits; verify.py checks GPU inference;
test_configure.py tests configuration preservation, repeat runs and model changes;
test_verify.py tests service conflicts, model context overrides, and GPU checks.

## Official references

- [Arch Ollama ROCm package](https://archlinux.org/packages/extra/x86_64/ollama-rocm/)
- [Pi installation](https://pi.dev/docs/latest/quickstart)
- [Ponytail installation](https://github.com/DietrichGebert/ponytail/blob/main/INSTALL.md)
