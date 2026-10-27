import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from journal_metadata import journal_metadata
from create_note_draft import prepare_draft


class JournalMetadataTests(unittest.TestCase):
    def test_actual_zotero_extra_and_no_topic_leak(self):
        result = journal_metadata({'publicationTitle': 'iScience', 'tags': [{'tag': 'motor mapping'}],
            'extra': 'JCR分区: Q1\n中科院分区升级版: 综合性期刊2区\n影响因子: 4.5\n5年影响因子: 5.0\n南农高质量: A\nTLDR: unrelated text'})
        self.assertEqual(result['journal_tags'], ['iScience', 'JCR Q1', '中科院 综合性期刊2区', 'IF 4.5', '5年IF 5.0', '南农高质量 A'])
        self.assertEqual(result['journal_tags_source'], ['publicationTitle', 'extra'])

    def test_tags_take_precedence_by_category_and_do_not_duplicate(self):
        result = journal_metadata({'tags': [{'tag': 'JCR Q2'}, {'tag': 'JCR Q2'}, {'tag': 'IF: 3.1'}], 'extra': 'JCR分区: Q1\n影响因子: 4.5\n中科院: 3区'})
        self.assertEqual(result['journal_tags'], ['JCR Q2', '中科院 3区', 'IF 3.1'])

    def test_no_rank_is_invented_for_missing_or_unrelated_data(self):
        self.assertEqual(journal_metadata({})['journal_tags'], [])
        self.assertEqual(journal_metadata({'extra': 'JCR分区: 未收录\n中科院: 未知\nIF: N/A\nTLDR: Q1'})['journal_tags'], [])

    def test_template_draft_renders_native_list_below_title(self):
        with tempfile.TemporaryDirectory() as root:
            vault = Path(root)
            destination, body = prepare_draft(vault, {'zotero_key': 'ABCD1234', 'title': 'Example', 'title_zh': '示例资料',
                'publication_title': 'iScience', 'journal_tags': ['iScience', 'JCR Q1']})
            self.assertIn('标题: "Example"\n作者: ""\n期刊标签: ["iScience", "JCR Q1"]', body)
            self.assertIn('"note_status":"draft"', body)
            self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
