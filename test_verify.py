"""Verification fails on conflicting service settings before running inference."""
import contextlib
import io
import json
import unittest
from unittest.mock import MagicMock, patch

import verify


class VerificationTests(unittest.TestCase):
    def run_check(self, environment, context=65536, vram=1000):
        opener = MagicMock()
        responses = [
            {'model': 'example:latest'},
            {'models': [{'name': 'example:latest', 'size_vram': vram,
                         'context_length': context}]},
        ]
        opener.open.side_effect = [contextlib.closing(io.StringIO(json.dumps(r)))
                                   for r in responses]
        with patch('sys.argv', ['verify.py', '--model', 'example', '--context', '65536',
                                '--kv-cache', 'q8_0', '--flash-attention', '1']), \
             patch('verify.urllib.request.build_opener', return_value=opener), \
             patch('verify.subprocess.check_output', side_effect=[
                 environment, 'invocation-id', 'library=ROCm ROCm0']), \
             contextlib.redirect_stdout(io.StringIO()):
            verify.main()
        return opener

    environment = ('OLLAMA_CONTEXT_LENGTH=65536 OLLAMA_KV_CACHE_TYPE=q8_0 '
                   'OLLAMA_FLASH_ATTENTION=1')

    def test_matching_service_and_loaded_context_pass(self):
        self.assertEqual(self.run_check(self.environment).open.call_count, 2)

    def test_later_override_is_rejected(self):
        with self.assertRaisesRegex(SystemExit, 'OLLAMA_CONTEXT_LENGTH'):
            self.run_check(self.environment.replace('65536', '262144'))

    def test_model_context_override_is_rejected(self):
        with self.assertRaisesRegex(SystemExit, 'loaded context=262144'):
            self.run_check(self.environment, context=262144)

    def test_cpu_only_model_is_rejected(self):
        with self.assertRaisesRegex(SystemExit, 'GPU allocation was not detected'):
            self.run_check(self.environment, vram=0)


if __name__ == '__main__':
    unittest.main()
