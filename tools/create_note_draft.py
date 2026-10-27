"""Prepare one Chinese-property Zotero note; dry-run unless --write is passed."""
from __future__ import annotations
import argparse
from datetime import date
import json
import re
import sys
from pathlib import Path
from config import REPO_ROOT, configured_path, load_config
from journal_metadata import journal_metadata
from retrieval_gateway import RetrievalError, RetrievalGateway, resolve_vault_path
from vault_schema import render_properties, identity_comment

def safe_filename(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', value).strip(' .')[:110].rstrip(' .') or '未命名论文'

def prepare_draft(vault: Path, metadata: dict, *, collection: str = '未分类', fulltext_path: str = ''):
    key = metadata.get('zotero_key')
    if not key or not str(key).isalnum():
        raise RetrievalError('必须提供核实的Zotero父条目键。')
    original_title = str(metadata.get('title') or '').strip()
    if not original_title:
        raise RetrievalError('Zotero原始标题缺失，不能编造标题。')
    title = original_title
    collection = safe_filename(collection)
    relative = f'02阅读笔记/论文/{collection}/{safe_filename(title)}.md'
    target = resolve_vault_path(vault, relative)
    template_path = vault / '模板/论文精读模板.md'
    if not template_path.is_file():
        template_path = REPO_ROOT / 'templates/论文精读模板.md'
    template = template_path.read_text(encoding='utf-8-sig')
    body = template.split('---', 2)[2].lstrip('\r\n').replace('{{title}}', title)
    attachments = [a.get('pdf_key') for a in metadata.get('pdf_attachments', []) if a.get('pdf_key')]
    if len(attachments) > 1 and not metadata.get('pdf_key'):
        raise RetrievalError('存在多个PDF附件，必须先核对主附件。')
    pdf_key = metadata.get('pdf_key') or (attachments[0] if attachments else '')
    item_uri = f'zotero://select/library/items/{key}'
    pdf_uri = f'zotero://open-pdf/library/items/{pdf_key}' if pdf_key else ''
    values = {'type': '论文精读', 'title': title, 'author': metadata.get('author') or '',
              'journal_tags': metadata.get('journal_tags', journal_metadata(metadata)['journal_tags']),
              'tags': ['文献精读', '阅读笔记'], 'year': metadata.get('year') or '',
              'created': date.today().isoformat(), 'zotero_pdf': pdf_uri,
              'collection': collection, 'fulltext_path': fulltext_path}
    identity = {'zotero_key': str(key), 'pdf_key': str(pdf_key),
                'library_type': metadata.get('library_type', 'users'),
                'library_id': str(metadata.get('library_id', '0')),
                'doi': metadata.get('doi') or '', 'original_title': original_title,
                'note_path': relative, 'note_status': 'draft', 'reading_status': 'to_read'}
    body = body.replace('| 作者与年份 |  |', f'| 作者与年份 | {values["author"]}；{values["year"]} |')
    body = body.replace('| 年份 |  |', f'| 年份 | {values["year"]} |')
    body = body.replace('| 原文入口 |  |', f'| 原文入口 | [Zotero条目]({item_uri}) |')
    warning = '> 本文件仅依据Zotero元数据建立草稿，尚未完成原文精读；方法、发现和引文须经原文核验。\n\n'
    body = body.replace('## 一句话摘要\n', '## 一句话摘要\n\n' + warning, 1)
    return target, render_properties(values) + '\n' + identity_comment(identity) + '\n\n' + body

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vault', type=Path)
    p.add_argument('--config', type=Path)
    p.add_argument('--key', required=True)
    p.add_argument('--title-zh', help='兼容旧调用；论文标题始终保留Zotero原题，此参数不改写标题')
    p.add_argument('--collection', default='未分类')
    p.add_argument('--write', action='store_true')
    args = p.parse_args()
    vault = args.vault or configured_path('vault_root', load_config(args.config))
    if not vault:
        p.error('需要--vault或配置vault_root。')
    try:
        gateway = RetrievalGateway(vault, config_path=args.config)
        existing = gateway.resolve_note(args.key)
        if existing:
            raise RetrievalError(f'已存在对应笔记，请原位补全：{existing}')
        metadata = gateway.zotero_record(args.key)
        if args.title_zh:
            metadata['title_zh'] = args.title_zh
        fulltext = gateway.resolve_fulltext(args.key, None)
        relative_fulltext = fulltext.relative_to(gateway.vault).as_posix() if fulltext else ''
        target, body = prepare_draft(gateway.vault, metadata, collection=args.collection, fulltext_path=relative_fulltext)
        if target.exists():
            raise RetrievalError(f'目标已存在，不覆盖：{target}')
        if args.write:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('x', encoding='utf-8') as stream:
                stream.write(body)
        print(json.dumps({'status': 'created' if args.write else 'dry_run', 'note_path': str(target), 'write_performed': args.write}, ensure_ascii=False))
        return 0
    except (RetrievalError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
