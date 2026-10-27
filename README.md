# Local model setup: Arch Linux + AMD ROCm

Installs Ollama with ROCm, your two models, Claude Code, Pi coding agent, and
Ponytail in both agents. Written for your Arch Linux x86_64 / RX 9060 XT setup.
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
Downloads include roughly 36 GB of model files plus ROCm and agent packages;
existing Ollama blobs are reused. Internet access is required.

Open a fresh terminal afterward and run `claude` or `pi`. Both use local
Ollama at `127.0.0.1:11434`; `/model` selects a model. Start new sessions to load
Ponytail; `/ponytail-help` shows its commands. No paid API key is needed for
local inference. Agent and plugin behavior still depends on model tool support.

## Change models or settings

Edit **config.sh**, the only file needed for ordinary changes:

```bash
MODELS=(
  "qwen3-coder:30b"
  "orcarouter/Qwen3.8-27B-Uncensored:latest"
)
DEFAULT_MODEL="${MODELS[0]}"
CONTEXT_LENGTH=32768
MAX_OUTPUT_TOKENS=8192
```

Add/remove model lines, change the default, and rerun `bash setup.sh`. It pulls
the selected models and rebuilds the two agent menus. It **never deletes old
model downloads**; remove unwanted ones yourself with `ollama rm NAME`.
Use local models with tool support and a context window at least as large as
CONTEXT_LENGTH. The generated Pi entries default to text input.

Both models also receive Pi compaction overrides: with the default context,
16,384 tokens are reserved and 4,096 tokens of recent history are retained.
This leaves room for responses and summaries and avoids retaining too much
history to compact a smaller local session. The limits scale down for smaller
contexts, and the reserve is always at least `MAX_OUTPUT_TOKENS`. Unrelated
model overrides and an explicitly disabled compaction preference are preserved.
After applying this fix with `--configure-only`, restart Pi, resume the affected
session, and run `/compact` before continuing. Responses can still be truncated
if they exceed the output limit.

`bash setup.sh --configure-only` updates agent settings and Bash/Fish PATH
files without downloading, installing plugins, or restarting Ollama. Use this
only if the models are already installed and the service already has the
desired context length. Run the full script when changing the server context.

`CLAUDE_VERSION` accepts `latest`, `stable`, or a version number. `PI_PACKAGE`
can include a version suffix. The default is current releases. Claude Code's
custom model picker requires version 2.1.242 or newer. Pi needs Node >=22.19.0;
if nvm shadows the system Node with an older version, update your active nvm
version first. The installer installs system Node so Ponytail hooks can also
find Node in non-interactive shells.

## What changes

- System packages: Ollama, its ROCm backend, Node/npm, Git, curl, Python, jq.
- `/etc/systemd/system/ollama.service.d/90-local-model-setup.conf`: disables
  Vulkan to choose ROCm, sets loopback binding, context, one parallel request,
  one loaded model, and keep-alive. It leaves the existing model-store path
  alone. Existing custom systemd overrides can still affect the service.
- Claude Code: official native installer into the current user's home.
- Pi: npm installation under `~/.local/npm` (without dependency install scripts).
- `~/.claude/settings.json`: local endpoint, context/output limits, model menu,
  default and background model mappings. All aliases initially use the default.
- `~/.pi/agent/models.json` and `settings.json`: Ollama model list, default,
  context/output limits, and compaction overrides for every configured model.
- `~/.ollama/config.json`: Claude and Pi launch selections.
- Bash startup files plus `~/.config/fish/conf.d/local-model-setup.fish`:
  make the installed agent commands available in new terminals.
- Ponytail: official Claude plugin marketplace and official Pi Git package.

Changed existing configuration files receive timestamped `.backup-*` siblings.
Unrelated JSON settings, permissions, other providers, and existing plugin
entries are preserved. The script does not enable permission bypasses.
Repeated configuration runs make no writes when nothing changes. A failed
installation stops with an error; completed packages/downloads remain and
the script can be rerun. There is no automatic transaction rollback.

To undo the service configuration, remove only the drop-in named above and
run `sudo systemctl daemon-reload` and `sudo systemctl restart ollama`.
Restore individual JSON or shell files from their backups as needed.
Ponytail can be removed with `claude plugin uninstall ponytail@ponytail`
and `pi remove git:github.com/DietrichGebert/ponytail`.

## Verification and tests

At the end of installation, verify.py generates a short default-model response,
checks `/api/ps` GPU allocation, and checks ROCm detection in the current
systemd invocation's logs. This verifies inference, not agent tool-call quality.
Other models are downloaded and listed but are not loaded for inference tests.

Validation: all eight offline configuration tests passed, Bash and
Python syntax checks passed, generated Fish configuration parsed successfully,
and dry-run completed. The full installer has not been executed end to end;
no packages or live agent settings were changed while creating these files.

Offline development checks (no system changes):

```sh
cd /home/xay/Local-Model-Setup-Script-with-ROCM
bash -n setup.sh config.sh
python -m unittest -v test_configure.py
bash setup.sh --dry-run
```

Files: config.sh contains preferences; setup.sh orchestrates installation;
configure.py handles backed-up JSON/shell edits; verify.py checks GPU inference;
test_configure.py tests configuration preservation, repeat runs and model changes.

## Official references

- [Arch Ollama ROCm package](https://archlinux.org/packages/extra/x86_64/ollama-rocm/)
- [Ollama with Claude Code](https://docs.ollama.com/integrations/claude-code)
- [Claude Code installer](https://code.claude.com/docs/en/setup)
- [Claude Code model configuration](https://code.claude.com/docs/en/model-config)
- [Pi installation](https://pi.dev/docs/latest/quickstart)
- [Ponytail installation for both agents](https://github.com/DietrichGebert/ponytail/blob/main/INSTALL.md)
