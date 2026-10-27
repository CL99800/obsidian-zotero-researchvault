from pathlib import Path
import tempfile
import unittest
import sys
import json
import re
import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from vault_schema import FIELDS,CATEGORIES,read_fields,route_material
from create_note_draft import prepare_draft
from create_material_note import prepare_material
from retrieval_gateway import RetrievalGateway,RetrievalError
from init_vault import initialize
from validate_research_vault_literature_links import validate

class ChineseWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.v=Path(self.tmp.name)/'vault'
        initialize(self.v,Path(self.tmp.name)/'config.toml',with_codex=True)

    def test_18_properties_and_hidden_identity_round_trip(self):
        target,body=prepare_draft(self.v,{'zotero_key':'ABCD1234','title':'Original English Title','title_zh':'原始英文资料的中文标题','pdf_key':'PDFK1234'},collection='主题')
        self.assertEqual(target.relative_to(self.v).as_posix(),'02阅读笔记/论文/主题/Original English Title.md')
        data=yaml.safe_load(body.split('---',2)[1]);self.assertEqual(list(data),list(FIELDS.values()))
        self.assertEqual(len(data),18);self.assertNotIn('zotero_key',data)
        target.parent.mkdir(parents=True);target.write_text(body,encoding='utf-8')
        fields=read_fields(target)
        self.assertEqual(fields['zotero_key'],'ABCD1234');self.assertEqual(fields['title'],'Original English Title')
        self.assertEqual(fields['original_title'],'Original English Title')
        self.assertEqual(RetrievalGateway(self.v).resolve_note('ABCD1234'),target)
        self.assertEqual(fields['note_status'],'draft')

    def test_original_language_title_is_preserved(self):
        for title in ['English Title', '中文文献标题']:
            target, body = prepare_draft(self.v, {'zotero_key':'ABCD1234', 'title':title})
            data = yaml.safe_load(body.split('---',2)[1])
            self.assertEqual(data['标题'], title)
            self.assertIn('# '+title, body)
            self.assertEqual(target.stem, title)
        with self.assertRaises(RetrievalError):
            prepare_draft(self.v, {'zotero_key':'ABCD1234'})

    def test_source_category_and_nested_topic_are_mirrored(self):
        for category in CATEGORIES:
            self.assertTrue((self.v/'02阅读笔记'/category).is_dir())
            raw=self.v/'03原始资料'/category/'神经科学'/'子主题'/'source.md'
            raw.parent.mkdir(parents=True,exist_ok=True);raw.write_text('真实资料',encoding='utf-8')
            target,body=prepare_material(self.v,raw,'中文资料标题')
            self.assertEqual(target.relative_to(self.v).parts[:4],('02阅读笔记',category,'神经科学','子主题'))
            target.parent.mkdir(parents=True,exist_ok=True);target.write_text(body,encoding='utf-8')
            self.assertEqual(read_fields(target)['fulltext_path'],raw.relative_to(self.v).as_posix())
        issues,summary=validate(self.v);self.assertEqual(summary['errors'],0,issues)
        self.assertEqual(len(RetrievalGateway(self.v).note_paths()),8)

    def test_raw_source_escape_is_rejected(self):
        outside=self.v.parent/'private.md';outside.write_text('source',encoding='utf-8')
        with self.assertRaises(ValueError):route_material(self.v,outside,'中文标题')

if __name__=='__main__':unittest.main()
