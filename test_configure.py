"""Offline tests: configuration preservation, reruns and model changes."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from configure import configure


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.models = ['qwen3-coder:30b', 'orcarouter/Qwen3.8-27B-Uncensored:latest']

    def write(self, name, data):
        path = self.home / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def read(self, name):
        return json.loads((self.home / name).read_text())

    def run_configuration(self, models=None):
        models = self.models if models is None else models
        with contextlib.redirect_stdout(io.StringIO()):
            configure(self.home, models, models[0], 32768, 8192)

    def test_existing_settings_and_plugins_are_preserved(self):
        original = {'theme': 'dark', 'permissions': {'deny': ['Bash(rm *)']},
                    'enabledPlugins': {'example@market': True},
                    'env': {'UNRELATED': 'preserve', 'ANTHROPIC_MODEL': 'old-model',
                            'DISABLE_AUTO_COMPACT': '1'}}
        self.write('.claude/settings.json', original)
        self.write('.pi/agent/settings.json', {'packages': ['git:example/repo'], 'theme': 'dark'})
        self.write('.pi/agent/models.json', {'providers': {'other': {'baseUrl': 'https://example.test'}}})
        self.run_configuration()
        actual = self.read('.claude/settings.json')
        for key in ['theme', 'permissions', 'enabledPlugins']:
            self.assertEqual(actual[key], original[key])
        self.assertEqual(actual['env']['UNRELATED'], 'preserve')
        self.assertNotIn('ANTHROPIC_MODEL', actual['env'])
        self.assertNotIn('DISABLE_AUTO_COMPACT', actual['env'])
        self.assertEqual(self.read('.pi/agent/settings.json')['packages'], ['git:example/repo'])
        self.assertIn('other', self.read('.pi/agent/models.json')['providers'])
        backups = list((self.home / '.claude').glob('settings.json.backup-*'))
        self.assertEqual(json.loads(backups[0].read_text()), original)

    def test_second_run_changes_nothing(self):
        self.run_configuration()
        self.assertNotIn('DISABLE_AUTO_COMPACT', self.read('.claude/settings.json')['env'])
        before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in self.home.rglob('*') if p.is_file()}
        self.run_configuration()
        after = {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                 for p in self.home.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_both_models_get_limits_and_compaction_without_losing_preferences(self):
        unrelated = {'reserveTokens': 10000, 'keepRecentTokens': 5000}
        self.write('.pi/agent/settings.json', {'compaction': {
            'enabled': False, 'keepRecentTokens': 20000,
            'modelOverrides': {'other/model': unrelated},
        }})
        self.run_configuration()
        models = self.read('.pi/agent/models.json')['providers']['ollama']['models']
        compaction = self.read('.pi/agent/settings.json')['compaction']
        self.assertFalse(compaction['enabled'])
        self.assertEqual(compaction['keepRecentTokens'], 20000)
        self.assertEqual(compaction['modelOverrides']['other/model'], unrelated)
        self.assertEqual([model['id'] for model in models], self.models)
        for model in models:
            self.assertEqual((model['contextWindow'], model['maxTokens']), (32768, 8192))
            self.assertEqual(compaction['modelOverrides']['ollama/' + model['id']], {
                'reserveTokens': 16384, 'keepRecentTokens': 4096,
            })

    def test_compaction_scales_to_smaller_context_and_larger_output(self):
        for context, output in [(8192, 2048), (32768, 24576)]:
            with contextlib.redirect_stdout(io.StringIO()):
                configure(self.home, self.models, self.models[0], context, output)
            overrides = self.read('.pi/agent/settings.json')['compaction']['modelOverrides']
            for name in self.models:
                limits = overrides['ollama/' + name]
                self.assertGreaterEqual(limits['reserveTokens'], output)
                self.assertLess(limits['reserveTokens'], context)
                self.assertLess(limits['keepRecentTokens'], context - limits['reserveTokens'])

    def test_switching_models_updates_both_agents(self):
        self.run_configuration()
        self.run_configuration(['example/new-model:latest'])
        claude = self.read('.claude/settings.json')
        self.assertEqual([m['model'] for m in claude['modelPicker']['options']], ['example/new-model:latest'])
        pi = self.read('.pi/agent/models.json')['providers']['ollama']['models']
        self.assertEqual([m['id'] for m in pi], ['example/new-model:latest'])
        self.assertEqual(pi[0]['contextWindow'], 32768)
        self.assertEqual(pi[0]['maxTokens'], 8192)
        self.assertEqual(self.read('.pi/agent/settings.json')['defaultModel'], 'example/new-model:latest')

    def test_bad_existing_json_fails_before_writes(self):
        self.write('.claude/settings.json', {'theme': 'dark'})
        p = self.home / '.pi/agent/models.json'
        p.parent.mkdir(parents=True)
        p.write_text('{bad json')
        with self.assertRaises(json.JSONDecodeError):
            self.run_configuration()
        self.assertEqual(self.read('.claude/settings.json'), {'theme': 'dark'})
        self.assertFalse(list(self.home.rglob('*.backup-*')))

    def test_invalid_limits_and_duplicates_are_rejected(self):
        for models, context, output in [(['a', 'a'], 32768, 8192), (['a'], 8192, 8192)]:
            with self.assertRaises(ValueError):
                configure(self.home, models, 'a', context, output)
        self.assertFalse(list(self.home.iterdir()))

    def test_new_login_profile_preserves_profile_loading(self):
        (self.home / '.profile').write_text('# existing profile\n')
        self.run_configuration()
        profile = (self.home / '.bash_profile').read_text()
        self.assertIn('. "$HOME/.profile"', profile)
        self.assertIn('. "$HOME/.bashrc"', profile)
        self.assertIn('fish_add_path', (self.home / '.config/fish/conf.d/local-model-setup.fish').read_text())

    def test_all_three_models_receive_full_context(self):
        models = self.models + ['huihui_ai/Qwen3.8-abliterated:27b']
        with contextlib.redirect_stdout(io.StringIO()):
            configure(self.home, models, models[0], 262144, 8192)
        claude = self.read('.claude/settings.json')
        self.assertEqual(claude['env']['CLAUDE_CODE_MAX_CONTEXT_TOKENS'], '262144')
        self.assertEqual([m['model'] for m in claude['modelPicker']['options']], models)
        pi = self.read('.pi/agent/models.json')['providers']['ollama']['models']
        self.assertEqual({m['id']: m['contextWindow'] for m in pi},
                         dict.fromkeys(models, 262144))


if __name__ == '__main__':
    unittest.main()
