#!/usr/bin/env python3
"""Merge local-model configuration into both agents; preserve unrelated settings."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile


def read_json(path):
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f'{path} must contain a JSON object')
    return data


def save(path, text):
    """Back up changed files, then replace atomically; unchanged files stay alone."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f'Refusing to replace symlink {path}; edit its target manually')
    if path.exists() and path.read_text() == text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    if path.exists():
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        shutil.copy2(path, path.with_name(path.name + '.backup-' + stamp))
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as output:
            output.write(text)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(f'Updated {path}')


def configure(home, models, default, context, max_output):
    if not models or len(set(models)) != len(models) or default not in models:
        raise ValueError('Models must be unique and include the default')
    if not 0 < max_output < context:
        raise ValueError('Require 0 < max output tokens < context length')
    paths = {
        'claude': home / '.claude/settings.json',
        'pi_models': home / '.pi/agent/models.json',
        'pi_settings': home / '.pi/agent/settings.json',
        'ollama': home / '.ollama/config.json',
    }
    # Read every JSON file before writing any: invalid JSON should fail early.
    data = {key: read_json(path) for key, path in paths.items()}
    claude = data['claude']
    claude['model'] = default
    claude.setdefault('env', {}).update({
        'ANTHROPIC_BASE_URL': 'http://127.0.0.1:11434',
        'ANTHROPIC_AUTH_TOKEN': 'ollama',
        'ANTHROPIC_API_KEY': '',
        'ANTHROPIC_DEFAULT_MODEL': default,
        'ANTHROPIC_DEFAULT_OPUS_MODEL': default,
        'ANTHROPIC_DEFAULT_SONNET_MODEL': default,
        'ANTHROPIC_DEFAULT_HAIKU_MODEL': default,
        'ANTHROPIC_DEFAULT_FABLE_MODEL': default,
        'CLAUDE_CODE_MAX_CONTEXT_TOKENS': str(context),
        'CLAUDE_CODE_MAX_OUTPUT_TOKENS': str(max_output),
        # Local models can mistake the compaction prompt's tool prohibition
        # for a lasting user instruction and carry it into the summary.
        'DISABLE_AUTO_COMPACT': '1',
    })
    # Let /model save a different choice instead of forcing the original model
    # again at every startup through a higher-priority environment variable.
    claude['env'].pop('ANTHROPIC_MODEL', None)
    claude['modelPicker'] = {
        'replaceBuiltInOptions': True,
        'options': [{'model': name, 'label': name, 'description': 'Local Ollama model'}
                    for name in models],
    }
    # Only replace the Ollama provider, not other configured providers.
    provider = data['pi_models'].setdefault('providers', {}).setdefault('ollama', {})
    provider.update({
        'api': 'openai-completions', 'apiKey': 'ollama',
        'baseUrl': 'http://127.0.0.1:11434/v1',
        'models': [{'id': name, 'name': name, 'contextWindow': context,
                    'maxTokens': max_output, 'input': ['text']}
                   for name in models],
    })
    data['pi_settings'].update({'defaultProvider': 'ollama', 'defaultModel': default})
    # Leave room for generation and summaries, and retain less history than
    # the compaction threshold. Pi's 20k default can leave nothing to compact
    # with a 32k local context. Scale down for smaller configured contexts.
    reserve = max(max_output, min(16384, context // 2))
    keep_recent = min(4096, (context - reserve) // 2)
    overrides = data['pi_settings'].setdefault('compaction', {}).setdefault('modelOverrides', {})
    for name in models:
        overrides.setdefault(f'ollama/{name}', {}).update({
            'reserveTokens': reserve, 'keepRecentTokens': keep_recent,
        })
    integrations = data['ollama'].setdefault('integrations', {})
    ordered = [default] + [name for name in models if name != default]
    for agent in ['claude', 'pi']:
        integrations.setdefault(agent, {})['models'] = ordered
    for key, path in paths.items():
        save(path, json.dumps(data[key], indent=2) + '\n')

    # Avoid global API environment exports: only these agents use Ollama.
    path_script = '''# Managed by LocalModelSetupScript. Bash login/interactive PATH.
case ":$PATH:" in
  *":$HOME/.local/npm/bin:"*) ;;
  *) export PATH="$HOME/.local/npm/bin:$PATH" ;;
esac
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) export PATH="$HOME/.local/bin:$PATH" ;;
esac
'''
    save(home / '.config/local-model-setup/path.sh', path_script)
    source_line = '[ ! -f "$HOME/.config/local-model-setup/path.sh" ] || . "$HOME/.config/local-model-setup/path.sh"'
    for name in ['.bashrc', '.bash_profile']:
        path = home / name
        existing = path.read_text() if path.exists() else ''
        # A new .bash_profile must not hide an existing .profile.
        if name == '.bash_profile' and not path.exists():
            existing = '[ ! -f "$HOME/.profile" ] || . "$HOME/.profile"\n'
            existing += '[ ! -f "$HOME/.bashrc" ] || . "$HOME/.bashrc"\n'
        if source_line not in existing.splitlines():
            save(path, existing.rstrip('\n') + '\n\n# Local model agents\n' + source_line + '\n')
    save(home / '.config/fish/conf.d/local-model-setup.fish',
         '# Managed by LocalModelSetupScript.\n'
         'fish_add_path --path "$HOME/.local/npm/bin" "$HOME/.local/bin"\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, required=True)
    parser.add_argument('--models', nargs='+', required=True)
    parser.add_argument('--default', required=True)
    parser.add_argument('--context', type=int, required=True)
    parser.add_argument('--max-output', type=int, required=True)
    args = parser.parse_args()
    configure(args.home, args.models, args.default, args.context, args.max_output)


if __name__ == '__main__':
    main()
