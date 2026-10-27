"""Create a metadata-only draft beside the matching category/topic of a source."""
from __future__ import annotations
import argparse
from datetime import date
import sys
from pathlib import Path
from vault_schema import route_material, render_properties, identity_comment

def prepare_material(vault: Path, source: Path, title_zh: str):
    target = route_material(vault, source, title_zh)
    source_rel = source.resolve().relative_to(vault.resolve()).as_posix()
    note_rel = target.relative_to(vault.resolve()).as_posix()
    relative_parts = source.resolve().relative_to((vault / '03原始资料').resolve()).parts
    values = {'type': '资料阅读', 'title': title_zh, 'created': date.today().isoformat(),
              'tags': ['资料阅读'], 'fulltext_path': source_rel, 'collection': '/'.join(relative_parts[:-1])}
    template = (vault / '模板/资料阅读模板.md').read_text(encoding='utf-8-sig')
    body = template.split('---', 2)[2].lstrip('\r\n').replace('{{title}}', title_zh)
    identity = {'type': 'material-note', 'note_path': note_rel, 'fulltext_path': source_rel,
                'original_title': source.stem, 'note_status': 'draft', 'source_type': relative_parts[0] if len(relative_parts)>1 else '未分类'}
    return target, render_properties(values) + '\n' + identity_comment(identity) + '\n\n' + body

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vault', type=Path, required=True)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--title-zh', required=True)
    p.add_argument('--write', action='store_true')
    args = p.parse_args()
    source = args.source if args.source.is_absolute() else args.vault / args.source
    target, body = prepare_material(args.vault, source, args.title_zh)
    if target.exists():
        p.error('目标笔记已存在，请读取并在原路径补全；本工具不覆盖。')
    if args.write:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x', encoding='utf-8') as stream:
            stream.write(body)
    print(('已创建元数据草稿：' if args.write else '只读预览路径：') + str(target))
    return 0

if __name__ == '__main__':
    sys.exit(main())
