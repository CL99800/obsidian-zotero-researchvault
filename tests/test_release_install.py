from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from init_vault import initialize


class ReleaseInstallTests(unittest.TestCase):
    def test_discovery_and_style_preserve_existing_preferences(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'vault'
            (root / '.obsidian').mkdir(parents=True)
            (root / '.obsidian/appearance.json').write_text(json.dumps({'cssTheme': 'Existing Theme', 'enabledCssSnippets': ['my-style']}), encoding='utf-8')
            (root / '.obsidian/types.json').write_text(json.dumps({'types': {'custom': 'checkbox', '年份': 'number'}}), encoding='utf-8')
            config = Path(temp) / 'config.toml'
            initialize(root, config, with_codex=True, enable_style=True)
            self.assertTrue((root / '.agents/skills/researchvault-reading/SKILL.md').is_file())
            self.assertTrue((root / '.obsidian/snippets/researchvault-journal-tags.css').is_file())
            appearance = json.loads((root / '.obsidian/appearance.json').read_text(encoding='utf-8'))
            self.assertEqual(appearance['cssTheme'], 'Existing Theme')
            self.assertEqual(appearance['enabledCssSnippets'], ['my-style', 'researchvault-journal-tags'])
            types = json.loads((root / '.obsidian/types.json').read_text(encoding='utf-8'))['types']
            self.assertEqual(types['custom'], 'checkbox')
            self.assertEqual(types['年份'], 'number')
            self.assertEqual(types['期刊标签'], 'multitext')
            self.assertEqual(initialize(root, config, with_codex=True, enable_style=True), [])

    def test_style_is_opt_in(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'vault'
            initialize(root, Path(temp) / 'config.toml')
            self.assertFalse((root / '.obsidian').exists())


if __name__ == '__main__':
    unittest.main()
