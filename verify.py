#!/usr/bin/env python3
"""Smoke-test local inference and confirm ROCm appears in the current service log."""
import argparse
import json
import subprocess
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    args = parser.parse_args()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = 'http://127.0.0.1:11434'

    def request(path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(base + path, data=data,
                                     headers={'Content-Type': 'application/json'})
        with opener.open(req, timeout=900) as response:
            result = json.load(response)
        if result.get('error'):
            raise RuntimeError(result['error'])
        return result

    result = request('/api/generate', {
        'model': args.model, 'prompt': 'Say hello briefly.', 'stream': False,
        'options': {'num_predict': 16, 'temperature': 0},
    })
    # Canonical IDs can append :latest, so compare the server's response ID.
    model_name = result.get('model', args.model)
    canonical = lambda name: name if ':' in name.rsplit('/', 1)[-1] else name + ':latest'
    loaded = [item for item in request('/api/ps').get('models', [])
              if canonical(item.get('name', '')) == canonical(model_name)]
    if not loaded or loaded[0].get('size_vram', 0) <= 0:
        raise SystemExit('Model generated, but GPU allocation was not detected. Check journalctl -u ollama.')
    # Restrict logs to the current systemd invocation; old ROCm runs are not evidence.
    invocation = subprocess.check_output(
        ['systemctl', 'show', 'ollama.service', '--property=InvocationID', '--value'], text=True).strip()
    if not invocation:
        raise SystemExit('Cannot identify the current Ollama service invocation.')
    logs = subprocess.check_output(
        ['sudo', 'journalctl', f'_SYSTEMD_INVOCATION_ID={invocation}', '--no-pager', '-o', 'cat'],
        text=True, errors='replace')
    if 'library=ROCm' not in logs or 'ROCm0' not in logs:
        raise SystemExit('GPU allocation exists, but ROCm was not verified in current logs. Inspect journalctl -u ollama.')
    print(f"ROCm verified: {args.model}, GPU allocation {loaded[0]['size_vram'] / 2**30:.2f} GiB")
    if result.get('eval_duration'):
        print(f"Short smoke test: {result.get('eval_count', 0) * 1e9 / result['eval_duration']:.1f} tokens/s")
    print('This checks inference, not agent tool-call quality or a full performance benchmark.')


if __name__ == '__main__':
    main()
